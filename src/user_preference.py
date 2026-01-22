# src/user_preference.py
from dataclasses import dataclass, field
from typing import List

@dataclass
class UserPreference:
    """
    用户偏好数据模型。
    用于存储用户的个性化偏好设置，以便进行文章推荐和过滤。
    """
    user_id: str  # 用户唯一ID
    preferred_sources: List[str] = field(default_factory=list)  # 偏好来源 (e.g., 'arXiv API', 'OpenAI Blog')
    preferred_categories: List[str] = field(default_factory=list)  # 偏好分类 (e.g., 'cs.AI', '媒体/官方')
    preferred_entities: List[str] = field(default_factory=list)  # 偏好实体 (e.g., 'LLM', 'Google', 'OpenAI')
    preferred_tags: List[str] = field(default_factory=list)  # 偏好主线标签 (e.g., '能力', '格局')
    excluded_keywords: List[str] = field(default_factory=list)  # 排除关键词
    min_score: float = 0.0  # 最小匹配分数，用于未来更复杂的推荐算法
