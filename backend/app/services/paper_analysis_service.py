import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple
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
from openai.types.chat import ChatCompletion

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
        
    # 删除null字节(0x00)，这会导致PostgreSQL UTF-8编码错误
    text = text.replace('\x00', '')
        
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

# --- 辅助函数：用于解析和清理 LLM 返回的 JSON --- 
def _parse_and_clean_llm_response(json_string: str, paper_id: str) -> Optional[Dict[str, Any]]:
    """解析LLM返回的JSON字符串并进行数据清洗"""
    try:
        analysis_data = json.loads(json_string)
        
        # 数据清洗：确保所有字段都是字符串，并将列表/字典转为合适的字符串格式
        def clean_value(value):
            if isinstance(value, list):
                clean_list = []
                for item in value:
                    if isinstance(item, str):
                        item = item.strip()
                        # 尝试添加项目符号，如果不是已经有的话
                        if item and not re.match(r'^[-*•\d+\.\)]\s*', item):
                             item = "• " + item
                    clean_list.append(str(item))
                return '\n'.join(clean_list)
            elif isinstance(value, dict):
                formatted_items = []
                for k, v in value.items():
                    if isinstance(v, str):
                        v = v.strip()
                    formatted_items.append(f"{k}: {v}")
                return '\n'.join(formatted_items)
            elif isinstance(value, str):
                return value.replace('\\n', '\n') # 替换转义的换行符
            return str(value) # 其他类型转为字符串

        cleaned_data = {}
        expected_keys = ["summary", "key_findings", "contributions", "methodology", "limitations", "future_work", "keywords"]
        for k in expected_keys:
            v = analysis_data.get(k) # 使用 .get 避免 KeyError
            if v is not None:
                original_type = type(v).__name__
                cleaned_v = clean_value(v)
                cleaned_type = type(cleaned_v).__name__
                # 进一步清理字符串：替换连续换行，统一数字列表格式
                if isinstance(cleaned_v, str):
                     cleaned_v = cleaned_v.replace('\\n', '\n')
                     cleaned_v = re.sub(r'\n{3,}', '\n\n', cleaned_v) 
                     cleaned_v = re.sub(r'^(\d+)\)([\s])', r'\1.\2', cleaned_v, flags=re.MULTILINE)
                     cleaned_v = cleaned_v.strip()
                cleaned_data[k] = cleaned_v
                # if original_type != cleaned_type:
                #     logger.info(f"Paper {paper_id}: 字段 {k} 类型从 {original_type} 转换为 {cleaned_type}")
            else:
                 cleaned_data[k] = None # 确保所有预期键都存在
                 logger.warning(f"Paper {paper_id}: LLM 响应缺少字段 '{k}'")

        return cleaned_data
       
    except json.JSONDecodeError as e:
        logger.error(f"无法将LLM响应解析为JSON for {paper_id}: {e}")
        logger.debug(f"原始响应文本 for {paper_id}: {json_string}")
        return None
    except Exception as e:
        logger.error(f"解析和清理LLM响应时发生意外错误 for {paper_id}: {e}")
        return None
# ----------------------------------------------

class PaperAnalysisService:
    """
    论文分析服务，负责协调PDF提取、LLM调用和结果保存
    """
    
    def __init__(self):
        """初始化论文分析服务"""
        self.is_analyzing = False
        self.current_task = None
        self.batch_size = int(os.getenv("ANALYSIS_BATCH_SIZE", "5")) # 从环境变量获取批处理大小
        # Max chars for LLM input (adjust per model, e.g., qwen-turbo 8k context -> ~24k chars)
        self.max_llm_input_chars = int(os.getenv("LLM_MAX_INPUT_CHARS", "24000"))
    
    async def _extract_text_from_pdf(self, paper_id: str, pdf_url: str) -> Optional[Tuple[str, int]]:
        """
        从PDF URL提取文本内容，并计算字数。
        
        Returns:
            一个元组 (提取的文本内容, 字数) 或 None (如果提取失败)
        """
        start_time = time.time()
        try:
            logger.info(f"开始下载PDF for {paper_id}: {pdf_url}")
            
            # 设置合理的超时，例如 60 秒
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(pdf_url) as response:
                    if response.status != 200:
                        logger.error(f"下载PDF失败 for {paper_id} ({pdf_url}), 状态码: {response.status}")
                        return None
                    
                    pdf_content = await response.read()
                    download_time = time.time() - start_time
                    logger.info(f"PDF下载完成 for {paper_id}，大小: {len(pdf_content)/1024:.1f} KB, 耗时: {download_time:.2f} 秒")
            
            # 使用PyMuPDF提取文本
            extraction_start = time.time()
            text = ""
            word_count = 0
            
            try:
                # 增加内存使用提示和处理大型PDF的策略
                # PyMuPDF 通常内存效率较高，但超大文件仍可能出问题
                with fitz.open(stream=pdf_content, filetype="pdf") as doc:
                    total_pages = len(doc)
                    logger.info(f"PDF共 {total_pages} 页 for {paper_id}")
                    
                    # 提取前 N 页 (例如 15 页)
                    max_pages_to_extract = int(os.getenv("PDF_EXTRACT_MAX_PAGES", "15"))
                    pages_to_process = min(max_pages_to_extract, total_pages)
                    
                    extracted_texts = []
                    for i in range(pages_to_process):
                        try:
                            page = doc.load_page(i)
                            page_text = page.get_text("text") 
                            if page_text:
                                # 立即清理每个页面的空字节
                                page_text = page_text.replace('\x00', '')
                                extracted_texts.append(page_text.strip()) 
                        except Exception as page_error:
                             logger.warning(f"提取PDF页面 {i+1}/{total_pages} 出错 for {paper_id}: {page_error}")
                             continue # 跳过出错页面
                            
                    text = "\n\n".join(extracted_texts) # 使用双换行符分隔页面
                
                # 最后再清理一次整个文本的空字节
                text = text.replace('\x00', '')
                
                extraction_time = time.time() - extraction_start
                logger.info(f"PDF文本提取完成 for {paper_id}，提取了 {pages_to_process}/{total_pages} 页, 耗时: {extraction_time:.2f} 秒")
                
                # 注意：文本清理 (clean_text_for_api) 现在由 llm_service 处理
                # 文本长度限制也移至 llm_service
                
                total_time = time.time() - start_time
                logger.info(f"PDF处理完成 {paper_id} ({pdf_url}), 总耗时: {total_time:.2f} 秒, 提取文本长度: {len(text)} 字符")
                
                # Calculate word count after joining pages
                if text:
                     word_count = len(text.split()) 
                
                return text, word_count
                
            except fitz.fitz.FileDataError as fe:
                 logger.error(f"PyMuPDF无法打开或处理PDF数据 for {paper_id}: {fe}")
                 return None
            except Exception as e_fitz:
                logger.error(f"PyMuPDF提取文本时出错 for {paper_id}: {e_fitz.__class__.__name__} - {e_fitz}")
                return None
                
        except asyncio.TimeoutError:
             logger.error(f"下载PDF超时 for {paper_id} ({pdf_url})")
             return None
        except aiohttp.ClientError as e_http:
             logger.error(f"下载PDF时发生客户端错误 for {paper_id} ({pdf_url}): {e_http}")
             return None
        except Exception as e_main:
            logger.error(f"提取PDF文本过程中发生意外错误 for {paper_id} ({pdf_url}): {e_main}")
            return None
    
    async def _generate_llm_analysis_json(self, paper_id: str, text: str) -> Optional[str]:
        """
        准备文本、构建prompt、调用通用LLM服务并获取原始JSON响应字符串。
        """
        # 1. 清理文本 (使用本文件内的函数)
        cleaned_text = clean_text_for_api(text)
        
        # 2. 检查和截断文本长度
        if not cleaned_text or len(cleaned_text) < 50:
             logger.warning(f"论文 {paper_id} 清理后的文本过短或为空，无法进行分析。")
             return None
             
        if len(cleaned_text) > self.max_llm_input_chars:
             logger.warning(f"论文 {paper_id} 清理后文本长度 {len(cleaned_text)} 超过限制 {self.max_llm_input_chars}，进行截断")
             cleaned_text = cleaned_text[:self.max_llm_input_chars] + "... [Input Truncated]"
        
        # 3. 构建 Prompt 和 Messages (现在在这里定义)
        system_prompt = "You are an expert academic paper analyst, focused on providing objective, accurate, and strictly JSON-formatted paper analysis. All JSON fields must be simple strings, never nested objects or arrays."
        user_prompt = f"""Please analyze the following paper content and provide a structured analysis.

Paper Content:
{cleaned_text}

Please provide analysis in the following aspects:
1. Summary: Brief overview of the paper's main content and contributions.
2. Key Findings: List the main findings and conclusions of the paper.
3. Contributions: What are the paper's main contributions to the field?
4. Methodology: What methods were used in the paper?
5. Limitations: What are the limitations of the paper's methods or results?
6. Future Work: What future research directions does the paper suggest?
7. Keywords: Extract 5-10 important technical keywords or phrases from the paper. Focus on specific technical terms, methods, datasets, or concepts that best represent the paper's content.

Please output the result strictly in JSON format without any explanatory text or prefix, following this structure:
{{
  "summary": "Paper summary",
  "key_findings": "Key findings",
  "contributions": "Main contributions",
  "methodology": "Methodology used",
  "limitations": "Limitations",
  "future_work": "Future work",
  "keywords": "keyword1, keyword2, keyword3, ..."
}}

IMPORTANT: Each field must be a simple string. Use line breaks within the string for lists if needed.
For keywords, provide a comma-separated list.
If any aspect is not explicitly mentioned, mark it as "Not explicitly mentioned"."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # 4. 调用通用的LLM服务
        try:
            logger.info(f"调用 LLM 服务进行分析: {paper_id} (文本长度: {len(cleaned_text)}) ")
            completion = await llm_service.get_chat_completion(
                messages=messages,
                # 使用 llm_service 中的默认模型、温度、max_tokens，但指定 JSON 输出
                response_format={"type": "json_object"} 
            )
            
            # 5. 处理响应
            if completion and completion.choices and completion.choices[0].message:
                response_content = completion.choices[0].message.content
                if response_content:
                    logger.info(f"成功从 LLM 获取到分析响应 for {paper_id}")
                    return response_content
                else:
                    logger.error(f"LLM 响应内容为空 for {paper_id}")
                    return None
            else:
                logger.error(f"无法从LLM响应中提取有效内容 for {paper_id}")
                if completion:
                     logger.debug(f"原始 LLM 响应对象 for {paper_id}: {completion.model_dump_json()}")
                return None
                
        except Exception as e:
             # Handle potential errors during the call or response processing within this service
             logger.error(f"在调用LLM或处理其响应时出错 for {paper_id}: {e.__class__.__name__} - {e}")
             return None

    async def analyze_paper(self, paper_id: str, timeout_seconds: int = 120) -> Optional[PaperAnalysis]:
        """
        分析单篇论文：获取信息 -> 提取文本 -> 保存文本+字数 -> 调用LLM -> 解析结果 -> 保存分析
        
        Args:
            paper_id: 论文ID
            timeout_seconds: 单篇论文分析的超时时间（秒），默认2分钟
        """
        logger.info(f"[{paper_id}] 开始分析论文")
        paper_start_time = time.time()
        
        # 设置任务超时控制
        try:
            return await asyncio.wait_for(
                self._analyze_paper_internal(paper_id),
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.error(f"[{paper_id}] 分析超时，超过了{timeout_seconds}秒的限制")
            return None
        except Exception as e:
            logger.error(f"[{paper_id}] 分析过程中发生错误: {e}", exc_info=True)
            return None
        finally:
            paper_duration = time.time() - paper_start_time
            logger.info(f"[{paper_id}] 分析任务结束，总耗时: {paper_duration:.2f}秒")
    
    async def _analyze_paper_internal(self, paper_id: str) -> Optional[PaperAnalysis]:
        """内部方法，实际执行论文分析逻辑"""
        # 1. 检查分析是否已存在
        existing_analysis = await db_service.get_paper_analysis(paper_id)
        if existing_analysis:
            logger.info(f"[{paper_id}] 分析已存在，跳过")
            return existing_analysis
        
        # 2. 获取论文信息 (需要 PDF URL)
        paper = await db_service.get_paper_by_id(paper_id)
        if not paper:
            logger.error(f"[{paper_id}] 未找到论文，无法分析")
            return None
        if not paper.pdf_url:
             logger.error(f"[{paper_id}] 缺少 PDF URL，无法分析")
             return None

        # 3. 提取 PDF 文本 和 字数
        logger.info(f"[{paper_id}] 开始提取 PDF 文本: {paper.pdf_url}")
        extraction_result = await self._extract_text_from_pdf(paper_id, paper.pdf_url)
        
        if extraction_result is None:
            logger.error(f"[{paper_id}] 提取 PDF 文本失败")
            return None
        
        extracted_text, word_count = extraction_result # Unpack the tuple
        logger.info(f"[{paper_id}] PDF 文本提取完成，长度: {len(extracted_text)} 字符, 字数: {word_count}")
        
        # 4. 保存提取的文本和字数到数据库 
        if extracted_text: 
             logger.info(f"[{paper_id}] 尝试保存提取的文本和字数 ({word_count}) 到数据库...")
             # Pass word_count to the save function
             save_text_success = await db_service.save_or_update_extracted_text(paper_id, extracted_text, word_count)
             if save_text_success:
                  logger.info(f"[{paper_id}] 成功保存提取的文本和字数")
             else:
                  logger.error(f"[{paper_id}] 保存提取的文本到数据库失败，但将继续尝试分析")
        else:
             logger.warning(f"[{paper_id}] 提取的文本为空，不保存到数据库，中止分析")
             return None
        
        # 5. 调用 LLM 服务生成分析 JSON 字符串 
        logger.info(f"[{paper_id}] 开始调用 LLM 服务生成分析...")
        analysis_json_string = await self._generate_llm_analysis_json(paper_id, extracted_text)
        if not analysis_json_string:
             logger.error(f"[{paper_id}] LLM 未能生成分析 JSON")
             return None
             
        # 6. 解析和清理 LLM 返回的 JSON 
        logger.info(f"[{paper_id}] 开始解析和清理 LLM 响应...")
        cleaned_analysis_data = _parse_and_clean_llm_response(analysis_json_string, paper_id)
        if not cleaned_analysis_data:
             logger.error(f"[{paper_id}] 解析或清理 LLM 分析结果失败")
             return None
             
        # 7. 创建 PaperAnalysis 对象
        logger.info(f"[{paper_id}] 准备创建分析对象...")
        try:
            now = datetime.now()
            new_analysis = PaperAnalysis(
                paper_id=paper_id,
                summary=cleaned_analysis_data.get("summary"),
                key_findings=cleaned_analysis_data.get("key_findings"),
                contributions=cleaned_analysis_data.get("contributions"),
                methodology=cleaned_analysis_data.get("methodology"),
                limitations=cleaned_analysis_data.get("limitations"),
                future_work=cleaned_analysis_data.get("future_work"),
                keywords=cleaned_analysis_data.get("keywords"),
                created_at=now,
                updated_at=now
            )
        except Exception as e:
             logger.error(f"[{paper_id}] 创建 PaperAnalysis 对象失败: {e}", exc_info=True)
             return None

        # 8. 保存分析结果到数据库 
        logger.info(f"[{paper_id}] 尝试保存最终分析结果到数据库...")
        save_analysis_success = await db_service.save_paper_analysis(new_analysis)
        if save_analysis_success:
            logger.info(f"[{paper_id}] 成功保存分析结果到数据库")
            return new_analysis
        else:
            logger.error(f"[{paper_id}] 保存分析结果到数据库失败")
            return None
            
    async def analyze_pending_papers(self, process_all: bool = False, max_papers: int = None) -> Dict[str, Any]:
        """
        分析一批待处理的论文
        
        Args:
            process_all: 是否处理所有待分析论文，而不受批量大小限制
            max_papers: 最大处理论文数量限制（如果设置）
        """
        if self.is_analyzing:
            logger.info("分析任务已在运行中")
            return {"status": "already_running", "message": "Analysis task is already running.", "task_id": str(self.current_task.get_name() if self.current_task else None)}

        self.is_analyzing = True
        start_time = time.time()
        processed_count = 0
        failed_count = 0
        total_pending = 0
        total_processed = 0
        
        try:
            # 设置获取论文的批次大小和最大数量限制
            batch_limit = None if process_all else self.batch_size
            if max_papers is not None:
                batch_limit = min(max_papers, batch_limit) if batch_limit else max_papers
                
            logger.info(f"开始分析任务: {'处理所有待分析论文' if process_all else f'批量大小={batch_limit}'}")
            
            # 第一次获取待分析论文
            pending_papers = await db_service.get_papers_without_analysis(limit=batch_limit)
            
            if not pending_papers:
                logger.info("没有需要分析的论文")
                return {"status": "no_pending", "message": "No papers found needing analysis.", "processed": 0, "failed": 0}
            
            while pending_papers:
                batch_size = len(pending_papers)
                total_pending += batch_size
                logger.info(f"开始处理新批次: {batch_size} 篇待分析论文")
                
                analysis_tasks = []
                for paper in pending_papers:
                    # 为每篇论文创建一个分析任务，添加2分钟超时
                    analysis_tasks.append(self.analyze_paper(paper.paper_id, timeout_seconds=120))
                
                # 并发执行分析任务
                results = await asyncio.gather(*analysis_tasks, return_exceptions=True)
                
                # 处理结果
                batch_processed = 0
                batch_failed = 0
                for result in results:
                    if isinstance(result, PaperAnalysis):
                        batch_processed += 1
                        processed_count += 1
                    elif isinstance(result, Exception):
                        logger.error(f"批量分析中遇到错误: {result}")
                        batch_failed += 1
                        failed_count += 1
                    else: # 分析失败返回 None
                        batch_failed += 1
                        failed_count += 1
                
                total_processed += batch_size
                logger.info(f"当前批次完成. 成功: {batch_processed}, 失败: {batch_failed}")
                
                # 如果不处理所有论文或已达到最大数量，则退出循环
                if not process_all or (max_papers is not None and total_processed >= max_papers):
                    break
                    
                # 获取下一批待分析论文
                if process_all:
                    next_batch_limit = max_papers - total_processed if max_papers is not None else None
                    if next_batch_limit is not None and next_batch_limit <= 0:
                        break
                    pending_papers = await db_service.get_papers_without_analysis(limit=next_batch_limit)
                else:
                    break
            
            duration = time.time() - start_time
            logger.info(f"分析任务完成. 总耗时: {duration:.2f} 秒. 总计论文: {total_pending}, 成功: {processed_count}, 失败: {failed_count}")
            
            return {
                "status": "completed", 
                "message": f"Analysis finished.",
                "total_pending": total_pending,
                "processed": processed_count, 
                "failed": failed_count,
                "duration_seconds": round(duration, 2)
            }
            
        except Exception as e:
            logger.error(f"分析任务失败: {e}", exc_info=True)
            return {"status": "error", "message": str(e), "processed": processed_count, "failed": failed_count}
        finally:
            self.is_analyzing = False
            self.current_task = None
            
    async def start_analysis_task(self, process_all: bool = False, max_papers: int = None) -> Dict[str, Any]:
        """
        异步启动批量论文分析任务
        
        Args:
            process_all: 是否处理所有待分析论文，而不受批量大小限制
            max_papers: 最大处理论文数量限制（如果设置）
        """
        if self.is_analyzing:
            logger.info("分析任务已在运行中，无法启动新的任务")
            return {"status": "already_running", "message": "Analysis task is already running.", "task_id": str(self.current_task.get_name() if self.current_task else None)}

        logger.info(f"准备启动后台批量分析任务 (处理所有={process_all}, 最大数量={max_papers or '无限制'})")
        self.is_analyzing = True # 标记任务开始
        
        # 使用 asyncio.create_task 在后台运行 analyze_pending_papers
        # 将任务对象保存起来，如果需要的话可以用于查询状态或取消
        self.current_task = asyncio.create_task(
            self.analyze_pending_papers(process_all=process_all, max_papers=max_papers), 
            name=f"paper_analysis_task_{datetime.now():%Y%m%d_%H%M%S}"
        )
        
        logger.info(f"后台批量分析任务已启动: {self.current_task.get_name()}")
        
        return {
            "status": "started", 
            "message": "Background analysis task started.",
            "task_id": str(self.current_task.get_name())
        }

# 创建全局服务实例
paper_analysis_service = PaperAnalysisService() 