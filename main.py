"""
SEO Article Generator - Web App (Enhanced)
競合分析 + E-E-A-T + FAQ + Schema.org 対応
"""

import asyncio
import json
import os
from pathlib import Path

import anthropic
import replicate
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
    article_body: str  # META/SCHEMA除去済みのMarkdown本文


async def gen_image(prompt: str, aspect_ratio: str = "16:9") -> str:
    """Replicate Flux-schnell で画像を1枚生成してURLを返す"""
    loop = asyncio.get_event_loop()
    try:
        output = await loop.run_in_executor(
            None,
            lambda: replicate.run(
                "black-forest-labs/flux-schnell",
                input={
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "output_format": "webp",
                    "num_outputs": 1,
                    "num_inference_steps": 4,
                    "go_fast": True,
                },
            ),
        )
        return str(list(output)[0])
    except Exception:
        return ""


def search_competitors(keyword: str, num: int = 5) -> list[dict]:
    """DuckDuckGoで上位表示中の競合サイトを取得"""
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
        # Phase 1: 競合分析
        yield f"data: {json.dumps({'phase': 'searching', 'message': '競合サイトを調査中...'}, ensure_ascii=False)}\n\n"
        competitors = search_competitors(req.keyword)
        competitor_summary = build_competitor_summary(competitors)
        yield f"data: {json.dumps({'phase': 'competitors', 'data': competitors}, ensure_ascii=False)}\n\n"

        # Phase 2: 記事生成
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
    replicate_token = os.environ.get("REPLICATE_API_TOKEN")
    if not replicate_token:
        raise HTTPException(status_code=400, detail="REPLICATE_API_TOKEN が未設定です")
    os.environ["REPLICATE_API_TOKEN"] = replicate_token

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key)

    # Claude（高速モデル）で画像プロンプトを生成
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"""以下のnote記事に最適な画像プロンプトをEnglishで生成してください。

記事キーワード: {req.keyword}
記事本文（先頭600文字）:
{req.article_body[:600]}

以下のJSON形式のみ出力してください（前置き不要）:
{{
  "title": "（この記事の最適なnoteタイトル・30文字以内・クリックしたくなる）",
  "header": "（noteカバー画像用プロンプト・16:9・記事テーマを象徴するシーン）",
  "images": [
    {{"section": "（どのセクション向けか・日本語）", "prompt": "（画像プロンプト・英語）"}},
    {{"section": "（どのセクション向けか・日本語）", "prompt": "（画像プロンプト・英語）"}},
    {{"section": "（どのセクション向けか・日本語）", "prompt": "（画像プロンプト・英語）"}}
  ]
}}

全プロンプトに必ず含めること: flat design illustration, clean, professional, japanese blog aesthetic, soft pastel colors, no text, no letters, no words""",
            }
        ],
    )

    try:
        prompts = json.loads(resp.content[0].text)
    except Exception:
        raise HTTPException(status_code=500, detail="プロンプト生成に失敗しました")

    # ヘッダー + 記事内画像を並列生成
    header_task = gen_image(prompts["header"], "16:9")
    article_tasks = [gen_image(img["prompt"], "4:3") for img in prompts.get("images", [])]
    all_urls = await asyncio.gather(header_task, *article_tasks)

    return {
        "title": prompts.get("title", ""),
        "header": {"url": all_urls[0], "prompt": prompts["header"]},
        "images": [
            {"url": all_urls[i + 1], "section": img["section"], "prompt": img["prompt"]}
            for i, img in enumerate(prompts.get("images", []))
            if i + 1 < len(all_urls)
        ],
    }
