# Hot-Daily-Trend

一个智能化的每日热点新闻聚合与分析系统，能够自动从多个数据源抓取文章，使用 AI 进行深度分析，并将结果存储到数据库中。

## 🌟 主要功能

### 1. 多源数据抓取
- **arXiv 论文**：自动抓取指定类别（如 cs.AI、cs.LG、cs.CL）的最新学术论文
- **RSS 订阅源**：支持从多个 RSS 源抓取新闻文章（如 OpenAI Blog、Google Research Blog 等）
- **Serper News**：通过 Serper API 搜索和抓取新闻文章

### 2. AI 驱动的 NLP 处理
- **智能摘要生成**：使用 OpenAI API 为每篇文章生成摘要
- **标签提取**：自动识别文章的主要标签和关键词
- **实体识别**：提取人名、组织、地点等命名实体
- **情感分析**：分析文章的情感倾向
- **可读性评分**：评估文章的阅读难度

### 3. 数据存储与管理
- **Supabase 集成**：将处理后的文章存储到 Supabase 数据库
- **自动去重**：基于文章链接自动识别和过滤重复内容
- **数据验证**：确保数据格式正确，符合数据库 schema

### 4. 内容展示
- **思维导图生成**：自动生成文章主题的思维导图
- **时间线视图**：按时间顺序展示文章
- **统计摘要**：生成文章数量、来源分布等统计信息

## 📋 环境要求

### 系统要求
- **Python 版本**：3.8 或更高版本
- **操作系统**：Windows、Linux、macOS

### 必需的 API 密钥
在运行程序之前，你需要准备以下 API 密钥：

1. **OpenAI API Key**
   - 用于 NLP 处理（摘要生成、标签提取、实体识别等）
   - 获取地址：https://platform.openai.com/api-keys

2. **Supabase 配置**
   - Supabase URL：你的 Supabase 项目 URL
   - Supabase Service Role Key：用于绕过 RLS 策略的后端操作
   - 获取地址：https://supabase.com

3. **Serper API Key**（可选）
   - 用于新闻搜索功能
   - 获取地址：https://serper.dev

4. **Resend API Key**（可选）
   - 用于邮件发送功能
   - 获取地址：https://resend.com

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/erosxin/Hot-Daily-Trend.git
cd Hot-Daily-Trend
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

在项目根目录创建 `.env` 文件，并添加以下配置：

```env
# 必需的 API 密钥
OPENAI_API_KEY=your_openai_api_key_here
SERPER_API_KEY=your_serper_api_key_here
RESEND_API_KEY=your_resend_api_key_here

# Supabase 配置
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
# 或者使用旧版配置
# SUPABASE_KEY=your_supabase_key_here
SUPABASE_TABLE_ARTICLES=articles

# 可选配置
DEBUG=False
DAYS_AGO=1
ARXIV_MAX_RESULTS_PER_CATEGORY=20
MAX_ARTICLES_PER_FEED=100
NLP_BATCH_SIZE=10
SUMMARY_TOKEN_LIMIT=1024
SIMILARITY_THRESHOLD=0.6

# 输出和邮件配置（可选）
OUTPUT_DIR=output
RECIPIENT_EMAIL=your_email@example.com
SENDER_EMAIL=noreply@example.com
GITHUB_PAGES_BASE_URL=https://your-username.github.io/Hot-Daily-Trend
```

### 4. 运行程序

#### Windows

```bash
python -m src.main_scraper
```

或使用批处理脚本：

```bash
run_scraper.bat
```

#### Linux/macOS

```bash
python -m src.main_scraper
```

或使用 shell 脚本（需要先添加执行权限）：

```bash
chmod +x run_scraper.sh
./run_scraper.sh
```

## 📁 项目结构

```
Hot-Daily-Trend/
├── src/                      # 源代码目录
│   ├── main_scraper.py      # 主程序入口
│   ├── config.py            # 配置管理
│   ├── data_models.py       # 数据模型定义
│   ├── supabase_manager.py  # Supabase 数据库管理
│   ├── nlp_processor.py     # NLP 处理模块
│   ├── display_module.py    # 内容展示模块
│   ├── scrapers/            # 抓取器模块
│   │   ├── arxiv_scraper.py
│   │   ├── rss_scraper.py
│   │   └── serper_news_scraper.py
│   └── data/
│       └── rss_feeds.json   # RSS 源配置
├── requirements.txt         # Python 依赖包
├── .env                     # 环境变量配置（需要自己创建）
├── .gitignore              # Git 忽略文件
├── run_scraper.bat         # Windows 运行脚本
├── run_scraper.sh          # Linux/macOS 运行脚本
└── README.md               # 本文件
```

## 🔧 配置说明

### 必需配置项

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | `sk-...` |
| `SUPABASE_URL` | Supabase 项目 URL | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase 服务角色密钥 | `eyJ...` |

### 可选配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DEBUG` | `False` | 启用调试模式，输出详细日志 |
| `DAYS_AGO` | `1` | 抓取最近 N 天的文章 |
| `ARXIV_MAX_RESULTS_PER_CATEGORY` | `20` | 每个 arXiv 类别的最大结果数 |
| `MAX_ARTICLES_PER_FEED` | `100` | 每个 RSS 源的最大文章数 |
| `NLP_BATCH_SIZE` | `10` | NLP 处理的批次大小 |
| `SUMMARY_TOKEN_LIMIT` | `1024` | 摘要生成的 token 限制 |
| `SIMILARITY_THRESHOLD` | `0.6` | 文章相似度阈值 |

## 📊 数据流程

1. **数据抓取阶段**
   - 并发抓取来自 arXiv、RSS 和 Serper News 的文章
   - 根据日期范围过滤文章

2. **NLP 处理阶段**
   - 批量处理文章，生成摘要
   - 提取标签、实体和情感信息
   - 计算可读性评分

3. **数据存储阶段**
   - 自动去重（基于文章链接）
   - 验证数据格式
   - 插入或更新 Supabase 数据库

4. **内容生成阶段**
   - 生成思维导图
   - 生成时间线视图
   - 生成统计摘要

## 🐛 故障排除

### 常见错误

#### 1. ModuleNotFoundError: No module named 'src'

**原因**：直接运行 `python src/main_scraper.py` 时，Python 无法找到 `src` 模块。

**解决方案**：使用 `python -m src.main_scraper` 而不是 `python src/main_scraper.py`

#### 2. ImportError: cannot import name 'settings' from 'src.config'

**原因**：当前工作目录不在项目根目录。

**解决方案**：确保在项目根目录（包含 `src` 文件夹的目录）下运行命令。

#### 3. Missing required environment variable

**原因**：`.env` 文件中缺少必需的配置项。

**解决方案**：检查 `.env` 文件，确保所有必需的 API 密钥都已配置。

#### 4. Supabase 插入失败

**可能原因**：
- RLS（Row Level Security）策略阻止写入
- 数据格式不匹配
- 表结构不正确

**解决方案**：
- 使用 `SUPABASE_SERVICE_ROLE_KEY` 而不是 `SUPABASE_ANON_KEY`
- 检查 Supabase 表结构是否与代码中的字段匹配
- 启用 `DEBUG=True` 查看详细错误信息

### 调试模式

启用调试模式可以查看详细的日志信息：

```bash
# Windows
set DEBUG=True
python -m src.main_scraper

# Linux/macOS
export DEBUG=True
python -m src.main_scraper
```

## 📝 依赖包

主要依赖包列表（详见 `requirements.txt`）：

- `supabase>=2.0.0` - Supabase 客户端
- `openai>=1.0.0` - OpenAI API 客户端
- `requests>=2.31.0` - HTTP 请求库
- `python-dotenv>=1.0.0` - 环境变量管理
- `beautifulsoup4>=4.12.0` - HTML 解析
- `feedparser>=6.0.0` - RSS 解析
- `arxiv>=2.0.0` - arXiv API 客户端
- `httpx>=0.24.0` - 异步 HTTP 客户端
- `resend>=0.6.0` - 邮件发送服务

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 MIT 许可证。

## 🔗 相关文档

- [运行说明](RUNNING.md)
- [Supabase 设置指南](SUPABASE_SETUP.md)
- [Supabase 日志指南](SUPABASE_LOGS_GUIDE.md)
- [字段隔离指南](FIELD_ISOLATION_GUIDE.md)

## 📧 联系方式

如有问题或建议，请通过 GitHub Issues 联系。

---

**注意**：使用本程序需要消耗 OpenAI API 配额，请合理使用并注意成本控制。
