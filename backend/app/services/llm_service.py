import os
import logging
import requests
import json
import time
import httpx
import asyncio
import re
from typing import Dict, Any, Optional, List
import aiohttp
import io
import fitz  # PyMuPDF
from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError

from app.models.paper import PaperAnalysis

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

class LLMService:
    """
    大语言模型服务，用于分析PDF内容 (使用OpenAI兼容模式)
    """
    
    def __init__(self):
        """初始化LLM服务"""
        # 获取API密钥和URL（从环境变量）
        self.api_key = os.getenv("LLM_API_KEY")
        self.api_url = os.getenv("LLM_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.model = os.getenv("LLM_MODEL", "qwen-turbo")
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4000"))
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        self.retry_attempts = int(os.getenv("LLM_RETRY_ATTEMPTS", "3"))
        self.retry_delay = int(os.getenv("LLM_RETRY_DELAY", "5"))
        if not self.api_key:
            logger.warning("LLM API密钥未设置，PDF分析功能将不可用")
            self.client = None
        else:
            # 初始化 AsyncOpenAI 客户端
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_url,
                max_retries=self.retry_attempts # Use openai's retry mechanism
            )
    
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
        if not self.client:
            logger.error("LLM 客户端未初始化 (API密钥缺失?)，无法分析PDF")
            return None
        
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
            
            # 准备提示词 (使用处理后的文本)
            prompt = f"""You are an expert academic paper analyst. Please analyze the following paper content and provide a structured analysis.

Paper Content:
{processed_text}

Please provide analysis in the following aspects:
1. Summary: Brief overview of the paper's main content and contributions.
2. Key Findings: List the main findings and conclusions of the paper.
3. Contributions: What are the paper's main contributions to the field?
4. Methodology: What methods were used in the paper?
5. Limitations: What are the limitations of the paper's methods or results?
6. Future Work: What future research directions does the paper suggest?

Please output the result strictly in JSON format without any explanatory text or prefix, following this structure:
{{
  "summary": "Paper summary",
  "key_findings": "Key findings",
  "contributions": "Main contributions",
  "methodology": "Methodology used",
  "limitations": "Limitations",
  "future_work": "Future work"
}}

IMPORTANT: Each field must be a simple string, NOT a nested structure. For all fields, provide a single coherent paragraph or a bulleted list with line breaks, but never use objects or arrays. If you need to present multiple items, simply separate them with line breaks within the string.

Ensure your response is objective and based on the paper content. If any aspect is not explicitly mentioned in the paper, mark it as "Not explicitly mentioned"."""
            
            # 调用LLM API - 使用 openai 兼容模式
            logger.info(f"向模型 {self.model} 发送分析请求: {paper_id}")
            try:
                completion = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert academic paper analyst, focused on providing objective, accurate, and strictly JSON-formatted paper analysis. All JSON fields must be simple strings, never nested objects or arrays."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={ "type": "json_object" } # 请求JSON格式输出
                )

                # 从响应中提取内容
                if completion.choices and completion.choices[0].message:
                    response_text = completion.choices[0].message.content
                    if not response_text:
                         logger.error("LLM响应内容为空")
                         return None
                    logger.info(f"收到来自模型 {self.model} 的响应: {paper_id}")
                else:
                    logger.error("无法从LLM响应中提取有效内容")
                    logger.debug(f"原始响应: {completion.model_dump_json()}")
                    return None

                # 尝试解析JSON
                try:
                    # 由于请求了JSON格式，直接解析
                    analysis_data = json.loads(response_text)

                    # --- 数据清洗：将可能的列表值或字典值合并为字符串 ---
                    def clean_value(value):
                        if isinstance(value, list):
                            # 将列表元素连接成字符串，用换行符分隔
                            clean_list = []
                            for item in value:
                                if isinstance(item, str):
                                    # 确保每个列表项都是单独一行
                                    item = item.strip()
                                    if item and not item.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                                        item = "• " + item
                                clean_list.append(str(item))
                            return '\n'.join(clean_list)
                        elif isinstance(value, dict):
                            # 将字典转换为字符串，采用"键: 值"的格式，每项一行
                            formatted_items = []
                            for k, v in value.items():
                                if isinstance(v, str):
                                    v = v.strip()
                                formatted_items.append(f"{k}: {v}")
                            return '\n'.join(formatted_items)
                        elif isinstance(value, str):
                            # 确保字符串中的换行符是一致的
                            return value.replace('\\n', '\n')
                        return value
                    
                    cleaned_data = {}
                    # 添加详细日志，记录清洗前后的数据类型
                    for k, v in analysis_data.items():
                        if k in ["summary", "key_findings", "contributions", "methodology", "limitations", "future_work"]:
                            original_type = type(v).__name__
                            cleaned_v = clean_value(v)
                            cleaned_type = type(cleaned_v).__name__
                            cleaned_data[k] = cleaned_v
                            
                            if original_type != cleaned_type:
                                logger.info(f"字段 {k} 类型从 {original_type} 转换为 {cleaned_type}")
                    
                    # 对最终结果再次进行格式整理，确保文本格式一致
                    for k, v in cleaned_data.items():
                        if isinstance(v, str):
                            # 1. 替换 "\\n" 转义字符为真正的换行符
                            v = v.replace('\\n', '\n')
                            # 2. 替换连续的多个换行符为两个换行符
                            v = re.sub(r'\n{3,}', '\n\n', v)
                            # 3. 确保数字列表项格式统一（例如 "1. "，"2. " 等）
                            v = re.sub(r'(\d+)\)([\s])', r'\1.\2', v)
                            cleaned_data[k] = v.strip()
                    # ----------------------------------------------

                    # 使用不带时区信息的时间戳
                    from datetime import datetime
                    now = datetime.now()  # 创建不带时区信息的时间戳，而不是使用time.time()

                    return PaperAnalysis(
                        paper_id=paper_id,
                        summary=cleaned_data.get("summary"),
                        key_findings=cleaned_data.get("key_findings"),
                        contributions=cleaned_data.get("contributions"),
                        methodology=cleaned_data.get("methodology"),
                        limitations=cleaned_data.get("limitations"),
                        future_work=cleaned_data.get("future_work"),
                        created_at=now,
                        updated_at=now
                    )
                except json.JSONDecodeError as e:
                    logger.error(f"无法将LLM响应解析为JSON: {str(e)}")
                    logger.debug(f"响应文本: {response_text}")
                    return None

            # 处理 OpenAI/兼容模式 的特定错误
            except APIConnectionError as e:
                logger.error(f"LLM API 连接错误: {e}")
                return None
            except RateLimitError as e:
                logger.error(f"LLM API 速率限制错误: {e}")
                # 可以考虑在这里增加等待重试逻辑，但openai库本身会重试
                return None
            except APIStatusError as e:
                logger.error(f"LLM API 状态错误: status_code={e.status_code}, response={e.response}")
                return None
            except UnicodeError as e:
                # 专门处理Unicode编码错误
                logger.error(f"Unicode编码错误: {e}. 尝试进一步清理文本...")
                try:
                    # 更激进的文本清理 - 只保留ASCII字符
                    ascii_text = processed_text.encode('ascii', errors='ignore').decode('ascii')
                    # 截断文本以减少大小
                    if len(ascii_text) > 10000:
                        ascii_text = ascii_text[:10000] + "...[截断]"
                    
                    logger.info(f"尝试使用ASCII文本重新发送请求，长度: {len(ascii_text)}")
                    
                    # 重新构建提示词并发送请求
                    simple_prompt = f"""Analyze this paper text and provide a JSON with: summary, key_findings, contributions, methodology, limitations, future_work.
                    
Text: {ascii_text}"""

                    completion = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are an expert academic paper analyst. Format all responses as simple strings in JSON."},
                            {"role": "user", "content": simple_prompt}
                        ],
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        response_format={ "type": "json_object" }
                    )
                    
                    # 从响应中提取内容...
                    if completion.choices and completion.choices[0].message:
                        response_text = completion.choices[0].message.content
                        if response_text:
                            analysis_data = json.loads(response_text)
                            # 上一步的数据清洗代码继续处理...
                            from datetime import datetime
                            now = datetime.now()
                            
                            cleaned_data = {}
                            for k, v in analysis_data.items():
                                if k in ["summary", "key_findings", "contributions", "methodology", "limitations", "future_work"]:
                                    original_type = type(v).__name__
                                    cleaned_v = clean_value(v)
                                    cleaned_data[k] = cleaned_v
                            
                            return PaperAnalysis(
                                paper_id=paper_id,
                                summary=cleaned_data.get("summary"),
                                key_findings=cleaned_data.get("key_findings"),
                                contributions=cleaned_data.get("contributions"),
                                methodology=cleaned_data.get("methodology"),
                                limitations=cleaned_data.get("limitations"),
                                future_work=cleaned_data.get("future_work"),
                                created_at=now,
                                updated_at=now
                            )
                except Exception as retry_error:
                    logger.error(f"尝试ASCII文本分析仍然失败: {retry_error}")
                    return None
            except Exception as e: # 捕获其他潜在的openai库或网络错误
                 logger.error(f"调用LLM API时发生未知错误: {e}")
                 return None

        except Exception as e:
            logger.error(f"分析PDF时发生意外错误 {pdf_url}: {e}")
            return None

# 创建全局实例
llm_service = LLMService() 