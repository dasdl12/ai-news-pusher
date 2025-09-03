"""
DeepSeek API集成模块
用于AI内容处理和改写
"""
import asyncio
import aiohttp
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class DeepSeekAPI:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or Config.DEEPSEEK_API_KEY or "sk-efa37b506d774cc7b447ac8fa4afd981"
        self.base_url = Config.DEEPSEEK_BASE_URL
        self.model = Config.DEEPSEEK_MODEL
        self.session = None
        
    async def _ensure_session(self):
        """确保HTTP会话存在"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close_session(self):
        """关闭HTTP会话"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def generate_daily_report(self, articles: List[Dict], target_date: str) -> Dict:
        """
        生成AI日报
        Args:
            articles: 采集的文章列表
            target_date: 目标日期 (YYYY-MM-DD)
        Returns:
            生成的日报内容字典
        """
        try:
            await self._ensure_session()
            
            # 准备文章内容
            content_parts = []
            for i, article in enumerate(articles, 1):
                content_part = f"""
【资讯{i}】
来源：{article.get('source', '未知')}（权重：{article.get('weight', 5)}分）
标题：{article.get('title', '')}
时间：{article.get('date', '')} {article.get('time_text', '')}
内容：{article.get('content', article.get('summary', ''))}
URL：{article.get('url', '')}
---
"""
                content_parts.append(content_part)
            
            # 构建完整的prompt
            full_content = "".join(content_parts)
            prompt = Config.AI_PROMPT_TEMPLATE.format(
                date=target_date,
                content=full_content
            )
            
            logger.info(f"开始生成{target_date}的AI日报，输入{len(articles)}条原始资讯")
            
            # 调用DeepSeek API
            response = await self._call_api(prompt)
            
            if response and response.get('success'):
                report_content = response.get('content', '')
                logger.info(f"AI日报生成成功，输出内容长度：{len(report_content)}")
                
                return {
                    'success': True,
                    'date': target_date,
                    'content': report_content,
                    'source_count': len(articles),
                    'generated_at': datetime.now().isoformat(),
                    'model': self.model
                }
            else:
                error_msg = response.get('error', 'API调用失败') if response else 'API响应为空'
                logger.error(f"AI日报生成失败: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'date': target_date,
                    'source_count': len(articles)
                }
                
        except Exception as e:
            logger.error(f"生成AI日报时出错: {e}")
            return {
                'success': False,
                'error': str(e),
                'date': target_date,
                'source_count': len(articles)
            }
    
    async def generate_poster_html(self, report_content: str, date: str) -> Dict:
        """
        生成海报HTML
        Args:
            report_content: 日报内容
            date: 日期
        Returns:
            生成的HTML内容字典
        """
        try:
            await self._ensure_session()
            
            prompt = f"""设计一个视觉冲击力强的AI资讯海报。

设计要求：
1. 布局：530px宽度，高度自适应，苹果风格极简设计
2. 标题：“AI前哨日报”，超大字号(56px)，排版靠左，黑色粗体，吸引眼球
3. 内容：每条不超过50字
4. 视觉元素：
   - 使用emoji图标增强视觉效果
   - 数字和关键词用红色高亮
   - 重要信息用大号卡片展示，不重要信息则作为次要信息处理
   - 添加渐变色块作为装饰元素
5. 排版：大量留白，信息层次分明，一眼看懂

将以下日报内容提炼成精华海报（{date}）：
{report_content}

注意：
- 如何分辨信息重要或不重要：根据信息的新闻价值和影响力
- 重要信息：对行业有重大影响的新闻、技术突破、市场动态等
- 不重要信息：重复性高、影响力小的新闻
- 每条信息精炼（标题+几句话说明）
- 突出数字和关键成果
- 直接输出完整HTML代码，不要任何markdown标记
"""
            logger.info(f"开始生成{date}的海报HTML")
            
            response = await self._call_api(prompt, temperature=0.7)
            
            if response and response.get('success'):
                html_content = response.get('content', '')
                
                # 使用更强的HTML内容清理逻辑
                html_content = self._extract_html_content(html_content)
                
                logger.info(f"海报HTML生成成功，内容长度：{len(html_content)}")
                
                return {
                    'success': True,
                    'date': date,
                    'html': html_content,
                    'generated_at': datetime.now().isoformat()
                }
            else:
                error_msg = response.get('error', 'API调用失败') if response else 'API响应为空'
                logger.error(f"海报HTML生成失败: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'date': date
                }
                
        except Exception as e:
            logger.error(f"生成海报HTML时出错: {e}")
            return {
                'success': False,
                'error': str(e),
                'date': date
            }
    
    def _extract_html_content(self, raw_content: str) -> str:
        """
        从AI返回的内容中提取纯HTML内容，清理额外说明文字
        """
        import re
        
        # 去除首尾空白
        content = raw_content.strip()
        
        # 方法1：查找```html...```代码块
        html_pattern = r'```html\s*\n?(.*?)\n?```'
        html_match = re.search(html_pattern, content, re.DOTALL | re.IGNORECASE)
        if html_match:
            return html_match.group(1).strip()
        
        # 方法2：查找```...```代码块（不带语言标识）
        code_pattern = r'```\s*\n?(.*?)\n?```'
        code_match = re.search(code_pattern, content, re.DOTALL)
        if code_match:
            html_candidate = code_match.group(1).strip()
            # 检查是否包含HTML标签
            if '<html' in html_candidate.lower() or '<div' in html_candidate.lower():
                return html_candidate
        
        # 方法3：直接查找HTML标签内容
        html_tag_pattern = r'<!DOCTYPE html>.*?</html>'
        html_tag_match = re.search(html_tag_pattern, content, re.DOTALL | re.IGNORECASE)
        if html_tag_match:
            return html_tag_match.group(0)
        
        # 方法4：查找<html>...</html>标签
        html_simple_pattern = r'<html[^>]*>.*?</html>'
        html_simple_match = re.search(html_simple_pattern, content, re.DOTALL | re.IGNORECASE)
        if html_simple_match:
            return html_simple_match.group(0)
        
        # 方法5：如果包含HTML标签，且看起来是HTML内容，则直接返回
        if ('<div' in content.lower() or '<html' in content.lower()) and not content.startswith('这'):
            # 查找从第一个<开始的内容
            first_tag = content.find('<')
            if first_tag >= 0:
                html_part = content[first_tag:]
                # 清理末尾可能的解释文字（通常中文解释在HTML后面）
                lines = html_part.split('\n')
                html_lines = []
                for line in lines:
                    # 如果这行看起来是解释文字（以中文开头且不包含HTML标签），则停止
                    stripped_line = line.strip()
                    if (stripped_line and 
                        stripped_line[0] in '这该海报包含具有采用设计' and 
                        '<' not in stripped_line):
                        break
                    html_lines.append(line)
                return '\n'.join(html_lines).strip()
        
        # 如果以上方法都失败，记录警告并返回原内容
        logger.warning("无法提取HTML内容，将使用原始内容")
        return content
    
    async def _call_api(self, prompt: str, temperature: float = 0.3) -> Optional[Dict]:
        """
        调用DeepSeek API
        Args:
            prompt: 提示词
            temperature: 温度参数
        Returns:
            API响应结果
        """
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': self.model,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'temperature': temperature,
                'max_tokens': 4000,
                'stream': False
            }
            
            url = f"{self.base_url}/v1/chat/completions"
            
            async with self.session.post(url, headers=headers, json=payload, timeout=120) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    if 'choices' in result and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content']
                        return {
                            'success': True,
                            'content': content,
                            'usage': result.get('usage', {}),
                            'model': result.get('model', self.model)
                        }
                    else:
                        logger.error(f"API响应格式错误: {result}")
                        return {
                            'success': False,
                            'error': f'响应格式错误: {result}'
                        }
                else:
                    error_text = await response.text()
                    logger.error(f"API请求失败，状态码: {response.status}, 错误: {error_text}")
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}: {error_text}'
                    }
                    
        except asyncio.TimeoutError:
            logger.error("API请求超时")
            return {
                'success': False,
                'error': 'API请求超时'
            }
        except Exception as e:
            logger.error(f"API请求异常: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_connection(self) -> Dict:
        """
        测试API连接
        Returns:
            连接测试结果
        """
        try:
            test_prompt = "请回复'连接测试成功'"
            response = await self._call_api(test_prompt)
            
            if response and response.get('success'):
                return {
                    'success': True,
                    'message': '连接测试成功',
                    'model': self.model,
                    'response': response.get('content', '')
                }
            else:
                return {
                    'success': False,
                    'message': '连接测试失败',
                    'error': response.get('error', '未知错误') if response else 'API响应为空'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': '连接测试异常',
                'error': str(e)
            }


# 工具函数
async def process_articles_with_ai(articles: List[Dict], target_date: str, api_key: str = None) -> Dict:
    """
    便捷函数: 使用AI处理文章生成日报
    """
    api = DeepSeekAPI(api_key)
    try:
        result = await api.generate_daily_report(articles, target_date)
        return result
    finally:
        await api.close_session()


async def generate_poster_html_simple(report_content: str, date: str, api_key: str = None) -> Dict:
    """
    便捷函数: 生成海报HTML
    """
    api = DeepSeekAPI(api_key)
    try:
        result = await api.generate_poster_html(report_content, date)
        return result
    finally:
        await api.close_session()


# 测试函数
async def test_deepseek_connection(api_key: str = None):
    """测试DeepSeek连接"""
    api = DeepSeekAPI(api_key)
    try:
        result = await api.test_connection()
        print(f"连接测试结果: {result}")
        return result
    finally:
        await api.close_session()


if __name__ == "__main__":
    # 测试代码
    asyncio.run(test_deepseek_connection())