import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const API_KEY = Deno.env.get('API_KEY') ?? 'default-api-key'

serve(async (req: Request) => {
  try {
    // 验证 API Key - 支持从 header 或 query parameter 获取
    const requestApiKey = req.headers.get('x-api-key') || new URL(req.url).searchParams.get('api_key')
    if (requestApiKey !== API_KEY) {
      return new Response(JSON.stringify({ error: 'Invalid API key' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' }
      })
    }

    const { article_id } = await req.json()
    
    if (!article_id) {
      return new Response(JSON.stringify({ error: 'article_id is required' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      })
    }

    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    
    const supabase = createClient(supabaseUrl, supabaseKey)

    // 获取文章
    const { data: article, error: fetchError } = await supabase
      .from('articles')
      .select('*')
      .eq('id', article_id)
      .single()

    if (fetchError || !article) {
      return new Response(JSON.stringify({ error: 'Article not found' }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' }
      })
    }

    // 如果已有简析，直接返回
    if (article.is_favorite && article.plain_summary && article.favorite_analysis) {
      return new Response(JSON.stringify({ 
        success: true, 
        message: 'Already processed',
        plain_summary: article.plain_summary,
        favorite_analysis: article.favorite_analysis
      }), {
        headers: { 'Content-Type': 'application/json' }
      })
    }

    // 准备内容给 OpenAI
    const content = article.content || article.summary || article.title || ''
    const content_preview = content.slice(0, 3000)

    // 调用 OpenAI API
    const openaiKey = Deno.env.get('OPENAI_API_KEY')
    let plain_summary = ''
    let favorite_analysis = ''

    if (openaiKey) {
      // 生成通俗总结
      const plainPrompt = `请用简单的话解释以下内容，让非专业读者也能理解。100-200字：
      
标题: ${article.title}
内容: ${content_preview}`
      
      const plainResp = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${openaiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: 'gpt-4o-mini',
          messages: [
            { role: 'system', content: '你是AI新闻分析助手。只输出中文文本，不要额外格式。' },
            { role: 'user', content: plainPrompt }
          ],
          temperature: 0.2
        })
      })
      
      if (plainResp.ok) {
        const plainData = await plainResp.json()
        plain_summary = plainData.choices?.[0]?.message?.content?.trim() || ''
      }

      // 生成收藏简析
      const favPrompt = `请基于以下文章内容，给出精炼中文分析，要求：
1) 150-250字
2) 删掉废话，保留关键信息
3) 点出对行业的影响或趋势判断

标题: ${article.title}
内容: ${content_preview}`
      
      const favResp = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${openaiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: 'gpt-4o-mini',
          messages: [
            { role: 'system', content: '你是AI新闻分析助手。只输出中文文本，不要额外格式。' },
            { role: 'user', content: favPrompt }
          ],
          temperature: 0.2
        })
      })
      
      if (favResp.ok) {
        const favData = await favResp.json()
        favorite_analysis = favData.choices?.[0]?.message?.content?.trim() || ''
      }
    }

    // 更新数据库
    const { error: updateError } = await supabase
      .from('articles')
      .update({
        is_favorite: true,
        plain_summary: plain_summary || article.plain_summary || '（AI生成失败，请稍后重试）',
        favorite_analysis: favorite_analysis || article.favorite_analysis || '（AI生成失败，请稍后重试）'
      })
      .eq('id', article_id)

    if (updateError) {
      return new Response(JSON.stringify({ error: updateError.message }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      })
    }

    return new Response(JSON.stringify({
      success: true,
      message: '收藏成功，简析已生成',
      plain_summary,
      favorite_analysis
    }), {
      headers: { 'Content-Type': 'application/json' }
    })

  } catch (error) {
    return new Response(JSON.stringify({ error: String(error) }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    })
  }
})
