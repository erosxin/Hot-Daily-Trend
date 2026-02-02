"""
定时任务：每日运行爬虫并发送邮件
"""
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
import sys
sys.path.insert(0, str(project_root))

from src.config import settings
from src.supabase_manager import SupabaseManager
from src.display_module import DisplayModule
from src.email_sender import send_daily_email

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """每日任务主流程"""
    logger.info("=" * 50)
    logger.info("开始每日AI趋势简报任务")
    logger.info(f"时间: {datetime.now().isoformat()}")
    logger.info("=" * 50)
    
    # 1. 从 Supabase 获取今日文章
    try:
        supabase_manager = SupabaseManager(use_service_role=True)
        articles = supabase_manager.fetch_articles(limit=50, days_ago=1)
        logger.info(f"从数据库获取到 {len(articles)} 篇文章")
    except Exception as e:
        logger.error(f"获取文章失败: {e}")
        return
    
    if not articles:
        logger.info("今日暂无新文章")
        return
    
    # 2. 生成邮件 HTML
    display_module = DisplayModule()
    email_html = display_module.generate_email_html(articles, settings.GITHUB_PAGES_BASE_URL)
    
    # 3. 生成静态页面
    display_module.generate_static_site(
        settings.OUTPUT_DIR,
        articles,
        settings.GITHUB_PAGES_BASE_URL,
        settings.SUPABASE_URL,
        settings.SUPABASE_ANON_KEY
    )
    
    # 4. 发送邮件
    if settings.SENDER_EMAIL and settings.RECIPIENT_EMAIL:
        try:
            send_daily_email("每日AI趋势简报", email_html)
            logger.info("邮件发送成功！")
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
    else:
        logger.warning("邮件配置不完整，跳过发送")
    
    logger.info("任务完成！")

if __name__ == "__main__":
    asyncio.run(main())
