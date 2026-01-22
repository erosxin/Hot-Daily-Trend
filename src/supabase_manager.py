import os
import logging
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
from supabase import create_client, Client
import json

from src.data_models import Article
from src.config import settings

logger = logging.getLogger(__name__)
# Ensure DEBUG level logs are visible when DEBUG mode is enabled
logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

class SupabaseManager:
    """
    Manages interactions with Supabase, including client initialization and
    upserting Article data.
    """
    def __init__(self, use_service_role: bool = True):
        """
        Initialize SupabaseManager.
        
        Args:
            use_service_role: If True, use service_role key (bypasses RLS).
                            If False, use anon key (subject to RLS).
        """
        self.supabase_url = settings.SUPABASE_URL
        
        # Determine which key to use
        if use_service_role:
            # Prefer SUPABASE_SERVICE_ROLE_KEY, fallback to SUPABASE_KEY if it's service_role
            if hasattr(settings, 'SUPABASE_SERVICE_ROLE_KEY') and settings.SUPABASE_SERVICE_ROLE_KEY:
                self.supabase_key = settings.SUPABASE_SERVICE_ROLE_KEY
                key_type = "service_role"
            elif settings.supabase_key_type.startswith("service_role"):
                self.supabase_key = settings.SUPABASE_KEY
                key_type = "service_role"
            else:
                # If no service_role key available, warn but continue
                logger.warning("Service role key not found, using available key. RLS may block operations.")
                self.supabase_key = settings.SUPABASE_KEY
                key_type = settings.supabase_key_type
        else:
            # Use anon key
            if hasattr(settings, 'SUPABASE_ANON_KEY') and settings.SUPABASE_ANON_KEY:
                self.supabase_key = settings.SUPABASE_ANON_KEY
                key_type = "anon"
            else:
                self.supabase_key = settings.SUPABASE_KEY
                key_type = settings.supabase_key_type
        
        self.table_name = settings.SUPABASE_TABLE_ARTICLES

        if not self.supabase_url or not self.supabase_key or not self.table_name:
            logger.error("Supabase URL, Key, or Table Name is not configured in settings.")
            raise ValueError("Supabase configuration is incomplete.")
        
        try:
            self.client: Client = create_client(self.supabase_url, self.supabase_key)
            logger.info(f"Supabase client initialized successfully with {key_type} key.")
            logger.debug(f"Using Supabase key type: {key_type}, URL: {self.supabase_url[:40]}...")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}", exc_info=True)
            raise

    def _article_to_dict(self, article: Article) -> Dict[str, Any]:
        """
        Converts an Article Pydantic model to a dictionary suitable for Supabase insertion.
        Handles nested structures and type conversions.
        """
        try:
            # Use model_dump() for Pydantic v2+, fallback to dict() for v1
            if hasattr(article, 'model_dump'):
                article_dict = article.model_dump()
            else:
                article_dict = article.dict()
            
            # Convert HttpUrl to string
            if article_dict.get('link'):
                article_dict['link'] = str(article_dict['link'])
            if article_dict.get('image_url'):
                article_dict['image_url'] = str(article_dict['image_url'])

            # Convert datetime objects to ISO format strings
            if article_dict.get('published'):
                article_dict['published'] = article_dict['published'].isoformat()
            if article_dict.get('created_at'):
                article_dict['created_at'] = article_dict['created_at'].isoformat()
            if article_dict.get('updated_at'):
                article_dict['updated_at'] = article_dict['updated_at'].isoformat()

            # Handle list/dict fields for Supabase jsonb columns
            # IMPORTANT: Supabase Python SDK expects native Python types (list, dict) for jsonb columns
            # It will automatically serialize them to JSON. Using json.dumps() here would create
            # a string instead of jsonb, which may cause issues.
            # 
            # However, we need to ensure the data is in the correct format:
            # - Lists should be Python lists
            # - Dicts should be Python dicts
            # - None values should remain None (Supabase handles NULL)
            
            # Verify and log the types of jsonb fields
            if article_dict.get('tags') is not None:
                if not isinstance(article_dict['tags'], list):
                    logger.warning(f"tags is not a list: {type(article_dict['tags'])}. Converting...")
                    article_dict['tags'] = list(article_dict['tags']) if article_dict['tags'] else []
            if article_dict.get('main_tags') is not None:
                if not isinstance(article_dict['main_tags'], list):
                    logger.warning(f"main_tags is not a list: {type(article_dict['main_tags'])}. Converting...")
                    article_dict['main_tags'] = list(article_dict['main_tags']) if article_dict['main_tags'] else []
            
            # --- IMPORTANT: Handle entities type change ---
            # entities is now Dict[str, List[str]], should be a Python dict for jsonb
            if article_dict.get('entities') is not None:
                if not isinstance(article_dict['entities'], dict):
                    logger.warning(f"entities is not a dict: {type(article_dict['entities'])}. Converting...")
                    article_dict['entities'] = dict(article_dict['entities']) if article_dict['entities'] else {}

            if article_dict.get('authors') is not None:
                if not isinstance(article_dict['authors'], list):
                    logger.warning(f"authors is not a list: {type(article_dict['authors'])}. Converting...")
                    article_dict['authors'] = list(article_dict['authors']) if article_dict['authors'] else []
            if article_dict.get('sentiment') is not None:
                if not isinstance(article_dict['sentiment'], dict):
                    logger.warning(f"sentiment is not a dict: {type(article_dict['sentiment'])}. Converting...")
                    article_dict['sentiment'] = dict(article_dict['sentiment']) if article_dict['sentiment'] else {}

            # Final validation: ensure all jsonb fields are native Python types
            jsonb_fields = ['tags', 'main_tags', 'entities', 'authors', 'sentiment']
            for field in jsonb_fields:
                if field in article_dict and article_dict[field] is not None:
                    value = article_dict[field]
                    # If it's a string (from json.dumps), parse it back
                    if isinstance(value, str):
                        try:
                            article_dict[field] = json.loads(value)
                            logger.debug(f"Parsed {field} from JSON string back to Python object")
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse {field} from JSON string: {value[:100]}")
                    # Ensure it's the correct type
                    if field in ['tags', 'main_tags', 'authors'] and not isinstance(article_dict[field], list):
                        logger.warning(f"{field} is not a list after conversion: {type(article_dict[field])}")
                    elif field in ['entities', 'sentiment'] and not isinstance(article_dict[field], dict):
                        logger.warning(f"{field} is not a dict after conversion: {type(article_dict[field])}")
            
            logger.debug(f"Converted article to dict for Supabase: {article_dict.get('title')}")
            return article_dict
        except Exception as e:
            logger.error(f"Error converting Article to dict for Supabase: {e}", exc_info=True)
            logger.error(f"Problematic article data (title/link): {article.title} / {article.link}")
            raise

    def upsert_articles(self, articles: List[Article]) -> Tuple[int, int]:
        """
        Upserts a list of Article objects into the Supabase table.
        Uses the 'link' as the unique identifier for conflict resolution.
        
        Args:
            articles: A list of Article Pydantic models.
            
        Returns:
            A tuple (inserted_count, skipped_count) indicating the number of
            successfully inserted/updated articles and skipped articles.
        """
        if not articles:
            logger.info("No articles to upsert to Supabase.")
            return 0, 0

        # ====================================================================
        # DEDUPLICATION: Remove duplicate articles based on 'link' field
        # ====================================================================
        logger.info("=" * 70)
        logger.info("🔄 DEDUPLICATION: Removing duplicate articles based on 'link' field")
        logger.info("=" * 70)
        original_count = len(articles)
        
        seen_links = set()
        unique_articles = []
        skipped_empty_link = 0
        
        for article in articles:
            # Convert link to string for comparison (handles HttpUrl type)
            link_str = str(article.link) if article.link else None
            
            if not link_str:
                # Skip articles with empty or None link
                skipped_empty_link += 1
                logger.debug(f"Skipping article due to empty link: {article.title if hasattr(article, 'title') else 'N/A'}")
                continue
            
            # Check if we've seen this link before
            if link_str not in seen_links:
                seen_links.add(link_str)
                unique_articles.append(article)
            else:
                logger.debug(f"Skipping duplicate article with link: {link_str[:80]}...")
        
        unique_count = len(unique_articles)
        duplicate_count = original_count - unique_count - skipped_empty_link
        
        logger.info(f"Original articles: {original_count}")
        logger.info(f"Unique articles (after deduplication): {unique_count}")
        logger.info(f"Duplicates removed: {duplicate_count}")
        logger.info(f"Articles with empty link (skipped): {skipped_empty_link}")
        logger.info("=" * 70)
        
        if not unique_articles:
            logger.warning("No unique articles to upsert to Supabase after deduplication.")
            return 0, original_count
        
        # Update articles list to use deduplicated articles
        articles = unique_articles
        # ====================================================================
        
        # ====================================================================
        # DEBUGGING MODE: Minimal field insertion test
        # ====================================================================
        # We're temporarily only inserting the 'title' field to isolate the issue.
        # If this succeeds, we'll gradually add more fields one by one.
        # ====================================================================
        logger.info("=" * 70)
        logger.info("🔍 MINIMAL FIELD TEST MODE")
        logger.info("=" * 70)
        logger.info("Currently only inserting 'title' field to test basic insertion.")
        logger.info("If this succeeds, we'll add fields one by one until we find the problematic field.")
        logger.info("=" * 70)
        
        articles_to_upsert = []
        for article in articles:
            try:
                # Include all fields that may be needed for Supabase table
                # Note: 'id' field is auto-generated by Supabase, we don't need to provide it
                article_dict = {
                    "title": article.title if article.title else None,
                    "link": str(article.link) if article.link else None,
                    "published": article.published.isoformat() if article.published else None,  # Convert datetime to ISO 8601 format
                    "summary": article.summary if article.summary else None
                }
                
                # Validate at least title is not None or empty
                if not article_dict["title"]:
                    logger.warning(f"Skipping article with None or empty title: {str(article.link)[:80] if article.link else 'N/A'}...")
                    continue
                
                articles_to_upsert.append(article_dict)
            except Exception as e:
                logger.warning(f"Skipping article due to conversion error: {str(article.link)[:80] if article.link else 'N/A'}... - {e}")
                continue

        if not articles_to_upsert:
            logger.warning("All articles were skipped due to conversion errors. No data to upsert.")
            return 0, len(articles) # All original articles were skipped

        inserted_count = 0
        skipped_count = 0 # Articles that caused an error during upsert or already existed and were not updated (if RLS prevents update)

        logger.info(f"Attempting to prepare {len(articles_to_upsert)} articles for Supabase table '{self.table_name}'...")
        
        # 验证所有文章都有 title 字段（title 是必需的）
        articles_without_title = [i for i, a in enumerate(articles_to_upsert) if not a.get('title')]
        if articles_without_title:
            logger.error(f"Found {len(articles_without_title)} articles without 'title' field. Indices: {articles_without_title[:10]}")
            articles_to_upsert = [a for a in articles_to_upsert if a.get('title')]
            if not articles_to_upsert:
                logger.error("No articles with valid 'title' field remaining. Cannot proceed.")
                return 0, len(articles)
            logger.warning(f"Proceeding with {len(articles_to_upsert)} articles that have valid 'title' field.")
        
        # 验证字段类型和格式
        logger.info("=" * 70)
        logger.info("VALIDATION (all fields: title, link, published, summary)")
        logger.info("=" * 70)
        validated_articles = []
        for i, article_dict in enumerate(articles_to_upsert):
            # Validate title (required)
            if not article_dict.get('title'):
                logger.warning(f"Article {i} missing 'title' field, skipping")
                continue
            if not isinstance(article_dict['title'], str):
                logger.warning(f"Article {i} 'title' is not a string: {type(article_dict['title'])}, skipping")
                continue
            
            # Validate link (optional but should be string if present)
            if article_dict.get('link') is not None and not isinstance(article_dict['link'], str):
                logger.warning(f"Article {i} 'link' is not a string: {type(article_dict['link'])}, converting...")
                article_dict['link'] = str(article_dict['link'])
            
            # Validate published (optional but should be ISO string if present)
            if article_dict.get('published') is not None and not isinstance(article_dict['published'], str):
                logger.warning(f"Article {i} 'published' is not a string: {type(article_dict['published'])}, skipping")
                continue
            
            # Validate summary (optional, can be None or string)
            if article_dict.get('summary') is not None and not isinstance(article_dict['summary'], str):
                logger.warning(f"Article {i} 'summary' is not a string: {type(article_dict['summary'])}, setting to None")
                article_dict['summary'] = None
            
            validated_articles.append(article_dict)
        
        if len(validated_articles) != len(articles_to_upsert):
            logger.warning(f"Validated {len(validated_articles)} articles out of {len(articles_to_upsert)} original articles")
            articles_to_upsert = validated_articles
        
        logger.info(f"✅ Validation complete: {len(validated_articles)} articles ready for JSON export (all fields)")
        logger.info("=" * 70)
        
        if not articles_to_upsert:
            logger.error("No valid articles to insert after validation")
            return 0, len(articles)
        
        # 详细日志：打印待插入的数据（所有字段）
        logger.info("=" * 70)
        logger.info("DATA TO EXPORT (all fields: title, link, published, summary)")
        logger.info("=" * 70)
        if articles_to_upsert:
            # 打印前 5 个文章的 JSON 数据
            for i, article_data in enumerate(articles_to_upsert[:5]):
                logger.info(f"\n--- Article {i+1} of {len(articles_to_upsert)} ---")
                try:
                    json_str = json.dumps(article_data, indent=2, ensure_ascii=False, default=str)
                    logger.info(json_str)
                except Exception as json_e:
                    logger.error(f"Failed to serialize article {i+1} to JSON: {json_e}")
                    logger.info(f"Article {i+1} data (raw dict): {article_data}")
            
            logger.info(f"\n--- Summary ---")
            logger.info(f"Total articles to insert: {len(articles_to_upsert)}")
            logger.info(f"Fields being inserted: {list(articles_to_upsert[0].keys()) if articles_to_upsert else 'N/A'}")
            logger.info(f"First article title: {articles_to_upsert[0].get('title', 'N/A')[:80] if articles_to_upsert else 'N/A'}")
        logger.info("=" * 70)
        
        logger.info("=" * 70)
        logger.info("IMPORTANT NOTES FOR JSON EXPORT:")
        logger.info("1. All fields (title, link, published, summary) are being exported to JSON")
        logger.info("2. 'id' field is NOT included (Supabase will auto-generate it)")
        logger.info("3. 'published' is converted to ISO 8601 format string")
        logger.info("4. 'link' is converted to string (handles HttpUrl type)")
        logger.info("5. Data will be saved to 'articles_to_insert.json' for analysis")
        logger.info("6. Supabase INSERT operation is temporarily disabled")
        logger.info("=" * 70)
        
        # DEBUGGING: Temporarily use INSERT instead of UPSERT to test if data can be inserted
        # This helps us understand if the issue is with upsert logic or data format
        # IMPORTANT: Ensure the table is empty before running this test
        logger.info("=" * 70)
        logger.info("DEBUGGING MODE: Using INSERT instead of UPSERT")
        logger.info("This is a temporary change to diagnose the issue.")
        logger.info("Please ensure the 'articles' table is empty before running.")
        logger.info("=" * 70)
        logger.info("⚠️  IMPORTANT: Try-except block has been REMOVED for debugging.")
        logger.info("Any errors will now be raised directly to help identify the issue.")
        logger.info("=" * 70)
        
        logger.info(f"Calling Supabase INSERT (not UPSERT) for {len(articles_to_upsert)} articles...")
        logger.info(f"Table name: '{self.table_name}'")
        logger.info(f"First article title: {articles_to_upsert[0].get('title', 'N/A')[:80] if articles_to_upsert else 'N/A'}")
        
        # Use insert() instead of upsert() for debugging
        # This will fail if there are duplicates, but will give us clearer error messages
        # NOTE: Try-except has been removed - errors will be raised directly
        
        # ====================================================================
        # FORCE PRINT: 强制打印待插入数据的详细内容
        # ====================================================================
        print("\n" + "=" * 70)
        print("--- BEGIN DATA TO INSERT (FORCE PRINT) ---")
        print("=" * 70)
        if articles_to_upsert:
            print(f"Total articles to insert (after deduplication): {len(articles_to_upsert)}")
            print(f"Fields being inserted: {list(articles_to_upsert[0].keys()) if articles_to_upsert else 'N/A'}")
            print("\n--- Sample Articles (first 5) ---")
            for i, article_data in enumerate(articles_to_upsert[:5]):
                print(f"\n--- Article {i+1} of {len(articles_to_upsert)} ---")
                try:
                    json_str = json.dumps(article_data, indent=2, ensure_ascii=False, default=str)
                    print(json_str)
                except Exception as json_e:
                    print(f"Failed to serialize article {i+1} to JSON: {json_e}")
                    print(f"Article {i+1} data (raw dict): {article_data}")
            if len(articles_to_upsert) > 5:
                print(f"\n... (and {len(articles_to_upsert) - 5} more articles)")
        else:
            print("WARNING: articles_to_upsert is empty!")
        print("=" * 70)
        print("--- END DATA TO INSERT (FORCE PRINT) ---")
        print("=" * 70 + "\n")
        # ====================================================================
        
        # ====================================================================
        # SAVE DATA TO LOCAL JSON FILE FOR ANALYSIS
        # ====================================================================
        output_filename = "articles_to_insert.json"
        try:
            with open(output_filename, 'w', encoding='utf-8') as f:
                json.dump(articles_to_upsert, f, ensure_ascii=False, indent=2, default=str)
            logger.info("=" * 70)
            logger.info(f"✅ Successfully saved {len(articles_to_upsert)} articles to {output_filename}")
            logger.info(f"File location: {os.path.abspath(output_filename)}")
            logger.info("=" * 70)
        except Exception as e:
            logger.error(f"❌ Failed to save articles to JSON file: {e}", exc_info=True)
        # ====================================================================
        
        # ====================================================================
        # TEMPORARILY COMMENTED OUT: Supabase INSERT operation
        # We're saving data to JSON file first for analysis
        # ====================================================================
        logger.info("⚠️  Supabase INSERT operation is temporarily COMMENTED OUT.")
        logger.info("Data has been saved to articles_to_insert.json for analysis.")
        logger.info("After reviewing the JSON file, we can uncomment the INSERT code below.")
        logger.info("=" * 70)
        
        logger.info("Executing Supabase INSERT operation...")
        response = self.client.table(self.table_name).insert(articles_to_upsert).execute()
        logger.info(f"Supabase INSERT call completed. Response type: {type(response)}")
        
        # The Supabase client's execute() method returns a Response object
        # The actual data is in response.data
        # The data contains the inserted/updated rows.
        
        # 详细日志：打印完整的响应信息
        logger.info("=" * 70)
        logger.info("SUPABASE INSERT RESPONSE DETAILS")
        logger.info("=" * 70)
        logger.info(f"Response object type: {type(response)}")
        logger.info(f"Response object attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
        logger.info(f"Response has 'data' attribute: {hasattr(response, 'data')}")
        logger.info(f"Response has 'count' attribute: {hasattr(response, 'count')}")
        
        # 检查 HTTP 状态码（如果可用）
        if hasattr(response, 'status_code'):
            logger.info(f"HTTP Status Code: {response.status_code}")
        if hasattr(response, 'status_text'):
            logger.info(f"HTTP Status Text: {response.status_text}")
        
        if hasattr(response, 'data'):
            logger.info(f"Response.data type: {type(response.data)}")
            if response.data is not None:
                if isinstance(response.data, list):
                    logger.info(f"Response.data length: {len(response.data)}")
                    if len(response.data) > 0:
                        logger.info(f"First returned article keys: {list(response.data[0].keys()) if isinstance(response.data[0], dict) else 'N/A'}")
                        logger.info(f"\n--- First Returned Article (JSON) ---")
                        try:
                            first_returned_json = json.dumps(response.data[0], indent=2, ensure_ascii=False, default=str)
                            logger.info(first_returned_json)
                        except Exception as json_e:
                            logger.warning(f"Failed to serialize returned article to JSON: {json_e}")
                            logger.info(f"First returned article (raw): {response.data[0]}")
                    else:
                        logger.warning("Response.data is an empty list")
                else:
                    logger.warning(f"Response.data is not a list: {type(response.data)}")
                    logger.info(f"Response.data value: {response.data}")
            else:
                logger.warning("Response.data is None")
        else:
            logger.error("Response object does not have 'data' attribute")
        
        logger.info("=" * 70)
        
        # Check for errors in the response
        if hasattr(response, 'data') and response.data is not None:
            if isinstance(response.data, list):
                inserted_count = len(response.data)
                logger.info(f"✅ Successfully INSERTED {inserted_count} articles to Supabase.")
                skipped_count = len(articles_to_upsert) - inserted_count
                return inserted_count, skipped_count
            else:
                logger.warning(f"Response.data is not a list: {type(response.data)}")
                return 0, len(articles_to_upsert)
        else:
            logger.warning("Response.data is None or missing. No articles were inserted.")
            return 0, len(articles_to_upsert)
        
        # NOTE: Try-except block has been REMOVED for debugging purposes.
        # Any exceptions from Supabase INSERT will now be raised directly,
        # allowing us to see the full error stack trace and identify the root cause.
        # 
        # If an exception occurs, check:
        # 1. Python console output for the full exception traceback
        # 2. Supabase Dashboard -> Logs -> Database Logs for PostgreSQL error messages
        # 3. The detailed data logs printed above to verify data format

    def fetch_articles(self, limit: int = 100, days_ago: int = 7) -> List[Article]:
        """
        Fetches articles from Supabase within a specified date range.
        
        Args:
            limit: Maximum number of articles to fetch.
            days_ago: Fetch articles published within the last N days.
            
        Returns:
            A list of Article objects.
        """
        try:
            # Calculate the cutoff date
            cutoff_date = datetime.utcnow() - timedelta(days=days_ago)
            
            response = self.client.table(self.table_name) \
                .select("*") \
                .gte("published", cutoff_date.isoformat()) \
                .order("published", desc=True) \
                .limit(limit) \
                .execute()
            
            articles = []
            if hasattr(response, 'data') and response.data:
                for item in response.data:
                    try:
                        # Re-parse JSON fields back into Python objects
                        if 'tags' in item and isinstance(item['tags'], str):
                            item['tags'] = json.loads(item['tags'])
                        if 'main_tags' in item and isinstance(item['main_tags'], str):
                            item['main_tags'] = json.loads(item['main_tags'])
                        if 'entities' in item and isinstance(item['entities'], str):
                            item['entities'] = json.loads(item['entities'])
                        if 'authors' in item and isinstance(item['authors'], str):
                            item['authors'] = json.loads(item['authors'])
                        if 'sentiment' in item and isinstance(item['sentiment'], str):
                            item['sentiment'] = json.loads(item['sentiment'])

                        articles.append(Article(**item))
                    except Exception as e:
                        logger.warning(f"Failed to convert fetched data to Article object: {e}. Data: {item.get('link')}")
            logger.info(f"Fetched {len(articles)} articles from Supabase.")
            return articles
        except Exception as e:
            logger.error(f"Error fetching articles from Supabase: {e}", exc_info=True)
            return []
