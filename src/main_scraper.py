import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import List, AsyncIterator

# Import the updated settings object
from src.config import settings
from src.data_models import Article
from src.supabase_manager import SupabaseManager # Re-introduced SupabaseManager

# Corrected scraper imports and usage
from src.scrapers.arxiv_scraper import ArxivScraper
from src.scrapers.rss_scraper import RSSScraper
from src.scrapers.serper_news_scraper import SerperNewsScraper

# Corrected NLP processor import
from src.nlp_processor import process_articles_batch as nlp_process_articles_batch

from src.email_sender import send_daily_email
from src.nlp_processor import generate_favorite_analysis

# Corrected DisplayModule import
from src.display_module import DisplayModule

# --- Logging Configuration ---
# Ensure DEBUG level is visible for detailed field isolation debugging
log_level = logging.DEBUG if settings.DEBUG else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
# Set specific loggers to appropriate levels
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
# Allow supabase and our modules to show DEBUG logs when DEBUG is enabled
logging.getLogger('supabase').setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
logging.getLogger('src.supabase_manager').setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(log_level)  # Explicitly set logger level

# --- Main Scraper Logic ---
async def _process_articles_with_nlp(articles: List[Article]) -> List[Article]:
    """
    Processes raw articles: performs NLP.
    Now directly accepts and processes Article objects.
    """
    logger.info(f"--- NLP Processing Debug ---")
    logger.info(f"Received {len(articles)} Article objects for processing.")

    if not articles:
        logger.warning("No valid Article objects received. Skipping further NLP processing.")
        return []

    # Perform NLP processing using the function
    logger.info(f"Starting NLP processing for {len(articles)} articles...")
    # Use settings.NLP_BATCH_SIZE for batch processing
    processed_articles = await nlp_process_articles_batch(articles, batch_size=settings.NLP_BATCH_SIZE)
    logger.info(f"Finished NLP processing. {len(processed_articles)} articles processed.")

    # Verify article object types and attributes after NLP
    if processed_articles:
        sample_article = processed_articles[0]
        logger.info(f"Sample processed article type: {type(sample_article)}")
        logger.info(f"Sample processed article attributes (first article):")
        logger.info(f"  Title: '{sample_article.title}'")
        logger.info(f"  Link: '{str(sample_article.link)}'")
        logger.info(f"  Summary: '{sample_article.summary[:100] if sample_article.summary else 'N/A'}...'")
        logger.info(f"  Tags: {sample_article.tags}")
        logger.info(f"  Main Tags: {sample_article.main_tags}")
        logger.info(f"  Entities: {sample_article.entities}")
        # Validate key fields
        missing_fields = []
        for a in processed_articles:
            if not a.title or not a.link or not a.published:
                missing_fields.append(str(a.link))
        if missing_fields:
            logger.warning(f"Some processed articles are missing 'title', 'link', or 'published' fields: {missing_fields[:3]}... This might affect Supabase upsert.")
    else:
        logger.warning("No articles remained after NLP processing. This might indicate an issue with nlp_process_articles_batch or filtering.")
        return []
    
    logger.info(f"--------------------------")
    return processed_articles


async def main():
    start_time = datetime.now()
    logger.info("Starting main scraper and processing pipeline...")

    # Initialize SupabaseManager
    supabase_manager = None
    try:
        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            # Use service_role key by default for backend operations (bypasses RLS)
            supabase_manager = SupabaseManager(use_service_role=True)
            logger.info(f"SupabaseManager initialized with {settings.supabase_key_type} key.")
            if 'service_role' in settings.supabase_key_type.lower():
                logger.info("Using service_role key - should bypass RLS policies.")
            else:
                logger.warning("Using non-service_role key - operations may be blocked by RLS policies.")
                logger.warning("Consider setting SUPABASE_SERVICE_ROLE_KEY in .env file.")
        else:
            logger.warning("Supabase URL or Key not configured. Supabase operations will be skipped.")
    except Exception as e:
        logger.error(f"Failed to initialize SupabaseManager: {e}", exc_info=True)
        supabase_manager = None # Ensure it's None if init fails

    # Determine date range for scraping
    end_date = datetime.now()
    start_date = end_date - timedelta(days=settings.DAYS_AGO)
    logger.info(f"Scraping articles from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    # Load RSS feed configs
    import json
    from pathlib import Path
    rss_feeds_path = Path(__file__).parent / 'data' / 'rss_feeds.json'
    try:
        with open(rss_feeds_path, 'r', encoding='utf-8') as f:
            rss_feeds_data = json.load(f)
        rss_feed_configs = [
            {'name': feed['name'], 'url': feed['url']}
            for feed in rss_feeds_data
        ]
        logger.info(f"Loaded {len(rss_feed_configs)} RSS feeds from {rss_feeds_path}")
    except FileNotFoundError:
        logger.warning(f"RSS feeds config file not found at {rss_feeds_path}, using default feeds")
        rss_feed_configs = [
            {'name': 'OpenAI Blog', 'url': 'https://openai.com/blog/rss'},
            {'name': 'Google Research Blog', 'url': 'https://blog.google/technology/ai/rss'},
        ]
    except Exception as e:
        logger.error(f"Error loading RSS feeds config: {e}, using default feeds")
        rss_feed_configs = [
            {'name': 'OpenAI Blog', 'url': 'https://openai.com/blog/rss'},
            {'name': 'Google Research Blog', 'url': 'https://blog.google/technology/ai/rss'},
        ]

    # Initialize scrapers
    all_articles_collected: List[Article] = [] # Changed to store Article objects directly
    logger.info("Starting scrapers concurrently...")

    scraper_tasks = []
    
    # ArxivScraper
    arxiv_scraper = ArxivScraper(
        query_categories=settings.ARXIV_CATEGORIES,
        max_results_per_category=settings.ARXIV_MAX_RESULTS_PER_CATEGORY
    )
    arxiv_task = arxiv_scraper.scrape_articles(days_ago=settings.DAYS_AGO)
    scraper_tasks.append(arxiv_task)
    logger.info(f"ArxivScraper task created for categories: {settings.ARXIV_CATEGORIES}")
    
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
    logger.info(f"RSSScraper task created for {len(rss_feed_configs)} feeds")
    
    # SerperNewsScraper
    try:
        serper_scraper = SerperNewsScraper()
        serper_results = serper_scraper.search("AI news OR artificial intelligence OR LLM", num=20)
        serper_articles: List[Article] = []
        for item in serper_results:
            raw = {
                "title": item.get("title"),
                "link": item.get("link"),
                "published": item.get("date") or datetime.utcnow(),
                "source": item.get("source") or "Serper News",
                "summary": item.get("snippet")
            }
            try:
                serper_articles.append(Article.from_raw_article(raw))
            except Exception as e:
                logger.warning(f"Serper item conversion failed: {e}")
        scraper_tasks.append(asyncio.sleep(0, result=serper_articles))
        logger.info(f"SerperNewsScraper collected {len(serper_articles)} items")
    except Exception as e:
        logger.warning(f"SerperNewsScraper skipped due to error: {e}")

    # Await all scraper tasks with error handling
    logger.info(f"Awaiting {len(scraper_tasks)} scraper tasks concurrently...")
    results = await asyncio.gather(*scraper_tasks, return_exceptions=True)
    logger.info(f"All scraper tasks completed. Processing {len(results)} results...")
    
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Scraper task {i+1} failed with exception: {result}", exc_info=True)
            logger.warning(f"Continuing with other scrapers despite error in task {i+1}")
        elif isinstance(result, List):
            # Each result_list is expected to contain Article objects
            if result:
                # Verify result contains Article objects
                sample = result[0] if result else None
                if sample and isinstance(sample, Article):
                    logger.info(f"Scraper task {i+1} collected {len(result)} Article objects")
                    logger.debug(f"  Sample article from task {i+1}: type={type(sample)}, title='{sample.title[:50]}...'")
                else:
                    logger.warning(f"Scraper task {i+1} returned non-Article objects: {type(sample)}")
                all_articles_collected.extend(result)
            else:
                logger.info(f"Scraper task {i+1} returned empty list")
        else:
            logger.warning(f"Unexpected result type from scraper task {i+1}: {type(result)}")

    logger.info("All scrapers finished.")

    logger.info(f"--- Article Collection Debug ---")
    if not all_articles_collected:
        logger.warning("No articles collected by any scraper after concurrent execution.")
        logger.warning("Possible reasons:")
        logger.warning("  - Scrapers failed to fetch data.")
        logger.warning("  - Network issues preventing access to sources.")
        logger.warning("  - Source websites changed their structure.")
        logger.warning("  - Date filters in scrapers are too strict.")
        logger.warning("  - All fetched articles were filtered out by scraper's internal logic.")
        logger.info("Skipping further processing and output generation due to no articles.")
        return # Exit main if no articles
    else:
        logger.info(f"Successfully collected {len(all_articles_collected)} Article objects across all scrapers.")
        for i, article in enumerate(all_articles_collected):
            if i >= 3: # Print first 3 raw articles
                break
            # Access properties directly, not with .get()
            logger.info(f"  Sample collected article {i+1}: Title='{article.title[:80]}...', Link='{str(article.link)[:80]}...'")
    logger.info(f"------------------------------------------------")

    # Process articles (NLP, deduplication logic will be here later)
    logger.info(f"--- NLP Processing Stage ---")
    initial_article_count_before_nlp = len(all_articles_collected)
    logger.info(f"Articles before NLP processing: {initial_article_count_before_nlp}")
    
    # Verify all collected articles are Article objects
    if all_articles_collected:
        sample_collected = all_articles_collected[0]
        logger.info(f"Sample collected article type: {type(sample_collected)}")
        if isinstance(sample_collected, Article):
            logger.info(f"Sample collected article: title='{sample_collected.title[:50]}...', link='{str(sample_collected.link)[:50]}...'")
        else:
            logger.error(f"CRITICAL: Collected article is not an Article object! Type: {type(sample_collected)}")
    
    # Pass Article objects directly to NLP processor
    processed_articles = await _process_articles_with_nlp(all_articles_collected)
    logger.info(f"Articles after NLP processing: {len(processed_articles)}")
    logger.info(f"NLP processing: {initial_article_count_before_nlp} -> {len(processed_articles)} articles")

    # =====================================================
    # 去重逻辑 - 基于标题相似度
    # =====================================================
    logger.info(f"--- Deduplication Stage ---")
    deduplicated_articles = _deduplicate_articles(processed_articles)
    logger.info(f"Articles after deduplication: {len(deduplicated_articles)}")
    
    # =====================================================
    # 热度筛选 - 只保留高热度文章
    # =====================================================
    logger.info(f"--- Heat Score Filtering Stage ---")
    MIN_HEAT_SCORE = 30  # 热度阈值，低于此值的文章被过滤
    filtered_articles = [a for a in deduplicated_articles if (a.heat_score or 0) >= MIN_HEAT_SCORE]
    logger.info(f"Articles with heat_score >= {MIN_HEAT_SCORE}: {len(filtered_articles)}")

    # 如果过滤后太少，降低阈值再试
    if len(filtered_articles) < 10:
        MIN_HEAT_SCORE = 20
        filtered_articles = [a for a in deduplicated_articles if (a.heat_score or 0) >= MIN_HEAT_SCORE]
        logger.info(f"Lowered threshold to {MIN_HEAT_SCORE}: {len(filtered_articles)} articles")
    
    # 最终限制数量，确保阅读体验
    MAX_FINAL_ARTICLES = 30  # 最多显示30篇
    if len(filtered_articles) > MAX_FINAL_ARTICLES:
        # 按热度排序，取 top N
        filtered_articles = sorted(filtered_articles, key=lambda a: a.heat_score or 0, reverse=True)[:MAX_FINAL_ARTICLES]
        logger.info(f"Limited to top {MAX_FINAL_ARTICLES} by heat_score")
    
    logger.info(f"Final articles for email: {len(filtered_articles)}")

    if processed_articles:
        sample_article_nlp = processed_articles[0]
        logger.info(f"Verifying first NLP processed article:")
        logger.info(f"  Type: {type(sample_article_nlp)}")
        logger.info(f"  Title: '{sample_article_nlp.title[:80]}...'")
        logger.info(f"  Link: '{str(sample_article_nlp.link)[:80]}...'")
        logger.info(f"  Published: '{sample_article_nlp.published}'")
        logger.info(f"  Summary length: {len(sample_article_nlp.summary or '')} characters")
        logger.info(f"  Tags: {sample_article_nlp.main_tags}")
        logger.info(f"  Entities: {sample_article_nlp.entities}")
    else:
        logger.warning("No articles survived NLP processing or initial conversion. This is a critical point.")
    logger.info(f"---------------------------------------------")

    # --- Calling upsert before checks ---
    logger.info(f"--- Supabase Upsert Pre-check Debug ---")
    if not processed_articles:
        logger.warning("No processed articles available for Supabase upsert.")
        logger.warning("Possible reasons: No articles collected, all articles filtered out during processing, or NLP failed.")
        logger.info("Skipping Supabase upsert operation.")
    else:
        logger.info(f"Found {len(processed_articles)} processed articles ready for Supabase upsert.")
        for i, article in enumerate(processed_articles):
            if i >= 3: # Print first 3 processed articles for upsert
                break
            logger.info(f"  Sample article {i+1} for upsert: Title='{article.title[:80]}...', Link='{str(article.link)[:80]}...'")
            logger.info(f"    Published: {article.published}, Source: {article.source}")
            # Validate key fields for Supabase
            if not article.title or not article.link or not article.published:
                 logger.error(f"    CRITICAL: Article {i+1} is missing title, link, or published date. This will likely cause Supabase upsert to fail or skip.")
            # HttpUrl automatically ensures it starts with http(s), but we can add an extra check if needed.
            # elif not str(article.link).startswith("http"):
            #      logger.error(f"    CRITICAL: Article {i+1} link '{str(article.link)[:80]}...' does not look like a valid URL. Supabase 'url' field requires valid URL.")
    logger.info(f"----------------------------------------")

    # --- Conditional Check for Supabase Upsert ---
    logger.info(f"--- Supabase Upsert Conditional Check ---")
    is_supabase_ready = supabase_manager is not None and settings.SUPABASE_URL and settings.SUPABASE_KEY
    has_articles_to_upsert = bool(filtered_articles)

    logger.info(f"Supabase Manager initialized and configured: {is_supabase_ready}")
    logger.info(f"Processed articles available for upsert: {has_articles_to_upsert} (Count: {len(filtered_articles)})")
    
    if is_supabase_ready and has_articles_to_upsert:
        logger.info("Conditions met: Attempting to upsert articles to Supabase.")
        
        # Log sample article structure before upsert
        if filtered_articles:
            sample_for_upsert = filtered_articles[0]
            logger.info(f"Sample article structure for upsert:")
            logger.info(f"  Type: {type(sample_for_upsert)}")
            logger.info(f"  Title: '{sample_for_upsert.title[:50]}...'")
            logger.info(f"  Link: '{str(sample_for_upsert.link)[:50]}...'")
            logger.info(f"  Published: {sample_for_upsert.published}")
            logger.info(f"  Source: '{sample_for_upsert.source}'")
            logger.info(f"  Has summary: {bool(sample_for_upsert.summary)}")
            logger.info(f"  Tags count: {len(sample_for_upsert.tags)}")
            logger.info(f"  Main tags: {sample_for_upsert.main_tags}")
            logger.info(f"  Entities type: {type(sample_for_upsert.entities)}, keys: {list(sample_for_upsert.entities.keys()) if isinstance(sample_for_upsert.entities, dict) else 'N/A'}")
        
        logger.info(f"Attempting to upsert {len(filtered_articles)} articles to Supabase table '{supabase_manager.table_name}'...")
        try:
            # SupabaseManager.upsert_articles is synchronous, wrap with asyncio.to_thread
            inserted_count, skipped_count = await asyncio.to_thread(
                supabase_manager.upsert_articles, filtered_articles
            )
            logger.info(f"Supabase upsert result: Inserted/Updated: {inserted_count}, Skipped: {skipped_count}")
            if inserted_count == 0 and skipped_count == len(filtered_articles) and len(filtered_articles) > 0:
                logger.warning("All articles were skipped by Supabase. This often indicates RLS policies are blocking INSERT/UPDATE, or all articles already exist.")
            elif inserted_count < len(filtered_articles):
                logger.info(f"Some articles were skipped/not inserted. This is normal if they already exist based on 'link' conflict.")

        except Exception as e:
            logger.error(f"An error occurred during Supabase upsert: {e}", exc_info=True)
            logger.error("Possible reasons for Supabase upsert failure:")
            logger.error("  - Supabase client initialization failed (check previous logs).")
            logger.error("  - Network connectivity issues to Supabase.")
            logger.error("  - Incorrect Supabase table name or column definitions.")
            logger.error("  - RLS (Row Level Security) policies preventing writes (check Supabase dashboard).")
            logger.error("  - Data format mismatch (e.g., non-string for text fields, invalid URLs for 'link' field).")
    else:
        logger.warning("Supabase upsert conditions not met. Skipping upsert operation.")
        if not is_supabase_ready:
            logger.warning("Reason: Supabase Manager not properly initialized or configured (URL/KEY missing/invalid).")
        if not has_articles_to_upsert:
            logger.warning("Reason: No processed articles available after scraping and NLP stages.")
        logger.warning("Please ensure SUPABASE_URL and SUPABASE_KEY are set correctly in your environment/config, and articles are successfully processed.")
    logger.info(f"------------------------------------------")

    # --- Static Page Generation and Email Sending ---
    logger.info("Generating static page and preparing email content.")
    display_module = DisplayModule()

    if filtered_articles:
        email_html = display_module.generate_email_html(filtered_articles, settings.GITHUB_PAGES_BASE_URL)
        display_module.generate_static_site(
            settings.OUTPUT_DIR,
            filtered_articles,
            settings.GITHUB_PAGES_BASE_URL,
            settings.SUPABASE_URL,
            settings.SUPABASE_ANON_KEY
        )

        if settings.SENDER_EMAIL and settings.RECIPIENT_EMAIL:
            send_daily_email("每日AI趋势简报", email_html)
        else:
            logger.warning("SENDER_EMAIL or RECIPIENT_EMAIL missing, skipping email send.")
    else:
        logger.warning("No processed articles available. Skipping email and static site generation.")

    # --- Favorite analysis ---
    if supabase_manager is not None:
        try:
            favorite_articles = await asyncio.to_thread(supabase_manager.fetch_favorites_needing_analysis)
            if favorite_articles:
                logger.info(f"Found {len(favorite_articles)} favorite articles needing analysis")
                for fav in favorite_articles:
                    analysis = await generate_favorite_analysis(fav)
                    if analysis:
                        await asyncio.to_thread(supabase_manager.update_favorite_analysis, fav.id, analysis)
            else:
                logger.info("No favorite articles pending analysis")
        except Exception as e:
            logger.warning(f"Favorite analysis failed: {e}")

    end_time = datetime.now()
    duration = end_time - start_time
    logger.info(f"Main scraper pipeline finished. Total duration: {duration}")


async def collect_from_async_iterator(async_iterator: AsyncIterator[Article]) -> List[Article]:
    """Helper to collect all items from an async iterator into a list."""
    items = []
    async for item in async_iterator:
        items.append(item)
    return items


def _deduplicate_articles(articles: List[Article]) -> List[Article]:
    """
    基于标题相似度去重。
    使用简单的词重叠算法，避免重复内容出现在邮件中。
    """
    if not articles:
        return []
    
    unique_articles = []
    for article in articles:
        title_lower = article.title.lower()
        # 提取标题中的关键词（去掉常见词）
        stop_words = {'the', 'a', 'an', 'of', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'it', 'its'}
        words = set(title_lower.split())
        words = words - stop_words
        
        is_duplicate = False
        for existing in unique_articles:
            existing_title = existing.title.lower()
            existing_words = set(existing_title.split()) - stop_words
            
            # 计算词重叠率
            if words and existing_words:
                overlap = len(words & existing_words)
                # 如果重叠词 >= 3，且两个标题都较短，认为是重复
                if overlap >= 3:
                    # 额外检查：标题长度相近
                    if abs(len(title_lower) - len(existing_title)) < 50:
                        is_duplicate = True
                        break
        
        if not is_duplicate:
            unique_articles.append(article)
    
    return unique_articles


if __name__ == "__main__":
    logger.info("Initializing main scraper. Running in DEBUG mode." if settings.DEBUG else "Initializing main scraper.")
    try:
        asyncio.run(main())
        logger.info("Main scraper execution completed.")
    except Exception as e:
        logger.exception("An unhandled exception occurred during main scraper execution:")
