#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试文件上传功能
"""

import requests
import json
import os

def test_file_upload():
    """测试文件上传到OpenRouter"""
    
    # 创建一个简单的测试文件
    test_content = "这是一个测试文档\n包含一些中文内容\n用于验证文件上传功能"
    test_file_path = "test_document.txt"
    
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    try:
        # 准备表单数据
        with open(test_file_path, 'rb') as f:
            files = {'files': (test_file_path, f, 'text/plain')}
            data = {
                'provider': 'openrouter',
                'model': 'anthropic/claude-3-haiku',
                'user_message': '请分析这个文档的内容',
                'temperature': '0.7',
                'max_tokens': '1024',
                'stream': 'false'
            }
            
            # 发送请求
            response = requests.post(
                'http://127.0.0.1:8000/api/v1/chat/completions/upload',
                files=files,
                data=data,
                timeout=30
            )
        
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n=== 成功响应 ===")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"\n=== 错误响应 ===")
            print(f"状态码: {response.status_code}")
            print(f"错误内容: {response.text}")
            
    except Exception as e:
        print(f"请求异常: {e}")
    finally:
        # 清理测试文件
        if os.path.exists(test_file_path):
            os.remove(test_file_path)

if __name__ == '__main__':
    test_file_upload()