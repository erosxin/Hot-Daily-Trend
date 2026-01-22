# 运行说明 (Running Instructions)

## 运行主程序

由于项目使用了 `from src.config import settings` 这样的绝对导入，你需要使用 Python 的模块运行方式。

### Windows

在项目根目录下运行：

```bash
python -m src.main_scraper
```

或者使用提供的批处理脚本：

```bash
run_scraper.bat
```

### Linux/Mac

在项目根目录下运行：

```bash
python -m src.main_scraper
```

或者使用提供的 shell 脚本（需要先添加执行权限）：

```bash
chmod +x run_scraper.sh
./run_scraper.sh
```

## 为什么使用 `python -m`？

`python -m src.main_scraper` 会：
1. 将项目根目录添加到 Python 的模块搜索路径 (`sys.path`)
2. 将 `src` 目录视为一个 Python 包
3. 正确解析 `from src.config import settings` 等导入语句

## 常见错误

### ModuleNotFoundError: No module named 'src'

**原因**：直接运行 `python src/main_scraper.py` 时，Python 无法找到 `src` 模块。

**解决方案**：使用 `python -m src.main_scraper` 而不是 `python src/main_scraper.py`

### ImportError: cannot import name 'settings' from 'src.config'

**原因**：当前工作目录不在项目根目录。

**解决方案**：确保在项目根目录（包含 `src` 文件夹的目录）下运行命令。

## 验证运行环境

在运行主程序之前，确保：

1. ✅ 已安装所有依赖：`pip install -r requirements.txt`
2. ✅ 已配置 `.env` 文件（包含 Supabase URL、Key 等配置）
3. ✅ 当前工作目录是项目根目录
4. ✅ Python 版本 >= 3.8

## 调试模式

如果遇到问题，可以设置环境变量启用调试模式：

```bash
# Windows
set DEBUG=True
python -m src.main_scraper

# Linux/Mac
export DEBUG=True
python -m src.main_scraper
```
