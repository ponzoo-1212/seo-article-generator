"""
SEO Article Generator - Web App
競合分析 + E-E-A-T + FAQ + Schema.org + Unsplash画像
"""

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

import anthropic
from duckduckgo_search import DDGS
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
    tone: str = "professional"


class ImageRequest(BaseModel):
    keyword: str
    article_body: str


# ── 競合検索 ──────────────────────────────────────────

def search_competitors(keyword: str, num: int = 5) -> list[dict]:
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(keyword, max_results=num):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "description": r.get("body", ""),
                })
    except Exception:
        pass
    return results


def build_competitor_summary(competitors: list[dict]) -> str:
    if not competitors:
        return "競合データなし"
    lines = []
    for i, c in enumerate(competitors, 1):
        lines.append(f"{i}. 【{c['title']}】")
        lines.append(f"   URL: {c['url']}")
        lines.append(f"   概要: {c['description'][:120]}...")
    return "\n".join(lines)


# ── Unsplash 画像検索 ──────────────────────────────────

def search_unsplash(query: str, orientation: str = "landscape", count: int = 1) -> list[dict]:
    """Unsplash APIで高品質画像を検索する"""
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    if not access_key:
        return []
    url = (
        "https://api.unsplash.com/search/photos"
        f"?query={urllib.parse.quote(query)}"
        f"&orientation={orientation}"
        f"&per_page={count}"
        f"&client_id={access_key}"
    )
    try:
        req = urllib.request.Request(url, headers={"Accept-Version": "v1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        results = []
        for photo in data.get("results", []):
            results.append({
                "display": photo["urls"]["regular"],
                "full": photo["urls"]["full"],
                "page": photo["links"]["html"],
                "author": photo["user"]["name"],
            })
        return results
    except Exception:
        return []


# ── エンドポイント ─────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


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
    client = anthropic.Anthropic(api_key=api_key)

    def stream():
        yield f"data: {json.dumps({'phase': 'searching'}, ensure_ascii=False)}\n\n"
        competitors = search_competitors(req.keyword)
        competitor_summary = build_competitor_summary(competitors)
        yield f"data: {json.dumps({'phase': 'competitors', 'data': competitors}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'phase': 'writing'}, ensure_ascii=False)}\n\n"

        prompt = f"""あなたはSEOの専門家兼Webライターです。
Googleのアルゴリズムに最大限対応し、検索上位表示を狙った記事を執筆してください。

## 基本条件
- メインキーワード: {req.keyword}
- 目標文字数: {req.length}文字
- 文体: {tone_desc}

## 競合サイト分析（上位{len(competitors)}件）
{competitor_summary}

競合を上回るために:
- 競合が触れていない角度・情報を盛り込む
- より具体的・網羅的な内容にする
- 独自の視点・体験談・事例を追加する

## Google アルゴリズム対応要件

### E-E-A-T（必須）
- **Experience（経験）**: 実体験・具体的なエピソードを含める
- **Expertise（専門性）**: 専門用語を正確に使い、数字・データで裏付ける
- **Authoritativeness（権威性）**: 信頼できる情報源・統計データを引用
- **Trustworthiness（信頼性）**: 正確な情報、根拠明示、デメリットも公平に記載

### Helpful Content Update 対応
- 検索者の悩みを完全に解決する「一次情報」を提供
- AI生成っぽい表現を避け、人間味のある文章にする
- 「なぜ」「どうやって」「いくら」など具体的な疑問に答える
- 読後に「この記事を読んでよかった」と思える付加価値を入れる

### 構造化・セマンティックSEO
- H1にメインキーワードを含める（35文字前後）
- H2見出しに検索される疑問形フレーズを使う
- LSIキーワード・共起語を自然に本文へ散りばめる
- FAQ セクションを必ず末尾近くに設ける

## 出力形式（この順序で出力すること）

### ① メタ情報
<!-- META
title: （H1タイトル・メインキーワード含む35文字前後）
description: （メタディスクリプション・120文字以内）
keywords: （関連キーワード6〜10個・カンマ区切り）
-->

### ② Schema.org JSON-LD
<!-- SCHEMA
{{
  "@context": "https://schema.org",
  "@graph": [
    {{
      "@type": "Article",
      "headline": "（タイトル）",
      "description": "（ディスクリプション）",
      "keywords": "（キーワード）"
    }},
    {{
      "@type": "FAQPage",
      "mainEntity": [
        {{"@type": "Question", "name": "（Q1）", "acceptedAnswer": {{"@type": "Answer", "text": "（A1）"}}}},
        {{"@type": "Question", "name": "（Q2）", "acceptedAnswer": {{"@type": "Answer", "text": "（A2）"}}}},
        {{"@type": "Question", "name": "（Q3）", "acceptedAnswer": {{"@type": "Answer", "text": "（A3）"}}}}
      ]
    }}
  ]
}}
-->

### ③ 記事本文（Markdown）
- FAQセクション（## よくある質問）を含める
- 結論・まとめにCTAを入れる
- 前置き不要。本文のみ出力

### ④ note有料区切り
記事本文の適切な位置（全体の30〜40%）に1箇所だけ挿入:
<!-- NOTE_PAID_START -->
無料部分: 問題提起・概要（読者が続きを読みたくなる導入）
有料部分: 具体的手順・ノウハウ・テンプレート・FAQ・まとめ"""

        try:
            with client.messages.stream(
                model="claude-opus-4-6",
                max_tokens=6000,
                messages=[{"role": "user", "content": prompt}],
            ) as s:
                for text in s.text_stream:
                    yield f"data: {json.dumps({'phase': 'text', 'text': text}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except anthropic.AuthenticationError:
            yield f"data: {json.dumps({'error': 'APIキーが無効です'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/images")
async def generate_images(req: ImageRequest):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    # Claudeでタイトルと画像検索クエリを生成
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"""以下のnote記事に最適な画像検索クエリを生成してください。

記事キーワード: {req.keyword}
記事本文（先頭600文字）:
{req.article_body[:600]}

以下のJSON形式のみ出力してください（コードブロック不要）:
{{
  "title": "（noteタイトル・30文字以内・クリックされる表現）",
  "header_query": "（ヘッダー画像の英語検索クエリ・シンプルで的確に）",
  "images": [
    {{"section": "（用途・日本語）", "query": "（英語検索クエリ）"}},
    {{"section": "（用途・日本語）", "query": "（英語検索クエリ）"}},
    {{"section": "（用途・日本語）", "query": "（英語検索クエリ）"}}
  ]
}}""",
        }],
    )

    try:
        raw = resp.content[0].text.strip()
        start = raw.find("{")
        end = raw.rfind("}") + 1
        data = json.loads(raw[start:end])
    except Exception:
        raise HTTPException(status_code=500, detail="クエリ生成に失敗しました")

    # Unsplash検索リンクを生成（APIキー不要）
    def unsplash_link(query: str, orientation: str = "landscape") -> str:
        q = urllib.parse.quote(query)
        return f"https://unsplash.com/s/photos/{q}?orientation={orientation}"

    images = []
    for img in data.get("images", []):
        images.append({
            "section": img["section"],
            "query": img["query"],
            "link": unsplash_link(img["query"], "squarish"),
        })

    return {
        "title": data.get("title", ""),
        "header": {
            "query": data.get("header_query", req.keyword),
            "link": unsplash_link(data.get("header_query", req.keyword), "landscape"),
        },
        "images": images,
    }
