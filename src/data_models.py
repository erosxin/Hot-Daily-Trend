from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union

from pydantic import BaseModel, Field, HttpUrl, validator

class Article(BaseModel):
    """
    Represents a structured article with various metadata and content.
    """
    id: Optional[str] = Field(None, description="Unique identifier for the article, generated if not provided.")
    title: str = Field(..., min_length=5, max_length=250, description="Title of the article.")
    link: HttpUrl = Field(..., description="URL to the original article.")
    published: datetime = Field(..., description="Publication date and time of the article.")
    source: str = Field(..., description="Source (e.g., website name, RSS feed title) of the article.")
    summary: Optional[str] = Field(None, min_length=20, description="Generated summary of the article content.")
    content: Optional[str] = Field(None, description="Full or partial content of the article.")

    summary_zh: Optional[str] = Field(None, min_length=10, description="中文简报")
    is_favorite: bool = Field(False, description="是否收藏")

    key_points: List[str] = Field(default_factory=list, description="三条要点（中文）")
    trend_tag: Optional[str] = Field(None, description="趋势标签")
    heat_score: Optional[float] = Field(None, description="热度评分 0-100")
    favorite_analysis: Optional[str] = Field(None, description="收藏后AI简析（中文）")
    plain_summary: Optional[str] = Field(None, description="通俗总结（用简单的话解释专业术语）")
    image_url: Optional[HttpUrl] = Field(None, description="URL of the main image for the article.")
    tags: List[str] = Field(default_factory=list, description="Keywords or categories associated with the article.")
    main_tags: List[str] = Field(default_factory=list, description="Primary tags extracted from the article.")
    entities: Dict[str, List[str]] = Field(default_factory=dict, description="Named entities detected (e.g., people, organizations, locations).")
    authors: List[str] = Field(default_factory=list, description="Authors of the article.")
    language: Optional[str] = Field("en", max_length=10, description="Language of the article content (e.g., 'en', 'zh').")
    
    # NLP specific fields (optional as they are added post-scraping)
    sentiment: Optional[Dict[str, float]] = Field(None, description="Sentiment analysis scores (e.g., positive, negative, neutral).")
    readability_score: Optional[float] = Field(None, description="Readability score of the article.")
    
    # Metadata for internal use, not necessarily for display
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the article record was created in the system.")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp when the article record was last updated in the system.")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            HttpUrl: lambda v: str(v),
        }
        allow_population_by_field_name = True
        arbitrary_types_allowed = True # Needed for HttpUrl type

    @validator('link', 'image_url', pre=True)
    def convert_url_to_httpurl(cls, v):
        if isinstance(v, str):
            # Attempt to prepend 'https://' if schema is missing, for HttpUrl validation
            if not v.startswith('http://') and not v.startswith('https://'):
                v = 'https://' + v
        return v
    
    @validator('published', pre=True)
    def parse_published_date(cls, v):
        if isinstance(v, datetime):
            return v
        if isinstance(v, date): # If it's a date object, convert to datetime at midnight UTC
            return datetime(v.year, v.month, v.day, 0, 0, 0)
        if isinstance(v, str):
            # Attempt to parse common date formats
            for fmt in ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%a, %d %b %Y %H:%M:%S %Z'):
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    pass
            # Try parsing with dateutil if other formats fail
            try:
                from dateutil.parser import parse
                return parse(v)
            except ImportError:
                # Fallback if dateutil is not installed
                pass
            except Exception:
                pass # Let Pydantic's HttpUrl handle other invalid cases
        raise ValueError(f"Could not parse '{v}' into a datetime object.")

    @staticmethod
    def from_raw_article(raw_article: Dict[str, Any]) -> 'Article':
        """
        Creates an Article instance from a raw dictionary scraped by a scraper.
        This method handles potential variations in raw article data and
        converts them into the structured Article model.
        """
        # Ensure 'link' is present and valid for HttpUrl conversion
        link = raw_article.get('link') or raw_article.get('url')
        if not link:
            raise ValueError("Raw article is missing 'link' or 'url' field.")
        
        # Ensure 'published' is present and can be parsed
        published_date = raw_article.get('published') or raw_article.get('pubDate') or raw_article.get('publish_date')
        if not published_date:
            # Fallback to current UTC time if no published date is found
            published_date = datetime.utcnow()
            
        # Ensure 'source' is present
        source = raw_article.get('source') or raw_article.get('feed_title') or "Unknown Source"

        # Dynamically set 'id' if not provided
        article_id = raw_article.get('id')
        if not article_id and link:
            import hashlib
            article_id = hashlib.sha256(link.encode('utf-8')).hexdigest()

        return Article(
            id=article_id,
            title=raw_article.get('title', 'No Title'),
            link=link,
            published=published_date,
            source=source,
            summary=raw_article.get('summary') or raw_article.get('description'),
            content=raw_article.get('content'),
            image_url=raw_article.get('image_url') or raw_article.get('image'),
            tags=raw_article.get('tags', []),
            main_tags=raw_article.get('main_tags', []),
            entities=raw_article.get('entities', {}),
            authors=raw_article.get('authors', []),
            language=raw_article.get('language', 'en'),
            sentiment=raw_article.get('sentiment'),
            readability_score=raw_article.get('readability_score'),
            created_at=raw_article.get('created_at', datetime.utcnow()),
            updated_at=raw_article.get('updated_at', datetime.utcnow()),
        )

# Example usage (for testing data_models.py in isolation)
if __name__ == '__main__':
    print("Testing Article model...")
    
    # Test 1: Basic article
    raw_data_1 = {
        "title": "A New Study on AI Ethics",
        "link": "https://example.com/ai-ethics-study",
        "published": "2023-10-26T10:00:00Z",
        "source": "Tech News Daily",
        "summary": "This is a summary of the new AI ethics study.",
        "tags": ["AI", "Ethics"],
        "authors": ["Dr. Jane Doe"],
        "image_url": "https://example.com/ai-image.jpg"
    }
    article_1 = Article.from_raw_article(raw_data_1)
    print(f"Article 1: {article_1.json(indent=2)}")
    assert article_1.title == "A New Study on AI Ethics"
    assert str(article_1.link) == "https://example.com/ai-ethics-study"
    print("Test 1 passed.")

    # Test 2: Missing optional fields, different date format
    raw_data_2 = {
        "title": "Future of Quantum Computing",
        "url": "example.org/quantum", # Using 'url' instead of 'link'
        "published": "2023-11-15", # Date only
        "source": "Quantum World"
    }
    article_2 = Article.from_raw_article(raw_data_2)
    print(f"Article 2: {article_2.json(indent=2)}")
    assert article_2.summary is None
    assert article_2.published.year == 2023
    assert "https://example.org/quantum" in str(article_2.link) # HttpUrl adds https
    print("Test 2 passed.")

    # Test 3: Missing published date
    raw_data_3 = {
        "title": "Space Exploration Latest",
        "link": "https://space.com/explore",
        "source": "Space Today"
    }
    article_3 = Article.from_raw_article(raw_data_3)
    print(f"Article 3: {article_3.json(indent=2)}")
    assert article_3.published is not None # Should default to utcnow()
    print("Test 3 passed.")

    # Test 4: Invalid link (should raise error)
    raw_data_4 = {
        "title": "Invalid Link",
        "link": "not-a-valid-url",
        "published": "2023-01-01",
        "source": "Test"
    }
    try:
        Article.from_raw_article(raw_data_4)
        print("Test 4 failed (expected ValueError for invalid link).")
    except Exception as e:
        print(f"Test 4 passed (caught expected error: {e}).")
        assert "value is not a valid URL" in str(e)
    
    # Test 5: Missing link (should raise error)
    raw_data_5 = {
        "title": "Missing Link",
        "published": "2023-01-01",
        "source": "Test"
    }
    try:
        Article.from_raw_article(raw_data_5)
        print("Test 5 failed (expected ValueError for missing link).")
    except Exception as e:
        print(f"Test 5 passed (caught expected error: {e}).")
        assert "missing 'link' or 'url' field" in str(e)

    print("\nAll tests for Article model completed.")
