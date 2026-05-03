import os
import json
import hashlib
import re
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import openai
import uvicorn
import requests

app = FastAPI()

CONFIG_PATH = os.getenv("APP_CONFIG_PATH", "config.json")
RECORDS_PATH = os.getenv("APP_RECORDS_PATH", "records.json")
MAX_RECENT_PAGES = 64


def load_api_key() -> str | None:
    """流程名：配置加载流程｜读取本地配置并提取 API Key。"""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("api_key")
    return None


client = openai.OpenAI(
    api_key=load_api_key(),
    base_url="https://api.deepseek.com/v1",
)

_cache: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# HTML TEMPLATE
# ---------------------------------------------------------------------------
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>递归学习</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
/* ═══════════════════════════════════════
   TOKENS
═══════════════════════════════════════ */
:root {
  --bg:       #0f0f0e;
  --surface:  #181817;
  --raised:   #222221;
  --bd:       #2d2d2b;
  --bd-hi:    #444442;
  --t1:       #e8e7e2;
  --t2:       #8a897f;
  --t3:       #4e4d47;
  --acc:      #2c62d4;
  --acc-bg:   #111d3a;
  --acc-bd:   #1e3166;
  --grn:      #1fa84a;
  --grn-bg:   #091a0f;
  --amb:      #c97a1a;
  --amb-bg:   #1c1206;
  --red:      #c93838;
  --red-bg:   #1c0808;
  --font-ui:  "IBM Plex Mono", monospace;
  --font-body:"IBM Plex Sans", system-ui, sans-serif;
  --font-head:"Barlow Condensed", sans-serif;
}
[data-theme="light"] {
  --bg:       #f2f1ec;
  --surface:  #e6e5df;
  --raised:   #fafaf7;
  --bd:       #ccc9be;
  --bd-hi:    #aaa89e;
  --t1:       #111110;
  --t2:       #55544e;
  --t3:       #99978f;
  --acc:      #1a4db5;
  --acc-bg:   #dbe8fe;
  --acc-bd:   #93b4fd;
  --grn:      #15803d;
  --grn-bg:   #f0fdf4;
  --amb:      #92400e;
  --amb-bg:   #fffbeb;
  --red:      #b91c1c;
  --red-bg:   #fef2f2;
}

*,*::before,*::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { height: 100%; }
body {
  background: var(--bg);
  color: var(--t1);
  font-family: var(--font-body);
  font-size: 14px;
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ═══════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════ */
#sidebar {
  width: 272px;
  flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--bd);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* -- header -- */
.sb-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 14px;
  border-bottom: 1px solid var(--bd);
  flex-shrink: 0;
}
.brand {
  font-family: var(--font-head);
  font-size: 16px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--t1);
}
.brand em { color: var(--acc); font-style: normal; }

#theme-btn {
  font-family: var(--font-ui);
  font-size: 10px;
  letter-spacing: .06em;
  background: none;
  border: 1px solid var(--bd);
  border-radius: 1px;
  color: var(--t3);
  cursor: pointer;
  padding: 3px 8px;
  transition: color .1s, border-color .1s;
}
#theme-btn:hover { color: var(--t1); border-color: var(--bd-hi); }

/* -- add input -- */
.sb-add {
  padding: 10px 12px;
  border-bottom: 1px solid var(--bd);
  flex-shrink: 0;
}
.add-row { display: flex; gap: 6px; }

#topic-input {
  flex: 1;
  background: var(--bg);
  border: 1px solid var(--bd);
  border-radius: 1px;
  color: var(--t1);
  font-family: var(--font-body);
  font-size: 13px;
  padding: 7px 10px;
  outline: none;
  transition: border-color .12s;
}
#topic-input::placeholder { color: var(--t3); }
#topic-input:focus { border-color: var(--acc); }

#add-btn {
  background: var(--acc);
  border: none;
  border-radius: 1px;
  color: #fff;
  cursor: pointer;
  font-family: var(--font-ui);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: .04em;
  padding: 7px 11px;
  white-space: nowrap;
  transition: opacity .1s;
}
#add-btn:hover { opacity: .85; }

/* -- list header -- */
.sb-list-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 7px 14px 4px;
  flex-shrink: 0;
}
.list-label {
  font-family: var(--font-ui);
  font-size: 9px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--t3);
}
#item-count {
  font-family: var(--font-ui);
  font-size: 9px;
  color: var(--t3);
}

/* -- list -- */
#item-list {
  flex: 1;
  overflow-y: auto;
  padding: 2px 0 8px;
}
#item-list::-webkit-scrollbar { width: 3px; }
#item-list::-webkit-scrollbar-thumb { background: var(--bd); }

.list-empty {
  padding: 28px 14px;
  text-align: center;
  font-family: var(--font-ui);
  font-size: 10px;
  color: var(--t3);
  line-height: 2;
}

/* -- item row -- */
.item-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px 8px 10px;
  cursor: pointer;
  border-left: 2px solid transparent;
  transition: background .08s, border-color .08s;
  user-select: none;
  position: relative;
}
.item-row:hover { background: var(--raised); }
.item-row.selected {
  background: var(--raised);
  border-left-color: var(--acc);
}

/* status dot */
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot-pending { background: var(--t3); }
.dot-loading { background: var(--acc); animation: blink .7s ease-in-out infinite; }
.dot-done    { background: var(--grn); }
.dot-error   { background: var(--red); }

@keyframes blink {
  0%,100% { opacity: 1; }
  50%      { opacity: .3; }
}

.item-body { flex: 1; overflow: hidden; }
.item-topic {
  font-size: 12px;
  color: var(--t1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}
.item-meta {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 2px;
}
.tag {
  font-family: var(--font-ui);
  font-size: 8px;
  letter-spacing: .04em;
  padding: 1px 5px;
  border: 1px solid var(--bd);
  border-radius: 1px;
  color: var(--t3);
}
.tag-rec {
  border-color: var(--acc-bd);
  color: var(--acc);
  background: var(--acc-bg);
}
.item-time {
  font-family: var(--font-ui);
  font-size: 8px;
  color: var(--t3);
}

.item-del {
  display: none;
  background: none;
  border: none;
  color: var(--t3);
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
  padding: 1px 3px;
  flex-shrink: 0;
}
.item-row:hover .item-del { display: block; }
.item-del:hover { color: var(--red); }

/* ═══════════════════════════════════════
   MAIN
═══════════════════════════════════════ */
#main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

/* -- topbar -- */
#topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 24px;
  height: 46px;
  background: var(--surface);
  border-bottom: 1px solid var(--bd);
  flex-shrink: 0;
}
#top-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--t3);
  flex-shrink: 0;
  transition: background .2s;
}
#top-dot.loading { background: var(--acc); animation: blink .7s ease-in-out infinite; }
#top-dot.done    { background: var(--grn); }
#top-dot.error   { background: var(--red); }
#top-dot.pending { background: var(--amb); }

#top-topic {
  flex: 1;
  font-family: var(--font-head);
  font-size: 15px;
  font-weight: 600;
  letter-spacing: .04em;
  color: var(--t1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
#top-status {
  font-family: var(--font-ui);
  font-size: 9px;
  letter-spacing: .08em;
  color: var(--t3);
  text-transform: uppercase;
  flex-shrink: 0;
}

/* -- content scroll -- */
#content-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 32px 44px;
}
#content-scroll::-webkit-scrollbar { width: 4px; }
#content-scroll::-webkit-scrollbar-thumb { background: var(--bd); }

/* ── State Screens ── */
.state-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 58vh;
  gap: 14px;
  text-align: center;
}
.state-icon {
  width: 44px;
  height: 44px;
  color: var(--t3);
}
.state-title {
  font-family: var(--font-head);
  font-size: 20px;
  font-weight: 600;
  letter-spacing: .04em;
  color: var(--t2);
}
.state-sub {
  font-family: var(--font-ui);
  font-size: 11px;
  color: var(--t3);
  line-height: 1.8;
}
.gen-btn {
  margin-top: 6px;
  background: var(--acc);
  border: none;
  border-radius: 1px;
  color: #fff;
  cursor: pointer;
  font-family: var(--font-ui);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: .06em;
  padding: 9px 22px;
  text-transform: uppercase;
  transition: opacity .1s;
}
.gen-btn:hover { opacity: .85; }

/* Skeleton */
.skel { max-width: 640px; width: 100%; margin-top: 20px; }
.skel-line {
  height: 13px;
  background: var(--raised);
  border-radius: 1px;
  margin-bottom: 9px;
  animation: shimmer 1.1s ease-in-out infinite;
}
.skel-line.h1   { height: 26px; width: 50%; margin-bottom: 18px; }
.skel-line.w100 { width: 100%; }
.skel-line.w75  { width: 75%; }
.skel-line.w55  { width: 55%; }
.skel-line.w40  { width: 40%; }
@keyframes shimmer {
  0%,100% { opacity: .35; }
  50%      { opacity: .8; }
}

/* Error */
.err-box {
  background: var(--red-bg);
  border: 1px solid var(--red);
  border-radius: 1px;
  padding: 18px 22px;
  max-width: 420px;
}
.err-box p { color: var(--red); font-size: 12px; line-height: 1.6; margin-bottom: 12px; }
.retry-btn {
  background: var(--red);
  border: none;
  border-radius: 1px;
  color: #fff;
  cursor: pointer;
  font-family: var(--font-ui);
  font-size: 10px;
  letter-spacing: .06em;
  padding: 6px 14px;
  text-transform: uppercase;
}
.retry-btn:hover { opacity: .85; }

/* ═══════════════════════════════════════
   CONTENT DOC TYPOGRAPHY
═══════════════════════════════════════ */
#content-doc { max-width: 740px; }

#content-doc h1 {
  font-family: var(--font-head);
  font-size: 2rem;
  font-weight: 700;
  color: var(--t1);
  letter-spacing: -.01em;
  line-height: 1.15;
  margin-bottom: 10px;
}
#content-doc h2 {
  font-family: var(--font-head);
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--t1);
  letter-spacing: .03em;
  margin: 2rem 0 .6rem;
  padding-bottom: 5px;
  border-bottom: 1px solid var(--bd);
}
#content-doc h3 {
  font-family: var(--font-ui);
  font-size: .72rem;
  font-weight: 500;
  color: var(--t2);
  text-transform: uppercase;
  letter-spacing: .1em;
  margin: 1.4rem 0 .4rem;
}
#content-doc p {
  font-size: .88rem;
  line-height: 1.82;
  color: var(--t2);
  margin-bottom: .75rem;
}
#content-doc ul, #content-doc ol {
  list-style: none;
  margin: .4rem 0 .9rem;
  padding: 0;
}
#content-doc ul li, #content-doc ol li {
  font-size: .86rem;
  line-height: 1.7;
  color: var(--t2);
  padding: 5px 0 5px 16px;
  border-bottom: 1px solid var(--bd);
  position: relative;
}
#content-doc ul li:last-child,
#content-doc ol li:last-child { border-bottom: none; }
#content-doc ul li::before {
  content: "";
  position: absolute;
  left: 0; top: 13px;
  width: 5px; height: 5px;
  border-radius: 50%;
  background: var(--acc);
}
#content-doc ol { counter-reset: lic; }
#content-doc ol li::before {
  content: counter(lic, decimal-leading-zero);
  counter-increment: lic;
  position: absolute;
  left: 0; top: 6px;
  font-family: var(--font-ui);
  font-size: .65rem;
  color: var(--acc);
  font-weight: 500;
}
#content-doc pre {
  background: var(--surface);
  border: 1px solid var(--bd);
  border-left: 3px solid var(--acc);
  padding: 16px 18px;
  border-radius: 1px;
  overflow-x: auto;
  margin: .9rem 0;
  font-family: var(--font-ui);
  font-size: .78rem;
  line-height: 1.75;
  color: var(--t1);
}
#content-doc code {
  font-family: var(--font-ui);
  background: var(--raised);
  color: var(--acc);
  padding: .12em .38em;
  border-radius: 1px;
  font-size: .8em;
  border: 1px solid var(--bd);
}
#content-doc pre code {
  background: none; border: none; color: inherit; padding: 0;
}
#content-doc strong { color: var(--t1); font-weight: 600; }
#content-doc em { color: var(--acc); font-style: normal; }
#content-doc blockquote {
  border-left: 3px solid var(--bd-hi);
  padding: 8px 14px;
  background: var(--raised);
  margin: .9rem 0;
  color: var(--t2);
  font-size: .86rem;
}
#content-doc hr {
  border: none;
  border-top: 1px solid var(--bd);
  margin: 1.8rem 0;
}
#content-doc details {
  border: 1px solid var(--bd);
  border-radius: 1px;
  margin: .9rem 0;
  overflow: hidden;
}
#content-doc summary {
  padding: 9px 13px;
  background: var(--raised);
  cursor: pointer;
  font-family: var(--font-ui);
  font-size: .78rem;
  color: var(--acc);
  list-style: none;
  display: flex;
  align-items: center;
  gap: 7px;
  user-select: none;
}
#content-doc summary::before {
  content: "▶";
  font-size: .5rem;
  transition: transform .15s;
}
#content-doc details[open] summary::before { transform: rotate(90deg); }
#content-doc details > *:not(summary) { padding: 13px; }

/* ── Interactive: Quiz ── */
#content-doc .quiz-block {
  background: var(--raised);
  border: 1px solid var(--bd);
  border-radius: 1px;
  padding: 16px 18px;
  margin: 1.4rem 0;
}
#content-doc .quiz-q {
  font-family: var(--font-ui);
  font-size: .82rem;
  font-weight: 500;
  color: var(--t1);
  margin-bottom: 11px;
  line-height: 1.55;
}
#content-doc .quiz-option {
  display: flex;
  align-items: flex-start;
  gap: 7px;
  padding: 7px 11px;
  border: 1px solid var(--bd);
  border-radius: 1px;
  cursor: pointer;
  margin: 4px 0;
  font-size: .83rem;
  color: var(--t2);
  transition: border-color .1s, color .1s, background .1s;
  user-select: none;
  line-height: 1.5;
}
#content-doc .quiz-option:hover:not([disabled]) {
  border-color: var(--acc);
  color: var(--t1);
}
#content-doc .quiz-option.correct {
  border-color: var(--grn) !important;
  color: var(--grn) !important;
  background: var(--grn-bg) !important;
  pointer-events: none;
}
#content-doc .quiz-option.wrong {
  border-color: var(--red) !important;
  color: var(--red) !important;
  background: var(--red-bg) !important;
  pointer-events: none;
}
#content-doc .quiz-feedback {
  margin-top: 9px;
  padding: 7px 11px;
  font-family: var(--font-ui);
  font-size: .75rem;
  border-radius: 1px;
  display: none;
  line-height: 1.55;
}
#content-doc .quiz-feedback.show { display: block; }
#content-doc .quiz-feedback.ok {
  background: var(--grn-bg);
  color: var(--grn);
  border: 1px solid var(--grn);
}
#content-doc .quiz-feedback.err {
  background: var(--red-bg);
  color: var(--red);
  border: 1px solid var(--red);
}

/* ── Interactive: Flashcard ── */
#content-doc .flashcard-wrap {
  perspective: 900px;
  margin: 1.1rem 0;
}
#content-doc .flashcard {
  position: relative;
  width: 100%;
  min-height: 82px;
  transform-style: preserve-3d;
  transition: transform .32s ease;
  cursor: pointer;
}
#content-doc .flashcard.flipped { transform: rotateY(180deg); }
#content-doc .flashcard-front,
#content-doc .flashcard-back {
  position: absolute;
  width: 100%;
  min-height: 82px;
  backface-visibility: hidden;
  border-radius: 1px;
  padding: 16px 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: .86rem;
  text-align: center;
  line-height: 1.5;
}
#content-doc .flashcard-front {
  background: var(--raised);
  border: 1px solid var(--bd);
  color: var(--t1);
  font-weight: 500;
}
#content-doc .flashcard-back {
  background: var(--acc-bg);
  border: 1px solid var(--acc-bd);
  color: var(--t2);
  transform: rotateY(180deg);
}
#content-doc .flashcard-hint {
  font-family: var(--font-ui);
  font-size: 8px;
  color: var(--t3);
  margin-top: 4px;
  text-align: right;
  letter-spacing: .05em;
}

/* ── Interactive: Term & Chapter ── */
#content-doc .term-card {
  display: inline-block;
  background: var(--acc-bg);
  border: 1px solid var(--acc-bd);
  color: var(--acc);
  font-family: var(--font-ui);
  font-size: .72rem;
  padding: 1px 6px;
  border-radius: 1px;
  margin: 1px 2px;
}
#content-doc .chapter-nav {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin: .7rem 0 1.4rem;
  padding-bottom: 11px;
  border-bottom: 1px solid var(--bd);
}
#content-doc .chapter-pill {
  font-family: var(--font-ui);
  font-size: .68rem;
  padding: 3px 8px;
  border: 1px solid var(--bd);
  color: var(--t3);
  border-radius: 1px;
}
#content-doc .chapter-pill.active {
  background: var(--acc-bg);
  border-color: var(--acc-bd);
  color: var(--acc);
}

/* ── Float Button ── */
#float-btn {
  position: absolute;
  z-index: 999;
  display: none;
  background: var(--acc);
  color: #fff;
  border: none;
  border-radius: 1px;
  padding: 5px 12px;
  font-family: var(--font-ui);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: .06em;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(0,0,0,.35);
}
#float-btn:hover { opacity: .88; }


/* ═══════════════════════════════════════
   MOBILE ADAPTATION
═══════════════════════════════════════ */
#mobile-menu-btn,
#sidebar-mask { display: none; }

@media (max-width: 900px) {
  body { height: 100dvh; overflow: hidden; }

  #mobile-menu-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border: 1px solid var(--bd);
    background: var(--bg);
    color: var(--t2);
    font-family: var(--font-ui);
    font-size: 14px;
    cursor: pointer;
    flex-shrink: 0;
  }

  #sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    width: min(86vw, 320px);
    transform: translateX(-100%);
    transition: transform .2s ease;
    z-index: 1001;
    border-right: 1px solid var(--bd);
  }
  body.sidebar-open #sidebar { transform: translateX(0); }

  #sidebar-mask {
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.48);
    z-index: 1000;
  }
  body.sidebar-open #sidebar-mask { display: block; }

  #main { width: 100%; }
  #topbar {
    padding: 0 12px;
    height: 44px;
  }
  #top-topic { font-size: 13px; }
  #top-status { font-size: 8px; }

  #content-scroll {
    padding: 18px 14px 24px;
  }

  #content-doc h1 { font-size: 1.6rem; }
  #content-doc h2 { font-size: 1.05rem; }

  .item-del { display: block; }
}

</style>
</head>
<body>

<!-- ════════════ SIDEBAR ════════════ -->
<div id="sidebar">
  <div class="sb-top">
    <span class="brand">递归<em>·</em>学习</span>
    <button id="theme-btn">LIGHT</button>
  </div>

  <div class="sb-add">
    <div class="add-row">
      <input type="text" id="topic-input" placeholder="输入主题，回车添加" autocomplete="off">
      <button id="add-btn">+ 添加</button>
    </div>
    <div style="margin-top:8px;font-size:11px;color:var(--t2);font-family:var(--font-ui);display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
      <span id="force-interview-hint">已改为：直接生成，按需澄清</span>
    </div>
  </div>

  <div class="sb-list-top">
    <span class="list-label">学习记录</span>
    <span id="item-count">0 / 32</span>
  </div>

  <div id="item-list"></div>
  <div style="padding:8px 12px;border-top:1px solid var(--bd);font-family:var(--font-ui);font-size:10px;color:var(--t3);">
    API余额：<span id="api-balance">--</span>
  </div>
</div>
<div id="sidebar-mask"></div>

<!-- ════════════ MAIN ════════════ -->
<div id="main">
  <div id="topbar">
    <button id="mobile-menu-btn">☰</button>
    <div id="top-dot"></div>
    <div id="top-topic">选择或添加主题开始学习</div>
    <div id="top-status">—</div>
  </div>
  <div id="content-scroll">
    <div id="content-doc"></div>
    <button id="show-thinking-btn" class="gen-btn" style="display:none;margin-top:14px;">查看生成思考链</button>
    <details id="thinking-panel" style="display:none;margin-top:10px;">
      <summary>生成思考链（只读）</summary>
      <pre id="thinking-text" style="white-space:pre-wrap;background:var(--bg);border:1px solid var(--bd);padding:10px;font-family:var(--font-ui);font-size:12px;"></pre>
    </details>
    <button id="show-clarify-thinking-btn" class="gen-btn" style="display:none;margin-top:14px;">查看歧义判断思考链</button>
    <details id="clarify-thinking-panel" style="display:none;margin-top:10px;">
      <summary>歧义判断思考链（只读）</summary>
      <pre id="clarify-thinking-text" style="white-space:pre-wrap;background:var(--bg);border:1px solid var(--bd);padding:10px;font-family:var(--font-ui);font-size:12px;"></pre>
    </details>
  </div>
  <button id="float-btn">+ 加入队列</button>
</div>
<dialog id="interview-panel" aria-modal="true" style="width:min(92vw,560px);background:var(--surface);border:1px solid var(--bd);padding:14px;">
  <div style="font-family:var(--font-head);font-size:16px;margin-bottom:8px;">学习前追问（三问）</div>
  <div id="interview-topic" style="font-size:12px;color:var(--t2);margin-bottom:10px;"></div>
  <div id="interview-loading" style="display:none;font-size:12px;color:var(--t2);margin-bottom:8px;">AI 正在生成三问选项...</div>
  <div id="interview-questions" style="display:flex;flex-direction:column;gap:8px;">
    <div style="font-size:12px;color:var(--t2);">1) 你当前最想解决的具体问题？</div>
    <select id="interview-a1" style="width:100%;background:var(--bg);border:1px solid var(--bd);color:var(--t1);padding:8px 10px;"></select>
    <div style="font-size:12px;color:var(--t2);">2) 你的已有基础（0基础/入门/进阶）？</div>
    <select id="interview-a2" style="width:100%;background:var(--bg);border:1px solid var(--bd);color:var(--t1);padding:8px 10px;"></select>
    <div style="font-size:12px;color:var(--t2);">3) 你希望内容偏理论、实战还是速览？</div>
    <select id="interview-a3" style="width:100%;background:var(--bg);border:1px solid var(--bd);color:var(--t1);padding:8px 10px;"></select>
  </div>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">
    <button id="interview-submit-btn" class="gen-btn" style="margin:0;">确认并添加</button>
    <button id="interview-cancel-btn" class="gen-btn" style="margin:0;background:var(--t3);">取消</button>
  </div>
</div>
<dialog id="clarify-panel" aria-modal="true" style="width:min(92vw,520px);background:var(--surface);border:1px solid var(--bd);padding:14px;">
  <div style="font-family:var(--font-head);font-size:16px;margin-bottom:8px;">主题可能有歧义</div>
  <div id="clarify-topic" style="font-size:12px;color:var(--t2);margin-bottom:10px;"></div>
  <div id="clarify-options" style="display:flex;flex-direction:column;gap:6px;margin-bottom:10px;"></div>
  <input id="clarify-custom" placeholder="自行补充（可选）" style="width:100%;background:var(--bg);border:1px solid var(--bd);color:var(--t1);padding:8px 10px;margin-bottom:10px;">
  <div style="display:flex;gap:8px;flex-wrap:wrap;">
    <button id="clarify-custom-btn" class="gen-btn" style="margin:0;">使用自行补充</button>
    <button id="clarify-skip-btn" class="gen-btn" style="margin:0;background:var(--t3);">跳过</button>
  </div>
</div>

<script>
// ════════════════════════════════════════
//  STATE & PERSISTENCE
// ════════════════════════════════════════
var STORE_KEY = "rlq_v4";
var MAX = 64;

var items      = [];   // {id,topic,title,isRecursive,status,htmlContent,errorMsg,ts,thinking,clarifyThinking,vocabContext}
var selId      = null; // selected item id
var theme      = "dark";
var nextId     = 1;
var pendingTopic = null;
var forceInterview = false; // deprecated
var pendingClarifyOptions = [];
var pendingClarifyThinking = "";


function isMobile() {
  return window.matchMedia("(max-width: 900px)").matches;
}
function toggleSidebar() {
  document.body.classList.toggle("sidebar-open");
}
function closeSidebar() {
  document.body.classList.remove("sidebar-open");
}

function trimItemsToMax() {
  if (items.length <= MAX) return;
  items = items.slice(0, MAX);
  if (selId !== null && !findItem(selId)) {
    selId = items.length > 0 ? items[0].id : null;
  }
}

function saveState() {
  trimItemsToMax();
  var toSave = items.map(function(it) {
    return {
      id: it.id,
      topic: it.topic,
      title: it.title || it.topic,
      isRecursive: it.isRecursive,
      status: (it.status === "loading" || it.status === "clarify") ? "pending" : it.status,
      htmlContent: it.htmlContent || null,
      errorMsg: it.errorMsg || null,
      ts: it.ts,
      clarifyThinking: (typeof it.clarifyThinking === "string") ? it.clarifyThinking : ""
    };
  });
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify({
      items: toSave, selId: selId, theme: theme, nextId: nextId, forceInterview: forceInterview
    }));
  } catch(e) {}
}

async function syncRecordsToServer() {
  trimItemsToMax();
  try {
    await fetch("/api/records", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: items, selId: selId, theme: theme, nextId: nextId, forceInterview: forceInterview })
    });
  } catch(e) {}
}

async function loadRecordsFromServer() {
  try {
    var res = await fetch("/api/records");
    if (!res.ok) return;
    var d = await res.json();
    if (d && Array.isArray(d.items)) {
      items = d.items; selId = d.selId; theme = d.theme || theme; nextId = d.nextId || nextId; forceInterview = !!d.forceInterview;
      trimItemsToMax();
    }
  } catch(e) {}
}

function loadState() {
  try {
    var raw = localStorage.getItem(STORE_KEY);
    if (!raw) return;
    var d = JSON.parse(raw);
    items  = d.items  || [];
    selId  = (d.selId !== undefined) ? d.selId : null;
    theme  = d.theme  || "dark";
    nextId = d.nextId || items.length + 1;
    forceInterview = !!d.forceInterview;
    trimItemsToMax();
  } catch(e) {}
}

function renderForceInterviewState() {
  var toggle = document.getElementById("force-interview-toggle");
  var hint = document.getElementById("force-interview-hint");
  if (toggle) toggle.checked = false;
  if (hint) hint.textContent = "已改为：直接生成，按需澄清";
}
function toggleForceInterview(checked) {
  forceInterview = !!checked;
  renderForceInterviewState();
  saveState();
  syncRecordsToServer();
}

// ════════════════════════════════════════
//  UTILITIES
// ════════════════════════════════════════
function esc(t) {
  return String(t).replace(/[&<>"']/g, function(c) {
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c];
  });
}
function relTime(ts) {
  var d = Date.now() - ts;
  if (d < 60000)    return "刚刚";
  if (d < 3600000)  return Math.floor(d/60000) + "m前";
  if (d < 86400000) return Math.floor(d/3600000) + "h前";
  return Math.floor(d/86400000) + "d前";
}
function findItem(id) {
  for (var i = 0; i < items.length; i++) if (items[i].id === id) return items[i];
  return null;
}

// Re-execute scripts injected via innerHTML
function runScripts(el) {
  var scripts = el.querySelectorAll("script");
  for (var i = 0; i < scripts.length; i++) {
    var s = document.createElement("script");
    s.textContent = scripts[i].textContent;
    document.head.appendChild(s);
    document.head.removeChild(s);
  }
}

// ════════════════════════════════════════
//  THEME
// ════════════════════════════════════════
function applyTheme() {
  document.documentElement.setAttribute("data-theme", theme);
  document.getElementById("theme-btn").textContent = (theme === "dark") ? "LIGHT" : "DARK";
}
function toggleTheme() {
  theme = (theme === "dark") ? "light" : "dark";
  applyTheme();
  saveState();
}

// ════════════════════════════════════════
//  RENDER SIDEBAR
// ════════════════════════════════════════
function renderSidebar() {
  var listEl = document.getElementById("item-list");
  document.getElementById("item-count").textContent = items.length + " / " + MAX;

  if (items.length === 0) {
    listEl.innerHTML = "<div class=\"list-empty\">暂无记录<br>在上方添加第一个主题</div>";
    return;
  }

  listEl.innerHTML = items.map(function(it) {
    var active = (it.id === selId) ? " selected" : "";
    var dotCls = "dot dot-" + it.status;
    var tagHtml = it.isRecursive
      ? "<span class=\"tag tag-rec\">递归</span>"
      : "<span class=\"tag\">初始</span>";

    return "<div class=\"item-row" + active + "\" data-item-id=\"" + it.id + "\">" +
      "<div class=\"" + dotCls + "\"></div>" +
      "<div class=\"item-body\">" +
        "<div class=\"item-topic\">" + esc(it.title || it.topic) + "</div>" +
        "<div class=\"item-meta\">" + tagHtml +
          "<span class=\"item-time\">" + relTime(it.ts) + "</span>" +
        "</div>" +
      "</div>" +
      "<button class=\"item-del\" data-del-id=\"" + it.id + "\">×</button>" +
      "</div>";
  }).join("");
}

// ════════════════════════════════════════
//  RENDER MAIN CONTENT
// ════════════════════════════════════════
var STATUS_LABEL = {
  pending: "待生成",
  loading: "生成中",
  done:    "已完成",
  error:   "出错"
};

function setTopbar(topic, status) {
  var dot = document.getElementById("top-dot");
  dot.className = status ? ("status-dot " + status) : "";
  // Remove all status classes then add the right one
  dot.classList.remove("loading", "done", "error", "pending");
  if (status) dot.classList.add(status);
  document.getElementById("top-topic").textContent = topic || "选择或添加主题开始学习";
  document.getElementById("top-status").textContent = status ? (STATUS_LABEL[status] || "") : "—";
}

function renderMain() {
  var doc = document.getElementById("content-doc");
  var item = (selId !== null) ? findItem(selId) : null;
  var thinkingBtn = document.getElementById("show-thinking-btn");
  var thinkingPanel = document.getElementById("thinking-panel");
  var thinkingText = document.getElementById("thinking-text");
  var clarifyBtn = document.getElementById("show-clarify-thinking-btn");
  var clarifyPanel = document.getElementById("clarify-thinking-panel");
  var clarifyText = document.getElementById("clarify-thinking-text");

  if (!item) {
    thinkingBtn.style.display = "none";
    thinkingPanel.style.display = "none";
    thinkingPanel.open = false;
    clarifyBtn.style.display = "none";
    clarifyPanel.style.display = "none";
    clarifyPanel.open = false;
    setTopbar(null, null);
    doc.innerHTML =
      "<div class=\"state-screen\">" +
        "<svg class=\"state-icon\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\">" +
          "<path stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"1\" " +
          "d=\"M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13" +
          "C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 " +
          "16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 " +
          "0-3.332.477-4.5 1.253\"/>" +
        "</svg>" +
        "<div class=\"state-title\">递归学习队列</div>" +
        "<div class=\"state-sub\">在左侧输入主题并添加<br>点击任意记录查看内容</div>" +
      "</div>";
    return;
  }

  setTopbar(item.topic, item.status);

  if (item.status === "pending") {
    var hasClarifyOptions = Array.isArray(item.clarifyOptions) && item.clarifyOptions.length > 0;
    thinkingBtn.style.display = "none";
    thinkingPanel.style.display = "none";
    thinkingPanel.open = false;
    clarifyBtn.style.display = "inline-block";
    clarifyPanel.style.display = "none";
    clarifyPanel.open = false;
    clarifyText.textContent = item.clarifyThinking || "该次未返回思考链";
    doc.innerHTML =
      "<div class=\"state-screen\">" +
        "<div class=\"state-title\">" + esc(item.topic) + "</div>" +
        "<div class=\"state-sub\">" + (hasClarifyOptions ? "主题需要先澄清" : "内容尚未生成") + "</div>" +
        (hasClarifyOptions
          ? "<button id=\"open-clarify-btn\" class=\"gen-btn\">选择澄清方向</button>"
          : "<button id=\"generate-btn\" class=\"gen-btn\">生成内容</button>") +
      "</div>";
    return;
  }

  if (item.status === "loading") {
    thinkingBtn.style.display = "none";
    thinkingPanel.style.display = "none";
    thinkingPanel.open = false;
    clarifyBtn.style.display = "none";
    clarifyPanel.style.display = "none";
    clarifyPanel.open = false;
    doc.innerHTML =
      "<div class=\"state-screen\">" +
        "<div class=\"state-sub\">正在生成 <strong>" + esc(item.topic) + "</strong> 的内容…</div>" +
        "<div class=\"skel\">" +
          "<div class=\"skel-line h1\"></div>" +
          "<div class=\"skel-line w100\"></div>" +
          "<div class=\"skel-line w75\"></div>" +
          "<div class=\"skel-line w100\"></div>" +
          "<div class=\"skel-line w55\"></div>" +
          "<div class=\"skel-line w100\"></div>" +
          "<div class=\"skel-line w40\"></div>" +
        "</div>" +
      "</div>";
    return;
  }

  if (item.status === "done") {
    doc.innerHTML = item.htmlContent || "";
    thinkingBtn.style.display = item.thinking ? "inline-block" : "none";
    thinkingPanel.style.display = "none";
    thinkingPanel.open = false;
    thinkingText.textContent = item.thinking || "该次未返回思考链";
    clarifyBtn.style.display = "inline-block";
    clarifyPanel.style.display = "none";
    clarifyPanel.open = false;
    clarifyText.textContent = item.clarifyThinking || "该次未返回思考链";
    runScripts(doc);
    document.getElementById("content-scroll").scrollTo({ top: 0, behavior: "smooth" });
    return;
  }
  thinkingBtn.style.display = "none";
  thinkingPanel.style.display = "none";
  thinkingPanel.open = false;
  clarifyBtn.style.display = "none";
  clarifyPanel.style.display = "none";
  clarifyPanel.open = false;

  if (item.status === "error") {
    doc.innerHTML =
      "<div class=\"state-screen\">" +
        "<div class=\"err-box\">" +
          "<p>生成失败：" + esc(item.errorMsg || "未知错误") + "</p>" +
          "<button id=\"retry-btn\" class=\"retry-btn\">重试</button>" +
        "</div>" +
      "</div>";
    return;
  }
}

// ════════════════════════════════════════
//  GENERATE
// ════════════════════════════════════════
async function generateSelected() {
  if (selId === null) return;
  var item = findItem(selId);
  if (!item || item.status === "loading") return;

  item.status = "loading";
  item.htmlContent = null;
  item.errorMsg = null;
  item.clarifyOptions = [];
  renderSidebar();
  renderMain();
  saveState();

  try {
    var res = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        topic: item.topic,
        isRecursive: item.isRecursive,
        vocabContext: item.vocabContext || "",
        learningContext: item.learningContext || null
      })
    });
    if (!res.ok) {
      var e = await res.json().catch(function() { return { detail: "未知错误" }; });
      throw new Error(e.detail || "请求失败 (" + res.status + ")");
    }
    var data = await res.json();
    if (Array.isArray(data.options) && data.options.length) {
      item.status = "pending";
      item.clarifyOptions = data.options.slice(0,5);
      item.clarifyThinking = data.thinking || "";
      pendingClarifyThinking = item.clarifyThinking;
      renderSidebar();
      if (selId === item.id) renderMain();
      saveState();
      syncRecordsToServer();
      openClarifyPanel(item.topic, data.options.slice(0,5));
      return;
    }
    if (!data.htmlContent) throw new Error("生成内容为空");
    item.status = "done";
    item.htmlContent = data.htmlContent;
    item.thinking = data.thinking || "";
    item.clarifyOptions = [];
    if (data.title) item.title = data.title;
    refreshBalance();
  } catch(err) {
    item.status = "error";
    item.errorMsg = err.message;
  }

  renderSidebar();
  if (selId === item.id) renderMain();
  saveState();
  syncRecordsToServer();
}

// ════════════════════════════════════════
//  ADD / SELECT / DELETE
// ════════════════════════════════════════
function addItem(topic, isRecursive, learningContext, clarifyThinking) {
  topic = topic.trim();
  if (!topic) return;

  // Enforce MAX: evict oldest done, otherwise oldest non-loading
  if (items.length >= MAX) {
    var evictIdx = -1;
    for (var i = items.length - 1; i >= 0; i--) {
      if (items[i].status === "done")    { evictIdx = i; break; }
    }
    if (evictIdx < 0) {
      for (var i = items.length - 1; i >= 0; i--) {
        if (items[i].status !== "loading") { evictIdx = i; break; }
      }
    }
    if (evictIdx >= 0) {
      if (items[evictIdx].id === selId) selId = null;
      items.splice(evictIdx, 1);
    }
  }

  var it = {
    id: nextId++,
    topic: topic,
    title: topic,
    isRecursive: !!isRecursive,
    status: "pending",
    htmlContent: null,
    errorMsg: null,
    ts: Date.now(),
    learningContext: learningContext || null,
    clarifyThinking: (typeof clarifyThinking === "string") ? clarifyThinking : "",
    clarifyOptions: []
  };
  items.unshift(it);
  selId = it.id;

  renderSidebar();
  renderMain();
  saveState();
  syncRecordsToServer();
  generateSelected();
}

function selectItem(id) {
  if (isMobile()) closeSidebar();
  selId = id;
  renderSidebar();
  renderMain();
  saveState();
}

function delItem(e, id) {
  items = items.filter(function(it) { return it.id !== id; });
  if (selId === id) selId = items.length > 0 ? items[0].id : null;
  renderSidebar();
  renderMain();
  saveState();
  syncRecordsToServer();
}

function openClarifyPanel(topic, options) {
  pendingTopic = topic;
  document.getElementById("clarify-topic").textContent = "原主题：" + topic;
  var box = document.getElementById("clarify-options");
  box.innerHTML = "";
  options.forEach(function(op) {
    var btn = document.createElement("button");
    btn.className = "gen-btn";
    btn.style.margin = "0";
    btn.style.textAlign = "left";
    btn.textContent = op;
    btn.type = "button";
    btn.addEventListener("click", function() { selectClarifyOption(op); });
    box.appendChild(btn);
  });
  var panel = document.getElementById("clarify-panel");
  document.getElementById("clarify-custom").value = "";
  panel.showModal();
  trapFocus(panel);
}

function closeClarifyPanel() {
  closeDialog(document.getElementById("clarify-panel"));
}

function selectClarifyOption(val) {
  if (!pendingTopic) return;
  var it = (selId !== null) ? findItem(selId) : null;
  if (!it) return;
  it.learningContext = it.learningContext || {};
  it.learningContext.clarifyHistory = Array.isArray(it.learningContext.clarifyHistory) ? it.learningContext.clarifyHistory : [];
  it.learningContext.clarifyHistory.push({type:"option", value: val});
  it.status = "pending"; it.errorMsg = null; it.topic = pendingTopic;
  renderSidebar(); renderMain(); generateSelected();
  closeClarifyPanel();
  pendingTopic = null;
  pendingClarifyThinking = "";
}

function submitClarifyCustom() {
  if (!pendingTopic) return;
  var custom = document.getElementById("clarify-custom").value.trim();
  var it = (selId !== null) ? findItem(selId) : null;
  if (!it) return;
  it.learningContext = it.learningContext || {};
  it.learningContext.clarifyHistory = Array.isArray(it.learningContext.clarifyHistory) ? it.learningContext.clarifyHistory : [];
  it.learningContext.clarifyHistory.push({type:"custom", value: (custom || pendingTopic)});
  it.status = "pending"; it.errorMsg = null; it.topic = pendingTopic;
  renderSidebar(); renderMain(); generateSelected();
  closeClarifyPanel();
  pendingTopic = null;
  pendingClarifyThinking = "";
}

function skipClarify() {
  if (!pendingTopic) return;
  if (forceInterview) {
    openInterviewPanel(pendingTopic, pendingClarifyOptions);
  } else {
    addItem(pendingTopic, false, null, pendingClarifyThinking);
  }
  closeClarifyPanel();
  pendingTopic = null;
  pendingClarifyOptions = [];
  pendingClarifyThinking = "";
}


function fillInterviewSelect(elId, options, fallbackOptions) {
  var el = document.getElementById(elId);
  if (!el) return;
  var opts = (Array.isArray(options) && options.length) ? options : fallbackOptions;
  el.innerHTML = "";
  opts.forEach(function(op) {
    var o = document.createElement("option");
    o.value = op;
    o.textContent = op;
    el.appendChild(o);
  });
}

async function prepareInterviewOptions(topic, clarifyOptions) {
  var loading = document.getElementById("interview-loading");
  loading.style.display = "block";
  var fallback = {
    q1: ["快速入门并能马上动手","先理解核心概念再实践","解决一个真实场景问题"],
    q2: ["0基础","入门","进阶"],
    q3: ["偏理论","偏实战","先速览后深入"]
  };
  try {
    var res = await fetch("/api/interview-options", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic: topic, clarifyOptions: clarifyOptions || [] })
    });
    if (res.ok) {
      var data = await res.json();
      fillInterviewSelect("interview-a1", data.q1, fallback.q1);
      fillInterviewSelect("interview-a2", data.q2, fallback.q2);
      fillInterviewSelect("interview-a3", data.q3, fallback.q3);
      loading.style.display = "none";
      return;
    }
  } catch(e) {}
  fillInterviewSelect("interview-a1", null, fallback.q1);
  fillInterviewSelect("interview-a2", null, fallback.q2);
  fillInterviewSelect("interview-a3", null, fallback.q3);
  loading.style.display = "none";
}

function openInterviewPanel(topic, clarifyOptions) {
  pendingTopic = topic;
  pendingClarifyOptions = Array.isArray(clarifyOptions) ? clarifyOptions.slice(0, 5) : [];
  document.getElementById("interview-topic").textContent = "主题：" + topic + (pendingClarifyOptions.length ? (" ｜ 可选澄清：" + pendingClarifyOptions.join(" / ")) : "");
  prepareInterviewOptions(topic, pendingClarifyOptions);
  var panel = document.getElementById("interview-panel");
  panel.showModal();
  trapFocus(panel);
}

function closeInterviewPanel() {
  closeDialog(document.getElementById("interview-panel"));
}

function submitInterviewAnswers() {
  if (!pendingTopic) return;
  var learningContext = {
    clarifyOptions: pendingClarifyOptions,
    q1: document.getElementById("interview-a1").value.trim(),
    q2: document.getElementById("interview-a2").value.trim(),
    q3: document.getElementById("interview-a3").value.trim()
  };
  addItem(pendingTopic, false, learningContext, pendingClarifyThinking);
  closeInterviewPanel();
  pendingTopic = null;
  pendingClarifyOptions = [];
  pendingClarifyThinking = "";
}

async function handleAdd() {
  if (isMobile()) closeSidebar();
  var inp = document.getElementById("topic-input");
  var v = inp.value.trim();
  if (!v) return;
  inp.value = "";
  addItem(v, false, { clarifyHistory: [] }, "");
}

document.getElementById("topic-input").addEventListener("keypress", function(e) {
  if (e.key === "Enter") { e.preventDefault(); handleAdd(); }
});

function closeDialog(panel) {
  if (panel && panel.open) panel.close();
}

function trapFocus(panel) {
  var focusables = panel.querySelectorAll("button, input, [href], select, textarea, [tabindex]:not([tabindex='-1'])");
  if (!focusables.length) return;
  focusables[0].focus();
  panel.onkeydown = function(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      if (panel.id === "clarify-panel") closeClarifyPanel();
      if (panel.id === "interview-panel") closeInterviewPanel();
      return;
    }
    if (e.key === "Enter" && panel.id === "interview-panel") {
      e.preventDefault();
      submitInterviewAnswers();
      return;
    }
    if (e.key === "Enter" && panel.id === "clarify-panel") {
      e.preventDefault();
      submitClarifyCustom();
      return;
    }
    if (e.key !== "Tab") return;
    var nodes = panel.querySelectorAll("button, input, [href], select, textarea, [tabindex]:not([tabindex='-1'])");
    var first = nodes[0], last = nodes[nodes.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault(); first.focus();
    }
  };
}

// ════════════════════════════════════════
//  FLOAT SELECT-TO-QUEUE BUTTON
// ════════════════════════════════════════
var floatBtn = document.getElementById("float-btn");

function hideFloat() { floatBtn.style.display = "none"; }

function floatClick() {
  var text = floatBtn.dataset.seltext;
  if (text) addItem(text, true);
  hideFloat();
  window.getSelection().removeAllRanges();
}

document.getElementById("theme-btn").addEventListener("click", toggleTheme);
document.getElementById("add-btn").addEventListener("click", handleAdd);

document.getElementById("sidebar-mask").addEventListener("click", closeSidebar);
document.getElementById("mobile-menu-btn").addEventListener("click", toggleSidebar);
document.getElementById("show-thinking-btn").addEventListener("click", showThinking);
document.getElementById("show-clarify-thinking-btn").addEventListener("click", toggleClarifyThinking);
document.getElementById("float-btn").addEventListener("click", floatClick);
document.getElementById("clarify-custom-btn").addEventListener("click", submitClarifyCustom);
document.getElementById("clarify-skip-btn").addEventListener("click", skipClarify);
document.getElementById("interview-submit-btn").addEventListener("click", submitInterviewAnswers);
document.getElementById("interview-cancel-btn").addEventListener("click", closeInterviewPanel);
document.getElementById("item-list").addEventListener("click", function(e) {
  var delBtn = e.target.closest(".item-del");
  if (delBtn) {
    e.stopPropagation();
    delItem(e, Number(delBtn.dataset.delId));
    return;
  }
  var row = e.target.closest(".item-row");
  if (row) selectItem(Number(row.dataset.itemId));
});
document.getElementById("content-doc").addEventListener("click", function(e) {
  var actionBtn = e.target.closest("#generate-btn, #retry-btn, #open-clarify-btn");
  if (!actionBtn) return;

  if (actionBtn.id === "generate-btn" || actionBtn.id === "retry-btn") {
    generateSelected();
    return;
  }

  var current = (selId !== null) ? findItem(selId) : null;
  if (current && Array.isArray(current.clarifyOptions) && current.clarifyOptions.length) {
    pendingClarifyThinking = current.clarifyThinking || "";
    openClarifyPanel(current.topic, current.clarifyOptions);
  }
});

document.getElementById("content-scroll").addEventListener("mouseup", function() {
  setTimeout(function() {
    var sel = window.getSelection();
    var text = sel ? sel.toString().trim() : "";
    if (!text || !sel || sel.rangeCount === 0) { hideFloat(); return; }
    var range = sel.getRangeAt(0);
    var doc = document.getElementById("content-doc");
    if (!doc || !doc.contains(range.commonAncestorContainer)) { hideFloat(); return; }

    var rect = range.getBoundingClientRect();
    var mainEl = document.getElementById("main");
    var mr = mainEl.getBoundingClientRect();

    floatBtn.style.display = "block";
    floatBtn.style.left = (rect.left - mr.left + rect.width / 2 - 48) + "px";
    floatBtn.style.top  = (rect.bottom - mr.top + 6) + "px";
    floatBtn.dataset.seltext = text;
  }, 10);
});

document.addEventListener("mousedown", function(e) {
  if (e.target !== floatBtn) hideFloat();
});

// ════════════════════════════════════════
//  GLOBAL QUIZ HANDLER
// ════════════════════════════════════════
window.quizPick = function(el, type) {
  var block = el.closest(".quiz-block");
  if (!block || block.dataset.done) return;
  block.dataset.done = "1";
  block.querySelectorAll(".quiz-option").forEach(function(o) {
    o.style.pointerEvents = "none";
  });
  el.classList.add(type === "correct" ? "correct" : "wrong");
  var fbClass = type === "correct" ? ".quiz-feedback.ok" : ".quiz-feedback.err";
  var fb = block.querySelector(fbClass);
  if (fb) fb.classList.add("show");
};
document.getElementById("content-doc").addEventListener("click", function(e) {
  var opt = e.target.closest(".quiz-option[data-answer]");
  if (opt) {
    window.quizPick(opt, opt.dataset.answer);
    return;
  }
  var card = e.target.closest(".flashcard");
  if (card) card.classList.toggle("flipped");
});

function showThinking() {
  var item = (selId !== null) ? findItem(selId) : null;
  if (!item) return;
  var panel = document.getElementById("thinking-panel");
  var text = document.getElementById("thinking-text");
  text.textContent = item.thinking || "该次未返回思考链";
  panel.style.display = "block";
  panel.open = !panel.open;
}

function toggleClarifyThinking() {
  var item = (selId !== null) ? findItem(selId) : null;
  if (!item) return;
  var panel = document.getElementById("clarify-thinking-panel");
  var text = document.getElementById("clarify-thinking-text");
  text.textContent = item.clarifyThinking || "该次未返回思考链";
  panel.style.display = "block";
  panel.open = !panel.open;
}

async function refreshBalance() {
  try {
    var res = await fetch("/api/balance");
    var d = await res.json();
    document.getElementById("api-balance").textContent = d.balance || "--";
  } catch(e) {
    document.getElementById("api-balance").textContent = "--";
  }
}

// ════════════════════════════════════════
//  INIT
// ════════════════════════════════════════
(async function init() {
  loadState();
  await loadRecordsFromServer();
  applyTheme();
  renderForceInterviewState();
  renderSidebar();
  renderMain();
  refreshBalance();
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_cache_key(topic: str, is_recursive: bool, vocab_context: str = "", learning_context: dict | None = None) -> str:
    """流程名：内容缓存键生成流程｜为同一请求参数生成稳定缓存键。"""
    learning_sig = json.dumps(learning_context or {}, ensure_ascii=False, sort_keys=True)
    return hashlib.md5(f"{topic}|{is_recursive}|{vocab_context}|{learning_sig}".encode()).hexdigest()


def normalize_records_payload(payload: dict | None) -> dict:
    """流程名：记录归一化流程｜校验并修正前端状态快照结构。"""
    if not isinstance(payload, dict):
        return {"items": [], "selId": None, "theme": "dark", "nextId": 1, "forceInterview": False}

    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    items = items[:MAX_RECENT_PAGES]
    sel_id = payload.get("selId")
    if sel_id is not None and not any(it.get("id") == sel_id for it in items if isinstance(it, dict)):
        sel_id = items[0].get("id") if items and isinstance(items[0], dict) else None

    next_id = payload.get("nextId")
    if not isinstance(next_id, int) or next_id <= 0:
        next_id = len(items) + 1

    theme = payload.get("theme") if isinstance(payload.get("theme"), str) else "dark"
    force_interview = bool(payload.get("forceInterview"))
    return {"items": items, "selId": sel_id, "theme": theme, "nextId": next_id, "forceInterview": force_interview}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index():
    """流程名：主页渲染流程｜返回单页应用 HTML 模板。"""
    return HTML_TEMPLATE


@app.post("/api/generate")
async def generate(req: Request):
    """主流程D：内容生成管线（校验 -> 缓存 -> 组 Prompt -> 调模型 -> 解析返回）。"""
    # 步骤 D1：解析并校验请求体。
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"detail": "请求体必须是合法JSON"}, status_code=400)

    topic = body.get("topic")
    is_recursive = body.get("isRecursive", False)
    if not topic or not isinstance(topic, str):
        return JSONResponse({"detail": "缺少 topic 参数"}, status_code=400)

    # 步骤 D2：计算缓存键并执行命中短路。
    vocab_context = body.get("vocabContext", "")
    learning_context = body.get("learningContext") if isinstance(body.get("learningContext"), dict) else {}
    cache_key = get_cache_key(topic, is_recursive, vocab_context, learning_context)
    if cache_key in _cache:
        return JSONResponse(_cache[cache_key])

    # 步骤 D3：准备系统提示词模板。
    # ── System Prompt ──────────────────────────────────────────────────────
    system_prompt = """你是一个出色的自适应学习内容生成器，生成结构清晰、富含互动元素的学习页面HTML片段。

页面已有完整设计系统，请严格使用以下CSS变量和类，禁止用内联style定义颜色或字体：

CSS变量（深色/浅色主题自动切换）：
  --bg, --surface, --raised, --bd, --bd-hi
  --t1（主文）、--t2（次文）、--t3（弱文）
  --acc（强调蓝）、--acc-bg、--acc-bd
  --grn、--grn-bg、--red、--red-bg、--amb、--amb-bg
字体变量：--font-ui（IBM Plex Mono）、--font-body（IBM Plex Sans）、--font-head（Barlow Condensed）

内置样式的标签（直接使用，无需额外class）：
h1 h2 h3 p ul ol li code pre blockquote hr details/summary

互动组件（CSS已内置，按模板使用）：

【A. 单选测验】每篇至少1道，用全局函数 quizPick(el, 'correct'|'wrong')，不要定义此函数：
<div class="quiz-block">
  <div class="quiz-q">❓ 问题文字</div>
  <button class="quiz-option" type="button" data-answer="correct">A. 正确答案文字</button>
  <button class="quiz-option" type="button" data-answer="wrong">B. 错误选项文字</button>
  <button class="quiz-option" type="button" data-answer="wrong">C. 错误选项文字</button>
  <div class="quiz-feedback ok">✅ 正确！一句话解释原因。</div>
  <div class="quiz-feedback err">❌ 错误。正确答案是A，因为……</div>
</div>

【B. 翻转闪卡】每篇至少2张，使用 .flashcard 元素（点击行为由全局事件代理处理）：
<div class="flashcard-wrap">
  <div class="flashcard" role="button" tabindex="0" aria-label="翻转闪卡">
    <div class="flashcard-front">正面：概念或问题</div>
    <div class="flashcard-back">背面：定义或答案</div>
  </div>
  <div class="flashcard-hint">点击翻转</div>
</div>

【C. 可折叠深度内容】用details/summary（已内置样式）：
<details><summary>展开了解更多：副标题</summary><p>补充内容…</p></details>

【D. 关键术语标签】行内使用：
文中关键词用 <span class="term-card">术语</span> 标注（每篇3-6个）

【E. 章节导航】放在h1之后、正文之前：
<div class="chapter-nav">
  <span class="chapter-pill active">§1 简介</span>
  <span class="chapter-pill">§2 核心概念</span>
  <span class="chapter-pill">§3 应用</span>
</div>

【输出规则】
1. 严格输出JSON：{"htmlContent": "..."}
2. 首行必须是 <h1>主题名</h1>，紧接chapter-nav
3. 禁止包含<script>标签，交互通过 data-answer 与 .flashcard 事件代理完成
4. 禁止重定义任何CSS变量或已有class
5. 禁止使用内联style设置颜色、字体（可用内联style设置宽度/margin等布局属性）
6. 所有文字内容用中文，代码和专有名词保留英文
7. 递归模式（isRecursive=true）：聚焦主题本身，内容自足，300-600字，闪卡1-2张，测验1道
8. 初始模式（isRecursive=false）：展开背景+原理+应用，600-1200字，闪卡2-3张，测验1-2道，details至少1个
9. 若用户主题或上下文存在关键歧义，先不要生成正文，返回 options 包（2-5个候选）
"""

    # 步骤 D4：根据递归层级构造用户提示词。
    level = recursive_level(topic) if is_recursive else 0
    clarify_history = learning_context.get("clarifyHistory", []) if isinstance(learning_context, dict) else []
    interview_context = "无"
    if learning_context:
        interview_context = (
            f"澄清候选：{', '.join(learning_context.get('clarifyOptions', [])) or '无'}；"
            f"问题1：{learning_context.get('q1') or '未填写'}；"
            f"问题2：{learning_context.get('q2') or '未填写'}；"
            f"问题3：{learning_context.get('q3') or '未填写'}"
        )
    user_prompt = f"主题：{topic}\n递归模式：{'是' if is_recursive else '否'}\n{build_vocab_rule(level)}\n生词上下文：{vocab_context or '无'}\n学习者追问上下文：{interview_context}\n历史澄清上下文：{json.dumps(clarify_history, ensure_ascii=False)}\n若仍有歧义请返回 options 包，否则返回 htmlContent 包。"

    # 步骤 D5：调用模型并解析标准 JSON 返回。
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "enabled"}},
            max_tokens=4096,
        )
        msg = response.choices[0].message
        raw = msg.content.strip()
        result = json.loads(raw)
        options = result.get("options") if isinstance(result, dict) else None
        if isinstance(options, list) and options:
            options = [str(x).strip() for x in options if str(x).strip()][:5]
            if options:
                return JSONResponse({"options": options, "thinking": getattr(msg, "reasoning_content", "") or ""})
        html_content = result.get("htmlContent", "")
        if not html_content:
            raise ValueError("模型返回内容既非htmlContent也非options")
        thinking = ""
        if hasattr(msg, "reasoning_content"):
            thinking = msg.reasoning_content or ""
        title = gen_title_from_html(html_content)
        payload = {"htmlContent": html_content, "thinking": thinking, "title": title}
        _cache[cache_key] = payload
        return JSONResponse(payload)

    # Step 5/5：异常兜底（格式恢复 / API错误 / 未知错误）
    except json.JSONDecodeError:
        # 步骤 D6（降级）：尝试从包裹文本中抽取 JSON。
        if raw:
            try:
                s, e = raw.find("{"), raw.rfind("}")
                if s != -1 and e != -1:
                    result = json.loads(raw[s:e+1])
                    html_content = result.get("htmlContent", "")
                    if html_content:
                        payload = {"htmlContent": html_content, "thinking": "", "title": gen_title_from_html(html_content)}
                        _cache[cache_key] = payload
                        return JSONResponse(payload)
            except Exception:
                pass
        return JSONResponse({"detail": "生成内容格式错误，请重试"}, status_code=500)

    except openai.APIError as e:
        return JSONResponse({"detail": f"API调用失败: {e}"}, status_code=502)

    except Exception as e:
        return JSONResponse({"detail": f"服务内部错误: {str(e)}"}, status_code=500)


def recursive_level(topic: str) -> int:
    """流程名：递归层级识别流程｜根据括号层级估算递归深度。"""
    return topic.count("（") + topic.count("(")


def build_vocab_rule(level: int) -> str:
    """流程名：词汇约束生成流程｜按递归层级生成生词控制规则。"""
    if level <= 0:
        return "递归层级0：没有对生词的限制。"
    if level == 1:
        return "递归层级1：尽量减少生词，出现时要立即解释。"
    if level == 2:
        return "递归层级2：全局最多允许3个生词，并在首次出现处解释。"
    return "递归层级3及以上：不得出现生词，必须只用常见表达。"


def gen_title_from_html(html: str) -> str:
    """流程名：标题摘要流程｜从 HTML 文本中抽取简短标题。"""
    txt = re.sub(r"<[^>]+>", " ", html)
    txt = re.sub(r"\s+", " ", txt).strip()
    return (txt[:18] + "…") if len(txt) > 18 else txt

def parse_json_object_from_text(raw: str) -> dict:
    """流程名：JSON恢复流程｜从模型文本中提取首个JSON对象。"""
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            obj = json.loads(text[s:e+1])
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}

@app.get("/api/records")
async def get_records():
    """流程名：学习记录读取流程｜读取并归一化持久化状态。"""
    if not os.path.exists(RECORDS_PATH):
        return JSONResponse({"items": [], "selId": None, "theme": "dark", "nextId": 1})
    with open(RECORDS_PATH, "r", encoding="utf-8") as f:
        return JSONResponse(normalize_records_payload(json.load(f)))


@app.put("/api/records")
async def put_records(req: Request):
    """流程名：学习记录保存流程｜接收前端状态并写入本地存储。"""
    payload = normalize_records_payload(await req.json())
    with open(RECORDS_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return JSONResponse({"ok": True})


@app.get("/api/balance")
async def get_balance():
    """流程J：查询并返回 DeepSeek 账户余额。"""
    api_key = load_api_key()
    if not api_key:
        return JSONResponse({"balance": "--"})
    try:
        r = requests.get("https://api.deepseek.com/user/balance", headers={"Authorization": f"Bearer {api_key}"}, timeout=8)
        data = r.json()
        bal = str(data.get("balance_infos", [{}])[0].get("total_balance", "--"))
        return JSONResponse({"balance": bal})
    except Exception:
        return JSONResponse({"balance": "--"})


@app.api_route("/api/topic-clarify", methods=["GET", "HEAD"])
async def topic_clarify_probe():
    """流程名：主题消歧探活流程｜用于探针请求，避免 GET/HEAD 405 告警。"""
    return JSONResponse({"ok": True, "method": "POST", "detail": "Use POST with JSON body: {\"topic\": \"...\"}"})


@app.post("/api/topic-clarify")
async def topic_clarify(req: Request):
    """流程名：主题消歧流程｜识别主题歧义并返回候选语境。"""
    # Step 1/5：请求解析与基础校验
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"options": []})
    topic = (body.get("topic") or "").strip()
    if not topic:
        return JSONResponse({"options": []})
    prompt = (
        "你需要判断用户主题是否可能存在多种常见含义。"
        "返回JSON：{\"options\":[\"候选1\",...]}\n"
        "规则：1) 最多5个；2) 仅返回与该主题可能混淆的不同语境表达；"
        "3) 若无明显歧义返回空数组；4) 所有选项简洁。"
        f"\n主题：{topic}"
    )
    # Step 4/5：调用模型并解析结构化结果
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "enabled"}},
            max_tokens=300,
        )
        msg = response.choices[0].message
        data = parse_json_object_from_text((msg.content or ""))
        options = data.get("options") if isinstance(data, dict) else []
        if not isinstance(options, list):
            options = []
        options = [str(x).strip() for x in options if str(x).strip()][:5]
        thinking = ""
        if hasattr(msg, "reasoning_content"):
            thinking = msg.reasoning_content or ""
        return JSONResponse({"options": options, "thinking": thinking})
    except openai.APIError as e:
        return JSONResponse({"options": [], "thinking": "", "detail": f"API调用失败: {e}"}, status_code=502)
    except Exception as e:
        return JSONResponse({"options": [], "thinking": "", "detail": f"服务内部错误: {str(e)}"}, status_code=500)


@app.post("/api/interview-options")
async def interview_options(req: Request):
    """流程名：三问选项生成流程｜根据主题生成每问3个可选项。"""
    try:
        body = await req.json()
    except Exception:
        return JSONResponse({"q1": [], "q2": [], "q3": []})
    topic = (body.get("topic") or "").strip()
    clarify_options = body.get("clarifyOptions") if isinstance(body.get("clarifyOptions"), list) else []
    prompt = (
        "请基于学习主题生成学习前追问的选项，返回JSON："
        '{"q1":["...","...","..."],"q2":["...","...","..."],"q3":["...","...","..."]}。'
        "要求：每个数组恰好3个简洁中文选项；q1聚焦学习目标，q2聚焦基础水平，q3聚焦学习偏好。"
        f"\n主题：{topic}\n候选澄清：{', '.join([str(x) for x in clarify_options[:5]]) or '无'}"
    )
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=300,
        )
        data = json.loads(response.choices[0].message.content.strip())
        out = {}
        for k in ["q1", "q2", "q3"]:
            vals = data.get(k) if isinstance(data, dict) else []
            vals = [str(x).strip() for x in (vals if isinstance(vals, list) else []) if str(x).strip()][:3]
            out[k] = vals
        return JSONResponse(out)
    except Exception:
        return JSONResponse({"q1": [], "q2": [], "q3": []})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
