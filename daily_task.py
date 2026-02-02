"""
定时任务：每日运行爬虫并发送邮件
"""
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.config import settings
from src.supabase_manager import SupabaseManager
from src.display_module import DisplayModule
from src.email_sender import send_daily_email

# 导入爬虫模块
from src.scrapers.arxiv_scraper import ArxivScraper
from src.scrapers.rss_scraper import RSSScraper
from src.nlp_processor import process_articles_batch as nlp_process_articles_batch
from src.supabase_manager import SupabaseManager
from src.data_models import Article
from typing import List, AsyncIterator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def collect_from_async_iterator(async_iterator: AsyncIterator[Article]) -> List[Article]:
    """Helper to collect all items from an async iterator into a list."""
    items = []
    async for item in async_iterator:
        items.append(item)
    return items


async def scrape_and_process() -> List[Article]:
    """抓取并处理新文章"""
    logger.info("开始抓取新文章...")
    
    # 加载 RSS 配置
    import json
    rss_feeds_path = Path(__file__).parent / 'src' / 'data' / 'rss_feeds.json'
    try:
        with open(rss_feeds_path, 'r', encoding='utf-8') as f:
            rss_feeds_data = json.load(f)
        rss_feed_configs = [
            {'name': feed['name'], 'url': feed['url']}
            for feed in rss_feeds_data
        ]
        logger.info(f"加载了 {len(rss_feed_configs)} 个 RSS 源")
    except Exception as e:
        logger.warning(f"加载 RSS 配置失败: {e}，使用默认配置")
        rss_feed_configs = [
            {'name': 'OpenAI Blog', 'url': 'https://openai.com/blog/rss'},
            {'name': 'Google Research Blog', 'url': 'https://blog.google/technology/ai/rss'},
        ]
    
    # 初始化爬虫
    scraper_tasks = []
    
    # ArxivScraper
    arxiv_scraper = ArxivScraper(
        query_categories=settings.ARXIV_CATEGORIES,
        max_results_per_category=settings.ARXIV_MAX_RESULTS_PER_CATEGORY
    )
    arxiv_task = arxiv_scraper.scrape_articles(days_ago=settings.DAYS_AGO)
    scraper_tasks.append(arxiv_task)
    logger.info(f"ArxivScraper 已启动，类别: {settings.ARXIV_CATEGORIES}")
    
    # RSSScraper
    rss_scraper = RSSScraper(
        feed_configs=rss_feed_configs,
        max_entries_per_feed=settings.MAX_ARTICLES_PER_FEED,
        skip_full_content_for_arxiv=True
    )
    rss_task = collect_from_async_iterator(
        rss_scraper.scrape_articles(days_ago=settings.DAYS_AGO, fetch_full_content=True)
    )
    scraper_tasks.append(rss_task)
    logger.info(f"RSSScraper 已启动，RSS 源: {len(rss_feed_configs)}")
    
    # 并发执行所有爬虫
    logger.info("开始并发抓取...")
    results = await asyncio.gather(*scraper_tasks, return_exceptions=True)
    
    # 收集所有文章
    all_articles: List[Article] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"爬虫 {i+1} 出错: {result}")
        elif isinstance(result, List):
            logger.info(f"爬虫 {i+1} 获取到 {len(result)} 篇文章")
            all_articles.extend(result)
    
    logger.info(f"总共抓取到 {len(all_articles)} 篇文章")
    
    if not all_articles:
        logger.warning("没有抓取到任何文章")
        return []
    
    # NLP 处理
    logger.info("开始 NLP 处理...")
    processed_articles = await nlp_process_articles_batch(all_articles, batch_size=settings.NLP_BATCH_SIZE)
    logger.info(f"NLP 处理完成，{len(processed_articles)} 篇文章")
    
    return processed_articles


async def main():
    """每日任务主流程"""
    logger.info("=" * 50)
    logger.info("开始每日AI趋势简报任务")
    logger.info(f"时间: {datetime.now().isoformat()}")
    logger.info("=" * 50)
    
    # 修改环境变量，扩大时间范围到7天
    import os
    original_days = os.environ.get("DAYS_AGO")
    os.environ["DAYS_AGO"] = "7"
    
    # 1. 抓取新文章
    try:
        supabase_manager = SupabaseManager(use_service_role=True)
    except Exception as e:
        logger.error(f"初始化 Supabase 失败: {e}")
        return
    
    articles = await scrape_and_process()
    
    # 恢复原始设置
    if original_days:
        os.environ["DAYS_AGO"] = original_days
    
    # 如果没有抓取到新文章，尝试从数据库读取最近的
    if not articles:
        logger.info("没有抓取到新文章，从数据库读取最近的...")
        articles = supabase_manager.fetch_articles(limit=50, days_ago=1)
        logger.info(f"从数据库获取到 {len(articles)} 篇文章")
    
    if not articles:
        logger.info("今日暂无新文章，任务结束")
        return
    
    # 2. 保存到数据库
    if articles:
        logger.info("保存文章到数据库...")
        inserted, skipped = supabase_manager.upsert_articles(articles)
        logger.info(f"保存完成: 新增/更新 {inserted} 篇，跳过 {skipped} 篇")
    
    # 3. 生成邮件 HTML
    display_module = DisplayModule()
    email_html = display_module.generate_email_html(articles, settings.GITHUB_PAGES_BASE_URL)
    
    # 4. 生成静态页面
    display_module.generate_static_site(
        settings.OUTPUT_DIR,
        articles,
        settings.GITHUB_PAGES_BASE_URL,
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY
    )
    
    # 5. 发送邮件
    if settings.SENDER_EMAIL and settings.RECIPIENT_EMAIL:
        try:
            send_daily_email("每日AI趋势简报", email_html)
            logger.info("邮件发送成功！")
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
    else:
        logger.warning("邮件配置不完整，跳过发送")
    
    logger.info("任务完成！")


if __name__ == "__main__":
    asyncio.run(main())