# src/event_aggregator.py
import logging
from typing import List
import re

from src.data_models import Article

logger = logging.getLogger(__name__)

class EventAggregator:
    def __init__(self, similarity_threshold: float = 0.7):
        """
        初始化事件聚合器。
        
        :param similarity_threshold: 判断两篇文章是否相似的阈值 (0.0 到 1.0)。
                                     值越高，要求越严格，只有非常相似的文章才会被聚合。
        """
        self.similarity_threshold = similarity_threshold

    def _normalize_text(self, text: str) -> str:
        """
        标准化文本，去除标点、转小写。
        
        :param text: 待标准化的文本
        :return: 标准化后的文本
        """
        if not text:
            return ""
        # 去除标点符号，保留字母、数字和空格
        normalized = re.sub(r'[^\w\s]', '', text)
        # 转小写并去除首尾空格
        normalized = normalized.lower().strip()
        # 将多个空格替换为单个空格
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    def _jaccard_similarity(self, s1: str, s2: str) -> float:
        """
        计算两个字符串的 Jaccard 相似度（基于词集合的交集与并集）。
        
        :param s1: 第一个字符串
        :param s2: 第二个字符串
        :return: Jaccard 相似度 (0.0 到 1.0)
        """
        if not s1 or not s2:
            return 0.0
        
        # 将字符串分割为词集合
        set1 = set(s1.split())
        set2 = set(s2.split())
        
        # 计算交集和并集
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        # 返回相似度
        return intersection / union if union != 0 else 0.0

    def _calculate_similarity(self, article1: Article, article2: Article) -> float:
        """
        计算两篇文章的相似度。
        结合标题和短描述（如果存在）来计算相似度。
        
        :param article1: 第一篇文章
        :param article2: 第二篇文章
        :return: 相似度分数 (0.0 到 1.0)
        """
        # 标准化标题
        title1 = self._normalize_text(article1.title)
        title2 = self._normalize_text(article2.title)
        
        # 计算标题相似度
        title_similarity = self._jaccard_similarity(title1, title2)
        
        # 如果标题相似度已经很高，直接返回
        if title_similarity >= self.similarity_threshold:
            return title_similarity
        
        # 如果标题相似度不够，尝试结合短描述
        if article1.short_description and article2.short_description:
            text1_extended = self._normalize_text(article1.title + " " + article1.short_description)
            text2_extended = self._normalize_text(article2.title + " " + article2.short_description)
            extended_similarity = self._jaccard_similarity(text1_extended, text2_extended)
            
            # 返回较高的相似度
            return max(title_similarity, extended_similarity)
        
        return title_similarity

    def aggregate_events(self, articles: List[Article]) -> List[List[Article]]:
        """
        聚合相似的文章，形成事件组。
        使用简单的聚类算法：如果两篇文章的相似度超过阈值，它们将被归入同一个事件组。
        
        :param articles: 待聚合的文章列表
        :return: 包含多个文章列表的列表，每个内部列表代表一个聚合事件
        """
        if not articles:
            return []

        logger.info(f"Starting event aggregation for {len(articles)} articles with threshold {self.similarity_threshold}...")

        # 存储所有已经聚合过的文章的索引
        processed_indices = set()
        aggregated_events: List[List[Article]] = []

        for i, article1 in enumerate(articles):
            if i in processed_indices:
                continue  # 如果已经被聚合，跳过

            current_event = [article1]
            processed_indices.add(i)

            # 查找与当前文章相似的其他文章
            for j, article2 in enumerate(articles):
                if i == j or j in processed_indices:
                    continue  # 不与自己比较，跳过已聚合的文章

                # 计算相似度
                similarity = self._calculate_similarity(article1, article2)

                if similarity >= self.similarity_threshold:
                    current_event.append(article2)
                    processed_indices.add(j)
                    logger.debug(f"Articles '{article1.title[:50]}...' and '{article2.title[:50]}...' "
                                f"grouped together (similarity: {similarity:.2f})")
            
            aggregated_events.append(current_event)
        
        # 统计聚合结果
        total_articles = len(articles)
        total_events = len(aggregated_events)
        avg_articles_per_event = total_articles / total_events if total_events > 0 else 0
        
        logger.info(f"Finished event aggregation. Found {total_events} distinct events from {total_articles} articles.")
        logger.info(f"Average {avg_articles_per_event:.2f} articles per event.")
        
        return aggregated_events

    def deduplicate_articles(self, articles: List[Article]) -> List[Article]:
        """
        从聚合的事件组中选取最具代表性的文章，实现去重。
        
        当前策略：从每个事件组中选择第一篇文章作为代表。
        未来可以改进为：
        - 选择发布时间最新的文章
        - 选择来自更权威来源的文章
        - 选择标题更全面的文章
        - 选择内容更长的文章
        
        :param articles: 待去重的文章列表
        :return: 去重后的文章列表
        """
        aggregated_events = self.aggregate_events(articles)
        deduplicated_articles: List[Article] = []
        
        for event in aggregated_events:
            if not event:
                continue
            
            # 简单策略：选择第一篇文章作为代表
            # 未来可以改进为更智能的选择策略
            representative_article = event[0]
            
            # 如果事件组中有多篇文章，记录聚合信息
            if len(event) > 1:
                logger.debug(f"Event with {len(event)} articles, selected '{representative_article.title[:50]}...' as representative")
            
            deduplicated_articles.append(representative_article)
        
        original_count = len(articles)
        deduplicated_count = len(deduplicated_articles)
        reduction_rate = (1 - deduplicated_count / original_count) * 100 if original_count > 0 else 0
        
        logger.info(f"Deduplicated {original_count} articles to {deduplicated_count} unique articles "
                   f"(reduction: {reduction_rate:.1f}%).")
        
        return deduplicated_articles

    def get_aggregation_stats(self, articles: List[Article]) -> dict:
        """
        获取聚合统计信息。
        
        :param articles: 待分析的文章列表
        :return: 包含统计信息的字典
        """
        aggregated_events = self.aggregate_events(articles)
        
        event_sizes = [len(event) for event in aggregated_events]
        
        stats = {
            "total_articles": len(articles),
            "total_events": len(aggregated_events),
            "avg_articles_per_event": sum(event_sizes) / len(event_sizes) if event_sizes else 0,
            "max_event_size": max(event_sizes) if event_sizes else 0,
            "min_event_size": min(event_sizes) if event_sizes else 0,
            "single_article_events": sum(1 for size in event_sizes if size == 1),
            "multi_article_events": sum(1 for size in event_sizes if size > 1),
        }
        
        return stats
