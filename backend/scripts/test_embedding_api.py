# backend/scripts/test_embedding_api.py
import asyncio
import os
import sys
from dotenv import load_dotenv
import time
from typing import List

# 确保可以从脚本目录导入 app 服务
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# 加载 .env 文件
load_dotenv(os.path.join(project_root, '.env'))

# 导入 llm_service (确保在 load_dotenv 之后)
try:
    from app.services.llm_service import llm_service
except ImportError as e:
    print(f"导入 llm_service 失败: {e}")
    print("请确保你在项目根目录的 backend/ 文件夹下运行此脚本，或者路径设置正确。")
    sys.exit(1)

# --- 测试配置 ---
# 创建一些简单的测试文本
TEST_TEXTS = [f"This is test sentence number {i+1} for embedding." for i in range(55)] # 创建 55 个文本，方便测试不同批次
MODEL_TO_TEST = os.getenv("EMBEDDING_MODEL", "text-embedding-v3") # 从 env 获取模型

async def test_batch_embedding(texts_to_embed: List[str], batch_size: int):
    """
    测试以指定的批量大小调用嵌入 API。

    Args:
        texts_to_embed: 要嵌入的文本列表。
        batch_size: 每个 API 请求发送的文本数量。
    """
    print(f"\n--- 测试 Batch Size: {batch_size} ---")
    all_embeddings = []
    total_texts = len(texts_to_embed)
    batches_processed = 0
    start_overall = time.time()

    for i in range(0, total_texts, batch_size):
        batch = texts_to_embed[i : i + batch_size]
        batches_processed += 1
        print(f"  发送第 {batches_processed} 批，数量: {len(batch)} (文本 {i+1} 到 {min(i + batch_size, total_texts)})")
        start_batch = time.time()

        # 调用 get_embeddings
        batch_embeddings = await llm_service.get_embeddings(
            texts=batch,
            model=MODEL_TO_TEST
            # dimensions 参数不传递，使用模型默认值
        )

        end_batch = time.time()
        duration_batch = end_batch - start_batch

        if batch_embeddings is not None:
            print(f"  ✅ 成功获取 {len(batch_embeddings)} 个嵌入向量。耗时: {duration_batch:.2f} 秒.")
            all_embeddings.extend(batch_embeddings)
            # 可以在这里添加一个小的延迟，避免触发速率限制
            await asyncio.sleep(0.5) # 暂停 0.5 秒
        else:
            print(f"  ❌ 失败：未能获取该批次的嵌入向量。")
            # 可以选择在这里停止测试或继续测试其他批次
            # return False # 如果希望失败时停止整个测试

    end_overall = time.time()
    duration_overall = end_overall - start_overall
    print(f"--- 测试 Batch Size {batch_size} 完成 ---")
    print(f"总计 {batches_processed} 批，成功获取 {len(all_embeddings)} / {total_texts} 个嵌入向量。")
    print(f"总耗时: {duration_overall:.2f} 秒.")
    return len(all_embeddings) == total_texts

async def main():
    if not llm_service or not llm_service.client:
        print("LLM 服务未成功初始化，请检查 API Key 和 .env 文件。")
        return

    print(f"开始测试通义千问嵌入 API ({MODEL_TO_TEST}) 调用...")
    print(f"将使用 {len(TEST_TEXTS)} 个测试文本。")

    # 测试不同的批量大小
    batch_sizes_to_test = [50, 25, 16, 10, 5, 1]

    successful_batch_size = None
    for size in batch_sizes_to_test:
        success = await test_batch_embedding(TEST_TEXTS, size)
        if success:
            successful_batch_size = size
            print(f"\n🎉 批量大小 {size} 测试成功！")
            # 可以选择找到第一个成功的就停止
            # break
        else:
            print(f"\n⚠️ 批量大小 {size} 测试失败。")

    if successful_batch_size:
        print(f"\n结论：API 似乎支持至少 {successful_batch_size} 的批量大小。")
        print("建议在 vector_search_service.py 中使用这个或更小的批量大小。")
    else:
        print("\n结论：所有测试的批量大小都失败了。请检查：")
        print("1. API Key 是否有效且有足够额度。")
        print("2. 网络连接是否正常。")
        print(f"3. 模型名称 '{MODEL_TO_TEST}' 是否正确且被 API 端点支持。")
        print("4. 查看更详细的日志输出以获取线索。")

if __name__ == "__main__":
    asyncio.run(main())