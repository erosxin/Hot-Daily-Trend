# src/database.py
import json
import sqlite3
import logging
from typing import List, Optional
from pathlib import Path

from src.data_models import Article
from src.user_preference import UserPreference

logger = logging.getLogger(__name__)

DATABASE_FILE = "ai_news_feed.db"

class DatabaseManager:
    def __init__(self, db_file: str = DATABASE_FILE):
        """
        初始化数据库管理器。
        
        :param db_file: 数据库文件路径，默认为 "ai_news_feed.db"
        """
        # 如果提供的是相对路径，转换为绝对路径（相对于项目根目录）
        if not Path(db_file).is_absolute():
            # 获取项目根目录（假设 database.py 在 src/ 目录下）
            project_root = Path(__file__).parent.parent
            self.db_file = str(project_root / db_file)
        else:
            self.db_file = db_file
        self.conn = None

    def connect(self):
        """建立数据库连接"""
        try:
            self.conn = sqlite3.connect(self.db_file)
            self.conn.row_factory = sqlite3.Row  # 使查询结果可以通过字典方式访问
            logger.info(f"Connected to database: {self.db_file}")
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")

    def create_tables(self):
        """创建 Article 表"""
        if not self.conn:
            raise ConnectionError("Database not connected.")
        
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                link TEXT UNIQUE NOT NULL,
                published TEXT NOT NULL,
                summary TEXT,
                full_content TEXT,
                time TEXT NOT NULL,
                source_type TEXT,
                source TEXT NOT NULL,
                authors TEXT, -- 存储为 JSON 字符串
                categories TEXT, -- 存储为 JSON 字符串
                code_link TEXT,
                entities TEXT, -- 存储为 JSON 字符串
                main_tags TEXT, -- 存储为 JSON 字符串
                short_description TEXT,
                multimodal_description TEXT, -- 新增列：用于存储多模态信息抽取结果
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引以提高查询性能
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_link ON articles(link)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_published ON articles(published)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source ON articles(source)
        """)
        
        # 创建用户偏好表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id TEXT PRIMARY KEY,
                preferred_sources TEXT,
                preferred_categories TEXT,
                preferred_entities TEXT,
                preferred_tags TEXT,
                excluded_keywords TEXT,
                min_score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
        logger.info("Tables 'articles' and 'user_preferences' and indexes ensured to exist.")

    def insert_article(self, article: Article) -> Optional[int]:
        """
        插入单个 Article 实例。
        
        :param article: 要插入的 Article 实例
        :return: 插入成功返回新插入行的 ID，如果重复则返回 None
        """
        if not self.conn:
            raise ConnectionError("Database not connected.")
        
        cursor = self.conn.cursor()
        try:
            # 将列表字段转换为 JSON 字符串以便存储
            authors_json = json.dumps(article.authors, ensure_ascii=False)
            categories_json = json.dumps(article.categories, ensure_ascii=False)
            entities_json = json.dumps(article.entities, ensure_ascii=False)
            main_tags_json = json.dumps(article.main_tags, ensure_ascii=False)

            cursor.execute("""
                INSERT INTO articles (
                    title, link, published, summary, full_content, time, 
                    source_type, source, authors, categories, code_link,
                    entities, main_tags, short_description, multimodal_description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.title, article.link, article.published, article.summary, 
                article.full_content, article.time,
                article.source_type, article.source, authors_json, categories_json, 
                article.code_link,
                entities_json, main_tags_json, article.short_description, article.multimodal_description
            ))
            self.conn.commit()
            logger.debug(f"Inserted article: {article.title[:60]}...")
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Article with link '{article.link}' already exists. Skipping insertion.")
            return None
        except sqlite3.Error as e:
            logger.error(f"Error inserting article '{article.title[:60]}...': {e}")
            self.conn.rollback()
            raise

    def insert_articles_batch(self, articles: List[Article]) -> tuple[int, int]:
        """
        批量插入 Article 实例。
        
        :param articles: 要插入的 Article 实例列表
        :return: (插入成功数量, 跳过数量) 的元组
        """
        if not self.conn:
            raise ConnectionError("Database not connected.")
        
        cursor = self.conn.cursor()
        inserted_count = 0
        skipped_count = 0
        
        for article in articles:
            try:
                # 将列表字段转换为 JSON 字符串
                authors_json = json.dumps(article.authors, ensure_ascii=False)
                categories_json = json.dumps(article.categories, ensure_ascii=False)
                entities_json = json.dumps(article.entities, ensure_ascii=False)
                main_tags_json = json.dumps(article.main_tags, ensure_ascii=False)

                cursor.execute("""
                    INSERT INTO articles (
                        title, link, published, summary, full_content, time, 
                        source_type, source, authors, categories, code_link,
                        entities, main_tags, short_description, multimodal_description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    article.title, article.link, article.published, article.summary, 
                    article.full_content, article.time,
                    article.source_type, article.source, authors_json, categories_json, 
                    article.code_link,
                    entities_json, main_tags_json, article.short_description, article.multimodal_description
                ))
                inserted_count += 1
            except sqlite3.IntegrityError:
                skipped_count += 1
                logger.debug(f"Article with link '{article.link}' already exists. Skipping insertion.")
            except sqlite3.Error as e:
                logger.error(f"Error preparing article '{article.title[:60]}...' for batch insertion: {e}")
                
        self.conn.commit()
        logger.info(f"Batch insertion completed. Inserted: {inserted_count}, Skipped (duplicates): {skipped_count}.")
        return (inserted_count, skipped_count)

    def fetch_all_articles(self) -> List[Article]:
        """
        从数据库中获取所有文章。
        
        :return: Article 实例列表
        """
        if not self.conn:
            raise ConnectionError("Database not connected.")
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM articles ORDER BY published DESC")
        rows = cursor.fetchall()
        
        articles = []
        for row in rows:
            try:
                # 将 JSON 字符串转换回列表
                authors = json.loads(row['authors']) if row['authors'] else []
                categories = json.loads(row['categories']) if row['categories'] else []
                entities = json.loads(row['entities']) if row['entities'] else []
                main_tags = json.loads(row['main_tags']) if row['main_tags'] else []

                article = Article(
                    title=row['title'],
                    link=row['link'],
                    published=row['published'],
                    summary=row['summary'] or '',
                    full_content=row['full_content'],
                    source_type=row['source_type'] or '未知',
                    source=row['source'],
                    authors=authors,
                    categories=categories,
                    code_link=row['code_link'],
                    entities=entities,
                    main_tags=main_tags,
                    short_description=row['short_description'] or '',
                    multimodal_description=row['multimodal_description']
                )
                articles.append(article)
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON for article '{row['title'][:60]}...': {e}")
                continue
            except Exception as e:
                logger.error(f"Error reconstructing article from database row: {e}")
                continue
        
        return articles

    def get_article_count(self) -> int:
        """
        获取数据库中的文章总数。
        
        :return: 文章数量
        """
        if not self.conn:
            raise ConnectionError("Database not connected.")
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM articles")
        return cursor.fetchone()[0]

    def get_articles_by_source(self, source: str) -> List[Article]:
        """
        根据来源获取文章。
        
        :param source: 来源名称
        :return: Article 实例列表
        """
        if not self.conn:
            raise ConnectionError("Database not connected.")
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM articles WHERE source = ? ORDER BY published DESC", (source,))
        rows = cursor.fetchall()
        
        articles = []
        for row in rows:
            try:
                authors = json.loads(row['authors']) if row['authors'] else []
                categories = json.loads(row['categories']) if row['categories'] else []
                entities = json.loads(row['entities']) if row['entities'] else []
                main_tags = json.loads(row['main_tags']) if row['main_tags'] else []

                article = Article(
                    title=row['title'],
                    link=row['link'],
                    published=row['published'],
                    summary=row['summary'] or '',
                    full_content=row['full_content'],
                    source_type=row['source_type'] or '未知',
                    source=row['source'],
                    authors=authors,
                    categories=categories,
                    code_link=row['code_link'],
                    entities=entities,
                    main_tags=main_tags,
                    short_description=row['short_description'] or '',
                    multimodal_description=row['multimodal_description']
                )
                articles.append(article)
            except Exception as e:
                logger.error(f"Error reconstructing article from database row: {e}")
                continue
        
        return articles

    def save_user_preference(self, preference: UserPreference):
        """
        保存或更新用户偏好。
        
        :param preference: 要保存的 UserPreference 实例
        """
        if not self.conn:
            raise ConnectionError("Database not connected.")
        
        cursor = self.conn.cursor()
        try:
            # 使用 json.dumps 序列化列表
            preferred_sources_json = json.dumps(preference.preferred_sources, ensure_ascii=False)
            preferred_categories_json = json.dumps(preference.preferred_categories, ensure_ascii=False)
            preferred_entities_json = json.dumps(preference.preferred_entities, ensure_ascii=False)
            preferred_tags_json = json.dumps(preference.preferred_tags, ensure_ascii=False)
            excluded_keywords_json = json.dumps(preference.excluded_keywords, ensure_ascii=False)

            cursor.execute("""
                INSERT OR REPLACE INTO user_preferences (
                    user_id, preferred_sources, preferred_categories, 
                    preferred_entities, preferred_tags, excluded_keywords, min_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                preference.user_id, preferred_sources_json, preferred_categories_json,
                preferred_entities_json, preferred_tags_json, excluded_keywords_json, preference.min_score
            ))
            self.conn.commit()
            logger.info(f"User preference for '{preference.user_id}' saved successfully.")
        except sqlite3.Error as e:
            logger.error(f"Error saving user preference for '{preference.user_id}': {e}")
            self.conn.rollback()
            raise

    def load_user_preference(self, user_id: str) -> Optional[UserPreference]:
        """
        加载用户偏好。
        
        :param user_id: 用户ID
        :return: UserPreference 实例，如果不存在则返回 None
        """
        if not self.conn:
            raise ConnectionError("Database not connected.")
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()

        if row:
            try:
                # 使用 json.loads 反序列化列表
                return UserPreference(
                    user_id=row['user_id'],
                    preferred_sources=json.loads(row['preferred_sources']) if row['preferred_sources'] else [],
                    preferred_categories=json.loads(row['preferred_categories']) if row['preferred_categories'] else [],
                    preferred_entities=json.loads(row['preferred_entities']) if row['preferred_entities'] else [],
                    preferred_tags=json.loads(row['preferred_tags']) if row['preferred_tags'] else [],
                    excluded_keywords=json.loads(row['excluded_keywords']) if row['excluded_keywords'] else [],
                    min_score=row['min_score'] if row['min_score'] is not None else 0.0
                )
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON for user preference '{user_id}': {e}")
                return None
        return None
