# src/favorites_api.py
"""
收藏功能API处理器
用于处理收藏请求：标记文章为收藏，并生成AI简析
可部署为 Supabase Edge Function 或独立的 Flask/FastAPI 服务
"""
import os
import sys
import logging
import asyncio
from typing import Optional

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, '.env'))

from src.config import settings
from src.data_models import Article
from src.supabase_manager import SupabaseManager
from src.nlp_processor import generate_favorite_analysis, process_article_with_nlp

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def process_favorite_article(article_id: str) -> dict:
    """
    处理收藏文章：标记为收藏并生成AI简析
    
    Args:
        article_id: 文章ID
        
    Returns:
        dict: 处理结果
    """
    result = {
        "success": False,
        "article_id": article_id,
        "message": ""
    }
    
    try:
        # 初始化Supabase管理器
        supabase_manager = SupabaseManager(use_service_role=True)
        
        # 获取文章
        response = supabase_manager.client.table(settings.SUPABASE_TABLE_ARTICLES) \
            .select("*") \
            .eq("id", article_id) \
            .execute()
        
        if not hasattr(response, 'data') or not response.data:
            result["message"] = f"未找到文章: {article_id}"
            return result
        
        article_data = response.data[0]
        
        # 转换数据
        for field in ["tags", "main_tags", "entities", "authors", "sentiment", "key_points"]:
            if field in article_data and isinstance(article_data[field], str):
                try:
                    article_data[field] = __import__('json').loads(article_data[field])
                except Exception:
                    pass
        
        article = Article(**article_data)
        
        # 检查是否已有简析
        if article.favorite_analysis and article.plain_summary:
            result["success"] = True
            result["message"] = "文章已有简析，跳过生成"
            # 只更新收藏状态
            supabase_manager.client.table(settings.SUPABASE_TABLE_ARTICLES) \
                .update({"is_favorite": True}) \
                .eq("id", article_id) \
                .execute()
            return result
        
        # 生成AI简析
        favorite_analysis = ""
        plain_summary = ""
        
        if not article.favorite_analysis:
            favorite_analysis = await generate_favorite_analysis(article)
            logger.info(f"Generated favorite analysis for {article_id}: {len(favorite_analysis)} chars")
        
        if not article.plain_summary:
            # 使用NLP处理生成通俗总结
            processed_article = await process_article_with_nlp(article)
            plain_summary = processed_article.plain_summary or ""
            logger.info(f"Generated plain summary for {article_id}: {len(plain_summary)} chars")
        
        # 更新数据库
        update_data = {
            "is_favorite": True,
            "favorite_analysis": favorite_analysis,
            "plain_summary": plain_summary
        }
        
        supabase_manager.client.table(settings.SUPABASE_TABLE_ARTICLES) \
            .update(update_data) \
            .eq("id", article_id) \
            .execute()
        
        result["success"] = True
        result["message"] = "收藏成功，简析已生成"
        result["favorite_analysis_preview"] = (favorite_analysis[:100] + "...") if favorite_analysis else ""
        result["plain_summary_preview"] = (plain_summary[:100] + "...") if plain_summary else ""
        
    except Exception as e:
        logger.error(f"Error processing favorite article {article_id}: {e}", exc_info=True)
        result["message"] = f"处理失败: {str(e)}"
    
    return result


async def process_favorites_batch(article_ids: list) -> list:
    """
    批量处理收藏文章
    
    Args:
        article_ids: 文章ID列表
        
    Returns:
        list: 处理结果列表
    """
    results = await asyncio.gather(
        *[process_favorite_article(article_id) for article_id in article_ids],
        return_exceptions=True
    )
    
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append({
                "success": False,
                "article_id": article_ids[i],
                "message": str(result)
            })
        else:
            processed_results.append(result)
    
    return processed_results


# 以下是用于独立运行的入口点
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="收藏文章处理")
    parser.add_argument("--id", type=str, help="文章ID")
    parser.add_argument("--batch", type=str, help="文章ID列表（逗号分隔）")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    if args.id:
        result = asyncio.run(process_favorite_article(args.id))
        print(f"Result: {result}")
    elif args.batch:
        article_ids = [x.strip() for x in args.batch.split(",")]
        results = asyncio.run(process_favorites_batch(article_ids))
        for result in results:
            print(f"Result: {result}")
    else:
        print("Please provide --id or --batch argument")
