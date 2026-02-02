# src/scrapers/rss_scraper.py
import feedparser
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, AsyncIterator, Optional
import httpx  # 新增
from bs4 import BeautifulSoup  # 新增

from src.data_models import Article

logger = logging.getLogger(__name__)


class RSSScraper:
    def __init__(self, feed_configs: List[Dict[str, str]], max_entries_per_feed: int = 100,
                 skip_full_content_for_arxiv: bool = True):
        """
        初始化 RSSScraper。
        :param feed_configs: 包含 RSS feed 配置的字典列表。
                             每个字典应包含 'name' (feed 名称) 和 'url' (feed URL)。
                             例如：[{'name': 'OpenAI Blog', 'url': 'https://openai.com/blog/rss'}, ...]
        :param max_entries_per_feed: 每个 RSS 源最多处理多少条（用于加速测试）。
        :param skip_full_content_for_arxiv: 是否跳过 arXiv RSS 的详情页抓取。
        """
        self.feed_configs = feed_configs
        self.max_entries_per_feed = max_entries_per_feed
        self.skip_full_content_for_arxiv = skip_full_content_for_arxiv
        self.last_fetched_times: Dict[str, datetime] = {}  # 记录每个 feed 最后抓取时间，用于去重和增量抓取



    async def _fetch_full_content(self, url: str) -> Optional[str]:
        """
        访问文章链接并尝试提取文章正文。
        
        :param url: 文章链接
        :return: 提取到的正文内容，如果失败则返回 None
        """
        if not url or not url.startswith(('http://', 'https://')):
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()  # 检查 HTTP 错误

            soup = BeautifulSoup(response.text, 'html.parser')

            # 尝试通过常见的标签和属性提取正文
            # 这只是一个简化的例子，实际的网页抓取需要更复杂的规则或库 (如 Goose3, newspaper3k)
            content_tags = ['article', 'main', 'div', 'p']
            for tag in content_tags:
                found_content = soup.find(tag, class_='entry-content') or \
                                soup.find(tag, id='content') or \
                                soup.find(tag, class_='post-content') or \
                                soup.find(tag, class_='article-content') or \
                                soup.find(tag, class_='post-body')
                if found_content:
                    text = found_content.get_text(separator='\n', strip=True)
                    if text and len(text) > 100:  # 确保内容足够长
                        return text
            
            # 如果找不到特定标签，退而求其次抓取所有 p 标签
            paragraphs = soup.find_all('p')
            if paragraphs:
                text = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                if text and len(text) > 100:  # 确保内容足够长
                    return text

            return None  # 无法提取

        except httpx.RequestError as e:
            logger.warning(f"Failed to fetch content from {url}: {e}")
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error when fetching content from {url}: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error processing content from {url}: {e}", exc_info=True)
        return None

    async def scrape_articles(self, days_ago: int = 1, fetch_full_content: bool = True) -> AsyncIterator[Article]:
        """
        抓取配置的 RSS feeds 的最新文章。
        :param days_ago: 抓取过去多少天内的文章。
        :param fetch_full_content: 是否尝试抓取文章的完整内容。
        :return: 一个异步迭代器，每次返回一个 Article 实例。
        """
        start_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
        start_date_utc = start_date.astimezone(timezone.utc)
        logger.info(f"Filtering RSS articles published after: {start_date_utc.isoformat()} (UTC)")

        for config in self.feed_configs:
            feed_name = config['name']
            feed_url = config['url']
            logger.info(f"Fetching RSS feed: {feed_name} from {feed_url}")

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(feed_url, follow_redirects=True)
                    response.raise_for_status()
                feed = feedparser.parse(response.text)

                if feed.bozo:
                    logger.warning(f"Error parsing feed {feed_name} ({feed_url}): {feed.bozo_exception}")
                    continue

                fetched_count = 0
                filtered_count = 0

                # arXiv RSS 通常详情页抓取慢，按配置跳过
                effective_fetch_full_content = fetch_full_content
                if self.skip_full_content_for_arxiv and 'arxiv.org' in feed_url:
                    effective_fetch_full_content = False
                    logger.info(f"Skipping full content fetch for arXiv feed: {feed_name}")

                for entry in feed.entries:
                    # 限制每个 RSS 源处理的最大条数
                    if self.max_entries_per_feed and fetched_count >= self.max_entries_per_feed:
                        logger.info(
                            f"Reached max entries limit ({self.max_entries_per_feed}) for feed '{feed_name}'."
                        )
                        break

                    fetched_count += 1
                    published_parsed = entry.get('published_parsed')
                    if published_parsed:
                        # Convert entry's published date to UTC
                        entry_published_dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
                        entry_published_utc = entry_published_dt.astimezone(timezone.utc)
                    else:
                        entry_published_utc = datetime.now(timezone.utc)  # Fallback if no published date

                    # 日期过滤
                    if entry_published_utc >= start_date_utc:
                        filtered_count += 1

                        # 构建符合 Article.from_raw_article() 期望的数据结构
                        title = entry.get('title', 'N/A')
                        link = entry.get('link', 'N/A')
                        summary = entry.get('summary', entry.get('description', ''))

                        # 提取作者列表
                        authors = []
                        if entry.get('authors'):
                            authors = [author.get('name', '') for author in entry.get('authors', []) if author.get('name')]

                        # 提取标签/分类
                        tags = []
                        if entry.get('tags'):
                            tags = [tag.get('term', '') for tag in entry.get('tags', []) if tag.get('term')]

                        article_data = {
                            "title": title,
                            "link": link,
                            "published": entry_published_utc.isoformat(),  # ISO format string
                            "source": feed_name,  # Required field
                            "authors": authors,
                            "summary": summary,
                            "tags": tags,
                            "main_tags": [],  # Will be filled by NLP processing
                            "entities": {},  # Dict[str, List[str]] format
                            "language": "en",  # Default language
                        }

                        # 创建 Article 实例
                        article = Article.from_raw_article(article_data)

                        # 尝试抓取完整内容
                        if effective_fetch_full_content and article.link:
                            logger.debug(f"Fetching full content for article: {article.title[:60]}...")
                            full_content = await self._fetch_full_content(str(article.link))
                            if full_content:
                                # Use 'content' field instead of 'full_content' for new Article model
                                article.content = full_content
                                logger.debug(f"Successfully fetched full content ({len(full_content)} chars)")
                            else:
                                logger.debug(f"Failed to fetch full content for article: {article.title[:60]}...")

                        logger.info(f"Scraped RSS article from '{feed_name}': {article.title}")
                        yield article
                    else:
                        logger.debug(f"RSS article '{entry.get('title', 'N/A')}' from '{feed_name}' "
                                     f"published: {entry_published_utc} (UTC) is too old. Excluded.")

                logger.info(f"Finished fetching feed '{feed_name}'. Total entries: {fetched_count}, "
                            f"passed date filter: {filtered_count}")

            except Exception as e:
                logger.error(f"An error occurred while scraping RSS feed '{feed_name}' ({feed_url}): {e}")

# 示例运行 (用于测试)
async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    test_feed_configs = [
        {'name': 'OpenAI Blog', 'url': 'https://openai.com/blog/rss'},
        {'name': 'Google Research Blog', 'url': 'https://blog.google/technology/ai/rss'},
        # 添加更多你产品设计中提到的 RSS 源
    ]

    rss_scraper = RSSScraper(feed_configs=test_feed_configs)
    all_rss_articles: List[Article] = []

    # 尝试抓取过去 7 天的 RSS 文章，便于测试
    async for article in rss_scraper.scrape_articles(days_ago=7, fetch_full_content=True):
        all_rss_articles.append(article)

    logger.info(f"\n--- Finished RSS Scraping ---")
    logger.info(f"Total RSS articles scraped: {len(all_rss_articles)}")
    for i, article in enumerate(all_rss_articles):
        logger.info(f"\n--- RSS Article {i+1} ---")
        logger.info(f"Title: {article.title}")
        logger.info(f"Link: {article.link}")
        logger.info(f"Published: {article.published}")
        logger.info(f"Source Type: {article.source_type}")
        logger.info(f"Source: {article.source}")
        logger.info(f"Summary: {article.summary[:150]}...")  # 只显示前150字符
        logger.info(f"Authors: {', '.join(article.authors)}")
        logger.info(f"Categories: {', '.join(article.categories)}")
        # 注意：code_link, entities, main_tags, short_description 默认是空的，会显示 None 或空列表

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
