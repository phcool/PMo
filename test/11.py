"""
测试并比较两种从 arXiv 论文提取文本的方法：
1. 下载 PDF 并使用 PyMuPDF (fitz) 提取。
2. 下载 LaTeX 源码压缩包，解压，使用 pylatexenc 和 ftfy 从 .tex 文件提取。

所需依赖:
pip install asyncio aiohttp aiofiles pymupdf pylatexenc ftfy

运行方式:
python backend/scripts/test_extraction_methods.py <arxiv_id>
例如:
python backend/scripts/test_extraction_methods.py 2101.00001
"""
import asyncio
import aiohttp
import aiofiles
import fitz  # PyMuPDF
import tarfile
import time
import os
import shutil
import argparse # For command-line arguments
import logging
from typing import Tuple, List, Optional
from pylatexenc.latex2text import LatexNodes2Text
import ftfy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 配置 ---
DOWNLOAD_TIMEOUT = 60 # 下载超时时间（秒）
# -------------

async def download_file(url: str, path: str, timeout: int = DOWNLOAD_TIMEOUT) -> bool:
    """异步下载文件"""
    logger.info(f"开始下载: {url} -> {path}")
    try:
        timeout_config = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            async with session.get(url) as resp:
                resp.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
                async with aiofiles.open(path, 'wb') as f:
                    bytes_downloaded = 0
                    async for chunk in resp.content.iter_chunked(8192): # Read in chunks
                        await f.write(chunk)
                        bytes_downloaded += len(chunk)
                logger.info(f"下载完成: {path} ({bytes_downloaded / 1024:.1f} KB)")
                return True
    except aiohttp.ClientResponseError as e:
        logger.error(f'下载失败 {url}: HTTP {e.status} - {e.message}')
        return False
    except asyncio.TimeoutError:
         logger.error(f'下载超时 {url} (超过 {timeout} 秒)')
         return False
    except Exception as e:
        logger.error(f'下载时发生未知错误 {url}: {e}')
        return False

def extract_text_from_pdf(path: str) -> Tuple[Optional[str], int]:
    """从 PDF 文件提取文本并返回文本和页数"""
    try:
        doc = fitz.open(path)
        page_count = len(doc)
        texts = []
        for i, page in enumerate(doc):
            try:
                texts.append(page.get_text("text"))
            except Exception as page_e:
                 logger.warning(f"提取 PDF 第 {i+1}/{page_count} 页时出错: {page_e}")
        full_text = "\n\n".join(texts) # Use double newline to separate pages
        logger.info(f"成功从 PDF ({path}) 提取了 {page_count} 页的文本。")
        return full_text, page_count
    except Exception as e:
        logger.error(f"打开或处理 PDF 文件 {path} 时出错: {e}")
        return None, 0

def extract_text_from_tex_archive(archive_path: str, extract_dir: str) -> Tuple[Optional[str], int, List[str]]:
    """从 .tar.gz 源码包中提取 .tex 文件内容"""
    tex_files_processed = []
    tex_texts = []
    file_count = 0
    try:
        logger.info(f"开始解压源码包: {archive_path} -> {extract_dir}")
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir, exist_ok=True)

        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(path=extract_dir)
        logger.info("源码包解压完成。")

        logger.info("开始查找并处理 .tex 文件...")
        # 尝试查找主 tex 文件 (常见的名称)
        main_tex_candidates = ['main.tex', 'ms.tex', f"{os.path.basename(extract_dir).split('_')[0]}.tex"]
        main_tex_path = None
        found_tex_files = []

        for root, _, files in os.walk(extract_dir):
            for file in files:
                 if file.endswith('.tex'):
                    full_path = os.path.join(root, file)
                    found_tex_files.append(full_path)
                    if file in main_tex_candidates and main_tex_path is None:
                         main_tex_path = full_path
                         logger.info(f"找到疑似主文件: {main_tex_path}")

        # 如果找到主文件，优先处理它，否则处理所有找到的 .tex 文件
        files_to_process = [main_tex_path] if main_tex_path else found_tex_files

        if not files_to_process:
             logger.warning(f"在 {extract_dir} 中未找到 .tex 文件。")
             return None, 0, []

        for tex_path in files_to_process:
            logger.debug(f"处理 TeX 文件: {tex_path}")
            try:
                with open(tex_path, 'r', encoding='utf-8', errors='ignore') as f:
                    tex_content = f.read()
                    # 简单预处理：移除注释行 (虽然pylatexenc可能处理，但先移除明确的)
                    tex_content_no_comments = '\n'.join(
                        line for line in tex_content.splitlines() if not line.strip().startswith('%')
                    )
                    # 转换 LaTeX 到文本
                    plain_text = LatexNodes2Text().latex_to_text(tex_content_no_comments)
                    # 清理可能的编码问题和格式
                    cleaned_text = ftfy.fix_text(plain_text)
                    tex_texts.append(cleaned_text)
                    tex_files_processed.append(tex_path)
                    file_count += 1
            except Exception as e:
                logger.error(f'处理 TeX 文件 {tex_path} 时出错: {e}')

        if not tex_texts:
             logger.error("成功找到 .tex 文件，但未能从中提取任何文本。")
             return None, file_count, tex_files_processed

        full_text = '\n\n'.join(tex_texts) # 合并文本
        logger.info(f"成功处理了 {file_count} 个 TeX 文件。")
        return full_text, file_count, tex_files_processed

    except tarfile.TarError as e:
        logger.error(f"解压源码包 {archive_path} 时出错: {e}")
        return None, 0, []
    except Exception as e:
        logger.error(f"处理 TeX 源码时发生未知错误: {e}")
        return None, 0, []

def clean_final_text(text: Optional[str]) -> str:
    """对提取的最终文本进行基本的空白清理"""
    if text is None:
        return ""
    # 移除首尾空白
    text = text.strip()
    # 将多个换行符合并为最多两个换行符
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

async def main(arxiv_id: str):
    pdf_url = f'https://arxiv.org/pdf/{arxiv_id}.pdf'
    source_url = f'https://arxiv.org/e-print/{arxiv_id}'
    pdf_path = f'{arxiv_id}.pdf'
    source_path = f'{arxiv_id}.tar.gz'
    extract_dir = f'{arxiv_id}_src'

    pdf_text: Optional[str] = None
    tex_text: Optional[str] = None
    pdf_pages: int = 0
    tex_file_count: int = 0
    processed_tex_files: List[str] = []

    try:
        # --- PDF 方法 ---
        logger.info("="*20 + " PDF 方法测试 " + "="*20)
        start_pdf = time.time()
        pdf_download_ok = await download_file(pdf_url, pdf_path)
        if pdf_download_ok:
            pdf_text, pdf_pages = extract_text_from_pdf(pdf_path)
        duration_pdf = time.time() - start_pdf
        logger.info(f'PDF 方法总耗时: {duration_pdf:.2f} 秒 (下载 + 提取)')
        logger.info(f'PDF 页数: {pdf_pages}')
        pdf_text_cleaned = clean_final_text(pdf_text)
        logger.info(f'PDF 清理后文本长度: {len(pdf_text_cleaned)} 字符')
        logger.info(f'PDF 提取文本片段 (前500字符):\n"""\n{pdf_text_cleaned[:500]}...\n"""')
        print("-" * 50) # Separator

        # --- TeX 方法 ---
        logger.info("="*20 + " TeX 方法测试 " + "="*20)
        start_tex = time.time()
        tex_download_ok = await download_file(source_url, source_path)
        if tex_download_ok:
            tex_text, tex_file_count, processed_tex_files = extract_text_from_tex_archive(source_path, extract_dir)
        duration_tex = time.time() - start_tex
        logger.info(f'TeX 方法总耗时: {duration_tex:.2f} 秒 (下载 + 解压 + 提取)')
        logger.info(f'处理的 TeX 文件数量: {tex_file_count}')
        if processed_tex_files:
            logger.info(f'处理的文件列表: {processed_tex_files}')
        tex_text_cleaned = clean_final_text(tex_text)
        logger.info(f'TeX 清理后文本长度: {len(tex_text_cleaned)} 字符')
        logger.info(f'TeX 提取文本片段 (前500字符):\n"""\n{tex_text_cleaned[:500]}...\n"""')
        print("-" * 50) # Separator

    finally:
        # 清理下载的文件和目录
        logger.info("开始清理临时文件...")
        for path in [pdf_path, source_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    logger.debug(f"已删除: {path}")
                except OSError as e:
                    logger.warning(f"删除文件 {path} 失败: {e}")
        if os.path.exists(extract_dir):
            try:
                shutil.rmtree(extract_dir)
                logger.debug(f"已删除目录: {extract_dir}")
            except OSError as e:
                logger.warning(f"删除目录 {extract_dir} 失败: {e}")
        logger.info("清理完成。")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='比较从 arXiv PDF 和 LaTeX 源码提取文本的方法。')
    parser.add_argument('arxiv_id', type=str, help='要测试的 arXiv 论文 ID (例如: 2101.00001)')
    args = parser.parse_args()

    asyncio.run(main(args.arxiv_id))