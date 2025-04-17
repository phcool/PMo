#!/usr/bin/env python3
"""
手动获取论文脚本
使用方法:
    python scripts/fetch_papers.py [--categories cs.LG cs.AI cs.CV] [--max-results 50]
"""

import asyncio
import sys
import os
import argparse
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 导入所需服务
from app.services.scheduler_service import scheduler_service


async def fetch_papers(categories=None, max_results=50):
    """
    手动获取论文
    
    Args:
        categories: 要获取的论文类别，默认使用配置中的默认类别
        max_results: 最大获取论文数量
    """
    print(f"开始获取论文，时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if categories:
        print(f"指定类别: {', '.join(categories)}")
    else:
        print(f"使用默认类别: {', '.join(scheduler_service.default_categories)}")
    
    print(f"最大获取数量: {max_results}")
    print("正在获取中，请稍候...")
    
    try:
        # 调用服务获取论文
        result = await scheduler_service.manual_fetch(categories=categories, max_results=max_results)
        
        if result["status"] == "success":
            print("\n✅ 获取成功!")
            print(f"获取了 {result.get('count', 0)} 篇新论文")
            print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            if result.get("message"):
                print(f"详细信息: {result['message']}")
        else:
            print("\n❌ 获取失败!")
            print(f"错误信息: {result.get('message', '未知错误')}")
    
    except Exception as e:
        print(f"\n❌ 执行出错: {str(e)}")
        return False
    
    return True


def main():
    """主函数，解析命令行参数并执行获取"""
    parser = argparse.ArgumentParser(description="手动获取arXiv论文")
    
    parser.add_argument(
        "--categories", 
        nargs="+", 
        help="要获取的论文类别，例如: cs.LG cs.AI cs.CV"
    )
    
    parser.add_argument(
        "--max-results", 
        type=int, 
        default=50,
        help="最大获取论文数量，默认50"
    )
    
    args = parser.parse_args()
    
    # 执行异步函数
    asyncio.run(fetch_papers(
        categories=args.categories,
        max_results=args.max_results
    ))


if __name__ == "__main__":
    main() 