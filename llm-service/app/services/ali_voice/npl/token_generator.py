#!/usr/bin/env python
# coding=utf-8
import os
import time
import json
import datetime
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from dotenv import load_dotenv

# token缓存文件路径
TOKEN_CACHE_FILE = os.path.join(os.path.dirname(__file__), 'token_cache.json')

def load_cached_token():
    """从缓存文件加载token"""
    if not os.path.exists(TOKEN_CACHE_FILE):
        return None, None
    
    try:
        with open(TOKEN_CACHE_FILE, 'r') as f:
            cache = json.load(f)
            token = cache.get('token')
            expire_time = cache.get('expire_time')
            
            # 检查token是否已过期（提前5分钟认为过期）
            if expire_time:
                now = int(time.time())
                if now + 300 < expire_time:  # 提前5分钟更新
                    return token, expire_time
            
        return None, None
    except Exception as e:
        print(f"读取缓存token出错: {e}")
        return None, None

def save_token_to_cache(token, expire_time):
    """将token保存到缓存文件"""
    try:
        cache = {
            'token': token,
            'expire_time': expire_time
        }
        with open(TOKEN_CACHE_FILE, 'w') as f:
            json.dump(cache, f)
        print(f"Token已缓存，过期时间: {datetime.datetime.fromtimestamp(expire_time)}")
    except Exception as e:
        print(f"保存token到缓存出错: {e}")

def generate_token(force_new=False):
    """生成阿里云语音服务的token
    
    Args:
        force_new: 是否强制生成新token，忽略缓存
    
    Returns:
        str: 有效的token
    """
    # 如果不强制生成新token，先尝试从缓存加载
    if not force_new:
        token, expire_time = load_cached_token()
        if token:
            print(f"使用缓存的token，过期时间: {datetime.datetime.fromtimestamp(expire_time)}")
            return token
    
    # 加载环境变量
    load_dotenv()
    
    # 创建AcsClient实例
    client = AcsClient(
        os.getenv('ALIYUN_AK_ID'),
        os.getenv('ALIYUN_AK_SECRET'),
        "cn-shanghai"
    )

    # 创建request，并设置参数
    request = CommonRequest()
    request.set_method('POST')
    request.set_domain('nls-meta.cn-shanghai.aliyuncs.com')
    request.set_version('2019-02-28')
    request.set_action_name('CreateToken')

    try:
        response = client.do_action_with_exception(request)
        jss = json.loads(response)
        if 'Token' in jss and 'Id' in jss['Token']:
            token = jss['Token']['Id']
            expire_time = jss['Token']['ExpireTime']
            
            # 保存token到缓存
            save_token_to_cache(token, expire_time)
            
            return token
        else:
            print("获取token失败，响应中没有token信息")
            return None
    except Exception as e:
        print(f"生成token出错: {e}")
        return None

if __name__ == "__main__":
    token = generate_token()
    if token:
        print(f"当前可用token: {token}")
    else:
        print("获取token失败")