# src/nlp_processor.py
import json
import logging
from typing import List, Dict, Any
import asyncio

from src.data_models import Article

logger = logging.getLogger(__name__)

# 模拟 OpenRouter API 调用的函数
async def call_openrouter_api(prompt: str) -> Dict[str, Any]:
    """
    模拟调用 OpenRouter API。
    在实际部署时，这里需要替换为真正的 OpenRouter API 调用。
    
    :param prompt: 发送给 API 的提示文本
    :return: 包含 API 响应的字典
    """
    logger.debug(f"Simulating OpenRouter API call with prompt: {prompt[:100]}...")
    await asyncio.sleep(0.5)  # 模拟网络延迟

    # 简单的模拟回复，根据 prompt 尝试提取信息
    prompt_lower = prompt.lower()
    
    entities = []
    main_tags = []
    
    # 简单的关键词匹配来模拟实体和标签抽取
    # 实体识别
    entity_keywords = {
        "Google": ["google", "alphabet"],
        "OpenAI": ["openai", "gpt", "chatgpt"],
        "NVIDIA": ["nvidia", "cuda"],
        "Microsoft": ["microsoft", "azure"],
        "Meta": ["meta", "facebook"],
        "Anthropic": ["anthropic", "claude"],
        "Hugging Face": ["hugging face", "huggingface"],
        "PyTorch": ["pytorch"],
        "TensorFlow": ["tensorflow"],
        "LLM": ["llm", "large language model", "language model"],
        "Transformer": ["transformer", "attention"],
    }
    
    for entity, keywords in entity_keywords.items():
        if any(keyword in prompt_lower for keyword in keywords):
            entities.append(entity)
    
    # 标签识别（能力/成本/范式/格局）
    if any(keyword in prompt_lower for keyword in ["capability", "ability", "performance", "benchmark", "accuracy", "能力", "性能"]):
        main_tags.append("能力")
    if any(keyword in prompt_lower for keyword in ["price", "cost", "rate limit", "pricing", "cost-effective", "成本", "价格", "费用"]):
        main_tags.append("成本")
    if any(keyword in prompt_lower for keyword in ["paradigm", "framework", "architecture", "method", "approach", "范式", "框架", "方法"]):
        main_tags.append("范式")
    if any(keyword in prompt_lower for keyword in ["company", "partnership", "ecosystem", "market", "finance", "business", "格局", "市场", "商业"]):
        main_tags.append("格局")
    
    # 如果没有匹配到标签，尝试从内容推断
    if not main_tags:
        if "ai" in prompt_lower or "artificial intelligence" in prompt_lower or "machine learning" in prompt_lower:
            main_tags.append("能力")
    
    # 返回模拟的响应结构（模拟 OpenRouter API 的响应格式）
    response_content = {
        "entities": entities[:10],  # 限制实体数量
        "main_tags": main_tags[:4]  # 最多4个标签
    }
    
    return {
        "choices": [{
            "message": {
                "content": json.dumps(response_content, ensure_ascii=False)
            }
        }]
    }

async def process_article_with_nlp(article: Article) -> Article:
    """
    使用 NLP (OpenRouter) 处理单个 Article 实例，填充实体、标签和简述。
    
    :param article: 待处理的 Article 实例
    :return: 处理后的 Article 实例（已填充 entities, main_tags, short_description）
    """
    logger.info(f"Processing article '{article.title[:60]}...' with NLP...")
    
    # 构建发送给 OpenRouter 的 prompt
    # 优先使用 content，如果不存在则使用 summary
    content_to_analyze = article.content if article.content else article.summary
    content_preview = content_to_analyze[:2000] if len(content_to_analyze) > 2000 else content_to_analyze  # 限制长度避免prompt过长
    
    prompt = f"""
请根据以下文章信息，提炼出核心实体、主要标签（能力/成本/范式/格局）。

文章标题: {article.title}
文章摘要/内容: {content_preview}

请以 JSON 格式返回结果，包含以下字段：
{{
    "entities": ["实体1", "实体2"],
    "main_tags": ["标签1", "标签2"]
}}
"""

    try:
        # 调用模拟的 OpenRouter API
        response = await call_openrouter_api(prompt)
        
        # 解析响应
        response_content_str = response['choices'][0]['message']['content']
        
        # 尝试解析 JSON
        try:
            nlp_data = json.loads(response_content_str)
        except json.JSONDecodeError:
            # 如果解析失败，尝试使用 eval（仅用于模拟，生产环境应避免）
            logger.warning(f"Failed to parse JSON response, using fallback parsing for article '{article.title[:60]}...'")
            try:
                nlp_data = eval(response_content_str)
            except Exception as e:
                logger.error(f"Failed to parse response for article '{article.title[:60]}...': {e}")
                nlp_data = {
                    "entities": [],
                    "main_tags": []
                }

        # 更新 Article 实例
        # Note: entities should be Dict[str, List[str]] according to Article model
        entities_list = nlp_data.get("entities", [])
        if isinstance(entities_list, list):
            # Convert list to dict format: {"PERSON": [...], "ORG": [...], etc.}
            article.entities = {"MISC": entities_list} if entities_list else {}
        else:
            article.entities = entities_list if isinstance(entities_list, dict) else {}
        
        article.main_tags = nlp_data.get("main_tags", [])
        # Note: Article model doesn't have short_description field, so we skip it
        
        logger.debug(f"NLP processed: '{article.title[:60]}...'. Entities: {article.entities}, Tags: {article.main_tags}")

    except Exception as e:
        logger.error(f"Error processing article '{article.title[:60]}...' with NLP: {e}", exc_info=True)
        # 确保即使出错也返回有效的默认值
        if not article.entities:
            article.entities = {}
        if not article.main_tags:
            article.main_tags = []
    
    return article

async def process_articles_batch(articles: List[Article], batch_size: int = 10) -> List[Article]:
    """
    批量处理文章，支持并发处理以提高效率。
    
    :param articles: 待处理的文章列表
    :param batch_size: 每批处理的文章数量（控制并发度）
    :return: 处理后的文章列表
    """
    logger.info(f"Processing {len(articles)} articles in batches of {batch_size}...")
    
    processed_articles = []
    
    # 分批处理
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} articles)...")
        
        # 并发处理当前批次
        batch_results = await asyncio.gather(
            *[process_article_with_nlp(article) for article in batch],
            return_exceptions=True
        )
        
        # 处理结果，过滤掉异常
        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Error in batch processing: {result}")
            else:
                processed_articles.append(result)
    
    logger.info(f"Finished processing {len(processed_articles)} articles.")
    return processed_articles
