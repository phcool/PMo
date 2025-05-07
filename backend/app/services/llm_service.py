import os
import logging
import json # Keep json for potential future use, but not needed now
import time
import httpx
import asyncio
import re # re is no longer needed here
from typing import Dict, Any, Optional, List
from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError
from openai.types.chat import ChatCompletion # Import specific type for clarity
from openai.types import Embedding # Import Embedding type for clarity

logger = logging.getLogger(__name__)

# Removed clean_latex_formula and clean_text_for_api

class LLMService:
    """
    General Language Model Service Client (based on OpenAI-compatible interface)
    Only handles API interactions, does not include task-specific logic (like prompts or parsing)
    """
    
    def __init__(self):
        """Initialize LLM service"""
        self.api_key = os.getenv("LLM_API_KEY")
        # Use DASHSCOPE_API_KEY if LLM_API_KEY is not set, for convenience
        if not self.api_key:
            self.api_key = os.getenv("DASHSCOPE_API_KEY")
            if self.api_key:
                 logger.info("Using DASHSCOPE_API_KEY for LLMService.")
                 
        self.api_url = os.getenv("LLM_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        self.default_model = os.getenv("LLM_MODEL", "qwen-turbo") # Default for chat
        self.default_embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-v2") # Default for embeddings
        self.default_embedding_dimensions = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
        self.default_max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4000")) 
        self.default_temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        self.request_timeout = int(os.getenv("LLM_REQUEST_TIMEOUT", "60")) # Adjusted timeout
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
                logger.info(f"LLMService initialized. Default chat model: {self.default_model}, Default embedding model: {self.default_embedding_model} at {self.api_url}")
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
    ) -> Optional[ChatCompletion]: # Return the specific completion object type
        """
        Call chat model API to get completion results.
        
        Args:
            messages: List of dialogue messages in format [{"role": "user", "content": "..."}]
            model: Model name to use (defaults to the model set during initialization)
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
        use_model = model if model is not None else self.default_model
        use_temperature = temperature if temperature is not None else self.default_temperature
        use_max_tokens = max_tokens if max_tokens is not None else self.default_max_tokens
        
        try:
            logger.debug(f"Sending request to LLM. Model: {use_model}, Temp: {use_temperature}, MaxTokens: {use_max_tokens}, Format: {response_format}")
            start_time = time.time()
            
            completion = await self.client.chat.completions.create(
                model=use_model,
                messages=messages,
                temperature=use_temperature,
                max_tokens=use_max_tokens,
                response_format=response_format # Pass format if provided
            )
            
            duration = time.time() - start_time
            logger.debug(f"Received LLM response. Duration: {duration:.2f} seconds. Usage: {completion.usage}")
            return completion
            
        except APIConnectionError as e:
            logger.error(f"LLM API connection error: {e}")
            return None
        except RateLimitError as e:
            logger.error(f"LLM API rate limit error: {e}. Consider adding specific retry logic if needed beyond client retries.")
            # await asyncio.sleep(self.retry_delay) # Optional manual delay before caller retries
            return None
        except APIStatusError as e:
            logger.error(f"LLM API status error: status_code={e.status_code}, response={e.response}")
            return None
        except Exception as e: # Catch broader errors like timeouts included in the client
             logger.error(f"Unknown error occurred when calling LLM API: {e.__class__.__name__} - {e}")
             return None

    async def get_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        dimensions: Optional[int] = None, # Parameter remains, but we won't pass it if using default
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
            
            # --- CHANGE: Do not pass dimensions parameter to the API call --- 
            # The API will use the model's default dimension.
            # We still need `use_dimensions` for potential internal checks later if needed.
            # extra_args = {}
            # if use_dimensions is not None: # Check if we *have* a dimension value
            #      # Maybe only pass if *not* the default for the model? Complex logic.
            #      # Safest bet for compatibility issues is often *not* to pass it.
            #      # extra_args['dimensions'] = use_dimensions
                 
            response = await self.client.embeddings.create(
                model=use_model,
                input=texts,
                encoding_format=encoding_format
                # **extra_args  <- Removed
            )
            # ---------------------------------------------------------------
            
            duration = time.time() - start_time
            logger.debug(f"Received LLM embedding response. Duration: {duration:.2f} seconds. Usage: {response.usage}")
            
            # Extract embeddings
            if response.data:
                sorted_embeddings = sorted(response.data, key=lambda e: e.index)
                # Optional: Check actual embedding dimension if needed
                # actual_dim = len(sorted_embeddings[0].embedding)
                # if actual_dim != use_dimensions:
                #    logger.warning(f"Requested dimension {use_dimensions} but received {actual_dim}")
                return [item.embedding for item in sorted_embeddings]
            else:
                 logger.warning(f"LLM embedding response did not contain data for model {use_model}")
                 return None

        except APIConnectionError as e:
            logger.error(f"LLM API (Embeddings) connection error: {e}")
            return None
        except RateLimitError as e:
            logger.error(f"LLM API (Embeddings) rate limit error: {e}")
            return None
        except APIStatusError as e:
            logger.error(f"LLM API (Embeddings) status error: status_code={e.status_code}, response={e.response}")
            return None
        except Exception as e: 
             logger.error(f"Unknown error occurred when calling LLM API (Embeddings): {e.__class__.__name__} - {e}")
             return None

# Create global LLM service instance
llm_service = LLMService() 