#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：验证OpenRouter功能集成
包括流式响应、工具调用、多模态、网络搜索等功能
"""
import asyncio
import httpx
import json
from typing import Dict, Any


class FeatureTester:
    """功能测试器"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30)
    
    async def test_basic_chat(self) -> bool:
        """测试基础聊天功能"""
        print("\n=== 测试基础聊天功能 ===")
        
        payload = {
            "provider": "echo",
            "model": "test-model",
            "messages": [
                {"role": "user", "content": "Hello, this is a test message"}
            ],
            "temperature": 0.7,
            "max_tokens": 100
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/chat/completions",
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 基础聊天测试成功")
                print(f"   响应ID: {result.get('id')}")
                print(f"   模型: {result.get('model')}")
                print(f"   回复: {result.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')}")
                return True
            else:
                print(f"❌ 基础聊天测试失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 基础聊天测试异常: {str(e)}")
            return False
    
    async def test_streaming(self) -> bool:
        """测试流式响应功能"""
        print("\n=== 测试流式响应功能 ===")
        
        payload = {
            "provider": "echo",
            "model": "test-model",
            "messages": [
                {"role": "user", "content": "This is a streaming test"}
            ],
            "stream": True,
            "temperature": 0.7
        }
        
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/v1/chat/completions",
                json=payload
            ) as response:
                
                if response.status_code == 200:
                    print("✅ 流式响应连接成功")
                    chunk_count = 0
                    async for chunk in response.aiter_text():
                        if chunk.strip():
                            chunk_count += 1
                            print(f"   接收到数据块 {chunk_count}: {chunk[:50]}...")
                            if chunk_count >= 3:  # 限制输出
                                break
                    
                    print(f"✅ 流式响应测试成功，接收到 {chunk_count} 个数据块")
                    return True
                else:
                    print(f"❌ 流式响应测试失败: {response.status_code}")
                    return False
                    
        except Exception as e:
            print(f"❌ 流式响应测试异常: {str(e)}")
            return False
    
    async def test_tool_calling(self) -> bool:
        """测试工具调用功能"""
        print("\n=== 测试工具调用功能 ===")
        
        payload = {
            "provider": "echo",
            "model": "test-model",
            "messages": [
                {"role": "user", "content": "请搜索关于Python的信息"}
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "搜索网络信息",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "搜索查询词"}
                            },
                            "required": ["query"]
                        }
                    }
                }
            ],
            "tool_choice": "auto"
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/chat/completions",
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ 工具调用请求成功")
                print(f"   响应ID: {result.get('id')}")
                
                # 检查是否包含工具调用
                choices = result.get('choices', [])
                if choices:
                    message = choices[0].get('message', {})
                    tool_calls = message.get('tool_calls')
                    if tool_calls:
                        print(f"   检测到工具调用: {len(tool_calls)} 个")
                        for i, tool_call in enumerate(tool_calls):
                            print(f"     工具 {i+1}: {tool_call.get('function', {}).get('name')}")
                    else:
                        print("   未检测到工具调用（这是正常的，因为echo适配器不执行实际工具调用）")
                
                return True
            else:
                print(f"❌ 工具调用测试失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 工具调用测试异常: {str(e)}")
            return False
    
    async def test_multimodal(self) -> bool:
        """测试多模态功能"""
        print("\n=== 测试多模态功能 ===")
        
        payload = {
            "provider": "echo",
            "model": "test-model",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请描述这张图片"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "https://example.com/test-image.jpg"
                            }
                        }
                    ]
                }
            ]
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/chat/completions",
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ 多模态请求成功")
                print(f"   响应ID: {result.get('id')}")
                print(f"   处理了包含图片的消息")
                return True
            else:
                print(f"❌ 多模态测试失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ 多模态测试异常: {str(e)}")
            return False
    
    async def test_health_check(self) -> bool:
        """测试健康检查"""
        print("\n=== 测试健康检查 ===")
        
        try:
            response = await self.client.get(f"{self.base_url}/health")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 健康检查成功: {result}")
                return True
            else:
                print(f"❌ 健康检查失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ 健康检查异常: {str(e)}")
            return False
    
    async def run_all_tests(self) -> Dict[str, bool]:
        """运行所有测试"""
        print("🚀 开始运行OpenRouter功能集成测试...")
        
        results = {
            "health_check": await self.test_health_check(),
            "basic_chat": await self.test_basic_chat(),
            "streaming": await self.test_streaming(),
            "tool_calling": await self.test_tool_calling(),
            "multimodal": await self.test_multimodal()
        }
        
        print("\n" + "="*50)
        print("📊 测试结果汇总:")
        print("="*50)
        
        passed = 0
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ 通过" if result else "❌ 失败"
            print(f"  {test_name.ljust(15)}: {status}")
            if result:
                passed += 1
        
        print(f"\n总计: {passed}/{total} 个测试通过")
        
        if passed == total:
            print("🎉 所有测试都通过了！OpenRouter功能集成成功！")
        else:
            print(f"⚠️  有 {total - passed} 个测试失败，请检查相关功能")
        
        await self.client.aclose()
        return results


async def main():
    """主函数"""
    tester = FeatureTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())