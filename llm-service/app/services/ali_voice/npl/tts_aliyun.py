import http.client
import os
import urllib.request
import json
import time
from dotenv import load_dotenv
import urllib.parse  # 新增：用于 urlencode
import urllib.error  # 新增：用于捕获 HTTPError

load_dotenv()

class TtsHeader:
    def __init__(self, appkey, token):
        self.appkey = appkey
        self.token = token

    def tojson(self, e):
        return {'appkey': e.appkey, 'token': e.token}

class TtsContext:
    def __init__(self, device_id):
        self.device_id = device_id

    def tojson(self, e):
        return {'device_id': e.device_id}

class TtsRequest:
    def __init__(self, voice, sample_rate, format, text, speech_rate=-200, pitch_rate=0):
        self.voice = voice
        self.sample_rate = sample_rate
        self.format = format
        self.text = text
        self.speech_rate = speech_rate
        self.pitch_rate = pitch_rate

    def tojson(self, e):
        return {
            'voice': e.voice,
            'sample_rate': e.sample_rate,
            'format': e.format,
            'text': e.text,
            'speech_rate': e.speech_rate,
            'pitch_rate': e.pitch_rate
        }

class TtsPayload:
    def __init__(self, tts_request, enable_notify=False, notify_url=""):
        self.enable_notify = enable_notify
        self.notify_url = notify_url
        self.tts_request = tts_request

    def tojson(self, e):
        return {
            'enable_notify': e.enable_notify,
            'notify_url': e.notify_url,
            'tts_request': e.tts_request.tojson(e.tts_request)
        }

class TtsBody:
    def __init__(self, tts_header, tts_context, tts_payload):
        self.tts_header = tts_header
        self.tts_context = tts_context
        self.tts_payload = tts_payload

    def tojson(self, e):
        return {
            'header': e.tts_header.tojson(e.tts_header),
            'context': e.tts_context.tojson(e.tts_context),
            'payload': e.tts_payload.tojson(e.tts_payload)
        }

def request_long_tts(text, voice="xiaoyun", sample_rate=16000, format="wav", speech_rate=-200, pitch_rate=0):
    """
    发起长文本语音合成请求，并返回任务ID。

    Args:
        text (str): 要合成的文本。
        voice (str): 发音人。
        sample_rate (int): 音频采样率。
        format (str): 音频格式。
        speech_rate (int): 语速。
        pitch_rate (int): 语调。

    Returns:
        tuple: (task_id, request_id, error_message)
    """
    from .token_generator import generate_token
    app_key = os.getenv('ALIYUN_APPKEY')
    token = generate_token()

    if not app_key or not token:
        return None, None, "无法获取 AppKey 或 Token"

    host = 'nls-gateway.cn-shanghai.aliyuncs.com'
    url = f'https://{host}/rest/v1/tts/async'

    header = TtsHeader(app_key, token)
    context = TtsContext("novel-tts-device")
    request = TtsRequest(voice, sample_rate, format, text, speech_rate, pitch_rate)
    payload = TtsPayload(request)
    body_obj = TtsBody(header, context, payload)
    
    body_str = json.dumps(body_obj, default=body_obj.tojson)

    try:
        conn = http.client.HTTPSConnection(host)
        http_headers = {'Content-Type': 'application/json'}
        conn.request(method='POST', url=url, body=body_str, headers=http_headers)
        response = conn.getresponse()
        body = response.read()

        if response.status == 200:
            data = json.loads(body)
            if data.get('error_code') == 20000000:
                task_id = data.get('data', {}).get('task_id')
                request_id = data.get('request_id')
                return task_id, request_id, None
            else:
                return None, None, data.get('error_message', '未知错误')
        else:
            return None, None, f"请求失败: {response.status} {response.reason}"
    except Exception as e:
        return None, None, str(e)
    finally:
        if 'conn' in locals():
            conn.close()

def poll_for_result(task_id: str, request_id: str) -> str | None:
    '''
    轮询TTS任务状态，直到任务完成或失败，打印详细日志。

    Args:
        task_id (str): 要查询的任务ID。
        request_id (str): 创建任务时返回的请求ID。

    Returns:
        str | None: 成功时返回音频地址，否则返回 None。
    '''
    from .token_generator import generate_token
    app_key = os.getenv('ALIYUN_APPKEY')
    token = generate_token()

    if not app_key or not token:
        print("❌ [轮询初始化] 无法获取 AppKey 或 Token，请检查 .env 与 token 生成逻辑。")
        return None

    host = 'nls-gateway.cn-shanghai.aliyuncs.com'
    base_url = f'https://{host}/rest/v1/tts/async'

    query_params = {
        'appkey': app_key,
        'task_id': task_id,
        'token': token,
        'request_id': request_id
    }
    full_url = f"{base_url}?{urllib.parse.urlencode(query_params)}"

    def mask_token(t: str) -> str:
        if not t or len(t) <= 8:
            return "****"
        return f"{t[:4]}****{t[-4:]}"

    print("====== 开始轮询任务结果 ======")
    print(f"🔎 task_id: {task_id}")
    print(f"🔎 request_id: {request_id}")
    print(f"🔎 app_key: {app_key}")
    print(f"🔎 token: {mask_token(token)}")
    print(f"🔎 请求URL: {base_url}?{urllib.parse.urlencode({**query_params, 'token': mask_token(token)})}")

    max_attempts = 30
    interval_sec = 10

    for i in range(max_attempts):
        attempt_no = i + 1
        try:
            with urllib.request.urlopen(full_url) as resp:
                status = getattr(resp, "status", None)
                body_text = resp.read().decode('utf-8', errors='ignore')
                print(f"\n--- 第 {attempt_no}/{max_attempts} 次轮询 ---")
                print(f"HTTP 状态: {status}")
                print(f"响应原文: {body_text}")

                try:
                    data = json.loads(body_text)
                except json.JSONDecodeError as je:
                    print(f"❌ JSON 解析失败: {je}")
                    return None

                print("响应JSON(美化):")
                print(json.dumps(data, indent=2, ensure_ascii=False))

                error_code = data.get("error_code")
                error_message = data.get("error_message")

                # 优先处理服务端错误
                if error_code and error_code != 20000000:
                    print(f"❌ 合成失败，error_code={error_code}, error_message={error_message}")
                    if "418" in (error_message or ""):
                        print("👉 可能原因：引擎侧限流/不可用或参数组合不被支持。建议：")
                        print("   - 降低请求频率，过几分钟后重试")
                        print("   - 确认文本使用纯文本（当前若包含 SSML 可能引擎不支持）")
                        print("   - 缩短文本长度，排除文本内容触发风控/非法文本的影响")
                        print("   - 尝试临时换一个标准发音人验证环境（仅用于对比定位）")
                        print(f"   - 保存 request_id={data.get('request_id')} 以便向阿里云支持排查")
                    return None

                # data 可能为 null，这里要安全处理
                data_obj = data.get("data") or {}
                state = data_obj.get("state")
                progress = data_obj.get("progress")
                if state:
                    print(f"ℹ️ 状态: {state}  进度: {progress}")

                audio_address = data_obj.get("audio_address")
                if audio_address:
                    print(f"✅ 获取到音频地址: {audio_address}")
                    return audio_address

                print(f"⏳ 未完成，{interval_sec}s后继续轮询...")
                time.sleep(interval_sec)

        except urllib.error.HTTPError as he:
            err_body = he.read().decode('utf-8', errors='ignore')
            print(f"\n❌ HTTPError: {he.code} {he.reason}")
            print(f"错误响应体: {err_body}")
            return None
        except Exception as e:
            print(f"\n❌ 轮询异常: {repr(e)}")
            return None

    print("❌ 超过最大轮询次数仍未成功获取音频地址。")
    return None

def download_audio(audio_url, output_filename):
    """
    下载音频文件。

    Args:
        audio_url (str): 音频文件的URL。
        output_filename (str): 保存的文件名。

    Returns:
        bool: 是否下载成功。
    """
    try:
        urllib.request.urlretrieve(audio_url, output_filename)
        print(f"音频下载成功: {os.path.abspath(output_filename)}")
        return True
    except Exception as e:
        print(f"下载失败: {e}")
        return False

if __name__ == '__main__':
    # 这是一个示例，展示如何使用重构后的模块
    test_text = "这是一个使用重构后模块的测试。"
    print("开始长文本合成测试...")
    task_id, request_id, error = request_long_tts(test_text, voice="xiaoyun")

    if error:
        print(f"创建任务失败: {error}")
    else:
        print(f"任务创建成功: {task_id}")
        print("开始轮询结果...")
        audio_url = poll_for_result(task_id, request_id)
        if audio_url:
            print(f"获取到音频地址: {audio_url}")
            download_audio(audio_url, "main_test_output.wav")
        else:
            print("获取音频失败。")