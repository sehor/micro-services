# -*- coding: utf-8 -*-
"""
语音复刻与合成路由。
提供：
- POST /api/v1/voice/clone       声音复刻（入参：audio_url, prefix；出参：voice_id）
- POST /api/v1/voice/synthesize  使用复刻声音合成音频（入参：voice_id, text, format；出参：音频字节流）
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Response
from app.schemas import VoiceCloneRequest, VoiceCloneResponse, VoiceSynthesizeRequest
from app.services.ali_voice.voice_clone.voice_clone import CosyVoiceClone
from app.services.ali_voice.voice_service import (
    clone_voice as svc_clone_voice,
    synthesize_speech as svc_synthesize_speech,
)

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

@router.post("/clone", response_model=VoiceCloneResponse)
async def clone_voice(request: VoiceCloneRequest):
    """声音复刻接口"""
    return await svc_clone_voice(request)
    logger.info(f"=== 声音复刻请求开始 ===")
    logger.info(f"请求参数 - prefix: {request.prefix}")
    logger.info(f"请求参数 - audio_url: {request.audio_url}")
    
    # 打印默认音频地址
    default_audio_url = os.getenv("ALIYUN_COSYVOICE_AUDIO_URL")
    logger.info(f"环境变量中的默认音频地址: {default_audio_url}")
    
    try:
        # 校验前缀长度
        if len(request.prefix) > 10:
            logger.error(f"前缀长度超限: {len(request.prefix)} > 10")
            raise HTTPException(status_code=400, detail="前缀长度不能超过10个字符")
        
        # 确定音频URL
        if request.audio_url:
            audio_url = request.audio_url
            logger.info(f"使用请求中的音频URL: {audio_url}")
        else:
            audio_url = default_audio_url
            logger.info(f"使用环境变量中的默认音频URL: {audio_url}")
            if not audio_url:
                logger.error("环境变量 ALIYUN_COSYVOICE_AUDIO_URL 未配置")
                raise HTTPException(status_code=400, detail="未提供音频URL且环境变量未配置")
        
        logger.info(f"最终使用的音频URL: {audio_url}")
        logger.info(f"音频URL长度: {len(audio_url)}")
        logger.info(f"音频URL是否以https开头: {audio_url.startswith('https://')}")
        
        # 初始化CosyVoiceClone客户端
        logger.info("初始化CosyVoiceClone客户端...")
        cosyvoice_client = CosyVoiceClone()
        
        # 调用声音复刻
        logger.info(f"调用clone_voice方法 - audio_url: {audio_url}, voice_prefix: {request.prefix}")
        result = cosyvoice_client.clone_voice(
            audio_url=audio_url,
            voice_prefix=request.prefix
        )
        
        logger.info(f"声音复刻API返回结果: {result}")
        logger.info(f"结果类型: {type(result)}")
        
        # 处理返回结果
        if isinstance(result, dict):
            if result.get('success'):
                voice_id = result.get('voice_id')
                logger.info(f"从结果字典中提取voice_id: {voice_id}")
            else:
                error_msg = result.get('error', '未知错误')
                logger.error(f"声音复刻失败: {error_msg}")
                raise HTTPException(status_code=500, detail=f"声音复刻失败: {error_msg}")
        else:
            # 如果直接返回字符串
            voice_id = result
            logger.info(f"直接使用返回的voice_id: {voice_id}")
        
        logger.info(f"最终voice_id: {voice_id}")
        logger.info(f"=== 声音复刻请求完成 ===")
        
        return VoiceCloneResponse(voice_id=voice_id)
        
    except HTTPException:
        logger.error("HTTPException 重新抛出")
        raise
    except Exception as e:
        logger.error(f"声音复刻失败: {str(e)}")
        logger.error(f"异常类型: {type(e).__name__}")
        logger.error(f"=== 声音复刻请求失败 ===")
        raise HTTPException(status_code=500, detail=f"声音复刻失败: {str(e)}")

@router.post("/synthesize")
def synthesize(payload: VoiceSynthesizeRequest):
    """语音合成接口：使用指定 voice_id 将文本合成为音频字节流。"""
    audio_bytes = svc_synthesize_speech(payload)
    media_type = "audio/wav"
    headers = {"Content-Disposition": f"attachment; filename=tts_output.{(payload.format or 'wav').lower()}"}
    return Response(content=audio_bytes, media_type=media_type, headers=headers)