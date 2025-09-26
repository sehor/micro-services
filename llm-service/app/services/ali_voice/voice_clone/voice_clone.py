import os
from typing import Optional, Dict, Any
import dashscope
from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer
from dotenv import load_dotenv
import logging
import requests
from urllib.parse import urlparse

load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

class CosyVoiceClone:
    """阿里云CosyVoice声音复刻客户端"""
    
    def __init__(self, api_key=None):
        """初始化客户端"""
        logger.info("初始化CosyVoiceClone客户端...")
        self.api_key = api_key or os.getenv('ALIYUN_COSYVOICE_API_KEY')
        if not self.api_key:
            logger.error("缺少API密钥")
            raise ValueError("缺少API密钥，请设置ALIYUN_COSYVOICE_API_KEY环境变量")
        
        logger.info(f"API密钥已配置，长度: {len(self.api_key)}")
        
        # 设置DashScope配置（不设置base_http_api_url，使用默认）
        dashscope.api_key = self.api_key
        
        # 初始化服务
        self.voice_service = VoiceEnrollmentService()
        self.target_model = "cosyvoice-v2"
        logger.info(f"使用模型: {self.target_model}")
    
    def _validate_audio_url(self, audio_url):
        """验证音频URL的可访问性"""
        logger.info(f"开始验证音频URL: {audio_url}")
        
        # 解析URL
        parsed_url = urlparse(audio_url)
        logger.info(f"URL解析结果 - scheme: {parsed_url.scheme}, netloc: {parsed_url.netloc}, path: {parsed_url.path}")
        
        # 检查URL格式
        if not parsed_url.scheme or not parsed_url.netloc:
            logger.error(f"URL格式无效: {audio_url}")
            return False, "URL格式无效"
        
        try:
            # 发送HEAD请求检查URL可访问性
            logger.info("发送HEAD请求检查URL可访问性...")
            response = requests.head(audio_url, timeout=10, allow_redirects=True)
            logger.info(f"HEAD请求响应 - 状态码: {response.status_code}")
            logger.info(f"响应头: {dict(response.headers)}")
            
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                content_length = response.headers.get('content-length', 'unknown')
                logger.info(f"URL可访问 - Content-Type: {content_type}, Content-Length: {content_length}")
                return True, "URL可访问"
            else:
                logger.error(f"URL不可访问 - 状态码: {response.status_code}")
                return False, f"HTTP状态码: {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            logger.error(f"URL验证失败: {str(e)}")
            return False, f"请求异常: {str(e)}"
    
    def clone_voice(self, audio_url, voice_prefix, timeout=300):
        """复刻声音"""
        logger.info(f"=== 开始声音复刻 ===")
        logger.info(f"参数 - audio_url: {audio_url}")
        logger.info(f"参数 - voice_prefix: {voice_prefix}")
        logger.info(f"参数 - timeout: {timeout}")
        
        try:
            # 验证音频URL
            is_valid, validation_msg = self._validate_audio_url(audio_url)
            logger.info(f"URL验证结果: {is_valid}, 消息: {validation_msg}")
            
            if not is_valid:
                logger.warning(f"URL验证失败，但继续尝试API调用: {validation_msg}")
            
            # 调用阿里云API
            logger.info("调用阿里云VoiceEnrollmentService.create_voice...")
            logger.info(f"API参数 - target_model: {self.target_model}")
            logger.info(f"API参数 - prefix: {voice_prefix}")
            logger.info(f"API参数 - url: {audio_url}")
            
            voice_id = self.voice_service.create_voice(
                target_model=self.target_model,
                prefix=voice_prefix,
                url=audio_url
            )
            
            request_id = self.voice_service.get_last_request_id()
            logger.info(f"API调用成功 - requestId: {request_id}")
            logger.info(f"API调用成功 - voice_id: {voice_id}")
            
            print(f"requestId: {request_id}")
            print(f"your voice id is {voice_id}")
            
            logger.info(f"=== 声音复刻成功 ===")
            return {
                'success': True,
                'voice_id': voice_id,
                'request_id': request_id,
                'message': '声音复刻成功'
            }
            
        except Exception as e:
            logger.error(f"声音复刻API调用失败: {str(e)}")
            logger.error(f"异常类型: {type(e).__name__}")
            logger.error(f"=== 声音复刻失败 ===")
            print(f"声音复刻失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': '声音复刻失败'
            }
    
    def list_voices(self, voice_prefix: str, page_index: int = 1, page_size: int = 10) -> Dict[str, Any]:
        """查询声音列表
        
        注意：DashScope SDK暂不支持直接查询声音列表，此方法返回空列表
        建议使用本地配置文件管理复刻的声音
        
        Args:
            voice_prefix: 声音前缀
            page_index: 页码，从1开始
            page_size: 每页大小
            
        Returns:
            声音列表字典
        """
        print(f"注意：DashScope SDK暂不支持查询声音列表功能")
        print(f"建议使用VoiceManager的本地配置管理功能")
        
        # 返回兼容格式的空结果
        return {
            'Code': '20000000',
            'Message': 'SUCCESS',
            'TotalCount': 0,
            'PageIndex': page_index,
            'PageSize': page_size,
            'Voices': [],
            'RequestId': None
        }
    
    def synthesize_speech(self, text, voice_id, output_format="wav"):
        """使用指定声音进行语音合成"""
        try:
            synthesizer = SpeechSynthesizer(
                model=self.target_model,
                voice=voice_id
            )
            
            audio_data = synthesizer.call(text)
            print(f"requestId: {synthesizer.get_last_request_id()}")
            print(f"audio_data type: {type(audio_data)}")
            
            # 检查audio_data是否为有效的字节数据
            if audio_data is not None and isinstance(audio_data, bytes) and len(audio_data) > 0:
                print(f"语音合成成功，音频大小: {len(audio_data)} 字节")
                return audio_data
            else:
                print(f"语音合成返回无效数据: {audio_data}")
                return None
                
        except Exception as e:
            print(f"语音合成失败: {e}")
            return None
    
    def delete_voice(self, voice_id):
        """删除指定的复刻声音"""
        try:
            # 使用VoiceEnrollmentService删除声音
            result = self.voice_service.delete_voice(
                voice_id=voice_id
            )
            
            request_id = self.voice_service.get_last_request_id()
            print(f"删除声音请求ID: {request_id}")
            
            return {
                'success': True,
                'request_id': request_id,
                'message': f'声音 {voice_id} 删除成功'
            }
            
        except Exception as e:
            print(f"删除声音失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'删除声音 {voice_id} 失败'
            }