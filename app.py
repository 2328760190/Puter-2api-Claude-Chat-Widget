from flask import Flask, render_template, request, jsonify, Response
import requests
import json
import time
import os
from functools import wraps

app = Flask(__name__)

OPENAI_API_KEY = OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","yyds666")

# 确保静态文件目录存在
os.makedirs('static', exist_ok=True)

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

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/demo')
def demo():
    return render_template('example.html')

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# 创建 templates 目录
os.makedirs('templates', exist_ok=True)

# 创建 templates/chat.html
with open('templates/chat.html', 'w', encoding='utf-8') as f:
    f.write("""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Chat</title>
    <script src="https://lf26-cdn-tos.bytecdntp.com/cdn/expire-1-M/tailwindcss/2.2.19/tailwind.min.js"></script>
    <link href="https://lf26-cdn-tos.bytecdntp.com/cdn/expire-1-M/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <link href="https://fonts.loli.net/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <link href="https://lf26-cdn-tos.bytecdntp.com/cdn/expire-1-M/highlight.js/11.4.0/styles/github-dark.min.css" rel="stylesheet">
    <script src="https://lf26-cdn-tos.bytecdntp.com/cdn/expire-1-M/highlight.js/11.4.0/highlight.min.js"></script>
    <script src="https://lf26-cdn-tos.bytecdntp.com/cdn/expire-1-M/highlight.js/11.4.0/languages/xml.min.js"></script>
    <script src="https://lf26-cdn-tos.bytecdntp.com/cdn/expire-1-M/highlight.js/11.4.0/languages/css.min.js"></script>
    <script src="https://lf26-cdn-tos.bytecdntp.com/cdn/expire-1-M/highlight.js/11.4.0/languages/javascript.min.js"></script>
    <style>
        :root {
            --primary-color: #4F46E5;
            --primary-hover: #4338CA;
            --bg-color: #F9FAFB;
            --chat-bg: #ffffff;
            --user-msg-bg: #F3F4F6;
            --assistant-msg-bg: #EEF2FF;
            --border-color: #E5E7EB;
            --text-primary: #111827;
            --text-secondary: #6B7280;
        }
        
        body {
            background-color: var(--bg-color);
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            color: var(--text-primary);
        }
        
        .chat-container {
            max-width: 1000px;
            margin: 2rem auto;
            height: calc(100vh - 4rem);
            display: flex;
            flex-direction: column;
            background: var(--chat-bg);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            border-radius: 1rem;
            overflow: hidden;
        }
        
        .header {
            padding: 1.25rem;
            background: var(--primary-color);
            color: white;
            display: flex;
            align-items: center;
            gap: 0.75rem;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        
        .header-title {
            font-size: 1.25rem;
            font-weight: 600;
            letter-spacing: -0.025em;
        }
        
        .header-subtitle {
            font-size: 0.875rem;
            opacity: 0.9;
        }
        
        .messages-container {
            flex: 1;
            overflow-y: auto;
            padding: 1.5rem;
            scroll-behavior: smooth;
            background-image: 
                radial-gradient(circle at 100% 100%, var(--bg-color) 0.5rem, transparent 0.5rem),
                radial-gradient(circle at 0 100%, var(--bg-color) 0.5rem, transparent 0.5rem),
                radial-gradient(circle at 100% 0, var(--bg-color) 0.5rem, transparent 0.5rem),
                radial-gradient(circle at 0 0, var(--bg-color) 0.5rem, transparent 0.5rem);
        }
        
        .message {
            max-width: 85%;
            margin: 1rem 0;
            padding: 1rem 1.25rem;
            border-radius: 1rem;
            line-height: 1.5;
            position: relative;
            animation: messageSlide 0.3s ease-out;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
        }
        
        @keyframes messageSlide {
            from { 
                opacity: 0;
                transform: translateY(1rem);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .user-message {
            background: var(--user-msg-bg);
            margin-left: auto;
            border-bottom-right-radius: 0.25rem;
        }
        
        .assistant-message {
            background: var(--assistant-msg-bg);
            margin-right: auto;
            border-bottom-left-radius: 0.25rem;
        }
        
        .message::before {
            content: '';
            position: absolute;
            bottom: 0;
            width: 1rem;
            height: 1rem;
            background: inherit;
        }
        
        .user-message::before {
            right: -0.5rem;
            clip-path: polygon(0 0, 0% 100%, 100% 100%);
        }
        
        .assistant-message::before {
            left: -0.5rem;
            clip-path: polygon(100% 0, 0 100%, 100% 100%);
        }
        
        .typing-indicator {
            display: none;
            padding: 1rem;
            background: var(--assistant-msg-bg);
            border-radius: 1rem;
            margin: 0.5rem 0;
            max-width: 85%;
            margin-right: auto;
            animation: messageSlide 0.3s ease-out;
        }
        
        .typing-dots {
            display: flex;
            gap: 0.4rem;
            padding: 0.25rem 0;
        }
        
        .typing-dot {
            width: 0.5rem;
            height: 0.5rem;
            background: var(--primary-color);
            border-radius: 50%;
            opacity: 0.6;
            animation: dotPulse 1.5s infinite;
        }
        
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }
        
        @keyframes dotPulse {
            0%, 100% { transform: scale(1); opacity: 0.6; }
            50% { transform: scale(1.2); opacity: 1; }
        }
        
        .input-box {
            padding: 1.25rem;
            background: var(--chat-bg);
            border-top: 1px solid var(--border-color);
        }
        
        .input-container {
            display: flex;
            gap: 0.75rem;
            background: white;
            border: 2px solid var(--border-color);
            border-radius: 1rem;
            padding: 0.75rem;
            transition: all 0.3s ease;
        }
        
        .input-container:focus-within {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
        }
        
        #message-input {
            flex: 1;
            border: none;
            outline: none;
            padding: 0.25rem;
            font-size: 1rem;
            background: transparent;
            resize: none;
            min-height: 24px;
            max-height: 200px;
            line-height: 1.5;
        }
        
        .send-button {
            background: var(--primary-color);
            color: white;
            border: none;
            border-radius: 0.75rem;
            padding: 0.75rem 1.25rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            white-space: nowrap;
        }
        
        .send-button:hover {
            background: var(--primary-hover);
            transform: translateY(-1px);
        }
        
        .send-button:active {
            transform: translateY(0);
        }
        
        .send-button:disabled {
            background: var(--text-secondary);
            cursor: not-allowed;
            transform: none;
        }
        
        .send-button i {
            font-size: 0.875rem;
        }
        
        @media (max-width: 768px) {
            .chat-container {
                margin: 0;
                height: 100vh;
                border-radius: 0;
            }
            
            .message {
                max-width: 90%;
            }
            
            .send-button span {
                display: none;
            }
            
            .send-button {
                padding: 0.75rem;
            }
        }
        
        /* 代码块样式优化 */
        pre {
            background: #1E293B;
            color: #E2E8F0;
            padding: 1rem;
            border-radius: 0.5rem;
            overflow-x: auto;
            margin: 0.5rem 0;
            position: relative;
        }
        
        pre code {
            font-family: 'Fira Code', Consolas, Monaco, 'Andale Mono', monospace;
            font-size: 0.875rem;
            line-height: 1.5;
            tab-size: 4;
        }
        
        /* 代码块语言标签 */
        pre::before {
            content: attr(data-language);
            position: absolute;
            top: 0;
            right: 0;
            padding: 0.25rem 0.5rem;
            font-size: 0.75rem;
            background: #2D3748;
            color: #A0AEC0;
            border-bottom-left-radius: 0.25rem;
            border-top-right-radius: 0.5rem;
        }
        
        /* 行内代码样式 */
        code:not(pre code) {
            background: #F3F4F6;
            color: #DC2626;
            padding: 0.125rem 0.25rem;
            border-radius: 0.25rem;
            font-size: 0.875em;
        }
        
        /* 滚动条样式 */
        .messages-container::-webkit-scrollbar {
            width: 0.5rem;
        }
        
        .messages-container::-webkit-scrollbar-track {
            background: var(--bg-color);
        }
        
        .messages-container::-webkit-scrollbar-thumb {
            background: var(--border-color);
            border-radius: 0.25rem;
        }
        
        .messages-container::-webkit-scrollbar-thumb:hover {
            background: var(--text-secondary);
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="header">
            <i class="fas fa-robot text-2xl"></i>
            <div>
                <div class="header-title">Claude Chat</div>
                <div class="header-subtitle">AI Assistant</div>
            </div>
        </div>
        <div class="messages-container" id="messages"></div>
        <div class="typing-indicator" id="typing">
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        </div>
        <div class="input-box">
            <form id="chat-form">
                <div class="input-container">
                    <textarea id="message-input" 
                           placeholder="输入消息..." 
                           rows="1"
                           autocomplete="off"></textarea>
                    <button type="submit" class="send-button">
                        <i class="fas fa-paper-plane"></i>
                        <span>发送</span>
                    </button>
                </div>
            </form>
        </div>
    </div>

    <script>
        const messagesContainer = document.getElementById('messages');
        const typingIndicator = document.getElementById('typing');
        const chatForm = document.getElementById('chat-form');
        const messageInput = document.getElementById('message-input');
        const sendButton = chatForm.querySelector('button');
        const messages = [];

        function addMessage(content, isUser = false) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user-message' : 'assistant-message'}`;
            
            // 创建一个临时的 div 来安全地处理内容
            const tempDiv = document.createElement('div');
            
            // 首先处理代码块，使用自定义占位符
            let processedContent = content;
            const codeBlocks = [];
            processedContent = processedContent.replace(/```(\\w*)\\n([\\s\\S]*?)```/g, (match, language, code) => {
                const id = `code-block-${codeBlocks.length}`;
                codeBlocks.push({
                    id,
                    language: language.trim() || 'plaintext',
                    code: code.trim()
                });
                return id;
            });
            
            // 处理行内代码，使用自定义占位符
            const inlineCodes = [];
            processedContent = processedContent.replace(/`([^`]+)`/g, (match, code) => {
                const id = `inline-code-${inlineCodes.length}`;
                inlineCodes.push({
                    id,
                    code: code
                });
                return id;
            });
            
            // 安全地设置文本内容
            tempDiv.textContent = processedContent;
            let safeContent = tempDiv.textContent;
            
            // 还原代码块
            codeBlocks.forEach(({id, language, code}) => {
                const escapedCode = escapeHtml(code);
                safeContent = safeContent.replace(
                    id,
                    `<pre data-language="${language}"><code class="language-${language}">${escapedCode}</code></pre>`
                );
            });
            
            // 还原行内代码
            inlineCodes.forEach(({id, code}) => {
                const escapedCode = escapeHtml(code);
                safeContent = safeContent.replace(
                    id,
                    `<code>${escapedCode}</code>`
                );
            });
            
            messageDiv.innerHTML = safeContent;
            
            // 对新添加的代码块应用语法高亮
            messageDiv.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
            
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
            return messageDiv;
        }
        
        function escapeHtml(unsafe) {
            return unsafe
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        function showTyping(show = true) {
            typingIndicator.style.display = show ? 'block' : 'none';
            if (show) {
                typingIndicator.scrollIntoView({ behavior: 'smooth' });
            }
        }

        async function* readSSEResponse(response) {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const {value, done} = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, {stream: true});
                const lines = buffer.split('\\n');
                
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data === '[DONE]') {
                            yield {done: true};
                        } else {
                            try {
                                yield {data: JSON.parse(data)};
                            } catch (e) {
                                console.error('Error parsing JSON:', e);
                            }
                        }
                    }
                }
            }
        }

        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const message = messageInput.value.trim();
            if (!message) return;

            // 禁用输入和发送按钮
            messageInput.disabled = true;
            sendButton.disabled = true;
            messageInput.style.height = 'auto';

            // 添加用户消息
            addMessage(message, true);
            messages.push({ role: 'user', content: message });
            messageInput.value = '';

            try {
                showTyping(true);
                
                const response = await fetch('/v1/chat/completions', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer sk-looks-nb'
                    },
                    body: JSON.stringify({
                        model: 'claude-3-5-sonnet-latest',
                        messages: messages,
                        stream: true
                    })
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error?.message || 'Unknown error');
                }

                let assistantMessage = '';
                let currentMessageDiv = null;

                for await (const chunk of readSSEResponse(response)) {
                    if (chunk.done) break;
                    
                    const delta = chunk.data?.choices?.[0]?.delta;
                    if (delta?.content) {
                        assistantMessage += delta.content;
                        if (!currentMessageDiv) {
                            currentMessageDiv = addMessage(delta.content);
                        } else {
                            currentMessageDiv.innerHTML = assistantMessage;
                        }
                    }
                }

                if (assistantMessage) {
                    messages.push({ role: 'assistant', content: assistantMessage });
                }
            } catch (error) {
                showTyping(false);
                addMessage(`Error: ${error.message}`);
                console.error('Chat error:', error);
            } finally {
                // 重新启用输入和发送按钮
                messageInput.disabled = false;
                sendButton.disabled = false;
                showTyping(false);
                messageInput.focus();
            }
        });

        // 添加输入框回车发送功能
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                chatForm.dispatchEvent(new Event('submit'));
            }
        });

        // 自动聚焦输入框
        messageInput.focus();
    </script>
</body>
</html>
""")

if __name__ == '__main__':
    # 设置日志级别
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # 运行 Flask 应用
    app.run(host='0.0.0.0', port=7860, debug=False) 

