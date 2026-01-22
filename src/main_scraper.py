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
    rss_scraper = RSSScraper(feed_configs=rss_feed_configs)
    rss_task = collect_from_async_iterator(
        rss_scraper.scrape_articles(days_ago=settings.DAYS_AGO, fetch_full_content=True)
    )
    scraper_tasks.append(rss_task)
    logger.info(f"RSSScraper task created for {len(rss_feed_configs)} feeds")
    
    # SerperNewsScraper - Note: This scraper only has a search() method, not scrape_articles()
    # We'll skip it for now
    logger.info("Note: SerperNewsScraper is skipped as it requires additional conversion logic.")

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
    has_articles_to_upsert = bool(processed_articles)

    logger.info(f"Supabase Manager initialized and configured: {is_supabase_ready}")
    logger.info(f"Processed articles available for upsert: {has_articles_to_upsert} (Count: {len(processed_articles)})")
    
    if is_supabase_ready and has_articles_to_upsert:
        logger.info("Conditions met: Attempting to upsert articles to Supabase.")
        
        # Log sample article structure before upsert
        if processed_articles:
            sample_for_upsert = processed_articles[0]
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
        
        logger.info(f"Attempting to upsert {len(processed_articles)} articles to Supabase table '{supabase_manager.table_name}'...")
        try:
            # SupabaseManager.upsert_articles is synchronous, wrap with asyncio.to_thread
            inserted_count, skipped_count = await asyncio.to_thread(
                supabase_manager.upsert_articles, processed_articles
            )
            logger.info(f"Supabase upsert result: Inserted/Updated: {inserted_count}, Skipped: {skipped_count}")
            if inserted_count == 0 and skipped_count == len(processed_articles) and len(processed_articles) > 0:
                logger.warning("All articles were skipped by Supabase. This often indicates RLS policies are blocking INSERT/UPDATE, or all articles already exist.")
            elif inserted_count < len(processed_articles):
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

    # --- New steps: Static Page Generation and Email Sending ---
    logger.info("Proceeding with generating static HTML page and preparing email content.")
    try:
        logger.info(f"Using output directory: {settings.OUTPUT_DIR}")
        logger.info(f"Using recipient email: {settings.RECIPIENT_EMAIL}")
        logger.info(f"Using sender email: {settings.SENDER_EMAIL}")
        logger.info(f"Using GitHub Pages Base URL: {settings.GITHUB_PAGES_BASE_URL}")
    except AttributeError as e:
        logger.warning(f"Some configuration attributes are missing: {e}. Using defaults.")
        logger.info("Note: OUTPUT_DIR, RECIPIENT_EMAIL, SENDER_EMAIL, GITHUB_PAGES_BASE_URL may not be configured.")

    # Use DisplayModule with processed_articles
    if processed_articles:
        display_module = DisplayModule() # No articles passed at init
        mindmap_content = display_module.generate_mindmap_markdown(processed_articles)
        timeline_content = display_module.generate_timeline_markdown(processed_articles)
        summary_statistics = display_module.generate_summary_statistics(processed_articles)
        
        logger.info(f"Generated mindmap content (first 200 chars): {mindmap_content[:200]}...")
        logger.info(f"Generated timeline content (first 200 chars): {timeline_content[:200]}...")
        logger.info(f"Generated summary statistics (first 200 chars): {summary_statistics[:200]}...")
        
        # Placeholder for writing to files and sending email
        # Example:
        # with open(os.path.join(settings.OUTPUT_DIR, "mindmap.md"), "w", encoding="utf-8") as f:
        #     f.write(mindmap_content)
        # with open(os.path.join(settings.OUTPUT_DIR, "timeline.md"), "w", encoding="utf-8") as f:
        #     f.write(timeline_content)
        # EmailSender.send_email(to=settings.RECIPIENT_EMAILS, subject="Daily Trend Report", body=timeline_content)
        
    else:
        logger.warning("No processed articles available for DisplayModule. Static page and email content will be empty or minimal.")

    logger.info("Static page generation and email sending will be finalized in subsequent steps.")
    # --- End of new steps ---

    end_time = datetime.now()
    duration = end_time - start_time
    logger.info(f"Main scraper pipeline finished. Total duration: {duration}")


async def collect_from_async_iterator(async_iterator: AsyncIterator[Article]) -> List[Article]:
    """Helper to collect all items from an async iterator into a list."""
    items = []
    async for item in async_iterator:
        items.append(item)
    return items


if __name__ == "__main__":
    logger.info("Initializing main scraper. Running in DEBUG mode." if settings.DEBUG else "Initializing main scraper.")
    try:
        asyncio.run(main())
        logger.info("Main scraper execution completed.")
    except Exception as e:
        logger.exception("An unhandled exception occurred during main scraper execution:")
