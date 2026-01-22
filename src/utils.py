"""
工具模块：Supabase 连接器、日志设置、API 请求封装
"""
import logging
import sys
from typing import Optional
from supabase import create_client, Client
from src.config import SUPABASE_URL, SUPABASE_KEY


def setup_logger(name: str = "daily_news_system", level: int = logging.INFO) -> logging.Logger:
    """
    设置并返回标准 logging 对象
    
    Args:
        name: logger 名称
        level: 日志级别，默认为 INFO
        
    Returns:
        配置好的 logging.Logger 实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 创建控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # 创建格式器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # 添加 handler 到 logger
    logger.addHandler(console_handler)
    
    return logger


def get_supabase_client() -> Optional[Client]:
    """
    创建并返回 Supabase 客户端实例
    
    Returns:
        Supabase Client 实例，如果连接失败则返回 None
        
    Raises:
        Exception: 如果配置无效或连接失败
    """
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # 尝试一个简单的查询来验证连接
        # 这里只是创建客户端，不进行实际查询，避免不必要的 API 调用
        return client
        
    except Exception as e:
        raise Exception(f"Failed to create Supabase client: {str(e)}") from e
