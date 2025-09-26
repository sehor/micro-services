import json
import os
import time
from typing import List, Dict, Any, Optional
# 尝试兼容包内/脚本直接运行两种导入方式
try:
    from .voice_clone import CosyVoiceClone
except ImportError:
    from voice_clone import CosyVoiceClone

class VoiceManager:
    """声音管理器，用于管理复刻的声音"""
    
    def __init__(self, config_file: str = "voice_clone_config.json"):
        """初始化声音管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = config_file
        self.clone_client = CosyVoiceClone()
        self.voices_config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
                return {"voices": []}
        return {"voices": []}
    
    def _save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.voices_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def clone_and_register(self, voice_prefix: str, audio_url: str, description: str = "") -> Optional[str]:
        """复刻声音并注册到本地配置
        
        Args:
            voice_prefix: 声音前缀
            audio_url: 音频URL
            description: 描述信息
            
        Returns:
            成功时返回voice_id，失败时返回None
        """
        try:
            # 调用复刻API
            result = self.clone_client.clone_voice(
                audio_url=audio_url,
                voice_prefix=voice_prefix
            )
            
            # 检查复刻结果
            if result.get('success'):
                voice_id = result.get('voice_id')
                request_id = result.get('request_id')
                
                # 保存到配置
                voice_info = {
                    'voice_id': voice_id,
                    'prefix': voice_prefix,
                    'audio_url': audio_url,
                    'description': description,
                    'request_id': request_id,
                    'created_at': int(time.time()),
                    'status': 'active'
                }
                
                self.voices_config['voices'].append(voice_info)
                self._save_config()
                
                print(f"声音复刻成功: {voice_id}")
                return voice_id
            else:
                error_msg = result.get('message', '未知错误')
                print(f"声音复刻失败: {error_msg}")
                return None

        except Exception as e:
            print(f"复刻声音时发生错误: {e}")
            return None
    
    def get_voice_by_id(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """根据voice_id获取声音信息"""
        for voice in self.voices_config["voices"]:
            if voice["voice_id"] == voice_id:
                return voice
        return None
    
    def delete_all_voices(self) -> bool:
        """删除所有注册的声音（阿里云上的和本地配置）"""
        try:
            success_count = 0
            total_count = len(self.voices_config["voices"])
            
            print(f"开始删除 {total_count} 个注册的声音...")
            
            # 删除阿里云上的声音
            for voice_info in self.voices_config["voices"]:
                voice_id = voice_info["voice_id"]
                print(f"正在删除声音: {voice_id}")
                
                result = self.clone_client.delete_voice(voice_id)
                if result.get('success'):
                    success_count += 1
                    print(f"✅ 删除成功: {voice_id}")
                else:
                    print(f"❌ 删除失败: {voice_id} - {result.get('message', '未知错误')}")
            
            # 清空本地配置
            self.voices_config["voices"] = []
            self._save_config()
            
            print(f"删除完成: {success_count}/{total_count} 个声音删除成功")
            print("本地配置已清空")
            
            return success_count == total_count
            
        except Exception as e:
            print(f"删除所有声音时发生错误: {e}")
            return False
    
    def list_local_voices(self) -> List[Dict[str, Any]]:
        """列出本地注册的声音"""
        return self.voices_config["voices"]
    
    def sync_with_remote(self, voice_prefix: str) -> bool:
        """与远程声音列表同步
        
        注意：由于DashScope SDK不支持查询声音列表，此方法仅更新本地状态
        
        Args:
            voice_prefix: 要同步的声音前缀
            
        Returns:
            是否同步成功
        """
        try:
            print(f"注意：DashScope SDK不支持远程声音列表查询")
            print(f"将所有匹配前缀的本地声音状态设为active")
            
            # 更新本地配置中的状态为active（假设都可用）
            updated = False
            for local_voice in self.voices_config["voices"]:
                if local_voice["prefix"] == voice_prefix:
                    local_voice["status"] = "active"
                    updated = True
            
            if updated:
                self._save_config()
                print(f"本地声音状态同步完成")
            
            return True
            
        except Exception as e:
            print(f"同步本地声音状态失败: {e}")
            return False
    
    def test_voice_synthesis(self, voice_id: str, test_text: str = "这是一个测试音频", output_file: str = "test_output.mp3") -> bool:
        """测试声音合成功能"""
        try:
            # 检查声音是否存在
            voice_info = self.get_voice_by_id(voice_id)
            if not voice_info:
                print(f"未找到声音: {voice_id}")
                return False
            
            print(f"测试声音合成: {voice_id}")
            
            # 调用语音合成
            audio_data = self.clone_client.synthesize_speech(
                text=test_text,
                voice_id=voice_id
            )
            
            if audio_data:
                # 保存测试音频
                with open(output_file, 'wb') as f:
                    f.write(audio_data)
                print(f"测试音频已保存: {output_file}")
                return True
            else:
                print("语音合成失败")
                return False
                
        except Exception as e:
            print(f"测试声音合成时发生错误: {e}")
            return False