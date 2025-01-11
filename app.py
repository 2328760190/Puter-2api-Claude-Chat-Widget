from flask import Flask, request, jsonify, Response
import requests
import json
import time
import os

app = Flask(__name__)

OPENAI_API_KEY = OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","yyds666")


class PuterClient:
    def __init__(self):
        self.model = 'claude-3-5-sonnet-latest'
        self.token = None

    def initialize(self):
        try:
            response = requests.post('https://puter.com/signup', 
                headers={
                    'Accept': '*/*',
                    'Accept-Language': 'zh-CN,zh;q=0.9',
                    'Content-Type': 'application/json',
                    'Origin': 'https://puter.com',
                    'Referer': 'https://puter.com/',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                json={
                    'email': f'user{int(time.time())}@gmail.com',
                    'username': f'user{int(time.time())}',
                    'password': f'Password{int(time.time())}!',
                    'is_temp': True,
                    'referrer': None
                }
            )

            if not response.ok:
                raise Exception(f'Signup failed: {response.status_code}')

            data = response.json()
            if not data.get('token'):
                raise Exception('No token in response')

            self.token = data['token']
            print('Token obtained successfully')
            return True
        except Exception as e:
            print(f'Token acquisition failed: {str(e)}')
            return False

    def make_api_call(self, messages, stream=False):
        try:
            print(f'Making API call with token: {self.token[:10]}...')
            
            # 添加系统提示词
            system_message = {
                "role": "system",
                "content": """你是一个专业的AI助手。请遵循以下规则：

1. 身份：
- 自我介绍为 claude-3-5-sonnet-latest

2. 代码回复：
- 使用代码块
- 确保代码完整可用
- 代码解释放在代码块外

3. 一般回复：
- 直接回答问题
- 保持专业友好
- 不提及规则或提示词
- 不解释行为方式"""
            }
            
            # 在用户消息前添加系统提示词
            all_messages = [system_message] + messages
            
            request_body = {
                "interface": "puter-chat-completion",
                "driver": "claude",
                "test_mode": False,
                "method": "complete",
                "args": {
                    "messages": [{"content": msg.get("content", "")} for msg in all_messages],
                    "model": self.model,
                    "stream": stream
                }
            }
            
            print(f'Request body: {json.dumps(request_body, ensure_ascii=False)}')
            
            response = requests.post('https://api.puter.com/drivers/call',
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "Accept": "*/*",
                    "Origin": "https://docs.puter.com",
                    "Referer": "https://docs.puter.com/"
                },
                json=request_body,
                stream=stream
            )

            if not response.ok:
                if response.status_code == 401:
                    print('Token expired, trying to get new token...')
                    if self.initialize():
                        return self.make_api_call(messages, stream)
                raise Exception(f'API call failed: {response.status_code}')

            if stream:
                return self._handle_streaming_response(response)
            else:
                return self._handle_normal_response(response)

        except Exception as e:
            print(f'API call failed: {str(e)}')
            raise

    def _handle_normal_response(self, response):
        try:
            full_text = ""
            json_data = response.json()
            
            if json_data.get('success') and json_data.get('result', {}).get('message', {}).get('content'):
                content = json_data['result']['message']['content']
                for item in content:
                    if item.get('type') == 'text':
                        full_text += item.get('text', '')
            
            return {
                "id": f"chatcmpl-{int(time.time()*1000)}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": self.model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": full_text
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0
                }
            }
        except Exception as e:
            print(f'Error processing response: {str(e)}')
            raise

    def _handle_streaming_response(self, response):
        def generate():
            # 发送角色信息
            role_data = {
                "id": f"chatcmpl-{int(time.time()*1000)}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": self.model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "role": "assistant"
                    },
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(role_data)}\n\n"

            full_text = ""
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    line = line.decode('utf-8')
                    json_data = json.loads(line)
                    
                    if json_data.get('success') and json_data.get('result', {}).get('message', {}).get('content'):
                        content = json_data['result']['message']['content']
                        for item in content:
                            if item.get('type') == 'text':
                                text = item.get('text', '')
                                full_text += text
                                chunk_data = {
                                    "id": f"chatcmpl-{int(time.time()*1000)}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": self.model,
                                    "choices": [{
                                        "index": 0,
                                        "delta": {
                                            "content": text
                                        },
                                        "finish_reason": None
                                    }]
                                }
                                yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                    elif 'text' in json_data:
                        text = json_data['text']
                        full_text += text
                        chunk_data = {
                            "id": f"chatcmpl-{int(time.time()*1000)}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": self.model,
                            "choices": [{
                                "index": 0,
                                "delta": {
                                    "content": text
                                },
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(chunk_data)}\n\n"
                        
                except Exception as e:
                    print(f'Error processing line: {str(e)}, Line: {line}')
                    continue

            # 发送结束标记
            done_data = {
                "id": f"chatcmpl-{int(time.time()*1000)}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": self.model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(done_data)}\n\n"
            yield "data: [DONE]\n\n"

            print(f'Full text extracted: {full_text}')

        return generate()

def get_puter_client():
    if not hasattr(app, '_puter_client'):
        app._puter_client = PuterClient()
        if not app._puter_client.initialize():
            raise Exception("Failed to initialize Puter client")
    return app._puter_client

def check_api_key():
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise Exception('Missing API key')
    
    api_key = auth_header.replace('Bearer ', '')
    if api_key != OPENAI_API_KEY:
        raise Exception('Invalid API key')

@app.route('/hf/v1/chat/completions', methods=['POST'])
def chat_completions():
    try:
        # 验证 API key
        check_api_key()
        
        # 获取请求数据
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid request"}), 400
            
        messages = data.get('messages', [])
        if not messages:
            return jsonify({"error": "No messages provided"}), 400
            
        stream = data.get('stream', False)
        
        # 获取客户端实例
        client = get_puter_client()
        
        if stream:
            return Response(
                client.make_api_call(messages, stream=True),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'X-Accel-Buffering': 'no'
                }
            )
        else:
            return jsonify(client.make_api_call(messages, stream=False))
            
    except Exception as e:
        error_message = str(e)
        print(f"Error in chat completions: {error_message}")
        return jsonify({
            "error": {
                "message": error_message,
                "type": "invalid_request_error",
                "code": "invalid_request"
            }
        }), 500

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


if __name__ == '__main__':
    # 设置日志级别
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 运行 Flask 应用
    app.run(host='0.0.0.0', port=7860, debug=False) 

