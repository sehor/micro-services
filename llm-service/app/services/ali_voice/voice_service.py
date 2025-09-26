# -*- coding: utf-8 -*-
"""
语音复刻与合成业务服务：封装校验、远端调用、结果转换。
"""
import os
import logging
from fastapi import HTTPException
from app.schemas import VoiceCloneRequest, VoiceCloneResponse, VoiceSynthesizeRequest
from app.services.ali_voice.voice_clone.voice_clone import CosyVoiceClone

logger = logging.getLogger(__name__)


async def clone_voice(request: VoiceCloneRequest) -> VoiceCloneResponse:
    """声音复刻：校验入参，选择音频URL，调用远端并返回 voice_id。"""
    # 校验前缀长度
    if len(request.prefix) > 10:
        raise HTTPException(status_code=400, detail="前缀长度不能超过10个字符")

    # 确定音频URL
    audio_url = request.audio_url or os.getenv("ALIYUN_COSYVOICE_AUDIO_URL")
    if not audio_url:
        raise HTTPException(status_code=400, detail="未提供音频URL且环境变量未配置")

    try:
        client = CosyVoiceClone()
        result = client.clone_voice(audio_url=audio_url, voice_prefix=request.prefix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"声音复刻失败: {str(e)}")

    # 处理返回结果
    if isinstance(result, dict):
        if result.get("success"):
            voice_id = result.get("voice_id")
        else:
            error_msg = result.get("error", "未知错误")
            raise HTTPException(status_code=500, detail=f"声音复刻失败: {error_msg}")
    else:
        voice_id = result

    return VoiceCloneResponse(voice_id=voice_id)


def synthesize_speech(payload: VoiceSynthesizeRequest) -> bytes:
    """语音合成：校验参数并调用远端返回音频字节流。"""
    if not payload.voice_id:
        raise HTTPException(status_code=400, detail="voice_id 不能为空")
    if not payload.text:
        raise HTTPException(status_code=400, detail="text 不能为空")

    fmt = (payload.format or "wav").lower()
    allowed = {"wav"}
    if fmt not in allowed:
        raise HTTPException(status_code=400, detail=f"不支持的音频格式: {fmt}，当前仅支持: {', '.join(sorted(allowed))}")

    try:
        client = CosyVoiceClone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"初始化语音客户端失败: {e}")

    audio_bytes = client.synthesize_speech(text=payload.text, voice_id=payload.voice_id, output_format=fmt)
    if not audio_bytes or not isinstance(audio_bytes, (bytes, bytearray)):
        raise HTTPException(status_code=500, detail="语音合成失败或返回空数据")

    return audio_bytes