#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
声音复刻功能测试脚本
"""

import os
import sys
import time
import json
import hmac
import hashlib
import base64
from urllib.parse import urlparse, urlunparse, urlencode
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 支持脚本直接运行：将当前目录加入模块搜索路径
sys.path.insert(0, os.path.dirname(__file__))

# 兼容导入：优先使用包内导入，失败则使用本地导入
try:
    from app.services.ali_voice.voice_clone.voice_manager import VoiceManager
    from app.services.ali_voice.voice_clone.voice_clone import CosyVoiceClone
except Exception:
    import voice_manager
    import voice_clone
    VoiceManager = voice_manager.VoiceManager
    CosyVoiceClone = voice_clone.CosyVoiceClone


def _oss_generate_presigned_get_url(url: str, ak_id: str, ak_secret: str, expires_in: int = 3600) -> str:
    """为阿里云OSS对象生成GET预签名URL（简化版，不含自定义头）。
    参数:
    - url: 形如 https://<bucket>.<endpoint>/<object_key>
    - ak_id/ak_secret: 访问凭证
    - expires_in: 链接有效期秒数
    返回: 带OSSAccessKeyId、Expires、Signature查询参数的URL
    """
    parsed = urlparse(url)
    host = parsed.netloc  # <bucket>.<endpoint>
    path = parsed.path or '/'
    if '.' not in host:
        raise ValueError('无法从URL解析出bucket与endpoint')
    bucket = host.split('.')[0]
    # 过期时间戳（秒）
    expires = int(time.time()) + max(60, int(expires_in))
    # CanonicalResource: /<bucket>/<object_key>
    canonical_resource = f"/{bucket}{path}"
    # 构造待签名字符串: VERB + "\n" + Content-MD5 + "\n" + Content-Type + "\n" + Expires + "\n" + CanonicalizedOSSHeaders + CanonicalizedResource
    string_to_sign = f"GET\n\n\n{expires}\n{canonical_resource}"
    signature = base64.b64encode(hmac.new(ak_secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1).digest()).decode('utf-8')
    query = {
        'OSSAccessKeyId': ak_id,
        'Expires': str(expires),
        'Signature': signature,
    }
    new_query = urlencode(query)
    presigned = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', new_query, ''))
    return presigned


def _maybe_presign_oss_url(url: str) -> str:
    """如果提供的是OSS未签名URL且环境变量提供了AK信息，则自动生成预签名URL。"""
    if not url:
        return url
    if ('Signature=' in url) or ('X-Amz-Signature' in url) or ('Expires=' in url and 'Signature=' in url):
        return url  # 已带签名
    # 仅对典型的阿里OSS域名进行处理
    parsed = urlparse(url)
    if not parsed.netloc or '.aliyuncs.com' not in parsed.netloc:
        return url
    ak_id = os.getenv('ALIYUN_AK_ID') or os.getenv('ALIYUN_ACCESS_KEY_ID')
    ak_secret = os.getenv('ALIYUN_AK_SECRET') or os.getenv('ALIYUN_ACCESS_KEY_SECRET')
    if not (ak_id and ak_secret):
        return url
    try:
        presigned = _oss_generate_presigned_get_url(url, ak_id, ak_secret, expires_in=3600)
        print('已为OSS对象生成预签名URL（有效期1小时）。')
        return presigned
    except Exception as e:
        print(f"⚠️  生成预签名URL失败，将继续使用原URL: {e}")
        return url


def _check_url_accessible(url: str) -> bool:
    """尝试检查URL是否可访问（返回200或206）。优先使用requests，其次使用urllib。"""
    if not url:
        return False
    try:
        import requests  # 项目已使用requests
        try:
            r = requests.head(url, timeout=5, allow_redirects=True)
            if r.status_code in (200, 206):
                return True
            else:
                print(f"[debug] HEAD 检查状态码: {r.status_code}")
        except Exception as e:
            print(f"[debug] HEAD 请求异常: {e}")
        try:
            r = requests.get(url, stream=True, timeout=8)
            ok = r.status_code in (200, 206)
            if not ok:
                print(f"[debug] GET 检查状态码: {r.status_code}")
            return ok
        except Exception as e:
            print(f"[debug] GET 请求异常: {e}")
            return False
    except Exception:
        # 退回urllib
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=8) as resp:
                return resp.status in (200, 206)
        except Exception as e:
            print(f"[debug] urllib 请求异常: {e}")
            return False


def get_audio_url() -> str:
    """获取用于声音复刻的音频URL，优先读取环境变量，其次读取本地配置文件，最后回退到占位符。"""
    # 1) 环境变量覆盖（支持两种变量名）
    env_url = os.getenv('VOICE_CLONE_AUDIO_URL') or os.getenv('ALIYUN_CLONE_AUDIO_URL')
    if env_url:
        return _maybe_presign_oss_url(env_url)

    # 2) 从本地配置文件读取（若已有示例/历史条目）
    config_path = os.path.join(os.path.dirname(__file__), 'voice_clone_config.json')
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            voices = cfg.get('voices') or []
            if voices and isinstance(voices, list):
                url = voices[0].get('audio_url')
                if url:
                    return _maybe_presign_oss_url(url)
    except Exception as e:
        print(f"⚠️  读取配置文件失败，将使用占位URL: {e}")

    # 3) 回退到占位URL（通常为私有OSS会导致403，需要用户替换）
    return _maybe_presign_oss_url("https://voice-to-clone.oss-cn-shenzhen.aliyuncs.com/voice-clone/to_clone_dtf1.mp3?Expires=1758597895&OSSAccessKeyId=TMP.3KoZbesQHqiwBGWH1rbPeTfXtxUKv6LzSZbbchFWWeENUkpWgFW2rSdztZWhpJNHBWLHFG5JV5ACMy1ryFi1tV3te1qvav&Signature=N2S8eKXC33g5E78BJfV1mkoTNj0%3D")


def test_voice_clone():
    """测试声音复刻功能"""
    print("=== 声音复刻功能测试 ===\n")
    
    # 初始化管理器
    try:
        voice_manager_inst = VoiceManager()
        print("✅ VoiceManager 初始化成功")
    except Exception as e:
        print(f"❌ VoiceManager 初始化失败: {e}")
        return False
    
    # 获取测试用的音频URL
    test_audio_url = get_audio_url()
    # 立即打印解析到的URL，便于定位问题
    print(f"解析到的音频URL: {test_audio_url}")
    # 云端限制：prefix 不得超过 10 个字符，这里使用 'tv' + 8位时间戳尾数，长度=10
    test_voice_prefix = f"tv{int(time.time()) % 100000000:08d}"
    test_description = "测试声音复刻功能"
    
    # 简单检查：若URL看起来不是预签名，提醒用户
    if 'Signature=' not in test_audio_url and 'X-Amz-Signature' not in test_audio_url and 'Expires=' not in test_audio_url:
        print("⚠️  当前音频URL可能为未签名的私有OSS地址，若返回403请提供预签名URL或公开可访问的音频地址。")
    
    # 可达性预检
    if not _check_url_accessible(test_audio_url):
        print("❌ 音频URL不可访问（可能403/404）。请设置 VOICE_CLONE_AUDIO_URL 为可公开访问或带签名的URL 后重试。")
        return False
    
    print(f"测试参数:")
    print(f"  音频URL: {test_audio_url}")
    print(f"  声音前缀: {test_voice_prefix}")
    print(f"  描述: {test_description}\n")
    
    # 1. 测试声音复刻
    print("1. 开始声音复刻测试...")
    voice_id = voice_manager_inst.clone_and_register(
        voice_prefix=test_voice_prefix,
        audio_url=test_audio_url,
        description=test_description
    )
    
    if voice_id:
        print(f"✅ 声音复刻成功，voice_id: {voice_id}\n")
    else:
        print("❌ 声音复刻失败\n")
        return False
    
    # 2. 测试本地声音列表
    print("2. 查看本地声音列表...")
    local_voices = voice_manager_inst.list_local_voices()
    print(f"本地注册的声音数量: {len(local_voices)}")
    for voice in local_voices:
        print(f"  - {voice['voice_id']} ({voice['prefix']}) - {voice['description']}")
    print()
    
    # 3. 测试语音合成
    print("3. 测试语音合成...")
    test_text = "这是一个声音复刻测试，请检查音质是否符合预期。"
    output_file = f"test_synthesis_{int(time.time())}.mp3"
    
    synthesis_success = voice_manager_inst.test_voice_synthesis(
        voice_id=voice_id,
        test_text=test_text,
        output_file=output_file
    )
    
    if synthesis_success:
        print(f"✅ 语音合成成功，输出文件: {output_file}\n")
    else:
        print("❌ 语音合成失败\n")
    
    # 4. 测试获取声音信息
    print("4. 测试获取声音信息...")
    voice_info = voice_manager_inst.get_voice_by_id(voice_id)
    if voice_info:
        print(f"✅ 声音信息获取成功:")
        print(f"  Voice ID: {voice_info['voice_id']}")
        print(f"  前缀: {voice_info['prefix']}")
        print(f"  状态: {voice_info['status']}")
        print(f"  创建时间: {voice_info['created_at']}")
        print()
    else:
        print("❌ 声音信息获取失败\n")
    
    # 5. 清理测试数据（在非交互环境下默认保留，防止阻塞）
    print("5. 清理测试数据...")
    if sys.stdin.isatty():
        user_input = input("是否删除刚创建的测试声音？(y/n): ").lower().strip()
    else:
        user_input = 'n'
        print("非交互环境检测到，默认保留测试声音（设置环境变量或手动删除）。")
    
    if user_input == 'y':
        clone_client = CosyVoiceClone()
        result = clone_client.delete_voice(voice_id)
        
        if result.get('success'):
            print(f"✅ 测试声音删除成功: {voice_id}")
            
            # 从本地配置中移除
            voice_manager_inst.voices_config['voices'] = [
                v for v in voice_manager_inst.voices_config['voices'] 
                if v['voice_id'] != voice_id
            ]
            voice_manager_inst._save_config()
            print("✅ 本地配置已更新")
        else:
            print(f"❌ 测试声音删除失败: {result.get('message', '未知错误')}")
    else:
        print("⚠️  测试声音已保留，请手动管理")
    
    print("\n=== 测试完成 ===")
    return True


def test_environment():
    """测试环境配置"""
    print("=== 环境配置检查 ===\n")
    
    # 检查API密钥
    api_key = os.getenv('ALIYUN_COSYVOICE_API_KEY')
    if api_key:
        print(f"✅ ALIYUN_COSYVOICE_API_KEY: {api_key[:10]}...{api_key[-4:]}")
    else:
        print("❌ ALIYUN_COSYVOICE_API_KEY 未设置")
        return False
    
    # 检查其他相关配置
    oss_bucket = os.getenv('OSS_BUCKET')
    oss_endpoint = os.getenv('OSS_ENDPOINT')
    
    print(f"OSS_BUCKET: {oss_bucket or '未设置'}")
    print(f"OSS_ENDPOINT: {oss_endpoint or '未设置'}")
    
    # 测试CosyVoiceClone初始化
    try:
        clone_client = CosyVoiceClone()
        print("✅ CosyVoiceClone 初始化成功")
    except Exception as e:
        print(f"❌ CosyVoiceClone 初始化失败: {e}")
        return False
    
    print()
    return True


def main():
    """主函数"""
    print("声音复刻功能测试工具\n")
    
    # 环境检查
    if not test_environment():
        print("环境配置检查失败，请检查配置后重试")
        return
    
    # 功能测试
    print("开始功能测试...\n")
    
    try:
        success = test_voice_clone()
        if success:
            print("🎉 所有测试通过！")
        else:
            print("❌ 测试过程中出现错误")
    except KeyboardInterrupt:
        print("\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"❌ 测试过程中发生异常: {e}")


if __name__ == "__main__":
    main()