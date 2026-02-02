# src/display_module.py
import logging
from typing import List
from src.data_models import Article
import os
from pathlib import Path

from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class DisplayModule:
    def __init__(self):
        """初始化展示模块"""
        pass

    def generate_mindmap_markdown(self, articles: List[Article]) -> str:
        """
        将文章列表转换为 Mind Map (Markmap) 兼容的 Markdown 格式。
        
        结构：
        # 主题 (所有文章)
        ## 来源1
        ### 文章1 (标题)
        - 简述
        - 实体
        - 标签
        ### 文章2
        ## 来源2
        ...
        
        :param articles: 待展示的文章列表
        :return: Markdown 格式的字符串
        """
        if not articles:
            return "# No Articles Found"

        mindmap_output = ["# AI News Feed Overview"]
        
        # 按来源分组文章
        articles_by_source = {}
        for article in articles:
            if article.source not in articles_by_source:
                articles_by_source[article.source] = []
            articles_by_source[article.source].append(article)
        
        # 按来源名称排序
        for source in sorted(articles_by_source.keys()):
            source_articles = articles_by_source[source]
            mindmap_output.append(f"## {source}")
            
            # 按发布时间排序（最新的在前）
            def get_timestamp(article):
                """获取文章发布时间的时间戳，用于排序"""
                if not article.published:
                    return datetime.min.timestamp()
                
                try:
                    if isinstance(article.published, datetime):
                        # 如果是 datetime 对象，转换为 UTC 时间戳
                        dt = article.published
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        else:
                            dt = dt.astimezone(timezone.utc)
                        return dt.timestamp()
                    elif isinstance(article.published, str):
                        # 如果是字符串，解析为 datetime 再转换
                        published_str = article.published.replace('Z', '+00:00')
                        dt = datetime.fromisoformat(published_str).astimezone(timezone.utc)
                        return dt.timestamp()
                    else:
                        return datetime.min.timestamp()
                except Exception as e:
                    logger.warning(f"Error parsing published date for article '{article.title}': {e}")
                    return datetime.min.timestamp()
            
            sorted_source_articles = sorted(
                source_articles,
                key=get_timestamp,
                reverse=True
            )
            
            for article in sorted_source_articles:
                # 清理标题中的特殊字符，避免 Markdown 解析问题
                clean_title = article.title.replace('[', '').replace(']', '').replace('(', '').replace(')', '')
                mindmap_output.append(f"### {clean_title}")
                
                # 添加摘要/简述
                summary = article.summary[:150] + '...' if article.summary and len(article.summary) > 150 else (article.summary or 'No summary')
                mindmap_output.append(f"- **Summary**: {summary}")
                
                # 添加实体（entities 现在是 Dict[str, List[str]]）
                if article.entities:
                    # 展平实体字典为列表
                    entity_list = []
                    for entity_type, entity_values in article.entities.items():
                        entity_list.extend(entity_values[:2])  # 每种类型最多2个
                        if len(entity_list) >= 5:
                            break
                    if entity_list:
                        mindmap_output.append(f"- **Entities**: {', '.join(entity_list[:5])}")  # 限制实体数量
                
                # 添加标签
                if article.main_tags:
                    mindmap_output.append(f"- **Tags**: {', '.join(article.main_tags)}")
                
                # 添加链接（将 HttpUrl 转换为字符串）
                link_str = str(article.link)
                # 如果链接很长，显示缩短版本
                if len(link_str) > 60:
                    display_link = f"{link_str[:30]}...{link_str[-20:]}"
                else:
                    display_link = link_str
                mindmap_output.append(f"- **Link**: [{display_link}]({link_str})")
        
        logger.info(f"Generated Mind Map Markdown output for {len(articles)} articles.")
        return "\n".join(mindmap_output)

    def generate_timeline_markdown(self, articles: List[Article]) -> str:
        """
        将文章列表转换为时间轴兼容的 Markdown 格式。
        
        结构：
        # 事件时间轴
        ## 年份-月份
        ### 日期
        - [时间] 来源: 标题 (简述)
        - 实体，标签
        
        :param articles: 待展示的文章列表
        :return: Markdown 格式的字符串
        """
        if not articles:
            return "# No Articles Found"

        timeline_output = ["# AI News Feed Timeline"]
        
        # 按时间排序文章（最新的在前）
        sorted_articles = []
        for article in articles:
            try:
                # 处理不同的时间格式
                if isinstance(article.published, datetime):
                    published_dt = article.published.astimezone(timezone.utc) if article.published.tzinfo else article.published.replace(tzinfo=timezone.utc)
                elif isinstance(article.published, str):
                    published_str = article.published
                    if 'Z' in published_str:
                        published_str = published_str.replace('Z', '+00:00')
                    published_dt = datetime.fromisoformat(published_str).astimezone(timezone.utc)
                else:
                    # 如果类型未知，尝试转换
                    published_dt = datetime.now(timezone.utc)
                sorted_articles.append((published_dt, article))
            except Exception as e:
                logger.warning(f"Error parsing date for article '{article.title}': {e}")
                # 如果解析失败，使用当前时间
                sorted_articles.append((datetime.now(timezone.utc), article))
        
        sorted_articles.sort(key=lambda x: x[0].timestamp(), reverse=True)
        
        current_month = ""
        current_day = ""

        for published_dt, article in sorted_articles:
            year_month = published_dt.strftime("%Y年%m月")
            day_str = published_dt.strftime("%Y年%m月%d日")
            time_str = published_dt.strftime("%H:%M")

            if year_month != current_month:
                timeline_output.append(f"\n## {year_month}")
                current_month = year_month
                current_day = ""  # 重置天数，因为月份变了

            if day_str != current_day:
                timeline_output.append(f"\n### {day_str}")
                current_day = day_str

            # 清理标题中的特殊字符
            clean_title = article.title.replace('[', '').replace(']', '')
            line_prefix = f"- **[{time_str}]** {article.source}: {clean_title}"
            
            # 添加摘要
            summary = article.summary[:100] + '...' if article.summary and len(article.summary) > 100 else (article.summary or 'No summary')
            timeline_output.append(f"{line_prefix}")
            timeline_output.append(f"  - {summary}")
            
            # 添加详细信息
            details = []
            if article.entities:
                # 展平实体字典为列表
                entity_list = []
                for entity_type, entity_values in article.entities.items():
                    entity_list.extend(entity_values[:2])  # 每种类型最多2个
                    if len(entity_list) >= 5:
                        break
                if entity_list:
                    details.append(f"**实体**: {', '.join(entity_list[:5])}")
            if article.main_tags:
                details.append(f"**标签**: {', '.join(article.main_tags)}")
            if details:
                timeline_output.append(f"  - {', '.join(details)}")
            
            # 添加链接（将 HttpUrl 转换为字符串）
            link_str = str(article.link)
            timeline_output.append(f"  - [查看原文]({link_str})")
            timeline_output.append("")  # 空行分隔
        
        logger.info(f"Generated Timeline Markdown output for {len(articles)} articles.")
        return "\n".join(timeline_output)

    def generate_summary_statistics(self, articles: List[Article]) -> str:
        """
        生成文章统计摘要。
        
        :param articles: 待统计的文章列表
        :return: Markdown 格式的统计摘要
        """
        if not articles:
            return "## Statistics\n- No articles found"
        
        stats_output = ["## Statistics"]
        stats_output.append(f"- **Total Articles**: {len(articles)}")
        
        # 按来源统计
        source_counts = {}
        for article in articles:
            source_counts[article.source] = source_counts.get(article.source, 0) + 1
        
        stats_output.append(f"\n### By Source")
        for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
            stats_output.append(f"- {source}: {count}")
        
        # 按标签统计
        tag_counts = {}
        for article in articles:
            for tag in article.main_tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        if tag_counts:
            stats_output.append(f"\n### By Tag")
            for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True):
                stats_output.append(f"- {tag}: {count}")

        # 按实体统计（entities 现在是 Dict[str, List[str]]）
        entity_counts = {}
        for article in articles:
            if article.entities:
                for entity_type, entity_values in article.entities.items():
                    for entity in entity_values:
                        entity_counts[entity] = entity_counts.get(entity, 0) + 1

        if entity_counts:
            stats_output.append(f"\n### Top Entities")
            for entity, count in sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                stats_output.append(f"- {entity}: {count}")

        return "\n".join(stats_output)

    def generate_email_html(self, articles: List[Article], base_url: str) -> str:
        base_url = (base_url or "").rstrip("/")

        # Sort by heat_score then published
        if not articles:
            return "<h2>今日暂无可用AI新闻</h2>"

        def _published_ts(article: Article) -> float:
            if not article.published:
                return 0.0
            if isinstance(article.published, datetime):
                dt = article.published
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return dt.timestamp()
            if isinstance(article.published, str):
                try:
                    published_str = article.published.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(published_str).astimezone(timezone.utc)
                    return dt.timestamp()
                except Exception:
                    return 0.0
            return 0.0

        def score_key(a: Article):
            return (a.heat_score or 0, _published_ts(a))

        top_articles = sorted(articles, key=score_key, reverse=True)

        # Trend radar
        trend_counts = {}
        for a in articles:
            tag = a.trend_tag or (a.main_tags[0] if a.main_tags else "其他")
            trend_counts[tag] = trend_counts.get(tag, 0) + 1

        trend_items = "".join([f"<li>{k}: {v}</li>" for k, v in sorted(trend_counts.items(), key=lambda x: x[1], reverse=True)])

        rows = []
        for a in top_articles:
            heat = f"{int(a.heat_score)}" if a.heat_score is not None else "-"
            summary = a.summary_zh or a.summary or ""
            plain_summary = a.plain_summary or ""
            key_points = "".join([f"<li>{p}</li>" for p in (a.key_points or [])[:3]])
            fav_link = f"{base_url}/favorite.html?id={a.id}" if a.id else "#"
            
            # 如果有通俗总结，添加到显示中
            plain_summary_html = f"<div style='font-size:13px;color:#2563eb;margin:8px 0;padding:8px;background:#f0f7ff;border-radius:4px;'>💡 {plain_summary}</div>" if plain_summary else ""
            
            rows.append(
                f"""
                <div style='padding:12px 0;border-bottom:1px solid #eee;'>
                  <div style='font-size:16px;font-weight:600;margin-bottom:6px;'>{a.title}</div>
                  <div style='color:#666;font-size:12px;margin-bottom:8px;'>来源: {a.source} | 热度: {heat}</div>
                  <div style='font-size:14px;margin-bottom:6px;'>{summary}</div>
                  {plain_summary_html}
                  <ul style='margin:4px 0 8px 18px;padding:0;'>{key_points}</ul>
                  <div style='font-size:13px;'>
                    <a href='{str(a.link)}' target='_blank'>查看原文</a> | 
                    <a href='{fav_link}' target='_blank'>收藏并生成简析</a>
                  </div>
                </div>
                """
            )

        html = f"""
        <html><body style='font-family:Arial,Helvetica,sans-serif;'>
          <h2>每日AI趋势简报</h2>
          <h3>趋势雷达</h3>
          <ul>{trend_items}</ul>
          <h3>今日要闻</h3>
          {''.join(rows)}
        </body></html>
        """
        return html

    def generate_static_site(self, output_dir: Path, articles: List[Article], base_url: str, supabase_url: str, supabase_anon_key: str) -> None:
        base_url = (base_url or "").rstrip("/")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Main index page
        items_html = []
        for a in articles:
            heat = f"{int(a.heat_score)}" if a.heat_score is not None else "-"
            summary = a.summary_zh or a.summary or ""
            plain_summary = a.plain_summary or ""
            fav_link = f"{base_url}/favorite.html?id={a.id}" if a.id else "#"
            
            # 如果有通俗总结，添加到显示中
            plain_summary_html = f"<div class='plain-summary'>💡 {plain_summary}</div>" if plain_summary else ""
            
            items_html.append(
                f"""
                <div class='item'>
                  <div class='title'>{a.title}</div>
                  <div class='meta'>来源: {a.source} | 热度: {heat}</div>
                  <div class='summary'>{summary}</div>
                  {plain_summary_html}
                  <div class='links'>
                    <a href='{str(a.link)}' target='_blank'>查看原文</a>
                    <a href='{fav_link}' target='_blank'>收藏并生成简析</a>
                  </div>
                </div>
                """
            )

        index_html = f"""
        <html>
        <head>
          <meta charset='utf-8' />
          <title>AI Daily Trend</title>
          <style>
            body {{ font-family: Arial, sans-serif; margin: 24px; color: #111; }}
            .item {{ padding: 12px 0; border-bottom: 1px solid #eee; }}
            .title {{ font-size: 18px; font-weight: 600; margin-bottom: 6px; }}
            .meta {{ font-size: 12px; color: #666; margin-bottom: 6px; }}
            .summary {{ font-size: 14px; margin-bottom: 6px; }}
            .plain-summary {{ font-size: 13px; color: #2563eb; margin: 8px 0; padding: 8px; background: #f0f7ff; border-radius: 4px; }}
            .links a {{ margin-right: 10px; }}
          </style>
        </head>
        <body>
          <h2>每日AI趋势简报</h2>
          {''.join(items_html)}
        </body>
        </html>
        """

        (output_dir / "index.html").write_text(index_html, encoding="utf-8")

        safe_supabase_url = supabase_url.replace("http://", "https://", 1) if supabase_url.startswith("http://") else supabase_url

        # Favorite handler page (static)
        favorite_html = f"""
        <html>
        <head><meta charset='utf-8' /></head>
        <body>
          <h3>正在收藏...</h3>
          <script>
            const params = new URLSearchParams(window.location.search);
            const id = params.get('id');
            if (!id) {{ document.body.innerHTML = '<h3>缺少文章ID</h3>'; throw new Error('Missing article ID'); }}

            const supabaseUrl = '{safe_supabase_url}';
            const supabaseKey = '{supabase_anon_key}';
            
            // 初始化 Supabase client
            const supabase = supabase.createClient(supabaseUrl, supabaseKey);

            // 调用 Edge Function
            async function processFavorite() {{
              try {{
                // 尝试匿名登录获取 JWT
                const {{ data: {{ user }}, error: authError }} = await supabase.auth.signInAnonymously();
                
                if (authError || !user) {{
                  // 如果匿名登录失败，直接调用（用 service role）
                  const response = await fetch(
                    supabaseUrl + '/functions/v1/process-favorite',
                    {{
                      method: 'POST',
                      headers: {{
                        'Authorization': 'Bearer ' + supabaseKey,
                        'Content-Type': 'application/json'
                      }},
                      body: JSON.stringify({{ article_id: id }})
                    }}
                  );
                  const result = await response.json();
                  if (result.success) {{
                    document.body.innerHTML = '<h3>收藏成功，简析已生成</h3><p>' + (result.plain_summary || '') + '</p>';
                  }} else {{
                    document.body.innerHTML = '<h3>处理失败: ' + (result.error || '未知错误') + '</h3>';
                  }}
                }} else {{
                  // 匿名登录成功，用 JWT 调用
                  const {{ data, error }} = await supabase.functions.invoke('process-favorite', {{
                    body: {{ article_id: id }}
                  }});
                  
                  if (error) {{
                    document.body.innerHTML = '<h3>错误: ' + error.message + '</h3>';
                  }} else if (data && data.success) {{
                    document.body.innerHTML = '<h3>收藏成功，简析已生成</h3><p>' + (data.plain_summary || '') + '</p>';
                  }} else {{
                    document.body.innerHTML = '<h3>处理失败</h3>';
                  }}
                }}
              }} catch (err) {{
                document.body.innerHTML = '<h3>错误: ' + err.message + '</h3>';
              }}
            }}

            processFavorite();
          </script>
        </body>
        </html>
        """

        (output_dir / "favorite.html").write_text(favorite_html, encoding="utf-8")
