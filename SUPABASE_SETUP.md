# Supabase 配置说明

## 第一步：修改 .env 文件，使用 SERVICE_ROLE 密钥

这是最关键的一步，它解决了权限问题。

### 当前配置（可能使用 Anon Key，权限受限）

```ini
SUPABASE_URL=https://ietunkxxgukxppeaoiiql.supabase.co
SUPABASE_KEY=your_anon_key_here  # 这个密钥权限受限，可能无法写入数据
```

### 需要修改为（使用 Service Role Key，具有完整权限）

```ini
SUPABASE_URL=https://ietunkxxgukxppeaoiiql.supabase.co
# 将 SUPABASE_KEY 改为你的 SERVICE_ROLE_KEY
SUPABASE_KEY=sb_secret_XONslS46oNgXcbIqqSttRLQ_u5FTjKo  # <-- 将这里的值替换为你的 Secret key (service_role)
```

### 如何获取 Service Role Key

1. 登录 Supabase Dashboard: https://supabase.com/dashboard
2. 选择你的项目
3. 进入 **Settings** → **API**
4. 在 **Project API keys** 部分，找到 **service_role** 密钥
5. 复制 **Secret key (service_role)** 的值（格式类似：`sb_secret_...`）
6. 将 `.env` 文件中的 `SUPABASE_KEY` 值替换为这个密钥

### 重要提示

- **Service Role Key 具有完整权限**，可以绕过 Row Level Security (RLS) 策略
- **请勿将 Service Role Key 提交到版本控制系统**（Git）
- **Service Role Key 应该只在服务器端使用**，不要在客户端代码中使用
- 确保 `.env` 文件已添加到 `.gitignore` 中

## 第二步：验证配置

运行程序后，检查日志输出：

1. 应该看到：`✓ SupabaseManager initialized successfully.`
2. 应该看到：`✓ SupabaseManager object successfully created and will be passed to run_all_scrapers.`
3. 应该看到：`✓ SupabaseManager provided to run_all_scrapers. Attempting to upsert X articles to Supabase via manager.`

如果看到 `✗` 标记的警告或错误，请检查：
- `.env` 文件中的 `SUPABASE_KEY` 是否正确
- `SUPABASE_URL` 是否正确
- 网络连接是否正常

## 第三步：提供表结构信息

如果仍然遇到问题，请提供 `public.articles` 表的详细结构：

1. 登录 Supabase Dashboard
2. 进入 **Table Editor** → 选择 `articles` 表
3. 或者进入 **SQL Editor**，执行以下查询：

```sql
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public' 
  AND table_name = 'articles'
ORDER BY ordinal_position;
```

4. 将结果截图或复制，以便排查字段类型不匹配或 NOT NULL 约束问题
