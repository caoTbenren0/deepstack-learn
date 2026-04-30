import os
import json
import hashlib
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import openai
import uvicorn

app = FastAPI()

# 初始化 OpenAI 客户端（DeepSeek 兼容）
client = openai.OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1",
)

# 缓存字典：key -> html_content
cache = {}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>递归学习队列</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        #float-btn {
            position: absolute;
            z-index: 1000;
            display: none;
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 14px;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            white-space: nowrap;
        }
        #float-btn:hover { background: #2563eb; }
        .queue-item { transition: background 0.2s; }
        .queue-item:hover { background: #f3f4f6; }
        #content h2 { font-size: 1.5rem; font-weight: 600; margin: 1rem 0 0.5rem; }
        #content p { margin: 0.5rem 0; line-height: 1.6; }
        #content ul { list-style: disc; margin-left: 1.5rem; margin-top: 0.5rem; }
        #content pre { background: #1e293b; color: #e2e8f0; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; margin: 0.5rem 0; }
        #content code { background: #f1f5f9; padding: 0.2em 0.4em; border-radius: 0.25rem; font-size: 0.9em; }
        #content pre code { background: none; padding: 0; }
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <div class="flex h-screen overflow-hidden">
        <!-- 左侧学习区 -->
        <div class="flex-1 p-6 overflow-y-auto bg-white shadow-inner" id="learning-area">
            <div id="content" class="prose max-w-none">
                <div class="text-center text-gray-400 mt-20">
                    <svg class="mx-auto h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                    <p class="mt-4 text-lg">在右侧添加主题开始学习</p>
                </div>
            </div>
            <!-- 浮动按钮 -->
            <button id="float-btn">一键插入队列</button>
        </div>

        <!-- 右侧队列面板 -->
        <div class="w-80 bg-gray-100 flex flex-col border-l border-gray-200">
            <div class="p-4 border-b border-gray-200 bg-white">
                <h2 class="text-lg font-semibold mb-3 text-gray-700">学习队列</h2>
                <div class="flex gap-2">
                    <input type="text" id="topic-input" placeholder="输入单词、概念...回车添加"
                           class="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm">
                    <button id="add-btn" class="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 text-sm font-medium">添加</button>
                </div>
            </div>

            <!-- 当前学习指示 -->
            <div class="p-4 border-b border-gray-200" id="current-panel">
                <p class="text-xs text-gray-400 uppercase font-semibold mb-1">当前学习</p>
                <div id="current-display" class="text-gray-500 italic text-sm">暂无</div>
            </div>

            <!-- 待学队列列表 -->
            <div class="flex-1 overflow-y-auto p-4">
                <p class="text-xs text-gray-400 uppercase font-semibold mb-2">待学队列</p>
                <ul id="queue-list" class="space-y-1">
                    <li class="text-gray-400 text-sm italic">队列为空</li>
                </ul>
            </div>

            <!-- 下一个按钮 -->
            <div class="p-4 border-t border-gray-200 bg-white">
                <button id="next-btn" class="w-full py-2.5 bg-green-500 text-white rounded-lg hover:bg-green-600 font-medium disabled:opacity-50 disabled:cursor-not-allowed" disabled>下一个 →</button>
            </div>
        </div>
    </div>

    <script>
        // ---------- 状态 ----------
        let queue = [];                // 待学主题 { id, topic, isRecursive }
        let current = null;           // 当前学习 { id, topic, isRecursive, htmlContent, status }
        const floatBtn = document.getElementById('float-btn');
        let nextId = 0;

        // ---------- DOM 元素 ----------
        const contentDiv = document.getElementById('content');
        const queueList = document.getElementById('queue-list');
        const currentDisplay = document.getElementById('current-display');
        const nextBtn = document.getElementById('next-btn');
        const topicInput = document.getElementById('topic-input');
        const addBtn = document.getElementById('add-btn');

        // ---------- 工具函数 ----------
        function renderQueuePanel() {
            // 当前学习
            if (current) {
                currentDisplay.innerHTML = `<span class="bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-sm font-medium">${escapeHtml(current.topic)}</span>`;
            } else {
                currentDisplay.innerHTML = '<span class="text-gray-400 italic text-sm">暂无</span>';
            }

            // 待学队列
            if (queue.length === 0) {
                queueList.innerHTML = '<li class="text-gray-400 text-sm italic">队列为空</li>';
            } else {
                queueList.innerHTML = queue.map((item, idx) => `
                    <li class="queue-item px-2 py-1.5 rounded text-sm flex justify-between items-center">
                        <span class="text-gray-700">${idx+1}. ${escapeHtml(item.topic)}</span>
                        <span class="text-xs text-gray-400">${item.isRecursive ? '递归' : '初始'}</span>
                    </li>
                `).join('');
            }

            // 下一个按钮状态
            nextBtn.disabled = !current;
        }

        function escapeHtml(text) {
            const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
            return text.replace(/[&<>"']/g, m => map[m]);
        }

        function showLoading() {
            contentDiv.innerHTML = '<div class="flex justify-center items-center py-20"><div class="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500"></div><span class="ml-3 text-gray-500">正在生成学习内容...</span></div>';
        }

        function showError(message, retryCallback) {
            contentDiv.innerHTML = `
                <div class="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
                    <p class="text-red-700 mb-3">❌ ${escapeHtml(message)}</p>
                    <button onclick="(${retryCallback.toString()})()" class="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 text-sm">重试</button>
                </div>`;
        }

        function showCompletion() {
            contentDiv.innerHTML = `
                <div class="text-center mt-20 text-gray-500">
                    <svg class="mx-auto h-12 w-12 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p class="mt-4 text-lg">学习完成，可以添加新主题</p>
                </div>`;
        }

        // ---------- API 调用生成内容 ----------
        async function generateContent(topic, isRecursive) {
            const response = await fetch('/api/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic, isRecursive })
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({ detail: '未知错误' }));
                throw new Error(err.detail || `请求失败 (${response.status})`);
            }
            const data = await response.json();
            if (!data.htmlContent) throw new Error('生成内容为空');
            return data.htmlContent;
        }

        // ---------- 开始学习当前主题 ----------
        async function startLearning(item) {
            current = item;
            renderQueuePanel();
            showLoading();
            try {
                const htmlContent = await generateContent(item.topic, item.isRecursive);
                current.htmlContent = htmlContent;
                current.status = 'done';
                contentDiv.innerHTML = htmlContent;
                renderQueuePanel();
            } catch (error) {
                console.error(error);
                current.status = 'error';
                showError(error.message, () => startLearning(item));
                renderQueuePanel();
            }
        }

        // ---------- 添加主题到队列 ----------
        function addTopic(topic, isRecursive) {
            if (!topic.trim()) return;
            const item = { id: nextId++, topic: topic.trim(), isRecursive };
            if (!current && queue.length === 0) {
                // 直接开始学习
                startLearning(item);
            } else {
                // 加入队列末尾
                queue.push(item);
                renderQueuePanel();
            }
        }

        // ---------- 下一个 ----------
        function nextTopic() {
            if (!current) return;
            current = null;
            if (queue.length > 0) {
                const next = queue.shift();
                startLearning(next);
            } else {
                showCompletion();
                renderQueuePanel();
            }
        }

        // ---------- 浮动按钮：选中文本插入队列 ----------
        function hideFloatBtn() {
            floatBtn.style.display = 'none';
        }

        document.getElementById('learning-area').addEventListener('mouseup', function(e) {
            setTimeout(() => {
                const selection = window.getSelection();
                const text = selection.toString().trim();
                if (!text || selection.rangeCount === 0) {
                    hideFloatBtn();
                    return;
                }

                // 确保选区在 content 内部
                const range = selection.getRangeAt(0);
                const container = contentDiv;
                if (!container.contains(range.commonAncestorContainer)) {
                    hideFloatBtn();
                    return;
                }

                const rect = range.getBoundingClientRect();
                const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

                floatBtn.style.display = 'block';
                floatBtn.style.left = (rect.left + scrollLeft + rect.width/2 - floatBtn.offsetWidth/2) + 'px';
                floatBtn.style.top = (rect.bottom + scrollTop + 6) + 'px';

                // 存储选中文本
                floatBtn.dataset.text = text;
            }, 10);
        });

        // 点击按钮插入
        floatBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            const text = floatBtn.dataset.text;
            if (text) {
                addTopic(text, true);
            }
            hideFloatBtn();
            window.getSelection().removeAllRanges();
        });

        // 点击其他地方隐藏按钮
        document.addEventListener('mousedown', function(e) {
            if (e.target !== floatBtn && !floatBtn.contains(e.target)) {
                hideFloatBtn();
            }
        });

        // ---------- 事件绑定 ----------
        addBtn.addEventListener('click', () => {
            const topic = topicInput.value;
            if (topic.trim()) {
                addTopic(topic, false);
                topicInput.value = '';
            }
        });

        topicInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                addBtn.click();
            }
        });

        nextBtn.addEventListener('click', nextTopic);

        // 初始渲染
        renderQueuePanel();
    </script>
</body>
</html>
"""


def get_cache_key(topic: str, is_recursive: bool) -> str:
    raw = f"{topic}|{is_recursive}"
    return hashlib.md5(raw.encode()).hexdigest()


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_TEMPLATE


@app.post("/api/generate")
async def generate(req: Request):
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"detail": "请求体必须是合法JSON"}, status_code=400)

    topic = body.get("topic")
    is_recursive = body.get("isRecursive", False)
    if not topic or not isinstance(topic, str):
        return JSONResponse({"detail": "缺少 topic 参数"}, status_code=400)

    # 检查缓存
    cache_key = get_cache_key(topic, is_recursive)
    if cache_key in cache:
        return JSONResponse({"htmlContent": cache[cache_key]})

    # 构造提示词
    system_prompt = (
        "你是一个出色的自适应学习内容生成器。根据用户提供的主题和是否为递归深入模式，生成一个学习页面的HTML正文。\n\n"
        "要求：\n"
        "1. 输出严格JSON，格式：{\"htmlContent\": \"...\"}\n"
        "2. htmlContent 是安全的HTML片段，使用适当标签（如<h2>、<p>、<ul>、<code>、<pre>等），结构清晰，便于阅读。\n"
        "3. 如果是递归模式（isRecursive: true），请专注于解释该主题，不要引入超出主题范围的额外需解释概念，让内容自足。\n"
        "4. 如果是初始模式（isRecursive: false），可以适当展开，但仍要保持易读。\n"
        "5. 长度根据主题复杂度自适应，确保解释透彻，但无需刻意拉长。如果主题是一个单词或简单概念，生成约300-500字；如果是复杂代码或概念，可生成800-1500字。\n"
        "6. 使用中文生成内容（若遇到英文术语或代码保留原文）。\n"
        "7. HTML片段中不要包含<html>、<body>等外层标签。\n"
    )

    user_prompt = f"主题：{topic}\n递归模式：{'是' if is_recursive else '否'}\n请生成JSON。"
    
    try:
        # 调用 DeepSeek，开启思考模式以获得更好质量
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "enabled"}},
            reasoning_effort="high",
            max_tokens=4096,
        )
        raw_content = response.choices[0].message.content.strip()
        # 尝试解析JSON
        result = json.loads(raw_content)
        html_content = result.get("htmlContent", "")
        if not html_content:
            raise ValueError("模型返回的htmlContent为空")
        # 存入缓存
        cache[cache_key] = html_content
        return JSONResponse({"htmlContent": html_content})
    except json.JSONDecodeError:
        # 如果解析失败，尝试提取花括号内的内容
        if raw_content:
            try:
                start = raw_content.find('{')
                end = raw_content.rfind('}')
                if start != -1 and end != -1:
                    possible_json = raw_content[start:end+1]
                    result = json.loads(possible_json)
                    html_content = result.get("htmlContent", "")
                    if html_content:
                        cache[cache_key] = html_content
                        return JSONResponse({"htmlContent": html_content})
            except Exception:
                pass
        return JSONResponse({"detail": "生成内容格式错误，请重试"}, status_code=500)
    except openai.APIError as e:
        return JSONResponse({"detail": f"API调用失败: {e}"}, status_code=502)
    except Exception as e:
        return JSONResponse({"detail": f"服务内部错误: {str(e)}"}, status_code=500)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)