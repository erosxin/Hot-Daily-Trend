# 字段隔离调试指南

## 目的

通过逐步添加字段的方式，定位导致 Supabase INSERT 失败的特定字段。

## 当前状态

**Step 1: 仅插入 `link` 字段** ✅ (当前)

## 调试步骤

### Step 1: 仅 `link` 字段（当前）

**代码状态**：
```python
article_dict = {
    "link": str(article.link) if article.link else None
}
```

**验证**：
1. 清空 `articles` 表
2. 运行 `python -m src.main_scraper`
3. 检查 Supabase Table Editor

**如果成功**：继续到 Step 2
**如果失败**：检查 `link` 列的定义和约束

---

### Step 2: `link` + `title`

**修改代码**（在 `src/supabase_manager.py` 的 `upsert_articles` 方法中）：
```python
article_dict = {
    "link": str(article.link) if article.link else None,
    "title": article.title if article.title else None
}
```

**验证**：
1. 清空 `articles` 表
2. 运行程序
3. 检查结果

**如果成功**：继续到 Step 3
**如果失败**：问题在 `title` 字段（检查列名、类型、约束）

---

### Step 3: `link` + `title` + `published`

**修改代码**：
```python
article_dict = {
    "link": str(article.link) if article.link else None,
    "title": article.title if article.title else None,
    "published": article.published.isoformat() if isinstance(article.published, datetime) else str(article.published) if article.published else None
}
```

**验证**：
1. 清空 `articles` 表
2. 运行程序
3. 检查结果

**如果成功**：继续到 Step 4
**如果失败**：问题在 `published` 字段（检查日期格式、时区、类型）

---

### Step 4: `link` + `title` + `published` + `source`

**修改代码**：
```python
article_dict = {
    "link": str(article.link) if article.link else None,
    "title": article.title if article.title else None,
    "published": article.published.isoformat() if isinstance(article.published, datetime) else str(article.published) if article.published else None,
    "source": article.source if article.source else None
}
```

**验证**：
1. 清空 `articles` 表
2. 运行程序
3. 检查结果

**如果成功**：继续到 Step 5
**如果失败**：问题在 `source` 字段

---

### Step 5: 添加可选字段（逐步）

按以下顺序逐个添加字段：

1. **`summary`** (text, nullable)
2. **`content`** (text, nullable)
3. **`image_url`** (text/url, nullable)
4. **`language`** (text, nullable, default 'en')
5. **`tags`** (jsonb, nullable) - 注意：应该是 Python list
6. **`main_tags`** (jsonb, nullable) - 注意：应该是 Python list
7. **`authors`** (jsonb, nullable) - 注意：应该是 Python list
8. **`entities`** (jsonb, nullable) - 注意：应该是 Python dict
9. **`sentiment`** (jsonb, nullable) - 注意：应该是 Python dict
10. **`readability_score`** (numeric, nullable)
11. **`created_at`** (timestamp, nullable)
12. **`updated_at`** (timestamp, nullable)

**每个字段的添加模板**：

对于 text 字段：
```python
"field_name": article.field_name if article.field_name else None
```

对于 HttpUrl 字段：
```python
"image_url": str(article.image_url) if article.image_url else None
```

对于 datetime 字段：
```python
"published": article.published.isoformat() if isinstance(article.published, datetime) else str(article.published) if article.published else None
```

对于 jsonb list 字段：
```python
"tags": article.tags if article.tags else []  # 确保是 Python list
```

对于 jsonb dict 字段：
```python
"entities": article.entities if article.entities else {}  # 确保是 Python dict
```

---

## 常见问题排查

### 如果 Step 1 (仅 link) 就失败

可能原因：
1. **`link` 列不存在**：检查 Supabase 表结构
2. **`link` 列类型不匹配**：应该是 `text` 或 `varchar`
3. **`link` 列有 NOT NULL 约束**：但某些 article.link 是 None
4. **`id` 列没有默认值**：需要设置 `gen_random_uuid()` 或 `uuid_generate_v4()`
5. **RLS 策略阻止**：检查 RLS 设置

### 如果某个字段添加后失败

检查该字段：
1. **列名是否匹配**（大小写敏感）
2. **数据类型是否匹配**
3. **是否有 NOT NULL 约束**（但值为 None）
4. **jsonb 字段格式**（应该是 Python list/dict，不是 JSON 字符串）
5. **日期格式**（应该是 ISO 8601 字符串）

### 如果所有字段都成功

说明问题可能在：
1. **字段组合**：某些字段组合导致问题
2. **数据值**：某些特定的数据值导致问题
3. **数据量**：批量插入时的限制

---

## 修改代码的位置

在 `src/supabase_manager.py` 的 `upsert_articles` 方法中，找到：

```python
article_dict = {
    "link": str(article.link) if article.link else None
}
```

然后按照上述步骤逐步添加字段。

---

## 记录结果

每完成一个步骤，请记录：

- ✅ **成功**：字段可以正常插入
- ❌ **失败**：字段导致插入失败，记录错误信息

最终目标：找到导致插入失败的第一个字段。
