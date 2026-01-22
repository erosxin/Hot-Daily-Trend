import asyncio
import arxiv
import logging
import re
import traceback
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

# 导入数据模型
from src.data_models import Article

# 配置日志（临时开启 DEBUG 用于调试）
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ArxivScraper:
    def __init__(self, query_categories: List[str] = ['cs.AI', 'cs.LG', 'cs.CL'], max_results_per_category: int = 20):
        """
        初始化 arXiv 抓取器。
        :param query_categories: 要查询的 arXiv 类别列表。
        :param max_results_per_category: 每个类别最多返回的论文数量。
        """
        self.query_categories = query_categories
        self.max_results_per_category = max_results_per_category
        logger.info(f"ArxivScraper initialized for categories: {', '.join(query_categories)}")

    async def scrape_articles(self, days_ago: int = 1) -> List[Article]:
        """
        从 arXiv 抓取指定天数内发布的文章。
        :param days_ago: 抓取过去多少天内发布的文章。
        :return: 抓取到的文章列表（Article 实例）。
        """
        all_arxiv_articles = []
        
        # 计算查询的日期范围 (用于本地过滤)，并提前转换为 UTC
        start_date = datetime.now(timezone.utc) - timedelta(days=days_ago)
        # 确保 start_date 是时区感知的 UTC 时间
        if start_date.tzinfo is None or start_date.tzinfo.utcoffset(start_date) is None:
            start_date_utc = start_date.replace(tzinfo=timezone.utc)
        else:
            start_date_utc = start_date.astimezone(timezone.utc)
        
        logger.info(f"Filtering papers published after: {start_date_utc} (UTC)")
        
        for category in self.query_categories:
            # 简化查询字符串，让 arxiv 库处理日期筛选
            query_string = f'cat:{category}'
            logger.info(f"Searching arXiv for category '{category}' with query: '{query_string}'")
            
            try:
                # arxiv 库的 search 方法是同步的，需要通过 asyncio.to_thread 包装
                search_results = await asyncio.to_thread(
                    arxiv.Search,
                    query=query_string,
                    max_results=self.max_results_per_category,  # 依然限制最大结果数
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending
                )
                
                # 获取所有结果
                client = arxiv.Client()  # 在循环内部创建 client
                all_papers_raw = await asyncio.to_thread(list, client.results(search_results))
                
                logger.info(f"Got {len(all_papers_raw)} papers from arXiv API for category '{category}'")
                
                logger.info(f"Category '{category}': Total papers fetched before filtering: {len(all_papers_raw)}")
                logger.debug(f"Filter start_date (UTC): {start_date_utc}")
                
                filtered_papers = []
                for p in all_papers_raw:
                    if p.published:
                        # 确保日期都是时区感知的 UTC 时间
                        # 如果 p.published 是 naive datetime，将其转换为 UTC
                        if p.published.tzinfo is None or p.published.tzinfo.utcoffset(p.published) is None:
                            published_utc = p.published.replace(tzinfo=timezone.utc)
                        else:
                            published_utc = p.published.astimezone(timezone.utc)
                        
                        # 调试信息：打印每篇论文的日期和比较结果
                        comparison_result = published_utc >= start_date_utc
                        logger.debug(f"  Paper: '{p.title[:60] if p.title else 'Unknown'}...'")
                        logger.debug(f"    Published (UTC): {published_utc}")
                        logger.debug(f"    Comparison: {published_utc} >= {start_date_utc} -> {comparison_result}")

                        if comparison_result:
                            filtered_papers.append(p)
                            logger.debug(f"    ✓ Included")
                        else:
                            logger.debug(f"    ✗ Excluded (too old)")
                    else:
                        logger.debug(f"  Paper '{p.title[:60] if p.title else 'Unknown'}...' has no published date - excluded")
                
                papers = filtered_papers
                
                logger.info(f"Category '{category}': {len(papers)} papers passed filtering (from {len(all_papers_raw)} total)")
                
                for paper in papers:
                    try:
                        # 确保日期是 UTC 并格式化为 ISO 格式
                        published_utc = None
                        if paper.published:
                            if paper.published.tzinfo is None or paper.published.tzinfo.utcoffset(paper.published) is None:
                                published_utc = paper.published.replace(tzinfo=timezone.utc)
                            else:
                                published_utc = paper.published.astimezone(timezone.utc)
                        
                        # 从 entry_id 中提取短 ID（例如从 http://arxiv.org/abs/1234.5678v1 提取 1234.5678）
                        paper_id = None
                        if paper.entry_id:
                            match = re.search(r'/(\d+\.\d+)', paper.entry_id)
                            if match:
                                paper_id = match.group(1)
                        
                        # 寻找代码链接的简化逻辑（安全地处理 None 值）
                        code_link = None
                        for link in paper.links:
                            link_title = getattr(link, 'title', '') or ''
                            link_url = str(getattr(link, 'url', '')) or ''
                            
                            if 'code' in link_title.lower() or 'code' in link_url.lower():
                                code_link = link_url
                                break
                        
                        # 构建符合 Article.from_raw_article() 期望的数据结构
                        article_data = {
                            "title": paper.title or "",
                            "link": paper.entry_id,  # arXiv paper ID acts as a direct link to abstract page
                            "published": published_utc.isoformat() if published_utc else datetime.now(timezone.utc).isoformat(),  # Use ISO format string
                            "source": "arXiv API",  # Required field
                            "authors": [author.name for author in paper.authors] if paper.authors else [],
                            "summary": paper.summary or "",
                            "tags": list(paper.categories) if paper.categories else [],  # Use 'tags' instead of 'categories' for compatibility
                            "main_tags": [],  # Will be filled by NLP processing
                            "entities": {},  # Changed from [] to {} to match new Article model (Dict[str, List[str]])
                            "language": "en",  # Default language
                        }
                        
                        # 将字典数据转换为 Article 实例
                        article_instance = Article.from_raw_article(article_data)
                        logger.info(f"Scraped article: {article_instance.title}")
                        all_arxiv_articles.append(article_instance)
                    
                    except Exception as e:
                        logger.error(f"Error processing paper '{paper.title if paper.title else 'Unknown'}': {e}")
                        continue
            
            except Exception as e:
                error_type = type(e).__name__
                logger.error(f"Error scraping arXiv category '{category}' ({error_type}): {e}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
                logger.info(f"Continuing with next category...")
            
            # 在不同类别查询之间添加延迟，避免触发速率限制
            await asyncio.sleep(2)
        
        logger.info(f"Finished scraping arXiv. Total articles found: {len(all_arxiv_articles)}")
        return all_arxiv_articles

# 示例用法
async def main():
    # 配置为 Minimal Test Configuration with extended days_ago
    logger.info("=== Starting ArXiv Scraper - Minimal Test Configuration ===")
    logger.info("Configuration: category=cs.AI, max_results=5, days_ago=7")
    
    scraper = ArxivScraper(query_categories=['cs.AI'], max_results_per_category=5)
    articles = await scraper.scrape_articles(days_ago=7)  # 将 days_ago 从 1 增加到 7

    # 打印前5条文章作为示例
    for i, article in enumerate(articles[:5]):
        print(f"\n--- ArXiv Article {i+1} ---")
        print(f"Title: {article.title}")
        print(f"Link: {article.link}")
        print(f"Published: {article.published}")
        print(f"Authors: {', '.join(article.authors)}")
        print(f"Categories: {', '.join(article.categories)}")
        print(f"Summary: {article.summary[:200]}...")  # 限制摘要长度
        if article.code_link:
            print(f"Code Link: {article.code_link}")
        print(f"Source: {article.source} ({article.source_type})")
        print(f"Time: {article.time}")
        print(f"Entities: {', '.join(article.entities) if article.entities else 'None'}")
        print(f"Main Tags: {', '.join(article.main_tags) if article.main_tags else 'None'}")
    
    if not articles:
        print("\nNo ArXiv articles were scraped.")


if __name__ == "__main__":
    # 确保安装了 arxiv 库
    # pip install arxiv
    try:
        asyncio.run(main())
    except ImportError:
        logger.error("Please install 'arxiv' library: pip install arxiv")
    except Exception as e:
        logger.critical(f"An unexpected error occurred during ArXiv scraping: {e}")
