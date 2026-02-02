import logging
import json
from typing import List, Dict, Any, Tuple, Set
from datetime import datetime, timedelta

import httpx
from supabase import create_client, Client

from src.data_models import Article
from src.config import settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)


class SupabaseManager:
    def __init__(self, use_service_role: bool = True):
        self.supabase_url = settings.SUPABASE_URL

        if use_service_role:
            if getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None):
                self.supabase_key = settings.SUPABASE_SERVICE_ROLE_KEY
                key_type = "service_role"
            else:
                self.supabase_key = settings.SUPABASE_KEY
                key_type = settings.supabase_key_type
        else:
            if getattr(settings, "SUPABASE_ANON_KEY", None):
                self.supabase_key = settings.SUPABASE_ANON_KEY
                key_type = "anon"
            else:
                self.supabase_key = settings.SUPABASE_KEY
                key_type = settings.supabase_key_type

        self.table_name = settings.SUPABASE_TABLE_ARTICLES

        if not self.supabase_url or not self.supabase_key or not self.table_name:
            raise ValueError("Supabase configuration is incomplete.")

        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        logger.info(f"Supabase client initialized successfully with {key_type} key.")

        self.allowed_columns: Set[str] = self._fetch_table_columns()

    def _fetch_table_columns(self) -> Set[str]:
        """Fetch table schema from PostgREST OpenAPI and cache allowed columns."""
        try:
            base_url = self.supabase_url.replace("http://", "https://").rstrip("/")
            openapi_url = f"{base_url}/rest/v1/?apikey={self.supabase_key}"
            resp = httpx.get(openapi_url, timeout=10)
            resp.raise_for_status()
            openapi = resp.json()
            definition = openapi.get("definitions", {}).get(self.table_name, {})
            props = definition.get("properties", {})
            columns = set(props.keys())
            if columns:
                logger.info(f"Detected {len(columns)} columns in Supabase table '{self.table_name}'.")
            else:
                logger.warning("Could not detect table columns from OpenAPI schema.")
            return columns
        except Exception as e:
            logger.warning(f"Failed to fetch Supabase schema, skip column filtering: {e}")
            return set()

    def _filter_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.allowed_columns:
            return payload
        filtered = {k: v for k, v in payload.items() if k in self.allowed_columns}
        dropped = set(payload.keys()) - set(filtered.keys())
        if dropped:
            logger.debug(f"Dropped fields not in table schema: {sorted(dropped)}")
        return filtered

    def _article_to_dict(self, article: Article) -> Dict[str, Any]:
        if hasattr(article, "model_dump"):
            article_dict = article.model_dump()
        else:
            article_dict = article.dict()

        if article_dict.get("link"):
            article_dict["link"] = str(article_dict["link"])
        if article_dict.get("image_url"):
            article_dict["image_url"] = str(article_dict["image_url"])

        if not article_dict.get("id") and article_dict.get("link"):
            import uuid
            article_dict["id"] = str(uuid.uuid4())

        for dt_field in ["published", "created_at", "updated_at"]:
            if article_dict.get(dt_field) and hasattr(article_dict[dt_field], "isoformat"):
                article_dict[dt_field] = article_dict[dt_field].isoformat()

        jsonb_fields = ["tags", "main_tags", "entities", "authors", "sentiment", "key_points"]
        for field in jsonb_fields:
            if field in article_dict and article_dict[field] is None:
                continue
            if field in ["tags", "main_tags", "authors", "key_points"] and not isinstance(article_dict.get(field, []), list):
                article_dict[field] = list(article_dict[field]) if article_dict[field] else []
            if field in ["entities", "sentiment"] and not isinstance(article_dict.get(field, {}), dict):
                article_dict[field] = dict(article_dict[field]) if article_dict[field] else {}

        return article_dict

    def _rest_upsert(self, payload: List[Dict[str, Any]]) -> Tuple[int, int]:
        base_url = self.supabase_url.replace("http://", "https://").rstrip("/")
        url = f"{base_url}/rest/v1/{self.table_name}?on_conflict=link"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        }
        resp = httpx.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code not in (200, 201):
            logger.error(f"Supabase upsert failed: {resp.status_code} {resp.text}")
            return 0, len(payload)
        try:
            data = resp.json()
        except Exception:
            data = []
        inserted = len(data) if isinstance(data, list) else 0
        skipped = len(payload) - inserted
        return inserted, skipped

    def upsert_articles(self, articles: List[Article]) -> Tuple[int, int]:
        if not articles:
            return 0, 0

        seen = set()
        unique_articles = []
        for article in articles:
            link_str = str(article.link) if article.link else None
            if not link_str:
                continue
            if link_str in seen:
                continue
            seen.add(link_str)
            unique_articles.append(article)

        if not unique_articles:
            return 0, len(articles)

        payload = []
        for article in unique_articles:
            try:
                article_dict = self._article_to_dict(article)
                article_dict = self._filter_payload(article_dict)
                payload.append(article_dict)
            except Exception as e:
                logger.warning(f"Skip article due to conversion error: {e}")

        if not payload:
            return 0, len(unique_articles)

        return self._rest_upsert(payload)

    def fetch_articles(self, limit: int = 100, days_ago: int = 7) -> List[Article]:
        cutoff_date = datetime.utcnow() - timedelta(days=days_ago)
        response = self.client.table(self.table_name) \
            .select("*") \
            .gte("published", cutoff_date.isoformat()) \
            .order("published", desc=True) \
            .limit(limit) \
            .execute()

        articles: List[Article] = []
        if hasattr(response, "data") and response.data:
            for item in response.data:
                for field in ["tags", "main_tags", "entities", "authors", "sentiment", "key_points"]:
                    if field in item and isinstance(item[field], str):
                        try:
                            item[field] = json.loads(item[field])
                        except Exception:
                            pass
                
                # 确保必填字段有默认值
                if 'source' not in item or not item['source']:
                    item['source'] = "Unknown Source"
                if 'key_points' not in item or item['key_points'] is None:
                    item['key_points'] = []
                if 'title' not in item:
                    item['title'] = "No Title"
                if 'link' not in item:
                    item['link'] = "https://example.com"
                if 'published' not in item:
                    item['published'] = datetime.utcnow()
                
                try:
                    articles.append(Article(**item))
                except Exception as e:
                    logger.warning(f"Failed to parse article from Supabase: {e}")
        return articles

    def fetch_favorites_needing_analysis(self, limit: int = 50) -> List[Article]:
        response = self.client.table(self.table_name) \
            .select("*") \
            .eq("is_favorite", True) \
            .is_("favorite_analysis", "null") \
            .order("updated_at", desc=True) \
            .limit(limit) \
            .execute()

        articles: List[Article] = []
        if hasattr(response, "data") and response.data:
            for item in response.data:
                for field in ["tags", "main_tags", "entities", "authors", "sentiment", "key_points"]:
                    if field in item and isinstance(item[field], str):
                        try:
                            item[field] = json.loads(item[field])
                        except Exception:
                            pass
                try:
                    articles.append(Article(**item))
                except Exception as e:
                    logger.warning(f"Failed to parse favorite article: {e}")
        return articles

    def update_favorite_analysis(self, article_id: str, analysis: str) -> None:
        self.client.table(self.table_name).update({"favorite_analysis": analysis}).eq("id", article_id).execute()
