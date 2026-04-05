"""
SEO Article Generator - Web App
FastAPI + Anthropic Streaming
"""

import json
import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="SEO Article Generator")

STATIC_DIR = Path(__file__).parent / "static"


class GenerateRequest(BaseModel):
    keyword: str
    length: int = 2000
    tone: str = "professional"  # professional / casual / academic


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY が設定されていません")

    tone_map = {
        "professional": "丁寧でプロフェッショナルな文体",
        "casual": "親しみやすくカジュアルな文体",
        "academic": "権威ある学術的な文体",
    }
    tone_desc = tone_map.get(req.tone, tone_map["professional"])

    prompt = f"""あなたはSEOの専門家兼Webライターです。
以下の条件でSEO上位表示を狙ったMarkdown形式の記事を執筆してください。

## 条件
- メインキーワード: {req.keyword}
- 目標文字数: {req.length}文字
- 文体: {tone_desc}

## SEO要件（必ず守ること）
1. H1タイトルにメインキーワードを含める（35文字前後）
2. 冒頭100文字以内にメインキーワードを自然に入れる
3. H2見出しを5〜7個設ける
4. 各H2にH3を2〜3個ずつ付ける
5. LSIキーワード・共起語を本文に自然に散りばめる
6. 結論セクションでCTA（行動喚起）を入れる
7. 読者の悩みに寄り添い、解決策を具体的に示す

## 出力形式
以下の順序でMarkdownを出力してください:

1. まず冒頭に以下のメタ情報をコメントとして記述:
<!-- META
title: (H1タイトル)
description: (メタディスクリプション120文字以内)
keywords: (関連キーワード5〜8個、カンマ区切り)
-->

2. 記事本文（Markdown形式）

記事本文のみ出力してください。前置き・説明・コメントは不要です。"""

    client = anthropic.Anthropic(api_key=api_key)

    def stream():
        try:
            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=5000,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except anthropic.AuthenticationError:
            yield f"data: {json.dumps({'error': 'APIキーが無効です。.envファイルを確認してください。'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
