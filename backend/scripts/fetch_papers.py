#!/usr/bin/env python3
"""
手动获取论文脚本
使用方法:
    python scripts/fetch_papers.py [--categories cs.LG cs.AI cs.CV] [--max-results 50] [--analyze]
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


async def fetch_papers(categories=None, max_results=50, analyze=False):
    """
    手动获取论文
    
    Args:
        categories: 要获取的论文类别，默认使用配置中的默认类别
        max_results: 最大获取论文数量
        analyze: 获取后是否立即分析论文
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
            
            # 如果指定了分析选项且有新论文，则启动分析
            if analyze and result.get("count", 0) > 0:
                print("\n开始分析新获取的论文...")
                analysis_result = await scheduler_service.manual_analyze()
                
                if analysis_result["status"] == "started":
                    print("✅ 论文分析任务已启动!")
                    print(f"开始时间: {analysis_result.get('timestamp', datetime.now().isoformat())}")
                elif analysis_result["status"] == "in_progress":
                    print("⚠️ 已有分析任务正在进行中，未启动新任务。")
                else:
                    print(f"⚠️ 分析任务状态: {analysis_result.get('status')}")
                    print(f"详细信息: {analysis_result.get('message', '无详细信息')}")
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
    
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="获取后立即分析新论文"
    )
    
    args = parser.parse_args()
    
    # 执行异步函数
    asyncio.run(fetch_papers(
        categories=args.categories,
        max_results=args.max_results,
        analyze=args.analyze
    ))


if __name__ == "__main__":
    main() 