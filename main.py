"""
SEO Article Generator - Web App (Enhanced)
競合分析 + E-E-A-T + FAQ + Schema.org + 無料画像検索
"""

import json
import os
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


def search_images(query: str, count: int = 1, wide: bool = True) -> list[str]:
    """DuckDuckGoでCC画像を検索してURLリストを返す"""
    urls = []
    try:
        with DDGS() as ddgs:
            results = ddgs.images(
                query,
                license_image="shareCommercially",
                max_results=count * 5,
            )
            for r in results:
                w = r.get("width", 0)
                h = r.get("height", 1)
                if wide and w > h:
                    urls.append(r["image"])
                elif not wide:
                    urls.append(r["image"])
                if len(urls) >= count:
                    break
    except Exception:
        pass
    return urls


def build_competitor_summary(competitors: list[dict]) -> str:
    if not competitors:
        return "競合データなし"
    lines = []
    for i, c in enumerate(competitors, 1):
        lines.append(f"{i}. 【{c['title']}】")
        lines.append(f"   URL: {c['url']}")
        lines.append(f"   概要: {c['description'][:120]}...")
    return "\n".join(lines)


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
        yield f"data: {json.dumps({'phase': 'searching', 'message': '競合サイトを調査中...'}, ensure_ascii=False)}\n\n"
        competitors = search_competitors(req.keyword)
        competitor_summary = build_competitor_summary(competitors)
        yield f"data: {json.dumps({'phase': 'competitors', 'data': competitors}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'phase': 'writing', 'message': 'AI が記事を執筆中...'}, ensure_ascii=False)}\n\n"

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
- H2見出しに検索される疑問形フレーズを使う（例:「〜とは？」「〜の方法」）
- LSIキーワード・共起語を自然に本文へ散りばめる
- FAQ セクションを必ず末尾近くに設ける（Googleの注目スニペット対策）

## 出力形式（この順序で出力すること）

### ① メタ情報（コメントブロック）
<!-- META
title: （H1タイトル・メインキーワード含む35文字前後）
description: （メタディスクリプション・120文字以内・クリックしたくなる文章）
keywords: （関連キーワード6〜10個・カンマ区切り）
-->

### ② Schema.org JSON-LD（コメントブロック）
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
        {{
          "@type": "Question",
          "name": "（よくある質問1）",
          "acceptedAnswer": {{"@type": "Answer", "text": "（回答1）"}}
        }},
        {{
          "@type": "Question",
          "name": "（よくある質問2）",
          "acceptedAnswer": {{"@type": "Answer", "text": "（回答2）"}}
        }},
        {{
          "@type": "Question",
          "name": "（よくある質問3）",
          "acceptedAnswer": {{"@type": "Answer", "text": "（回答3）"}}
        }}
      ]
    }}
  ]
}}
-->

### ③ 記事本文（Markdown）
- 上記メタ・スキーマの後に本文を書く
- 必ずFAQセクション（## よくある質問）を含める
- 結論・まとめにCTA（行動喚起）を入れる
- 前置き・説明は不要。記事本文のみ出力

### ④ note有料コンテンツ区切り（重要）
記事本文の途中の適切な位置に、以下のマーカーを1箇所だけ挿入してください:

<!-- NOTE_PAID_START -->

配置の基準:
- **無料部分（全体の30〜40%）**: 問題提起・悩みへの共感・記事の概要・読者が「続きを読みたい」と思う導入
- **有料部分（全体の60〜70%）**: 具体的な手順・ノウハウ・テンプレート・事例・FAQ・まとめ
- 読者が「ここから先が本当に価値ある情報だ」と感じる自然な区切り目に置くこと"""

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

    # Claudeで画像検索クエリとタイトルを生成
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"""以下のnote記事に最適な画像検索クエリを生成してください。

記事キーワード: {req.keyword}
記事本文（先頭600文字）:
{req.article_body[:600]}

以下のJSON形式のみ出力してください（前置き不要）:
{{
  "title": "（この記事の最適なnoteタイトル・30文字以内・クリックしたくなる）",
  "header_query": "（ヘッダー画像の英語検索クエリ・記事テーマに合う横長写真）",
  "images": [
    {{"section": "（どのセクション向けか・日本語）", "query": "（英語検索クエリ）"}},
    {{"section": "（どのセクション向けか・日本語）", "query": "（英語検索クエリ）"}},
    {{"section": "（どのセクション向けか・日本語）", "query": "（英語検索クエリ）"}}
  ]
}}""",
        }],
    )

    try:
        data = json.loads(resp.content[0].text)
    except Exception:
        raise HTTPException(status_code=500, detail="クエリ生成に失敗しました")

    # DuckDuckGoで画像検索（無料・APIキー不要）
    header_urls = search_images(data["header_query"], count=1, wide=True)
    images = []
    for img in data.get("images", []):
        urls = search_images(img["query"], count=1, wide=False)
        images.append({
            "section": img["section"],
            "query": img["query"],
            "url": urls[0] if urls else "",
        })

    return {
        "title": data.get("title", ""),
        "header": {
            "url": header_urls[0] if header_urls else "",
            "query": data["header_query"],
        },
        "images": [img for img in images if img["url"]],
    }
