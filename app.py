import os
import json
import hashlib
import threading
from pathlib import Path
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
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@500;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --black:   #0c0c0e;
            --dark:    #141418;
            --mid:     #1e1e26;
            --border:  #2a2a35;
            --muted:   #4a4a5e;
            --subtle:  #6b6b82;
            --white:   #f0f0f5;
            --dim:     #a0a0b8;
            --blue:    #2563eb;
            --blue-hi: #3b82f6;
            --blue-lo: #1d4ed8;
            --blue-bg: #0f1b38;
            --blue-dim: #1e2d55;
        }

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            background: var(--black);
            color: var(--white);
            font-family: 'Inter', sans-serif;
            height: 100vh;
            overflow: hidden;
        }

        /* ── Layout ── */
        .app-shell {
            display: flex;
            height: 100vh;
        }

        /* ── Left: Learning Area ── */
        #learning-area {
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            border-right: 1px solid var(--border);
        }

        .area-header {
            padding: 18px 28px;
            border-bottom: 1px solid var(--border);
            background: var(--dark);
            display: flex;
            align-items: center;
            gap: 12px;
            flex-shrink: 0;
        }

        .area-header-dot {
            width: 8px; height: 8px;
            border-radius: 50%;
            background: var(--blue);
            box-shadow: 0 0 8px var(--blue-hi);
            animation: pulse-dot 2s ease-in-out infinite;
        }
        @keyframes pulse-dot {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }

        .area-title {
            font-family: 'Syne', sans-serif;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--dim);
        }

        .current-badge {
            margin-left: auto;
            background: var(--blue-bg);
            border: 1px solid var(--blue-dim);
            color: var(--blue-hi);
            font-family: 'JetBrains Mono', monospace;
            font-size: 11px;
            padding: 3px 10px;
            border-radius: 3px;
            max-width: 240px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        #content-scroll {
            flex: 1;
            overflow-y: auto;
            padding: 36px 48px;
            scroll-behavior: smooth;
        }
        #content-scroll::-webkit-scrollbar { width: 4px; }
        #content-scroll::-webkit-scrollbar-track { background: transparent; }
        #content-scroll::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

        #content { max-width: 780px; }

        /* ── Content Typography ── */
        #content h1 {
            font-family: 'Syne', sans-serif;
            font-size: 2rem;
            font-weight: 800;
            color: var(--white);
            margin-bottom: 8px;
            letter-spacing: -0.02em;
            line-height: 1.2;
        }
        #content h2 {
            font-family: 'Syne', sans-serif;
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--white);
            margin: 2rem 0 0.75rem;
            padding-left: 12px;
            border-left: 3px solid var(--blue);
        }
        #content h3 {
            font-size: 1rem;
            font-weight: 600;
            color: var(--dim);
            margin: 1.5rem 0 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
        }
        #content p {
            font-size: 0.95rem;
            line-height: 1.75;
            color: #c8c8d8;
            margin-bottom: 0.85rem;
        }
        #content ul, #content ol {
            margin: 0.5rem 0 1rem 0;
            padding-left: 0;
            list-style: none;
        }
        #content ul li, #content ol li {
            position: relative;
            padding: 6px 0 6px 20px;
            font-size: 0.93rem;
            line-height: 1.65;
            color: #c0c0d4;
            border-bottom: 1px solid var(--border);
        }
        #content ul li:last-child, #content ol li:last-child { border-bottom: none; }
        #content ul li::before {
            content: '';
            position: absolute;
            left: 0;
            top: 14px;
            width: 6px; height: 6px;
            border-radius: 50%;
            background: var(--blue);
        }
        #content ol { counter-reset: ol-counter; }
        #content ol li::before {
            content: counter(ol-counter);
            counter-increment: ol-counter;
            position: absolute;
            left: 0;
            top: 5px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            color: var(--blue);
            font-weight: 600;
        }
        #content pre {
            background: var(--dark);
            border: 1px solid var(--border);
            border-top: 2px solid var(--blue);
            color: #e0e0f0;
            padding: 20px;
            border-radius: 4px;
            overflow-x: auto;
            margin: 1rem 0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.82rem;
            line-height: 1.7;
        }
        #content code {
            font-family: 'JetBrains Mono', monospace;
            background: var(--mid);
            color: var(--blue-hi);
            padding: 0.15em 0.45em;
            border-radius: 3px;
            font-size: 0.83em;
            border: 1px solid var(--border);
        }
        #content pre code {
            background: none;
            border: none;
            color: inherit;
            padding: 0;
        }
        #content strong { color: var(--white); font-weight: 600; }
        #content em { color: var(--blue-hi); font-style: normal; font-weight: 500; }
        #content blockquote {
            border-left: 3px solid var(--muted);
            padding: 10px 16px;
            background: var(--mid);
            border-radius: 0 4px 4px 0;
            margin: 1rem 0;
            color: var(--dim);
            font-style: italic;
        }

        /* ── Interactive elements injected by AI ── */
        /* Quiz / self-check */
        #content .quiz-block {
            background: var(--mid);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 20px;
            margin: 1.5rem 0;
        }
        #content .quiz-block .quiz-q {
            font-family: 'Syne', sans-serif;
            font-size: 0.95rem;
            font-weight: 700;
            color: var(--white);
            margin-bottom: 12px;
        }
        #content .quiz-option {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 9px 14px;
            border-radius: 4px;
            border: 1px solid var(--border);
            cursor: pointer;
            margin: 5px 0;
            font-size: 0.88rem;
            color: var(--dim);
            transition: all 0.15s;
            user-select: none;
        }
        #content .quiz-option:hover { border-color: var(--blue); color: var(--white); }
        #content .quiz-option.correct { border-color: #22c55e; color: #4ade80; background: #052e16; }
        #content .quiz-option.wrong   { border-color: #ef4444; color: #fca5a5; background: #2a0a0a; }
        #content .quiz-feedback {
            margin-top: 12px;
            font-size: 0.83rem;
            padding: 8px 12px;
            border-radius: 3px;
            display: none;
        }
        #content .quiz-feedback.show { display: block; }
        #content .quiz-feedback.ok  { background: #052e16; color: #4ade80; border: 1px solid #166534; }
        #content .quiz-feedback.err { background: #2a0a0a; color: #fca5a5; border: 1px solid #7f1d1d; }

        /* Collapsible sections */
        #content details {
            border: 1px solid var(--border);
            border-radius: 4px;
            margin: 1rem 0;
            overflow: hidden;
        }
        #content summary {
            padding: 12px 16px;
            background: var(--mid);
            cursor: pointer;
            font-family: 'Syne', sans-serif;
            font-size: 0.88rem;
            font-weight: 700;
            color: var(--blue-hi);
            list-style: none;
            display: flex;
            align-items: center;
            gap: 8px;
            user-select: none;
        }
        #content summary::before {
            content: '▶';
            font-size: 0.6rem;
            transition: transform 0.2s;
        }
        #content details[open] summary::before { transform: rotate(90deg); }
        #content details > *:not(summary) {
            padding: 16px;
            background: var(--dark);
        }

        /* Key term cards */
        #content .term-card {
            display: inline-block;
            background: var(--blue-bg);
            border: 1px solid var(--blue-dim);
            color: var(--blue-hi);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            padding: 3px 10px;
            border-radius: 3px;
            margin: 2px;
            cursor: default;
        }

        /* Progress / chapter bar */
        #content .chapter-nav {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            margin: 1rem 0 1.5rem;
        }
        #content .chapter-pill {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.72rem;
            padding: 4px 10px;
            border-radius: 2px;
            background: var(--mid);
            border: 1px solid var(--border);
            color: var(--muted);
        }
        #content .chapter-pill.active {
            background: var(--blue-bg);
            border-color: var(--blue);
            color: var(--blue-hi);
        }

        /* Flashcard flip */
        #content .flashcard-wrap {
            perspective: 800px;
            margin: 1.2rem 0;
        }
        #content .flashcard {
            position: relative;
            width: 100%;
            min-height: 90px;
            transform-style: preserve-3d;
            transition: transform 0.4s;
            cursor: pointer;
        }
        #content .flashcard.flipped { transform: rotateY(180deg); }
        #content .flashcard-front,
        #content .flashcard-back {
            position: absolute;
            width: 100%;
            min-height: 90px;
            backface-visibility: hidden;
            border-radius: 4px;
            padding: 18px 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.9rem;
            text-align: center;
        }
        #content .flashcard-front {
            background: var(--mid);
            border: 1px solid var(--border);
            color: var(--white);
            font-weight: 600;
        }
        #content .flashcard-back {
            background: var(--blue-bg);
            border: 1px solid var(--blue-dim);
            color: var(--dim);
            transform: rotateY(180deg);
        }
        #content .flashcard-hint {
            text-align: right;
            font-size: 0.7rem;
            color: var(--muted);
            margin-top: 4px;
            font-family: 'JetBrains Mono', monospace;
        }

        /* Divider */
        #content hr {
            border: none;
            border-top: 1px solid var(--border);
            margin: 2rem 0;
        }

        /* ── Empty / Loading / Done States ── */
        .state-center {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 60vh;
            gap: 12px;
            color: var(--muted);
        }
        .state-icon {
            width: 48px; height: 48px;
            opacity: 0.4;
        }
        .state-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.82rem;
            letter-spacing: 0.05em;
        }

        .spinner {
            width: 32px; height: 32px;
            border: 2px solid var(--border);
            border-top-color: var(--blue);
            border-radius: 50%;
            animation: spin 0.7s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }

        .error-box {
            background: #180a0a;
            border: 1px solid #7f1d1d;
            border-radius: 4px;
            padding: 20px 24px;
            color: #fca5a5;
            text-align: center;
            max-width: 480px;
            margin: 0 auto;
        }
        .error-box p { font-size: 0.88rem; margin-bottom: 12px; }
        .retry-btn {
            background: #7f1d1d;
            color: #fca5a5;
            border: none;
            border-radius: 3px;
            padding: 7px 18px;
            font-size: 0.82rem;
            cursor: pointer;
            font-family: 'JetBrains Mono', monospace;
        }
        .retry-btn:hover { background: #991b1b; }

        /* ── Floating "Insert" Button ── */
        #float-btn {
            position: absolute;
            z-index: 1000;
            display: none;
            background: var(--blue);
            color: #fff;
            border: none;
            border-radius: 3px;
            padding: 5px 12px;
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
            cursor: pointer;
            box-shadow: 0 4px 16px rgba(37,99,235,0.4);
            white-space: nowrap;
            letter-spacing: 0.03em;
        }
        #float-btn::before { content: '+ '; }
        #float-btn:hover { background: var(--blue-lo); }

        /* ── Right: Queue Panel ── */
        #queue-panel {
            width: 300px;
            flex-shrink: 0;
            background: var(--dark);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .panel-header {
            padding: 18px 20px 14px;
            border-bottom: 1px solid var(--border);
        }
        .panel-title {
            font-family: 'Syne', sans-serif;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 12px;
        }

        .input-row {
            display: flex;
            gap: 6px;
        }
        #topic-input {
            flex: 1;
            background: var(--mid);
            border: 1px solid var(--border);
            border-radius: 3px;
            color: var(--white);
            font-family: 'Inter', sans-serif;
            font-size: 0.83rem;
            padding: 8px 12px;
            outline: none;
            transition: border-color 0.15s;
        }
        #topic-input::placeholder { color: var(--muted); }
        #topic-input:focus { border-color: var(--blue); }

        #add-btn {
            background: var(--blue);
            color: #fff;
            border: none;
            border-radius: 3px;
            padding: 8px 14px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            font-family: 'Syne', sans-serif;
            letter-spacing: 0.04em;
            transition: background 0.15s;
        }
        #add-btn:hover { background: var(--blue-lo); }

        /* Current item */
        .section-label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 10px;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 6px;
        }
        .current-section {
            padding: 14px 20px;
            border-bottom: 1px solid var(--border);
        }
        #current-display {
            font-size: 0.85rem;
        }
        .current-chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: var(--blue-bg);
            border: 1px solid var(--blue-dim);
            color: var(--blue-hi);
            border-radius: 3px;
            padding: 4px 10px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.78rem;
            max-width: 240px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .current-chip::before {
            content: '';
            width: 6px; height: 6px;
            border-radius: 50%;
            background: var(--blue-hi);
            flex-shrink: 0;
            animation: pulse-dot 1.5s ease-in-out infinite;
        }

        /* Queue list */
        .queue-scroll {
            flex: 1;
            overflow-y: auto;
            padding: 14px 20px;
        }
        .queue-scroll::-webkit-scrollbar { width: 3px; }
        .queue-scroll::-webkit-scrollbar-thumb { background: var(--border); }

        .queue-empty {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--muted);
            text-align: center;
            padding: 24px 0;
        }

        .queue-item {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 9px 10px;
            border-radius: 3px;
            margin-bottom: 2px;
            transition: background 0.12s;
            cursor: default;
        }
        .queue-item:hover { background: var(--mid); }

        .q-index {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            color: var(--muted);
            flex-shrink: 0;
            width: 16px;
            text-align: center;
        }
        .q-topic {
            flex: 1;
            font-size: 0.83rem;
            color: var(--dim);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .q-tag {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.65rem;
            padding: 2px 6px;
            border-radius: 2px;
            flex-shrink: 0;
        }
        .q-tag.recursive {
            background: var(--blue-bg);
            color: var(--blue-hi);
            border: 1px solid var(--blue-dim);
        }
        .q-tag.initial {
            background: var(--mid);
            color: var(--muted);
            border: 1px solid var(--border);
        }

        /* Next button */
        .next-wrap {
            padding: 14px 20px;
            border-top: 1px solid var(--border);
        }
        #next-btn {
            width: 100%;
            padding: 11px;
            background: var(--blue);
            color: #fff;
            border: none;
            border-radius: 3px;
            font-family: 'Syne', sans-serif;
            font-size: 0.85rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            cursor: pointer;
            transition: background 0.15s, opacity 0.15s;
            text-transform: uppercase;
        }
        #next-btn:hover:not(:disabled) { background: var(--blue-lo); }
        #next-btn:disabled {
            opacity: 0.25;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <div class="app-shell">
        <!-- ── Left: Learning Area ── -->
        <div id="learning-area">
            <div class="area-header">
                <div class="area-header-dot"></div>
                <span class="area-title">学习区</span>
                <div class="current-badge" id="header-current">— 暂无主题 —</div>
            </div>
            <div id="content-scroll">
                <div id="content">
                    <div class="state-center">
                        <svg class="state-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                        </svg>
                        <span class="state-label">在右侧输入主题，开始学习</span>
                    </div>
                </div>
            </div>
            <button id="float-btn">插入队列</button>
        </div>

        <!-- ── Right: Queue Panel ── -->
        <div id="queue-panel">
            <div class="panel-header">
                <div class="panel-title">学习队列</div>
                <div class="input-row">
                    <input type="text" id="topic-input" placeholder="输入单词或概念，回车添加" autocomplete="off">
                    <button id="add-btn">添加</button>
                </div>
            </div>

            <div class="current-section">
                <div class="section-label">当前学习</div>
                <div id="current-display">
                    <span style="color:var(--muted);font-size:0.8rem;font-family:'JetBrains Mono',monospace;">— 暂无 —</span>
                </div>
            </div>

            <div class="queue-scroll">
                <div class="section-label" style="margin-bottom:8px;">待学队列</div>
                <ul id="queue-list" style="list-style:none;">
                    <li class="queue-empty">队列为空</li>
                </ul>
            </div>

            <div class="next-wrap">
                <button id="next-btn" disabled>下一个 →</button>
            </div>
        </div>
    </div>

    <script>
        // ── State ──
        let queue = [];
        let current = null;
        let nextId = 0;
        const floatBtn = document.getElementById('float-btn');

        // ── DOM ──
        const contentDiv    = document.getElementById('content');
        const queueList     = document.getElementById('queue-list');
        const currentDisplay= document.getElementById('current-display');
        const nextBtn       = document.getElementById('next-btn');
        const topicInput    = document.getElementById('topic-input');
        const addBtn        = document.getElementById('add-btn');
        const headerCurrent = document.getElementById('header-current');

        // ── Utilities ──
        function escapeHtml(t) {
            return t.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m]));
        }

        function renderQueuePanel() {
            // Header badge
            headerCurrent.textContent = current ? current.topic : '— 暂无主题 —';

            // Current chip
            if (current) {
                currentDisplay.innerHTML = `<span class="current-chip">${escapeHtml(current.topic)}</span>`;
            } else {
                currentDisplay.innerHTML = '<span style="color:var(--muted);font-size:0.8rem;font-family:\'JetBrains Mono\',monospace;">— 暂无 —</span>';
            }

            // Queue list
            if (queue.length === 0) {
                queueList.innerHTML = '<li class="queue-empty">队列为空</li>';
            } else {
                queueList.innerHTML = queue.map((item, idx) => `
                    <li class="queue-item">
                        <span class="q-index">${idx+1}</span>
                        <span class="q-topic">${escapeHtml(item.topic)}</span>
                        <span class="q-tag ${item.isRecursive ? 'recursive' : 'initial'}">${item.isRecursive ? '递归' : '初始'}</span>
                    </li>
                `).join('');
            }

            nextBtn.disabled = !current;
        }

        function showLoading() {
            contentDiv.innerHTML = `
                <div class="state-center">
                    <div class="spinner"></div>
                    <span class="state-label">正在生成学习内容…</span>
                </div>`;
        }

        function showError(message, retryCallback) {
            contentDiv.innerHTML = `
                <div class="state-center">
                    <div class="error-box">
                        <p>❌ ${escapeHtml(message)}</p>
                        <button class="retry-btn" onclick="(${retryCallback.toString()})()">重试</button>
                    </div>
                </div>`;
        }

        function showCompletion() {
            contentDiv.innerHTML = `
                <div class="state-center">
                    <svg class="state-icon" style="opacity:0.6;color:#22c55e;" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span class="state-label">已完成 · 可继续添加新主题</span>
                </div>`;
        }

        // ── Generate Content ──
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

        // ── Start Learning ──
        async function startLearning(item) {
            current = item;
            renderQueuePanel();
            showLoading();
            try {
                const htmlContent = await generateContent(item.topic, item.isRecursive);
                current.htmlContent = htmlContent;
                current.status = 'done';
                contentDiv.innerHTML = htmlContent;
                document.getElementById('content-scroll').scrollTo({ top: 0, behavior: 'smooth' });
                renderQueuePanel();
            } catch (error) {
                showError(error.message, () => startLearning(item));
            }
        }

        // ── Add Topic ──
        function addTopic(topic, isRecursive) {
            if (!topic.trim()) return;
            const item = { id: nextId++, topic: topic.trim(), isRecursive };
            if (!current && queue.length === 0) {
                startLearning(item);
            } else {
                queue.push(item);
                renderQueuePanel();
            }
        }

        // ── Next Topic ──
        function nextTopic() {
            if (!current) return;
            current = null;
            if (queue.length > 0) {
                startLearning(queue.shift());
            } else {
                showCompletion();
                renderQueuePanel();
            }
        }

        // ── Float Button ──
        function hideFloatBtn() { floatBtn.style.display = 'none'; }

        document.getElementById('learning-area').addEventListener('mouseup', function() {
            setTimeout(() => {
                const sel = window.getSelection();
                const text = sel.toString().trim();
                if (!text || sel.rangeCount === 0) { hideFloatBtn(); return; }
                const range = sel.getRangeAt(0);
                if (!contentDiv.contains(range.commonAncestorContainer)) { hideFloatBtn(); return; }
                const rect = range.getBoundingClientRect();
                const sl = window.pageXOffset || document.documentElement.scrollLeft;
                const st = window.pageYOffset || document.documentElement.scrollTop;
                floatBtn.style.display = 'block';
                floatBtn.style.left = (rect.left + sl + rect.width/2 - floatBtn.offsetWidth/2) + 'px';
                floatBtn.style.top  = (rect.bottom + st + 6) + 'px';
                floatBtn.dataset.text = text;
            }, 10);
        });

        floatBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            const text = floatBtn.dataset.text;
            if (text) addTopic(text, true);
            hideFloatBtn();
            window.getSelection().removeAllRanges();
        });

        document.addEventListener('mousedown', function(e) {
            if (e.target !== floatBtn && !floatBtn.contains(e.target)) hideFloatBtn();
        });

        // ── Events ──
        addBtn.addEventListener('click', () => {
            const topic = topicInput.value;
            if (topic.trim()) { addTopic(topic, false); topicInput.value = ''; }
        });

        topicInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); addBtn.click(); }
        });

        nextBtn.addEventListener('click', nextTopic);

        // Init
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

    # ── 系统提示词（黑白蓝主题 + 互动内容） ──
    system_prompt = """你是一个出色的自适应学习内容生成器，专门生成结构清晰、视觉一致、富含互动元素的学习页面。

页面运行在已设计好的黑白蓝主题界面中，已定义好以下 CSS 变量和样式类（你只需使用，无需重定义）：
- 颜色变量：--black, --dark, --mid, --border, --muted, --blue, --blue-hi, --blue-bg, --blue-dim, --white, --dim
- 字体：'Syne'（标题）、'Inter'（正文）、'JetBrains Mono'（代码/标签）
- 内置样式：h1, h2, h3, p, ul, ol, code, pre, blockquote, details/summary, hr
- 互动组件类（见下方说明）

【输出格式】
严格输出 JSON：{"htmlContent": "..."}
htmlContent 是 HTML 片段，不含 <html>/<body> 等外层标签。

【内容结构要求】
1. 第一行必须是 <h1>主题名称</h1>，简洁概括。
2. 核心概念用 <h2> 分节，每节有 <p> 解释。
3. 技术术语用 <code> 标注，多行代码用 <pre><code>。
4. 适当使用 <ul>/<ol> 列表、<blockquote> 引用。
5. 可折叠补充内容用 <details><summary>标题</summary>内容</details>。

【互动元素（必须在每篇内容中至少使用 2 种）】

A. 单选测验 — 用于知识检测，每次只放 1 道：
<div class="quiz-block">
  <div class="quiz-q">❓ 问题文字</div>
  <div class="quiz-option" onclick="quizPick(this,'correct')">A. 正确答案</div>
  <div class="quiz-option" onclick="quizPick(this,'wrong')">B. 错误选项</div>
  <div class="quiz-option" onclick="quizPick(this,'wrong')">C. 错误选项</div>
  <div class="quiz-feedback ok">✅ 正确！解释为何正确（1句话）</div>
  <div class="quiz-feedback err">❌ 错误。正确答案是A，因为…</div>
</div>
<script>
function quizPick(el, type) {
  const block = el.closest('.quiz-block');
  if (block.dataset.done) return;
  block.dataset.done = '1';
  block.querySelectorAll('.quiz-option').forEach(o => o.style.pointerEvents='none');
  el.classList.add(type === 'correct' ? 'correct' : 'wrong');
  block.querySelector('.quiz-feedback.' + (type==='correct'?'ok':'err')).classList.add('show');
}
</script>

B. 翻转闪卡 — 用于关键概念记忆，可放多张：
<div class="flashcard-wrap">
  <div class="flashcard" onclick="this.classList.toggle('flipped')">
    <div class="flashcard-front">正面：概念或问题</div>
    <div class="flashcard-back">背面：定义或答案</div>
  </div>
  <div class="flashcard-hint">点击翻转</div>
</div>

C. 关键术语标签 — 行内展示核心词汇：
<p>核心概念包括 <span class="term-card">术语A</span> 和 <span class="term-card">术语B</span>。</p>

D. 章节导航胶囊 — 页面顶部列出各章节（纯装饰性，无需跳转）：
<div class="chapter-nav">
  <span class="chapter-pill active">§1 简介</span>
  <span class="chapter-pill">§2 原理</span>
  <span class="chapter-pill">§3 应用</span>
</div>

【内容策略】
- 递归模式（isRecursive=true）：聚焦解释该主题本身，内容自足，不引入额外未解释概念。长度 300–600 字。闪卡 1–2 张，测验 1 道。
- 初始模式（isRecursive=false）：可适当展开背景、应用与对比。长度 600–1200 字。闪卡 2–3 张，测验 1–2 道，至少 1 个 <details> 折叠区块。
- 所有内容使用中文，代码和专有术语保留英文原文。
- 禁止在 htmlContent 中定义已存在的 CSS 类（如 .quiz-block, .flashcard 等），禁止重写颜色变量。
- 每道测验只写一组 quizPick 函数（用 <script> 包裹，可复用已有函数名）。
"""

    user_prompt = f"主题：{topic}\n递归模式：{'是' if is_recursive else '否'}\n请生成JSON。"

    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "enabled"}},
            max_tokens=4096,
        )
        raw_content = response.choices[0].message.content.strip()
        result = json.loads(raw_content)
        html_content = result.get("htmlContent", "")
        if not html_content:
            raise ValueError("模型返回的 htmlContent 为空")
        cache[cache_key] = html_content
        return JSONResponse({"htmlContent": html_content})

    except json.JSONDecodeError:
        if raw_content:
            try:
                start = raw_content.find('{')
                end   = raw_content.rfind('}')
                if start != -1 and end != -1:
                    result = json.loads(raw_content[start:end+1])
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