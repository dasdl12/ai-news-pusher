from datetime import date
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser
import asyncio
import re
from .base_scraper import BaseScraper, Article

class SohuScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            name="腾讯研究院AI速递",
            base_url="https://mp.sohu.com/profile?xpt=bGl1amluc29uZzIwMDBAMTI2LmNvbQ=="
        )
        self.source_weight = 8  # 权重分数
        
    async def get_article_list(self, start_date: date, end_date: date) -> List[Dict]:
        """获取搜狐腾讯研究院文章列表"""
        articles = []
        
        async with async_playwright() as p:
            browser_options = {
                'headless': True,
                'args': [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled'
                ]
            }
            browser = await p.chromium.launch(**browser_options)
            page = await browser.new_page()
            
            # 设置更真实的User-Agent
            await page.set_extra_http_headers({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
            try:
                await page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)  # 等待JavaScript加载，缩短等待时间
                
                # 滚动页面以加载更多内容
                for _ in range(2):  # 减少滚动次数
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(1000)  # 缩短等待时间
                
                # 更精确的选择器定位文章 - 增加更多可能的选择器
                article_selectors = [
                    "div.feed-item-content a",
                    "div[class*='item'] a[href*='/a/']",
                    ".article-item a",
                    "a[href*='/a/'][title]",
                    "div.list-item a",
                    "article a",
                    ".content-list a",
                    "[class*='article'] a",
                    "[class*='news'] a",
                    "a[href*='sohu.com/a/']",
                    "h3 a",
                    "h4 a",
                    ".title a"
                ]
                
                found_links = set()
                all_found_articles = []  # 用于调试
                
                for selector in article_selectors:
                    try:
                        links = await page.query_selector_all(selector)
                        self.logger.debug(f"选择器 {selector} 找到 {len(links)} 个链接")
                        for link in links:
                            href = await link.get_attribute('href')
                            if href and href not in found_links:
                                found_links.add(href)
                                
                                # 获取标题
                                title = await link.get_attribute('title') or await link.text_content()
                                if not title:
                                    continue
                                
                                # 记录所有找到的文章标题用于调试
                                all_found_articles.append(title.strip())
                                    
                                # 只处理标题包含"腾讯研究院AI速递"的文章
                                if "腾讯研究院AI速递" not in title:
                                    continue
                                
                                self.logger.info(f"找到匹配文章: {title.strip()}")
                                    
                                # 确保是完整的URL
                                if href.startswith('/'):
                                    href = "https://m.sohu.com" + href
                                elif not href.startswith('http'):
                                    href = "https://m.sohu.com/" + href
                                
                                # 尝试获取日期
                                parent = await link.evaluate_handle("el => el.parentElement")
                                date_text = ""
                                if parent:
                                    date_elem = await parent.query_selector("[class*='time'], [class*='date'], span")
                                    if date_elem:
                                        date_text = await date_elem.text_content()
                                
                                # 优先从标题中提取日期（腾讯研究院AI速递通常在标题中包含日期）
                                article_date = self._extract_date_from_title(title) or self._extract_date_from_text(date_text)
                                
                                articles.append({
                                    'title': title.strip(),
                                    'url': href,
                                    'date': article_date,
                                    'source': '腾讯研究院AI速递',
                                    'weight': self.source_weight
                                })
                    except Exception as e:
                        self.logger.debug(f"选择器 {selector} 处理失败: {e}")
                        continue
                        
            except Exception as e:
                self.logger.error(f"获取搜狐文章列表失败: {e}")
                
            finally:
                await browser.close()
                
        # 调试信息：输出所有找到的文章标题
        if all_found_articles:
            self.logger.info(f"总共找到 {len(all_found_articles)} 篇文章标题:")
            for i, article_title in enumerate(all_found_articles[:10]):  # 只显示前10个
                self.logger.info(f"  [{i+1}] {article_title}")
            if len(all_found_articles) > 10:
                self.logger.info(f"  ... 还有 {len(all_found_articles) - 10} 篇文章")
        else:
            self.logger.warning("未找到任何文章标题！页面结构可能已更改")
                
        # 根据日期范围过滤文章
        filtered_articles = []
        for article in articles:
            if article.get('date') and self.is_date_in_range(article['date'], start_date, end_date):
                filtered_articles.append(article)
                
        self.logger.info(f"找到 {len(articles)} 篇文章，过滤后 {len(filtered_articles)} 篇在指定日期范围内")
        return filtered_articles
        
    async def get_article_detail(self, article_url: str, list_date: str = "") -> Optional[Article]:
        """获取文章详细内容"""
        if not article_url:
            return None
            
        async with async_playwright() as p:
            browser_options = {
                'headless': True,
                'args': [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-dev-shm-usage'
                ]
            }
            browser = await p.chromium.launch(**browser_options)
            page = await browser.new_page()
            
            try:
                await page.goto(article_url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(1000)  # 缩短等待时间
                
                # 获取文章标题
                title_selectors = [
                    "h1",
                    "[class*='title']",
                    ".article-title",
                    ".content-title"
                ]
                
                title = ""
                for selector in title_selectors:
                    try:
                        title_element = await page.query_selector(selector)
                        if title_element:
                            title = await title_element.text_content()
                            if title and title.strip():
                                break
                    except:
                        continue
                        
                # 获取文章内容 - 针对搜狐页面结构优化
                content_selectors = [
                    ".text",  # 搜狐文章主要内容
                    "[class*='content']",
                    "[class*='article-body']",
                    ".article-content",
                    "article",
                    "[id*='content']",
                    ".text-content",  # 搜狐可能的内容区域
                ]
                
                content = ""
                for selector in content_selectors:
                    try:
                        content_element = await page.query_selector(selector)
                        if content_element:
                            # 获取纯文本内容，但保持段落结构
                            paragraphs = await content_element.query_selector_all("p, div")
                            if paragraphs:
                                content_parts = []
                                for p in paragraphs:
                                    p_text = await p.text_content()
                                    if p_text and p_text.strip() and len(p_text.strip()) > 10:
                                        content_parts.append(p_text.strip())
                                content = "\n\n".join(content_parts)
                            else:
                                content = await content_element.text_content()
                            
                            if content and len(content.strip()) > 100:  # 确保获取到有意义的内容
                                break
                    except:
                        continue
                        
                # 获取发布日期
                date_selectors = [
                    "[class*='time']",
                    "[class*='date']",
                    ".publish-time",
                    ".article-date"
                ]
                
                article_date = ""
                for selector in date_selectors:
                    try:
                        date_element = await page.query_selector(selector)
                        if date_element:
                            date_text = await date_element.text_content()
                            if date_text:
                                article_date = self._extract_date_from_text(date_text)
                                if article_date:
                                    break
                    except:
                        continue
                        
                if not title or not content:
                    self.logger.warning(f"无法从 {article_url} 获取完整文章信息")
                    return None
                    
                # 优先使用列表页日期，其次使用详情页日期，最后才使用今天
                final_date = list_date or article_date or date.today().strftime("%Y-%m-%d")
                
                return Article(
                    title=title.strip(),
                    date=final_date,
                    content=content.strip(),
                    url=article_url
                )
                
            except Exception as e:
                self.logger.error(f"获取文章详情失败 {article_url}: {e}")
                return None
                
            finally:
                await browser.close()
                
    def _extract_date_from_text(self, text: str) -> str:
        """从文本中提取日期，处理相对时间"""
        if not text:
            return ""
            
        import datetime
        now = datetime.datetime.now()
        current_year = now.year
        current_month = now.month
        
        # 清理文本，去除多余空格
        text = text.strip().replace('\n', ' ').replace('\t', ' ')
        
        # 首先处理相对时间
        # 处理 "今天"
        if '今天' in text:
            return now.strftime('%Y-%m-%d')
            
        # 处理 "昨天"
        if '昨天' in text:
            yesterday = now - datetime.timedelta(days=1)
            return yesterday.strftime('%Y-%m-%d')
            
        # 处理 "前天"
        if '前天' in text:
            day_before = now - datetime.timedelta(days=2)
            return day_before.strftime('%Y-%m-%d')
            
        # 处理 "X天前" 格式
        days_match = re.search(r'(\d+)天前', text)
        if days_match:
            days = int(days_match.group(1))
            target_date = now - datetime.timedelta(days=days)
            return target_date.strftime('%Y-%m-%d')
            
        # 处理 "X小时前" 格式
        hours_match = re.search(r'(\d+)小时前', text)
        if hours_match:
            hours = int(hours_match.group(1))
            target_date = now - datetime.timedelta(hours=hours)
            return target_date.strftime('%Y-%m-%d')
            
        # 处理 "X分钟前" （当做今天）
        minutes_match = re.search(r'(\d+)分钟前', text)
        if minutes_match:
            return now.strftime('%Y-%m-%d')
        
        # 处理绝对日期格式
        date_patterns = [
            (r'\d{4}-\d{2}-\d{2}', '%Y-%m-%d'),
            (r'\d{4}年\d{1,2}月\d{1,2}日', '%Y年%m月%d日'),
            (r'\d{4}/\d{2}/\d{2}', '%Y/%m/%d'),
            (r'\d{2}-\d{2}', '%m-%d'),
            (r'\d{1,2}月\d{1,2}日', '%m月%d日'),
            (r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', '%Y-%m-%d %H:%M:%S'),
            (r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', '%Y-%m-%d %H:%M')
        ]
        
        for pattern, format_str in date_patterns:
            match = re.search(pattern, text)
            if match:
                matched_text = match.group(0)
                
                # 如果包含时间，只取日期部分
                if ' ' in matched_text and (':' in matched_text):
                    matched_text = matched_text.split(' ')[0]
                    return matched_text
                
                # 处理月-日格式，补充年份
                if format_str == '%m-%d':
                    month, day = matched_text.split('-')
                    month = int(month)
                    
                    # 判断是否需要使用上一年（如果月份大于当前月份）
                    year = current_year
                    if month > current_month:
                        year = current_year - 1
                    
                    return f"{year}-{matched_text}"
                elif format_str == '%m月%d日':
                    month_day = matched_text.replace('月', '-').replace('日', '')
                    month = int(month_day.split('-')[0])
                    
                    year = current_year
                    if month > current_month:
                        year = current_year - 1
                        
                    return f"{year}-{month_day.zfill(5)}"  # 确保格式为 MM-DD
                    
                return matched_text
                
        return ""
    
    def _extract_date_from_title(self, title: str) -> str:
        """从标题中提取日期，专门针对腾讯研究院AI速递的标题格式"""
        if not title:
            return ""
            
        import datetime
        
        # 腾讯研究院AI速递标题通常格式为：腾讯研究院AI速递｜8.28
        # 或者：腾讯研究院AI速递 8月28日
        date_patterns = [
            (r'(\d{1,2})\.(\d{1,2})', '%m.%d'),  # 8.28 格式
            (r'(\d{1,2})月(\d{1,2})日', '%m月%d日'),  # 8月28日 格式  
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', '%Y.%m.%d'),  # 2024.8.28 格式
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', '%Y年%m月%d日'),  # 2024年8月28日 格式
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', '%Y-%m-%d'),  # 2024-8-28 格式
        ]
        
        for pattern, format_template in date_patterns:
            matches = re.findall(pattern, title)
            if matches:
                match = matches[0]
                try:
                    if format_template in ['%m.%d', '%m月%d日']:
                        # 只有月日，需要补充年份
                        current_year = datetime.datetime.now().year
                        month = int(match[0])
                        day = int(match[1])
                        
                        # 更合理的日期判断逻辑
                        today = datetime.date.today()
                        try_date = datetime.date(current_year, month, day)
                        
                        # 如果日期比今天晚超过1天，才使用上一年
                        # 这样可以处理当天或前一天的情况
                        if try_date > today and (try_date - today).days > 1:
                            current_year -= 1
                            
                        return f"{current_year}-{month:02d}-{day:02d}"
                        
                    elif format_template == '%Y.%m.%d':
                        year, month, day = int(match[0]), int(match[1]), int(match[2])
                        return f"{year}-{month:02d}-{day:02d}"
                        
                    elif format_template == '%Y年%m月%d日':
                        year, month, day = int(match[0]), int(match[1]), int(match[2])
                        return f"{year}-{month:02d}-{day:02d}"
                        
                    elif format_template == '%Y-%m-%d':
                        year, month, day = int(match[0]), int(match[1]), int(match[2])
                        return f"{year}-{month:02d}-{day:02d}"
                        
                except (ValueError, IndexError):
                    continue
                    
        return ""