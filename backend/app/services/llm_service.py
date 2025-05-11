import os
import logging
import json # Keep json for potential future use, but not needed now
import time
import httpx
import asyncio
import re # re is no longer needed here
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError, APITimeoutError, APIError
from openai.types.chat import ChatCompletion # Import specific type for clarity
from openai.types import Embedding # Import Embedding type for clarity

logger = logging.getLogger(__name__)

# Removed clean_latex_formula and clean_text_for_api

class LLMService:
    """
    General Language Model Service Client (based on OpenAI-compatible interface)
    Only handles API interactions, does not include task-specific logic (like prompts or parsing)
    Supports different models for paper analysis and conversation
    """
    
    def __init__(self):
        """Initialize LLM service"""
        self.api_key = os.getenv("LLM_API_KEY", "")
        # Use DASHSCOPE_API_KEY if LLM_API_KEY is not set, for convenience
        if not self.api_key:
            self.api_key = os.getenv("DASHSCOPE_API_KEY")
            if self.api_key:
                 logger.info("Using DASHSCOPE_API_KEY for LLMService.")
                 
        self.api_url = os.getenv("LLM_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        # Paper analysis model (for PDF processing)
        self.paper_analysis_model = os.getenv("LLM_PAPER_MODEL", "qwen-turbo") 
        
        # Conversation model (for user interaction)
        self.conversation_model = os.getenv("LLM_CONVERSATION_MODEL", "qwen-3") 
        
        # Embedding model
        self.default_embedding_model = os.getenv("LLM_EMBEDDING_MODEL", "text-embedding-ada-002") 
        self.default_embedding_dimensions = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
        
        # Default parameters
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4000")) 
        self.paper_analysis_temperature = float(os.getenv("LLM_PAPER_TEMPERATURE", "0.0"))
        self.conversation_temperature = float(os.getenv("LLM_CONVERSATION_TEMPERATURE", "0.8"))
        self.request_timeout = int(os.getenv("LLM_REQUEST_TIMEOUT", "60")) 
        self.retry_delay = int(os.getenv("LLM_RETRY_DELAY", "5")) 
        
        if not self.api_key:
            logger.warning("LLM/DASHSCOPE API key not set, LLM and Embedding calls will not be available")
            self.client = None
        else:
            try:
                self.client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.api_url,
                    timeout=self.request_timeout, 
                    max_retries=2 
                )
                logger.info(f"LLMService initialized. Paper model: {self.paper_analysis_model}, Conversation model: {self.conversation_model}, Embedding model: {self.default_embedding_model} at {self.api_url}")
            except Exception as e:
                 logger.error(f"Failed to initialize AsyncOpenAI client: {e}")
                 self.client = None
    
    async def get_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None
    ) -> Optional[ChatCompletion]: 
        """
        Call chat model API to get completion results for paper analysis.
        By default uses the paper analysis model (qwen-turbo).
        
        Args:
            messages: List of dialogue messages in format [{"role": "user", "content": "..."}]
            model: Model name to use (defaults to paper_analysis_model)
            temperature: Temperature to control randomness (defaults to the temperature set during initialization)
            max_tokens: Maximum number of tokens to generate in the response (defaults to the setting during initialization)
            response_format: Requested response format (e.g. {"type": "json_object"})
            
        Returns:
            OpenAI ChatCompletion object, or None if the API call fails.
        """
        if not self.client:
            logger.error("LLM client not initialized, cannot call API")
            return None
        
        # Use provided parameters or fall back to defaults
        use_model = model if model is not None else self.paper_analysis_model
        use_temperature = temperature if temperature is not None else self.paper_analysis_temperature
        use_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        try:
            logger.debug(f"Sending paper analysis request to LLM. Model: {use_model}, Temp: {use_temperature}, MaxTokens: {use_max_tokens}, Format: {response_format}")
            start_time = time.time()
            
            # 禁用思考模式
            extra_body = {
                "enable_thinking": False
            }
            
            completion = await self.client.chat.completions.create(
                model=use_model,
                messages=messages,
                temperature=use_temperature,
                max_tokens=use_max_tokens,
                response_format=response_format, # Pass format if provided
                extra_body=extra_body  # 禁用思考模式
            )
            
            duration = time.time() - start_time
            logger.debug(f"Received LLM response. Duration: {duration:.2f} seconds. Usage: {completion.usage}")
            return completion
            
        except RateLimitError as e:
            logger.error(f"LLM API rate limit exceeded: {e}")
            return None
        except APITimeoutError as e:
            logger.error(f"LLM API timeout: {e}")
            return None
        except APIConnectionError as e:
            logger.error(f"LLM API connection error: {e}")
            return None
        except APIError as e:
            logger.error(f"LLM API error: {e}")
            return None
        except Exception as e: # Catch broader errors like timeouts included in the client
             logger.error(f"Unknown error occurred when calling LLM API: {e.__class__.__name__} - {e}")
             return None

    async def get_conversation_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = True
    ) -> Optional[ChatCompletion]:
        """
        Call chat model API specifically for conversation purposes.
        By default uses the conversation model (qwen-3).
        
        Args:
            messages: List of dialogue messages in format [{"role": "user", "content": "..."}]
            temperature: Temperature to control randomness (defaults to the conversation temperature)
            max_tokens: Maximum number of tokens to generate in the response (defaults to the setting during initialization)
            stream: Whether to stream the response (default: True for qwen-3 model)
            
        Returns:
            OpenAI ChatCompletion object, or None if the API call fails.
            If stream=True, will collect all chunks and return the complete response.
        """
        if not self.client:
            logger.error("LLM client not initialized, cannot call API")
            return None
        
        # Use provided parameters or fall back to defaults
        use_temperature = temperature if temperature is not None else self.conversation_temperature
        use_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        try:
            logger.debug(f"Sending conversation request to LLM. Model: {self.conversation_model}, Temp: {use_temperature}, MaxTokens: {use_max_tokens}, Stream: {stream}")
            start_time = time.time()
            
            # 禁用思考模式
            extra_body = {
                "enable_thinking": False
            }
            
            # Always use stream mode for qwen-3 model as required by the API
            stream_response = await self.client.chat.completions.create(
                model=self.conversation_model,
                messages=messages,
                temperature=use_temperature,
                max_tokens=use_max_tokens,
                stream=True,  # 强制使用流式模式
                extra_body=extra_body  # 禁用思考模式
            )
            
            # 收集流式响应的所有块，合并为完整的响应
            full_content = ""
            async for chunk in stream_response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    full_content += chunk.choices[0].delta.content
            
            # 构造类似非流式响应的结构
            duration = time.time() - start_time
            logger.debug(f"Received complete conversation response from stream. Duration: {duration:.2f} seconds.")
            
            # 创建一个模拟的完整响应
            from openai.types.chat.chat_completion import ChatCompletion, Choice, ChatCompletionMessage
            from openai.types.completion_usage import CompletionUsage
            
            # 创建一个模拟的响应对象
            completion = ChatCompletion(
                id="stream-response",
                choices=[
                    Choice(
                        finish_reason="stop",
                        index=0,
                        message=ChatCompletionMessage(
                            content=full_content,
                            role="assistant"
                        )
                    )
                ],
                created=int(time.time()),
                model=self.conversation_model,
                object="chat.completion",
                # 由于我们无法准确获取token使用情况，所以这里提供一个估计值或空值
                usage=CompletionUsage(
                    completion_tokens=-1,
                    prompt_tokens=-1,
                    total_tokens=-1
                )
            )
            
            return completion
            
        except RateLimitError as e:
            logger.error(f"LLM API rate limit exceeded: {e}")
            return None
        except APITimeoutError as e:
            logger.error(f"LLM API timeout: {e}")
            return None
        except APIConnectionError as e:
            logger.error(f"LLM API connection error: {e}")
            return None
        except APIError as e:
            logger.error(f"LLM API error: {e}")
            return None
        except Exception as e:
             logger.error(f"Unknown error occurred when calling LLM API for conversation: {e.__class__.__name__} - {e}")
             return None

    async def get_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        dimensions: Optional[int] = None,
        encoding_format: str = "float"
    ) -> Optional[List[List[float]]]:
        """
        Call embedding model API to get vector embeddings for texts.
        
        Args:
            texts: List of texts to embed.
            model: Embedding model name to use (defaults to the embedding model set during initialization).
            dimensions: Dimension of the embedding vectors (defaults to the dimension set during initialization).
            encoding_format: Encoding format ("float" or "base64").
            
        Returns:
            List of embedding vectors [[float], [float], ...], or None if the API call fails.
        """
        if not self.client:
            logger.error("LLM client not initialized, cannot get embeddings")
            return None
        
        if not texts: # Handle empty input list
             return []
             
        use_model = model if model is not None else self.default_embedding_model
        # We get the dimension value, but might not use it in the API call
        use_dimensions = dimensions if dimensions is not None else self.default_embedding_dimensions 
        
        try:
            logger.debug(f"Sending embedding request to LLM. Model: {use_model}, Target Dimensions: {use_dimensions}, Num Texts: {len(texts)}")
            start_time = time.time()
            
            response = await self.client.embeddings.create(
                model=use_model,
                input=texts,
                encoding_format=encoding_format
            )
            
            duration = time.time() - start_time
            logger.debug(f"Received LLM embedding response. Duration: {duration:.2f} seconds. Usage: {response.usage}")
            
            # Extract embeddings
            if response.data:
                sorted_embeddings = sorted(response.data, key=lambda e: e.index)
                return [item.embedding for item in sorted_embeddings]
            else:
                 logger.warning(f"LLM embedding response did not contain data for model {use_model}")
                 return None

        except RateLimitError as e:
            logger.error(f"Embedding API rate limit exceeded: {e}")
            return None
        except APITimeoutError as e:
            logger.error(f"Embedding API timeout: {e}")
            return None
        except APIConnectionError as e:
            logger.error(f"Embedding API connection error: {e}")
            return None
        except APIError as e:
            logger.error(f"Embedding API error: {e}")
            return None
        except Exception as e: 
             logger.error(f"Unknown error occurred when calling LLM API (Embeddings): {e.__class__.__name__} - {e}")
             return None

# Create global LLM service instance
llm_service = LLMService() 