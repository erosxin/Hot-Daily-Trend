# Supabase PostgreSQL 日志查看指南

## 目的

当 Supabase INSERT 操作失败时，PostgreSQL 数据库日志会包含详细的错误信息，帮助我们诊断问题。

## 查看步骤

### 方法 1：通过 Logs Explorer（推荐）

1. **登录 Supabase Dashboard**
   - 访问 https://supabase.com/dashboard
   - 选择你的项目

2. **导航到 Logs**
   - 在左侧边栏，找到并点击 **"Logs"** 或 **"Logs Explorer"**
   - 注意：不是 "Logs & Analytics" 下的 "Edge Logs"

3. **选择 Database Logs**
   - 在 Logs Explorer 页面顶部，找到日志类型选择器
   - 选择 **"Database Logs"** 或 **"Postgres Logs"**
   - 这应该显示 PostgreSQL 数据库的查询日志

4. **过滤 INSERT 操作**
   - 在搜索框中输入：`INSERT` 或 `articles`
   - 或者使用时间过滤器，选择最近的时间范围（例如：Last 5 minutes）

5. **查看错误日志**
   - 查找红色标记的错误条目
   - 点击错误条目查看详细信息
   - 错误信息通常包含：
     - SQL 错误代码
     - 错误消息
     - 失败的 SQL 语句
     - 堆栈跟踪

### 方法 2：通过 Database -> Logs

1. **登录 Supabase Dashboard**
   - 访问 https://supabase.com/dashboard
   - 选择你的项目

2. **导航到 Database**
   - 在左侧边栏，点击 **"Database"**

3. **打开 Logs**
   - 在 Database 页面，找到 **"Logs"** 标签或链接
   - 点击进入日志查看页面

4. **查看 PostgreSQL 日志**
   - 选择日志类型为 **"Postgres"** 或 **"Database"**
   - 查看最近的日志条目

### 方法 3：通过 SQL Editor（查看系统表）

如果上述方法不可用，可以通过 SQL 查询查看日志：

```sql
-- 查看最近的错误日志
SELECT 
    log_time,
    error_severity,
    message,
    detail,
    hint,
    context
FROM pg_stat_statements
WHERE query LIKE '%INSERT%articles%'
ORDER BY log_time DESC
LIMIT 20;
```

**注意**：此方法需要 `pg_stat_statements` 扩展已启用，且可能需要管理员权限。

## 常见错误类型

在 PostgreSQL 日志中，你可能会看到以下类型的错误：

### 1. RLS (Row Level Security) 错误
```
ERROR: new row violates row-level security policy for table "articles"
```
**解决方案**：禁用 RLS 或创建允许 INSERT 的策略

### 2. 数据类型不匹配
```
ERROR: column "tags" is of type jsonb but expression is of type text
```
**解决方案**：确保 jsonb 字段是 Python 原生类型（list/dict），不是 JSON 字符串

### 3. 列名不匹配
```
ERROR: column "imageUrl" does not exist
```
**解决方案**：检查列名是否与 Python 模型字段名完全匹配（大小写敏感）

### 4. NOT NULL 约束违反
```
ERROR: null value in column "title" violates not-null constraint
```
**解决方案**：确保所有必需字段都有值

### 5. 唯一约束违反
```
ERROR: duplicate key value violates unique constraint "articles_link_key"
```
**解决方案**：这是正常的（如果表不为空），调试完成后改用 UPSERT

## 需要提供的信息

当查看日志时，请提供以下信息：

1. **错误消息**：完整的错误消息文本
2. **错误代码**：PostgreSQL 错误代码（如果有）
3. **SQL 语句**：失败的 INSERT 语句（如果日志中有）
4. **时间戳**：错误发生的时间
5. **截图**：日志条目的截图（如果有）

## 调试提示

1. **清空表**：在调试时，确保 `articles` 表是空的，避免重复键错误干扰
2. **时间窗口**：在运行程序后立即查看日志（最近 1-5 分钟）
3. **过滤搜索**：使用关键词如 `INSERT`、`articles`、`ERROR` 来过滤日志
4. **完整上下文**：查看错误前后的日志条目，了解完整的操作序列

## 如果找不到日志

如果无法在 Supabase Dashboard 中找到日志：

1. **检查项目设置**：某些 Supabase 计划可能不包含详细的日志功能
2. **联系支持**：如果问题持续，可以联系 Supabase 支持获取帮助
3. **使用 Python 错误**：即使没有数据库日志，Python 控制台的异常堆栈也会提供有价值的信息

---

**重要提示**：当前代码已移除 try-except 块，任何 Supabase 错误都会直接抛出。请同时检查：
- Python 控制台的完整异常堆栈
- Supabase Dashboard 中的 PostgreSQL 日志
- 代码中打印的详细数据格式日志
