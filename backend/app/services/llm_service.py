import os
import logging
import requests
import json
import time
import httpx
import asyncio
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError

from app.models.paper import PaperAnalysis

logger = logging.getLogger(__name__)

class LLMService:
    """
    大语言模型服务，用于分析文本 (使用OpenAI兼容模式)
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
            logger.warning("LLM API密钥未设置，分析功能将不可用")
            self.client = None
        else:
            # 初始化 AsyncOpenAI 客户端
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_url,
                max_retries=self.retry_attempts # Use openai's retry mechanism
            )
    
    async def analyze_paper_text(self, paper_id: str, text: str) -> Optional[PaperAnalysis]:
        """
        分析论文文本内容
        
        Args:
            paper_id: 论文ID
            text: 预处理后的论文文本
            
        Returns:
            分析结果或None（如果分析失败）
        """
        if not self.client:
            logger.error("LLM 客户端未初始化 (API密钥缺失?)，无法分析文本")
            return None
        
        try:
            # 准备提示词
            prompt = f"""You are an expert academic paper analyst. Please analyze the following paper content and provide a structured analysis.

Paper Content:
{text}

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
                    ascii_text = text.encode('ascii', errors='ignore').decode('ascii')
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
            logger.error(f"分析论文时发生意外错误: {e}")
            return None

# 创建全局实例
llm_service = LLMService() 