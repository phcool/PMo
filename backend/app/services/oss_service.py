# import os
# import logging
# import re
# import json
# from pathlib import Path
# import aiofiles
# import oss2
# from typing import Optional, Dict, List, Any, Tuple
# from datetime import datetime

# logger = logging.getLogger(__name__)

# class OssService:
    
#     def __init__(self):
#         self.oss_access_key_id = os.getenv("OSS_ACCESS_KEY_ID", "")
#         self.oss_access_key_secret = os.getenv("OSS_ACCESS_KEY_SECRET", "")
#         self.oss_endpoint = os.getenv("OSS_ENDPOINT", "")
#         self.oss_bucket_name = os.getenv("OSS_BUCKET_NAME", "")
#         self.oss_papers_prefix = os.getenv("OSS_PAPERS_PREFIX", "papers/")
#         self.oss_embeddings_prefix = os.getenv("OSS_EMBEDDINGS_PREFIX", "embeddings/")
        
#         if not all([self.oss_access_key_id, self.oss_access_key_secret, 
#                     self.oss_endpoint, self.oss_bucket_name]):
#             logger.warning("OSS configuration incomplete. Some functions may not work properly.")
        
#         logger.info(f"OSS Service initialized with endpoint: {self.oss_endpoint}, bucket: {self.oss_bucket_name}")

#     async def download_paper_from_oss(self, paper_id: str, target_dir: Path, custom_filename: Optional[str] = None) -> str:
#         try:
#             logger.info(f"Downloading PDF from OSS for paper_id: {paper_id}, custom filename: {custom_filename}")
            
#             sanitized_paper_id = re.sub(r'[^\w\.-]', '_', paper_id)
#             if sanitized_paper_id != paper_id:
#                 logger.info(f"Sanitized paper_id from '{paper_id}' to '{sanitized_paper_id}'")
#                 paper_id = sanitized_paper_id
            
#             match_format = re.match(r'^(\d{2})(\d{2})\.(\d+)', paper_id)
#             if not match_format:
#                 logger.error(f"Invalid paper_id format: {paper_id}")
#                 return ""
                
#             year, month, number = match_format.groups()
            
#             oss_paper_id = paper_id.replace('.', '_')
#             oss_key = f"{self.oss_papers_prefix}{year}/{month}/{oss_paper_id}.pdf"
            
#             local_dir = target_dir / year / month
#             os.makedirs(local_dir, exist_ok=True)
            
#             local_filename = f"{oss_paper_id}.pdf"
#             if custom_filename:
#                 name, ext = os.path.splitext(custom_filename)
#                 if not ext.lower() == '.pdf':
#                     ext = '.pdf'
#                 local_filename = f"{oss_paper_id}_{name}{ext}"
            
#             local_file_path = local_dir / local_filename
 
#             if await aiofiles.os.path.exists(local_file_path):
#                 logger.info(f"PDF file already exists locally at {local_file_path}")
#                 return str(local_file_path)
            
#             logger.info(f"PDF file not found locally, downloading from OSS with key: {oss_key}")
            
#             try:
#                 auth = oss2.Auth(self.oss_access_key_id, self.oss_access_key_secret)
#                 bucket = oss2.Bucket(auth, self.oss_endpoint, self.oss_bucket_name)
#                 logger.info("Successfully initialized OSS client")
#             except Exception as e:
#                 logger.error(f"Failed to initialize OSS client: {str(e)}")
#                 return ""
            
#             try:
#                 logger.info(f"Attempting to download object from OSS with key: {oss_key}")
#                 result = bucket.get_object(oss_key)
#                 file_content = result.read()
#                 logger.info(f"Successfully downloaded {len(file_content)} bytes from OSS")
#             except oss2.exceptions.NoSuchKey:
#                 logger.error(f"OSS key not found: {oss_key}")
#                 return ""
#             except oss2.exceptions.OssError as e:
#                 logger.error(f"OSS error during download: {str(e)}")
#                 return ""
#             except Exception as e:
#                 logger.error(f"Unexpected error during OSS download: {str(e)}")
#                 return ""
            
#             if not file_content:
#                 logger.error(f"Failed to download PDF for paper ID: {paper_id}")
#                 return ""
#             try:
#                 async with aiofiles.open(local_file_path, 'wb') as f:
#                     await f.write(file_content)
#                 logger.info(f"Successfully saved downloaded PDF to {local_file_path} ({len(file_content)} bytes)")
#                 return str(local_file_path)
#             except Exception as e:
#                 logger.error(f"Failed to save PDF file to {local_file_path}: {str(e)}")
#                 return ""
                
#         except Exception as e:
#             logger.error(f"Error downloading PDF from OSS for paper ID {paper_id}: {str(e)}", exc_info=True)
#             return ""
    
#     async def upload_file_to_oss(self, file_path: str, oss_key: str) -> bool:
#         try:
#             if not await aiofiles.os.path.exists(file_path):
#                 logger.error(f"File not found for upload: {file_path}")
#                 return False
                
            
#             auth = oss2.Auth(self.oss_access_key_id, self.oss_access_key_secret)
#             bucket = oss2.Bucket(auth, self.oss_endpoint, self.oss_bucket_name)
            
            
#             async with aiofiles.open(file_path, 'rb') as f:
#                 file_content = await f.read()
            
            
#             result = bucket.put_object(oss_key, file_content)
#             if result.status == 200:
#                 logger.info(f"Successfully uploaded file to OSS: {oss_key}")
#                 return True
#             else:
#                 logger.error(f"Failed to upload file to OSS: {oss_key}, status: {result.status}")
#                 return False
                
#         except Exception as e:
#             logger.error(f"Error uploading file to OSS: {str(e)}")
#             return False

#     async def get_vector_embeddings(self, paper_id: str) -> Tuple[Optional[List[str]], Optional[List[List[float]]]]:
#         try:
#             sanitized_paper_id = re.sub(r'[^\w\.-]', '_', paper_id)
#             if sanitized_paper_id != paper_id:
#                 paper_id = sanitized_paper_id
                
#             match_format = re.match(r'^(\d{2})(\d{2})\.(\d+)', paper_id)
#             if not match_format:
#                 logger.error(f"Invalid paper_id format for embedding lookup: {paper_id}")
#                 return None, None
                
#             year, month, number = match_format.groups()
#             oss_paper_id = paper_id.replace('.', '_')
#             oss_key = f"{self.oss_embeddings_prefix}{year}/{month}/{oss_paper_id}.json"
            
#             logger.info(f"Looking for vector embeddings at OSS key: {oss_key}")
            
#             auth = oss2.Auth(self.oss_access_key_id, self.oss_access_key_secret)
#             bucket = oss2.Bucket(auth, self.oss_endpoint, self.oss_bucket_name)
            
#             try:
#                 meta = bucket.head_object(oss_key)
#                 logger.info(f"Found embeddings file for {paper_id}, size: {meta.content_length} bytes")
#             except oss2.exceptions.NoSuchKey:
#                 logger.info(f"No embeddings found for paper_id: {paper_id}")
#                 return None, None
            
#             result = bucket.get_object(oss_key)
#             content = result.read()
            
#             if not content:
#                 logger.warning(f"Embeddings file exists but is empty for paper_id: {paper_id}")
#                 return None, None
                
#             try:
#                 data = json.loads(content)
#                 chunks = data.get("chunks", [])
#                 embeddings = data.get("embeddings", [])
                
#                 if not chunks or not embeddings or len(chunks) != len(embeddings):
#                     logger.warning(f"Invalid embeddings data for paper_id: {paper_id}. Chunks: {len(chunks)}, Embeddings: {len(embeddings)}")
#                     return None, None
                    
#                 logger.info(f"Successfully loaded embeddings for paper_id: {paper_id}. Chunks: {len(chunks)}")
#                 return chunks, embeddings
                
#             except json.JSONDecodeError:
#                 logger.error(f"Failed to parse embeddings JSON for paper_id: {paper_id}")
#                 return None, None
                
#         except Exception as e:
#             logger.error(f"Error getting vector embeddings for {paper_id}: {str(e)}")
#             return None, None
            
#     async def save_vector_embeddings(self, paper_id: str, chunks: List[str], embeddings: List[List[float]]) -> bool:
#         try:    
#             if not chunks or not embeddings or len(chunks) != len(embeddings):
#                 logger.error(f"Invalid data for saving embeddings. Chunks: {len(chunks)}, Embeddings: {len(embeddings)}")
#                 return False
                
#             sanitized_paper_id = re.sub(r'[^\w\.-]', '_', paper_id)
#             if sanitized_paper_id != paper_id:
#                 paper_id = sanitized_paper_id
                
#             match_format = re.match(r'^(\d{2})(\d{2})\.(\d+)', paper_id)
#             if not match_format:
#                 logger.error(f"Invalid paper_id format for embedding save: {paper_id}")
#                 return False
                
#             year, month, number = match_format.groups()
#             oss_paper_id = paper_id.replace('.', '_')
#             oss_key = f"{self.oss_embeddings_prefix}{year}/{month}/{oss_paper_id}.json"
            
#             logger.info(f"Preparing to save embeddings for paper_id: {paper_id} to OSS key: {oss_key}")

#             data = {
#                 "paper_id": paper_id,
#                 "chunks_count": len(chunks),
#                 "embeddings_count": len(embeddings),
#                 "chunks": chunks,
#                 "embeddings": embeddings,
#                 "created_at": str(datetime.now())
#             }
            
#             json_data = json.dumps(data)
            
#             auth = oss2.Auth(self.oss_access_key_id, self.oss_access_key_secret)
#             bucket = oss2.Bucket(auth, self.oss_endpoint, self.oss_bucket_name)
            
#             result = bucket.put_object(oss_key, json_data)
            
#             if result.status == 200:
#                 logger.info(f"Successfully saved embeddings for paper_id: {paper_id}, size: {len(json_data)} bytes")
#                 return True
#             else:
#                 logger.error(f"Failed to save embeddings for paper_id: {paper_id}, status: {result.status}")
#                 return False
                
#         except Exception as e:
#             logger.error(f"Error saving vector embeddings for {paper_id}: {str(e)}")
#             return False

# oss_service = OssService() 