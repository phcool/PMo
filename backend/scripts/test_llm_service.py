#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import sys
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# 确定.env文件的路径 (在backend目录下)
dotenv_path = Path(__file__).parent.parent / '.env'
# 加载环境变量
load_dotenv(dotenv_path=dotenv_path)

# 确保可以导入app模块
sys.path.append(str(Path(__file__).parent.parent))

from app.services.llm_service import llm_service
from app.services.paper_analysis_service import paper_analysis_service

async def test_analyze_pdf():
    """测试PDF分析功能"""
    print("开始测试PDF分析服务...")
    
    # 测试用的PDF URL，请替换为实际可访问的PDF URL
    pdf_url = "https://arxiv.org/pdf/2504.11421"  # 这是论文示例
    paper_id = "test_paper_123"
    
    print(f"使用API URL: {llm_service.api_url}")
    print(f"使用模型: {llm_service.model}")
    print(f"API密钥设置状态: {'已设置' if llm_service.api_key else '未设置'}")
    
    if not llm_service.api_key:
        print("错误: 未设置LLM API密钥。请在.env文件中设置LLM_API_KEY。")
        return
    
    try:
        print(f"开始分析PDF: {pdf_url}")
        print("正在提取PDF文本...")
        
        # 首先测试文本提取
        text = await paper_analysis_service.extract_text_from_pdf(pdf_url)
        if not text:
            print("错误: 无法提取PDF文本")
            return
        
        print(f"成功提取PDF文本，长度: {len(text)} 字符")
        print("前200个字符预览:")
        print(text[:200] + "...\n")
        
        # 测试完整分析
        print("开始PDF分析...")
        result = await paper_analysis_service.analyze_pdf(paper_id, pdf_url)
        
        if result:
            print("分析成功! 结果:")
            # 将对象转换为字典以便打印
            result_dict = {
                "paper_id": result.paper_id,
                "summary": result.summary,
                "key_findings": result.key_findings,
                "contributions": result.contributions,
                "methodology": result.methodology,
                "limitations": result.limitations,
                "future_work": result.future_work,
                "keywords": result.keywords
            }
            # 美化打印JSON
            print(json.dumps(result_dict, ensure_ascii=False, indent=2))
        else:
            print("分析失败，未返回结果")
    
    except Exception as e:
        print(f"测试过程中发生错误: {e}")

async def main():
    """主函数"""
    await test_analyze_pdf()

if __name__ == "__main__":
    asyncio.run(main()) 