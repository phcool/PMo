import logging
import asyncio
from typing import List, Optional, Dict, Any
import time
import os
import json
import re
import aiohttp
import fitz  # PyMuPDF
from datetime import datetime

from app.models.paper import Paper, PaperAnalysis
from app.services.db_service import db_service
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

def clean_latex_formula(formula: str) -> str:
    """
    清理LaTeX数学公式，尝试将其转换为可读的普通文本
    
    Args:
        formula: LaTeX公式字符串
    
    Returns:
        清理后的可读文本
    """
    # 去除首尾空白
    formula = formula.strip()
    
    # 替换常见的LaTeX命令
    replacements = {
        # 字体和格式命令
        r'\\bf{([^}]+)}': r'\1',
        r'\\mathbf{([^}]+)}': r'\1',
        r'\\it{([^}]+)}': r'\1',
        r'\\mathit{([^}]+)}': r'\1',
        r'\\text{([^}]+)}': r'\1',
        r'\\textbf{([^}]+)}': r'\1',
        r'\\textit{([^}]+)}': r'\1',
        r'\\rm{([^}]+)}': r'\1',
        r'\\mathrm{([^}]+)}': r'\1',
        r'\\emph{([^}]+)}': r'\1',
        
        # 空格和分隔符
        r'\\space': ' ',
        r'\\,': ' ',
        r'\\;': ' ',
        r'\\quad': '  ',
        r'\\qquad': '    ',
        
        # 常见的数学符号
        r'\\times': 'x',
        r'\\div': '/',
        r'\\pm': '+/-',
        r'\\cdot': '·',
        r'\\leq': '<=',
        r'\\geq': '>=',
        r'\\neq': '!=',
        r'\\approx': '~',
        r'\\equiv': '=',
        r'\\ldots': '...',
        r'\\rightarrow': '->',
        r'\\leftarrow': '<-',
        r'\\Rightarrow': '=>',
        r'\\Leftarrow': '<=',
        
        # 上下标
        r'\^{([^}]+)}': r'^(\1)',
        r'\_([a-zA-Z0-9])': r'_\1',
        r'\_\{([^}]+)\}': r'_(\1)',
        
        # 分数
        r'\\frac{([^}]+)}{([^}]+)}': r'(\1)/(\2)',
        
        # 括号
        r'\\left\(': '(',
        r'\\right\)': ')',
        r'\\left\[': '[',
        r'\\right\]': ']',
        r'\\left\\{': '{',
        r'\\right\\}': '}',
        
        # 希腊字母（常见）
        r'\\alpha': 'alpha',
        r'\\beta': 'beta',
        r'\\gamma': 'gamma',
        r'\\delta': 'delta',
        r'\\epsilon': 'epsilon',
        r'\\theta': 'theta',
        r'\\lambda': 'lambda',
        r'\\pi': 'pi',
        r'\\sigma': 'sigma',
        r'\\omega': 'omega',
    }
    
    # 应用所有替换
    for pattern, replacement in replacements.items():
        formula = re.sub(pattern, replacement, formula)
    
    # 移除任何剩余的LaTeX命令
    formula = re.sub(r'\\[a-zA-Z]+', '', formula)
    
    # 移除多余的空格
    formula = re.sub(r'\s+', ' ', formula).strip()
    
    return formula

def clean_text_for_api(text: str) -> str:
    """
    清理文本，使其对API友好：
    1. 删除无效的Unicode字符和代理对
    2. 替换不常见的Unicode字符为基本ASCII替代
    3. 处理其他潜在的编码问题
    4. 确保换行符正确显示
    5. 处理LaTeX数学符号
    
    Args:
        text: 原始文本
        
    Returns:
        清理后的文本
    """
    if not text:
        return ""
        
    # 删除surrogate pairs和无效Unicode字符
    # \ud800-\udfff是Unicode代理对范围
    text = re.sub(r'[\ud800-\udfff]', '', text)
    
    # 处理LaTeX数学公式
    # 处理特定的模式
    text = re.sub(r'\$\\bf\{(\d+)\s*\\space\s*([^}]+)\}\$', r'\1 \2', text)  # 如 $\bf{3 \space billion}$
    
    # 简单的数学公式（单行的$...$）
    text = re.sub(r'\$\\bf\{([^}]+)\}\$', r'\1', text)  # 替换粗体命令 \bf{...}
    text = re.sub(r'\$\\mathbf\{([^}]+)\}\$', r'\1', text)  # 替换粗体命令 \mathbf{...}
    text = re.sub(r'\$\\it\{([^}]+)\}\$', r'\1', text)  # 替换斜体命令 \it{...}
    text = re.sub(r'\$\\mathit\{([^}]+)\}\$', r'\1', text)  # 替换斜体命令 \mathit{...}
    text = re.sub(r'\$\\space\$', ' ', text)  # 替换空格命令 \space
    text = re.sub(r'\$\\([a-zA-Z]+)\$', r'\1', text)  # 替换其他简单命令 \command
    
    # 处理更复杂的数学公式
    text = re.sub(r'\$([^$]+)\$', lambda m: clean_latex_formula(m.group(1)), text)  # 处理$...$中的内容
    # 处理双美元符号的数学环境
    text = re.sub(r'\$\$([^$]+)\$\$', lambda m: clean_latex_formula(m.group(1)), text)  # 处理$$...$$中的内容
    
    # 替换常见的数学符号和特殊字符
    replacements = {
        # 各种引号
        '"': '"', '"': '"', ''': "'", ''': "'",
        # 破折号和其他标点
        '—': '-', '–': '-', '…': '...',
        # 常见数学符号 (可能出现在论文中)
        '×': 'x', '÷': '/', '≤': '<=', '≥': '>=', '≠': '!=', '≈': '~=',
        # 货币符号
        '€': 'EUR', '£': 'GBP', '¥': 'JPY',
        # 上下标和其他特殊字符
        '²': '^2', '³': '^3', '±': '+/-',
        # 可能导致问题的其他字符
        '\u2028': ' ', '\u2029': ' ',  # 行分隔符和段落分隔符
        # 处理可能的HTML标记字符
        '<': '&lt;',
        '>': '&gt;'
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # 标准化换行符 (确保所有换行都是\n)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # 作为最后的措施，编码然后解码来去除任何剩余的问题字符
    # 使用errors='ignore'忽略无法编码的字符
    text = text.encode('utf-8', errors='ignore').decode('utf-8')
    
    return text

class PaperAnalysisService:
    """
    论文分析服务，负责协调PDF分析任务
    """
    
    def __init__(self):
        """初始化论文分析服务"""
        self.is_analyzing = False
        self.current_task = None
        self.batch_size = 5  # 每批处理的论文数
    
    async def extract_text_from_pdf(self, pdf_url: str) -> Optional[str]:
        """
        从PDF URL提取文本内容，使用PyMuPDF高性能库
        
        Args:
            pdf_url: PDF的URL
            
        Returns:
            提取的文本内容或None（如果提取失败）
        """
        start_time = time.time()
        try:
            logger.info(f"开始下载PDF: {pdf_url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(pdf_url) as response:
                    if response.status != 200:
                        logger.error(f"下载PDF失败 {pdf_url}, 状态码: {response.status}")
                        return None
                    
                    pdf_content = await response.read()
                    download_time = time.time() - start_time
                    logger.info(f"PDF下载完成，大小: {len(pdf_content)/1024:.1f} KB, 耗时: {download_time:.2f} 秒")
            
            # 使用PyMuPDF提取文本
            extraction_start = time.time()
            text = ""
            
            try:
                with fitz.open(stream=pdf_content, filetype="pdf") as doc:
                    # 获取总页数
                    total_pages = len(doc)
                    logger.info(f"PDF共 {total_pages} 页")
                    
                    # 提取前15页（或全部页面如果少于15页）
                    max_pages = min(15, total_pages)
                    
                    # 高效提取文本
                    for i in range(max_pages):
                        page = doc.load_page(i)
                        # 获取纯文本，不包括表格结构
                        page_text = page.get_text("text")
                        if page_text:
                            text += page_text + "\n\n"
                
                extraction_time = time.time() - extraction_start
                logger.info(f"PDF文本提取完成，提取了 {max_pages}/{total_pages} 页, 耗时: {extraction_time:.2f} 秒")
                
                # 限制文本长度
                max_length = 50000  # 字符数
                original_length = len(text)
                if len(text) > max_length:
                    text = text[:max_length] + "...[截断]"
                    logger.info(f"文本已截断，从 {original_length} 字符截断到 {max_length} 字符")
                
                # 清理文本以防止编码问题
                text = clean_text_for_api(text)
                
                total_time = time.time() - start_time
                logger.info(f"PDF处理完成 {pdf_url}, 总耗时: {total_time:.2f} 秒, 提取文本长度: {len(text)} 字符")
                return text
                
            except fitz.FileDataError as e:
                logger.error(f"PyMuPDF无法解析PDF文件 {pdf_url}: {e}")
                return None
                
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"提取PDF文本时出错 {pdf_url}: {e}, 耗时: {total_time:.2f} 秒")
            return None
    
    async def analyze_pdf(self, paper_id: str, pdf_url: str) -> Optional[PaperAnalysis]:
        """
        分析PDF内容
        
        Args:
            paper_id: 论文ID
            pdf_url: PDF的URL
            
        Returns:
            分析结果或None（如果分析失败）
        """
        try:
            # 提取文本
            text = await self.extract_text_from_pdf(pdf_url)
            if not text:
                logger.error(f"无法从PDF提取文本: {pdf_url}")
                return None
            
            # --- 文本预处理：移除致谢和参考文献 --- 
            logger.info(f"原始提取文本长度: {len(text)}")
            processed_text = text
            section_to_remove = None
            
            # 查找常见的参考文献/致谢标题 (忽略大小写)
            # 从后往前找，因为参考文献通常在最后
            keywords_references = ["references", "bibliography"]
            keywords_acknowledgements = ["acknowledgments", "acknowledgements"]
            
            combined_keywords = keywords_references + keywords_acknowledgements
            
            # 将文本按行分割，更容易匹配标题
            lines = text.splitlines()
            found_section_line_index = -1
            
            # 从后往前查找标题行
            for i in range(len(lines) - 1, -1, -1):
                line_lower = lines[i].strip().lower()
                # 检查是否是常见的标题格式 (例如，单独一行，或以数字/字母开头)
                is_potential_title = (lines[i].strip() == line_lower.title() or 
                                      line_lower.startswith(tuple(f"{j}." for j in range(10))) or 
                                      line_lower.startswith(tuple(f"{chr(ord('a')+j)}." for j in range(26))))
                
                for keyword in combined_keywords:
                    # 匹配单独成行的标题或以关键字开头的行
                    if line_lower == keyword or (is_potential_title and keyword in line_lower):
                        found_section_line_index = i
                        section_to_remove = keyword # 记录找到的关键字
                        break # 找到第一个就停止
                if found_section_line_index != -1:
                    break
                    
            if found_section_line_index != -1:
                logger.info(f"找到疑似章节 '{section_to_remove}' 于第 {found_section_line_index + 1} 行，进行截断。")
                # 只保留该行之前的内容
                processed_text = "\n".join(lines[:found_section_line_index])
                logger.info(f"处理后文本长度: {len(processed_text)}")
            else:
                logger.info("未找到明确的致谢或参考文献标题进行移除。")
            # --- 预处理结束 ---
            
            # 再次清理文本确保没有编码问题
            processed_text = clean_text_for_api(processed_text)
            
            # 使用LLM服务分析处理后的文本
            return await llm_service.analyze_paper_text(paper_id, processed_text)
            
        except Exception as e:
            logger.error(f"分析PDF时发生意外错误 {pdf_url}: {e}")
            return None
        
    async def analyze_paper(self, paper_id: str) -> Optional[PaperAnalysis]:
        """
        分析单篇论文
        
        Args:
            paper_id: 论文ID
            
        Returns:
            分析结果或None（如果分析失败）
        """
        try:
            # 获取论文详情
            paper = await db_service.get_paper_by_id(paper_id)
            if not paper:
                logger.error(f"论文不存在: {paper_id}")
                return None
            
            # 检查是否已有分析
            existing_analysis = await db_service.get_paper_analysis(paper_id)
            if existing_analysis:
                logger.info(f"论文已有分析结果: {paper_id}")
                return existing_analysis
            
            # 分析PDF
            analysis = await self.analyze_pdf(paper_id, paper.pdf_url)
            if not analysis:
                logger.error(f"分析论文失败: {paper_id}")
                return None
            
            # 保存分析结果
            success = await db_service.save_paper_analysis(analysis)
            if not success:
                logger.error(f"保存分析结果失败: {paper_id}")
                return None
            
            return analysis
            
        except Exception as e:
            logger.error(f"分析论文时出错: {e}")
            return None
    
    async def analyze_pending_papers(self) -> Dict[str, Any]:
        """
        分析待处理的论文
        
        Returns:
            分析统计信息
        """
        if self.is_analyzing:
            return {
                "status": "in_progress",
                "message": "已有分析任务正在进行中"
            }
        
        try:
            self.is_analyzing = True
            start_time = time.time()
            
            # 获取未分析的论文
            papers = await db_service.get_papers_without_analysis(self.batch_size)
            if not papers:
                self.is_analyzing = False
                return {
                    "status": "completed",
                    "message": "没有待分析的论文",
                    "processed": 0,
                    "successful": 0,
                    "failed": 0,
                    "duration_seconds": time.time() - start_time
                }
            
            logger.info(f"开始分析 {len(papers)} 篇论文")
            
            # 处理每篇论文
            successful = 0
            failed = 0
            
            for paper in papers:
                try:
                    analysis = await self.analyze_pdf(paper.paper_id, paper.pdf_url)
                    if analysis:
                        success = await db_service.save_paper_analysis(analysis)
                        if success:
                            successful += 1
                            logger.info(f"成功分析论文: {paper.paper_id}")
                        else:
                            failed += 1
                            logger.error(f"保存分析结果失败: {paper.paper_id}")
                    else:
                        failed += 1
                        logger.error(f"分析论文失败: {paper.paper_id}")
                except Exception as e:
                    failed += 1
                    logger.error(f"处理论文时出错: {paper.paper_id}, 错误: {e}")
            
            end_time = time.time()
            duration = end_time - start_time
            
            result = {
                "status": "completed",
                "message": f"完成分析 {len(papers)} 篇论文",
                "processed": len(papers),
                "successful": successful,
                "failed": failed,
                "duration_seconds": duration
            }
            
            logger.info(f"分析任务完成: {result}")
            return result
            
        except Exception as e:
            logger.error(f"分析待处理论文时出错: {e}")
            return {
                "status": "error",
                "message": f"分析论文时出错: {str(e)}",
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "duration_seconds": time.time() - start_time
            }
        finally:
            self.is_analyzing = False
    
    async def start_analysis_task(self) -> Dict[str, Any]:
        """
        启动异步分析任务
        
        Returns:
            任务状态信息
        """
        if self.is_analyzing:
            return {
                "status": "in_progress",
                "message": "已有分析任务正在进行中"
            }
        
        # 创建异步任务
        self.current_task = asyncio.create_task(self.analyze_pending_papers())
        
        return {
            "status": "started",
            "message": "已启动论文分析任务",
            "timestamp": datetime.now().isoformat()
        }

# 创建全局实例
paper_analysis_service = PaperAnalysisService() 