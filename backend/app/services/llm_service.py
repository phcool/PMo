import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APITimeoutError, APIError
import dashscope
from http import HTTPStatus

logger = logging.getLogger(__name__)

class LLMService:
    """
    General LLM Service Client
    """
    
    def __init__(self):
        """Initialize LLM service"""
        # api key and url
        self.api_key = os.getenv("LLM_API_KEY", "")
                 
        self.api_url = os.getenv("LLM_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

        # default models and settings
        
        self.conversation_model = os.getenv("LLM_CONVERSATION_MODEL", "qwen-3") 

        self.default_embedding_model = os.getenv("LLM_EMBEDDING_MODEL", "text-embedding-v3") 
        self.default_embedding_dimensions = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
        self.BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "10"))

        self.rerank_model=os.getenv("LLM_RERANK_MODEL","gte-rerank-v2")
        self.rerank_topn=os.getenv("LLM_RERANK_TOPN",30)
        
        # Default parameters
        self.max_tokens = 4000 
        self.conversation_temperature = 0.8

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.api_url
        )
        if not self.client:
            raise ValueError("LLM client failed to initialize")

    async def get_conversation_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: Optional[bool] = True,
        thinking: Optional[bool] = False
    ) -> Optional[Any]:
        """
        call chat model to generate response
        """
        
        use_temperature = temperature if temperature is not None else self.conversation_temperature
        use_max_tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        try:
            logger.debug(f"Sending conversation request to LLM. Model: {self.conversation_model}, Stream:{stream}")
        
            extra_body={
                "enable_thinking":thinking
            }
            # Always use stream mode for LLM responses
            response = await self.client.chat.completions.create(
                model=self.conversation_model,
                messages=messages,
                temperature=use_temperature,
                max_tokens=use_max_tokens,
                stream=stream,    
                extra_body=extra_body
            )
            
            logger.debug(f"Returning response for LLM conversation.")
            return response
            
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
        dimensions: Optional[int] = None,
        encoding_format: str = "float"
    ) -> Optional[List[List[float]]]:
        """
        call embedding model to get vector embeddings for texts
        """
        if not self.client:
            logger.error("LLM client not initialized")
            return None
        
        if not texts:
             return []

        use_dimensions = dimensions if dimensions is not None else self.default_embedding_dimensions 
        
        try:
            logger.debug(f"Sending embedding request to LLM, Target Dimensions: {use_dimensions}, Num Texts: {len(texts)}")
            
            all_embeddings = []
            
            for i in range(0, len(texts), self.BATCH_SIZE):
                logger.info(f"Sending batch {i//self.BATCH_SIZE + 1}/{len(texts)//self.BATCH_SIZE + 1} to LLM")
                batch_texts = texts[i:i + self.BATCH_SIZE]
                
                batch_response = await self.client.embeddings.create(
                    model=self.default_embedding_model,
                    input=batch_texts,
                    encoding_format=encoding_format
                )
                
                if batch_response.data:
                    batch_embeddings = [item.embedding for item in batch_response.data]
                    all_embeddings.extend(batch_embeddings)
                else:
                    logger.warning(f"Batch {i//self.BATCH_SIZE + 1} embedding response did not contain data")
                    return None
                
                if i + self.BATCH_SIZE < len(texts):
                    await asyncio.sleep(0.1)
            
            return all_embeddings
            

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
        

    async def get_rerank(
        self,
        documents:List[str],
        query:str
    ) -> List[int]:
        dashscope.api_key = self.api_key
        response = dashscope.TextReRank.call(
        model="gte-rerank-v2",
        query=query,
        documents=documents,
        top_n=self.rerank_topn,
        return_documents=True
        )
        if response.status_code == HTTPStatus.OK:
            # Return the sorted indices from the results
            return [result['index'] for result in response.output['results']]
        return []

# Create global LLM service instance
llm_service = LLMService() 


