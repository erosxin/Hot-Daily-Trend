import os
from dotenv import load_dotenv

# ---------------------------------------------------------------------
# 确保 load_dotenv 在模块顶部立即执行，且只执行一次。
# 这可以保证在任何其他代码尝试访问环境变量之前，.env 文件已经加载。
# ---------------------------------------------------------------------

# 1. 构建 .env 文件的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
# 假设 .env 文件在 src 目录的上一级（即项目根目录）
project_root = os.path.abspath(os.path.join(current_dir, '..'))
dotenv_path = os.path.join(project_root, '.env')

# 2. 自动移除 .env 文件的 BOM（如果存在）
# 这可以防止 UTF-8 BOM 导致环境变量键名不匹配的问题
if os.path.exists(dotenv_path):
    with open(dotenv_path, 'rb') as f:
        content_bytes = f.read()
    if content_bytes.startswith(b'\xef\xbb\xbf'):
        # 检测到 BOM，移除它
        with open(dotenv_path, 'wb') as f:
            f.write(content_bytes[3:])
        print(f"Debug: Removed UTF-8 BOM from .env file")

# 3. 显式加载 .env 文件
print(f"Debug: Attempting to load .env from: {dotenv_path}")
load_dotenv(dotenv_path)

# 3. 调试输出：再次显示加载后环境变量的相关键，作为最终检查
print("--- Debug: Environment after .env load (final verification) ---")
# 检查关键变量是否存在于 os.environ 中
supabase_url_env = os.environ.get("SUPABASE_URL")
supabase_key_env = os.environ.get("SUPABASE_KEY")
supabase_service_key_env = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase_anon_key_env = os.environ.get("SUPABASE_ANON_KEY")
openai_key_env = os.environ.get("OPENAI_API_KEY")

print(f"  SUPABASE_URL = {supabase_url_env[:40] if supabase_url_env else 'None'}...")
print(f"  SUPABASE_KEY (legacy) = {supabase_key_env[:16] if supabase_key_env else 'None'}...")
print(f"  SUPABASE_SERVICE_ROLE_KEY = {'Set' if supabase_service_key_env else 'Not set'}")
print(f"  SUPABASE_ANON_KEY = {'Set' if supabase_anon_key_env else 'Not set'}")
print(f"  OPENAI_API_KEY = {openai_key_env[:40] if openai_key_env else 'None'}...")
print("------------------------------------------------------------------")


class Settings:
    def __init__(self):
        # 移除了 self.load_env_vars() 调用，直接在这里获取变量
        # 确保 load_dotenv 已经在模块顶部执行完毕
        
        # API Keys
        self.OPENAI_API_KEY = self._get_required_env("OPENAI_API_KEY")
        self.SERPER_API_KEY = self._get_required_env("SERPER_API_KEY")
        self.RESEND_API_KEY = self._get_required_env("RESEND_API_KEY")

        # Supabase
        self.SUPABASE_URL = self._get_required_env("SUPABASE_URL")
        
        # Support both SUPABASE_KEY (legacy) and separate ANON/SERVICE_ROLE keys
        # Priority: SUPABASE_SERVICE_ROLE_KEY > SUPABASE_KEY > SUPABASE_ANON_KEY
        self.SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        self.SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
        legacy_key = os.environ.get("SUPABASE_KEY")
        
        # Determine which key to use
        if self.SUPABASE_SERVICE_ROLE_KEY:
            self.SUPABASE_KEY = self.SUPABASE_SERVICE_ROLE_KEY
            self._supabase_key_type = "service_role"
        elif legacy_key:
            # Check if legacy key is service_role (usually longer)
            if len(legacy_key) > 200:
                self.SUPABASE_KEY = legacy_key
                self._supabase_key_type = "service_role (from SUPABASE_KEY)"
            else:
                self.SUPABASE_KEY = legacy_key
                self._supabase_key_type = "anon (from SUPABASE_KEY)"
        elif self.SUPABASE_ANON_KEY:
            self.SUPABASE_KEY = self.SUPABASE_ANON_KEY
            self._supabase_key_type = "anon"
        else:
            raise ValueError("Missing Supabase key. Please set SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY, or SUPABASE_KEY in .env")
        
        self.SUPABASE_TABLE_ARTICLES = os.environ.get("SUPABASE_TABLE_ARTICLES", "articles")
        
        # Log which key type is being used
        print(f"Debug: Using Supabase key type: {self._supabase_key_type}")

        # Scraper Configuration
        self.ARXIV_CATEGORIES = ['cs.AI', 'cs.LG', 'cs.CL']  # arXiv 查询类别
        try:
            self.ARXIV_MAX_RESULTS_PER_CATEGORY = int(os.environ.get("ARXIV_MAX_RESULTS_PER_CATEGORY")) if os.environ.get("ARXIV_MAX_RESULTS_PER_CATEGORY") else 20
        except (ValueError, TypeError):
            print("Warning: ARXIV_MAX_RESULTS_PER_CATEGORY in .env is not a valid integer. Using default 20.")
            self.ARXIV_MAX_RESULTS_PER_CATEGORY = 20

        # 其它设置，使用 os.environ.get() 获取并提供默认值
        self.DEBUG = os.environ.get("DEBUG") == "True"
        self.DAYS_AGO = int(os.environ.get("DAYS_AGO")) if os.environ.get("DAYS_AGO") else 1
        self.MAX_ARTICLES_PER_FEED = int(os.environ.get("MAX_ARTICLES_PER_FEED")) if os.environ.get("MAX_ARTICLES_PER_FEED") else 100
        self.SIMILARITY_THRESHOLD = float(os.environ.get("SIMILARITY_THRESHOLD")) if os.environ.get("SIMILARITY_THRESHOLD") else 0.6
        self.NLP_BATCH_SIZE = int(os.environ.get("NLP_BATCH_SIZE")) if os.environ.get("NLP_BATCH_SIZE") else 10
        self.SUMMARY_TOKEN_LIMIT = int(os.environ.get("SUMMARY_TOKEN_LIMIT")) if os.environ.get("SUMMARY_TOKEN_LIMIT") else 1024

        # Output and Email Configuration
        from pathlib import Path
        self.OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "output"))
        self.RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")
        self.SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
        self.GITHUB_PAGES_BASE_URL = os.environ.get("GITHUB_PAGES_BASE_URL", "")

    @property
    def supabase_key(self) -> str:
        """
        Get the Supabase key to use.
        Defaults to service_role key for backend operations (bypasses RLS).
        """
        return self.SUPABASE_KEY
    
    @property
    def supabase_key_type(self) -> str:
        """Get the type of Supabase key being used."""
        return getattr(self, '_supabase_key_type', 'unknown')

    def _get_required_env(self, key: str) -> str:
        """从环境变量中获取必需的键，如果不存在则抛出错误。"""
        value = os.environ.get(key)
        if not value:
            print(f"Fatal Error: Required environment variable '{key}' is missing or empty.")
            print(f"Please check your .env file at {dotenv_path}. Ensure '{key}' is defined and has a value.")
            raise ValueError(f"Missing required environment variable: {key}")
        return value

# ---------------------------------------------------------------------
# 创建一个 Settings 的单例，确保在整个应用生命周期中只有一个配置对象。
# 这样可以避免多次初始化导致的环境变量丢失问题。
# ---------------------------------------------------------------------
settings = Settings()

# 为了向后兼容，导出一些直接可用的变量
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY
OPENAI_API_KEY = settings.OPENAI_API_KEY
SERPER_API_KEY = settings.SERPER_API_KEY
RESEND_API_KEY = settings.RESEND_API_KEY

# 调试：输出最终加载的关键值
print(f"Debug: Final Loaded SUPABASE_URL (from settings object): {settings.SUPABASE_URL[:40]}...")
print(f"Debug: Final Loaded SUPABASE_KEY (from settings object): {settings.SUPABASE_KEY[:16]}...")
print(f"Debug: Supabase Key Type: {settings.supabase_key_type}")
