# src/nlp_processor.py
import json
import logging
import os
from typing import List, Dict, Any
import asyncio

from openai import OpenAI
from src.data_models import Article

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL")


def _build_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is missing")
    # OpenRouter key starts with sk-or-
    if OPENAI_API_KEY.startswith("sk-or-"):
        return OpenAI(api_key=OPENAI_API_KEY, base_url="https://openrouter.ai/api/v1")
    return OpenAI(api_key=OPENAI_API_KEY)


def _select_model() -> str:
    if OPENAI_MODEL:
        return OPENAI_MODEL
    if OPENAI_API_KEY and OPENAI_API_KEY.startswith("sk-or-"):
        return "openai/gpt-4o-mini"
    return "gpt-4o-mini"


async def call_llm(prompt: str) -> Dict[str, Any]:
    client = _build_client()
    model = _select_model()

    def _call():
        return client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是AI新闻分析助手。只输出JSON，不要额外文字。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

    response = await asyncio.to_thread(_call)
    return response.model_dump() if hasattr(response, "model_dump") else response


async def call_llm_text(prompt: str) -> str:
    client = _build_client()
    model = _select_model()

    def _call():
        return client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "你是AI新闻分析助手。只输出中文文本，不要额外格式。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )

    response = await asyncio.to_thread(_call)
    payload = response.model_dump() if hasattr(response, "model_dump") else response
    return payload["choices"][0]["message"]["content"].strip()


def _safe_json_parse(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                return {}
        return {}


async def process_article_with_nlp(article: Article) -> Article:
    logger.info(f"Processing article '{article.title[:60]}...' with NLP...")

    content_to_analyze = article.content or article.summary or article.title
    content_preview = (
        content_to_analyze[:3000] if len(content_to_analyze) > 3000 else content_to_analyze
    )

    prompt = f"""
请根据以下文章信息，输出中文结构化结果，字段如下：

{{
  "summary_zh": "中文简报（80-150字）",
  "plain_summary": "通俗总结（用简单的话解释专业术语，让非专业读者也能理解核心内容，100-200字）",
  "key_points": ["要点1", "要点2", "要点3"],
  "entities": ["实体1", "实体2"],
  "main_tags": ["能力", "成本", "范式", "格局", "产品", "政策", "融资", "开源"],
  "trend_tag": "趋势标签（能力/成本/范式/格局/产品/政策/融资/开源之一）",
  "heat_score": 0-100
}}

文章标题: {article.title}
文章摘要/内容: {content_preview}
"""

    try:
        response = await call_llm(prompt)
        response_content_str = response["choices"][0]["message"]["content"]
        nlp_data = _safe_json_parse(response_content_str)

        article.summary_zh = nlp_data.get("summary_zh")
        article.plain_summary = nlp_data.get("plain_summary")
        article.key_points = (
            nlp_data.get("key_points", [])
            if isinstance(nlp_data.get("key_points"), list)
            else []
        )

        entities_list = nlp_data.get("entities", [])
        if isinstance(entities_list, list):
            article.entities = {"MISC": entities_list} if entities_list else {}
        elif isinstance(entities_list, dict):
            article.entities = entities_list
        else:
            article.entities = {}

        article.main_tags = (
            nlp_data.get("main_tags", [])
            if isinstance(nlp_data.get("main_tags"), list)
            else []
        )
        article.trend_tag = nlp_data.get("trend_tag")

        heat_score = nlp_data.get("heat_score")
        if isinstance(heat_score, (int, float)):
            article.heat_score = max(0, min(100, float(heat_score)))
        else:
            article.heat_score = None

    except Exception as e:
        logger.error(
            f"Error processing article '{article.title[:60]}...' with NLP: {e}",
            exc_info=True,
        )
        if not article.entities:
            article.entities = {}
        if not article.main_tags:
            article.main_tags = []

    return article


async def generate_favorite_analysis(article: Article) -> str:
    content_to_analyze = article.content or article.summary or article.title
    content_preview = (
        content_to_analyze[:3500] if len(content_to_analyze) > 3500 else content_to_analyze
    )

    prompt = f"""
请基于以下文章内容，给出精炼中文分析，要求：
1) 150-250字
2) 删掉废话，保留关键信息
3) 点出对行业的影响或趋势判断

文章标题: {article.title}
文章内容: {content_preview}
"""

    try:
        return await call_llm_text(prompt)
    except Exception as e:
        logger.error(f"Failed to generate favorite analysis: {e}", exc_info=True)
        return ""


async def process_articles_batch(
    articles: List[Article], batch_size: int = 10
) -> List[Article]:
    logger.info(f"Processing {len(articles)} articles in batches of {batch_size}...")

    processed_articles = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]
        logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} articles)...")

        batch_results = await asyncio.gather(
            *[process_article_with_nlp(article) for article in batch],
            return_exceptions=True,
        )

        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Error in batch processing: {result}")
            else:
                processed_articles.append(result)

    logger.info(f"Finished processing {len(processed_articles)} articles.")
    return processed_articles
