from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
import asyncio
import aiohttp
import re
import logging
from concurrent.futures import ThreadPoolExecutor
from playwright.async_api import async_playwright, Page, Browser

try:
    from config import IMAGE_CONFIG
except ImportError:
    IMAGE_CONFIG = {
        'enabled': True,
        'max_images_per_news': 5,
        'processing_timeout': 30
    }

logger = logging.getLogger(__name__)

class AIBaseNewsScraper:
    """AIBase实时快讯采集器 - 高速优化版本"""
    
    def __init__(self):
        self.name = "AIBase快讯"
        self.base_url = "https://news.aibase.com/zh/news"
        self.browser = None
        self.page = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.source_weight = 5
        self.latest_news_id = None
        
        # 新增：缓存和优化相关
        self.id_cache = set()  # 缓存已处理的ID
        self.session = None   # HTTP会话复用
        self.concurrent_limit = 8  # 并发限制
        
    async def initialize_browser(self):
        """初始化浏览器实例和HTTP会话"""
        if not self.browser:
            playwright = await async_playwright().start()
            browser_options = {
                'headless': True,
                'args': [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-web-security',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-images',  # 禁用图片加载（如果不需要图片可以大幅提速）
                    '--disable-javascript',  # 如果可能的话禁用JS
                ]
            }
            self.browser = await playwright.chromium.launch(**browser_options)
            
        # 初始化HTTP会话
        if not self.session:
            connector = aiohttp.TCPConnector(
                limit=20,  # 连接池大小
                limit_per_host=10,
                keepalive_timeout=30
            )
            timeout = aiohttp.ClientTimeout(total=10, connect=5)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            )
            
    async def close_browser(self):
        """关闭浏览器和HTTP会话"""
        if self.page:
            await self.page.close()
            self.page = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        # 修复：确保 aiohttp session 被关闭
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

    async def _quick_check_news_exists(self, news_id: int) -> bool:
        """
        快速检查新闻ID是否存在（HTTP HEAD请求）
        Args:
            news_id: 新闻ID
        Returns:
            是否存在
        """
        if not self.session:
            await self.initialize_browser()
            
        try:
            url = f"{self.base_url}/{news_id}"
            async with self.session.head(url, allow_redirects=False) as response:
                return response.status == 200
        except asyncio.TimeoutError:
            logger.debug(f"检查新闻 {news_id} 超时")
            return False
        except Exception:
            return False

    async def _batch_check_news_exists(self, news_ids: List[int]) -> List[int]:
        """
        批量检查新闻ID是否存在
        Args:
            news_ids: 新闻ID列表
        Returns:
            存在的新闻ID列表
        """
        if not self.session:
            await self.initialize_browser()
            
        existing_ids = []
        semaphore = asyncio.Semaphore(self.concurrent_limit)
        
        async def check_single(news_id):
            async with semaphore:
                if await self._quick_check_news_exists(news_id):
                    existing_ids.append(news_id)
        
        tasks = [check_single(news_id) for news_id in news_ids]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return sorted(existing_ids)

    async def _get_news_html_fast(self, news_id: int) -> Optional[str]:
        """
        快速获取新闻页面HTML（使用aiohttp）
        Args:
            news_id: 新闻ID
        Returns:
            页面HTML内容
        """
        if not self.session:
            await self.initialize_browser()
            
        try:
            url = f"{self.base_url}/{news_id}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                return None
        except Exception as e:
            logger.debug(f"获取新闻 {news_id} HTML失败: {e}")
            return None

    def _parse_news_from_html(self, news_id: int, html: str) -> Optional[Dict]:
        """
        从HTML中快速解析新闻信息（使用正则表达式）
        Args:
            news_id: 新闻ID
            html: 页面HTML
        Returns:
            新闻数据字典
        """
        try:
            # 检查是否为404页面
            if "404" in html or "not found" in html.lower():
                return None
            
            # 使用正则表达式快速提取信息
            # 提取标题
            title_patterns = [
                r'<h1[^>]*>(.*?)</h1>',
                r'<title[^>]*>(.*?)</title>',
                r'class="[^"]*title[^"]*"[^>]*>(.*?)</[^>]+>',
                r'<meta\s+property="og:title"\s+content="([^"]*)"',
            ]
            
            title = ""
            for pattern in title_patterns:
                match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
                if match:
                    title = re.sub(r'<[^>]+>', '', match.group(1)).strip()
                    if title and len(title) > 5:
                        break
            
            if not title:
                return None
            
            # 提取发布时间
            time_patterns = [
                r'发布时间\s*[:：]\s*(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})',
                r'(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2})',
                r'(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2})',
                r'(\d{4}/\d{2}/\d{2}\s*\d{2}:\d{2})',
                r'"datePublished"[^>]*content="([^"]*)"',
                r'<time[^>]*datetime="([^"]*)"',
            ]
            
            publish_time = ""
            for pattern in time_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    publish_time = match.group(1)
                    break
            
            # 提取内容段落
            content_patterns = [
                r'<p[^>]*>(.*?)</p>',
                r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            ]
            
            content_paragraphs = []
            for pattern in content_patterns:
                matches = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    # 清理HTML标签
                    clean_text = re.sub(r'<[^>]+>', '', match).strip()
                    clean_text = re.sub(r'\s+', ' ', clean_text)
                    if clean_text and len(clean_text) > 10 and not self._is_irrelevant_content(clean_text):
                        content_paragraphs.append(clean_text)
            
            # 提取图片（如果启用）
            images = []
            if IMAGE_CONFIG.get('enabled', False):
                img_pattern = r'<img[^>]*src=["\']([^"\']*)["\'][^>]*(?:alt=["\']([^"\']*)["\'])?[^>]*>'
                img_matches = re.findall(img_pattern, html, re.IGNORECASE)
                
                for src, alt in img_matches[:IMAGE_CONFIG.get('max_images_per_news', 5)]:
                    if src:
                        # 转换为绝对URL
                        if src.startswith('/'):
                            src = f"https://news.aibase.com{src}"
                        elif src.startswith('//'):
                            src = f"https:{src}"
                        elif not src.startswith(('http://', 'https://')):
                            src = f"https://news.aibase.com/{src}"
                        
                        if not self._is_decorative_or_related_image(src, alt):
                            images.append({
                                'url': src,
                                'alt': alt.strip() if alt else '',
                                'position': len(images)
                            })
            
            # 转换时间格式
            standard_time = self._parse_publish_time(publish_time)
            
            news_data = {
                'id': news_id,
                'title': title,
                'url': f"{self.base_url}/{news_id}",
                'time': standard_time,
                'date': standard_time.split(' ')[0] if ' ' in standard_time else standard_time[:10],
                'time_text': publish_time,
                'content': '\n\n'.join(content_paragraphs),
                'images': images,
                'structured_content': [],
                'summary': "",
                'source': 'AIBase快讯',
                'weight': self.source_weight
            }
            
            return news_data
            
        except Exception as e:
            logger.debug(f"解析新闻 {news_id} HTML失败: {e}")
            return None

    async def _batch_get_news_fast(self, news_ids: List[int]) -> List[Dict]:
        """
        批量快速获取新闻信息
        Args:
            news_ids: 新闻ID列表
        Returns:
            新闻数据列表
        """
        news_list = []
        semaphore = asyncio.Semaphore(self.concurrent_limit)
        
        async def get_single_news(news_id):
            async with semaphore:
                try:
                    html = await self._get_news_html_fast(news_id)
                    if html:
                        news_data = self._parse_news_from_html(news_id, html)
                        if news_data:
                            return news_data
                except Exception as e:
                    logger.debug(f"批量获取新闻 {news_id} 失败: {e}")
                return None
        
        # 并发执行
        tasks = [get_single_news(news_id) for news_id in news_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤有效结果
        for result in results:
            if isinstance(result, dict):
                news_list.append(result)
        
        return news_list

    async def _discover_latest_news_id_fast(self) -> Optional[int]:
        """
        快速发现最新新闻ID（二分查找优化）
        """
        if not self.session:
            await self.initialize_browser()
        
        try:
            # 首先尝试从首页获取
            async with self.session.get(self.base_url) as response:
                if response.status == 200:
                    html = await response.text()
                    # 查找新闻链接
                    links = re.findall(r'/news/(\d+)', html)
                    if links:
                        max_id = max(int(link) for link in links)
                        logger.info(f"从首页发现最大ID: {max_id}")
                        
                        # 使用二分查找确定真正的最新ID
                        latest_id = await self._binary_search_latest_id(max_id)
                        return latest_id
            
            # 如果首页方法失败，使用保守估计
            estimated_id = 21000  # 基于当前趋势的估计
            return await self._binary_search_latest_id(estimated_id)
            
        except Exception as e:
            logger.error(f"快速发现最新ID失败: {e}")
            return None

    async def _binary_search_latest_id(self, start_id: int) -> int:
        """
        使用二分查找确定最新的有效ID
        Args:
            start_id: 起始搜索ID
        Returns:
            最新的有效ID
        """
        # 首先向上搜索找到一个不存在的ID
        upper_bound = start_id
        step = 100
        
        while await self._quick_check_news_exists(upper_bound):
            upper_bound += step
            step = min(step * 2, 1000)  # 指数增长，但限制最大步长
        
        # 现在在 start_id 和 upper_bound 之间二分查找
        left, right = start_id, upper_bound
        latest_valid = start_id
        
        while left <= right:
            mid = (left + right) // 2
            if await self._quick_check_news_exists(mid):
                latest_valid = mid
                left = mid + 1
            else:
                right = mid - 1
        
        logger.info(f"二分查找确定最新ID: {latest_valid}")
        return latest_valid

    async def get_latest_news(self, limit: int = 10) -> List[Dict]:
        """
        获取最新快讯（高速版本）
        """
        # --- FIX START: 添加 try...finally 确保资源关闭 ---
        try:
            logger.info(f"开始高速获取最新 {limit} 条快讯")
            
            await self.initialize_browser()
            
            # 快速发现最新ID
            latest_id = await self._discover_latest_news_id_fast()
            if not latest_id:
                logger.error("无法发现最新新闻ID")
                return []
            
            # 生成候选ID列表（批量处理）
            candidate_ids = list(range(latest_id, latest_id - limit * 2, -1))  # 多取一些以防有些ID不存在
            
            # 批量检查存在性
            logger.info(f"批量检查 {len(candidate_ids)} 个候选ID的存在性...")
            existing_ids = await self._batch_check_news_exists(candidate_ids)
            
            # 取前limit个
            target_ids = existing_ids[:limit]
            
            logger.info(f"开始并发获取 {len(target_ids)} 条新闻详情...")
            # 批量获取新闻详情
            news_list = await self._batch_get_news_fast(target_ids)
            
            # 按ID降序排序（最新的在前）
            news_list.sort(key=lambda x: x['id'], reverse=True)
            
            logger.info(f"高速获取完成，共获取 {len(news_list)} 条快讯")
            return news_list
        finally:
            await self.close_browser()
        # --- FIX END ---

    async def get_news_by_date(self, target_date: str) -> List[Dict]:
        """
        获取指定日期的快讯（高速版本）
        """
        try:
            target_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
            logger.info(f"开始高速获取 {target_date} 的快讯")
            
            await self.initialize_browser()
            
            latest_id = await self._discover_latest_news_id_fast()
            if not latest_id:
                return []
            
            all_news = []
            batch_size = 20  # 每批处理的数量
            current_id = latest_id
            # --- FIX START: 修正了循环终止逻辑 ---
            stop_fetching = False # 用于控制外层 while 循环
            max_batches = 25  # 最多处理25批（500篇文章）
            batch_count = 0
            
            while not stop_fetching and batch_count < max_batches:
                # 生成一批ID
                batch_ids = list(range(current_id, current_id - batch_size, -1))
                batch_count += 1
                
                logger.info(f"处理第 {batch_count} 批 (ID {batch_ids[-1]} - {batch_ids[0]})")
                
                # 批量检查存在性
                existing_ids = await self._batch_check_news_exists(batch_ids)
                
                if not existing_ids:
                    logger.warning(f"第 {batch_count} 批没有有效ID，跳过")
                    current_id -= batch_size
                    continue
                
                # 批量获取新闻详情
                batch_news = await self._batch_get_news_fast(existing_ids)
                
                # 为了逻辑更清晰，对获取到的批次按ID降序排序
                batch_news.sort(key=lambda x: x['id'], reverse=True)

                # 标记当前批次是否包含比目标日期更早的文章
                batch_contained_older_news = False

                # 遍历当前批次的所有结果，不再提前退出
                for news in batch_news:
                    try:
                        news_date_str = news.get('time')
                        if not news_date_str:
                            continue
                        news_date = datetime.strptime(news_date_str, "%Y-%m-%d %H:%M:%S").date()
                        
                        if news_date == target_date_obj:
                            all_news.append(news)
                            logger.info(f"找到目标日期文章: ID {news['id']}")
                        elif news_date < target_date_obj:
                            logger.info(f"遇到早于目标日期的文章: ID {news['id']}, 日期 {news_date}")
                            # 只设置标志，不中断循环，确保本批次处理完
                            batch_contained_older_news = True
                    except (ValueError, KeyError):
                        # 忽略解析时间失败或缺少 'time' 键的文章
                        continue
                
                # 在处理完整个批次后，检查是否需要停止
                if batch_contained_older_news:
                    stop_fetching = True

                # --- FIX END ---
                
                current_id = min(existing_ids) - 1 if existing_ids else current_id - batch_size
                
                # 每5批输出一次进度
                if batch_count % 5 == 0:
                    logger.info(f"已处理 {batch_count} 批，找到 {len(all_news)} 篇目标日期文章")
            
            # 去重并排序，以防万一有重复ID被加入
            final_news = {item['id']: item for item in all_news}.values()
            sorted_news = sorted(list(final_news), key=lambda x: x['id'], reverse=True)

            logger.info(f"高速获取完成，共找到 {len(sorted_news)} 篇 {target_date} 的快讯")
            return sorted_news
        finally:
            await self.close_browser()


    # 保留原有的辅助方法
    def _parse_publish_time(self, publish_time: str) -> str:
        """解析发布时间为标准格式"""
        if not publish_time:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            # 优先处理 ISO 格式 (YYYY-MM-DDTHH:MM:SS...)
            iso_match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', publish_time)
            if iso_match:
                return datetime.fromisoformat(iso_match.group(1)).strftime("%Y-%m-%d %H:%M:%S")

            time_formats = [
                ('%Y年%m月%d日 %H:%M', r'\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}'),
                ('%Y-%m-%d %H:%M', r'\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}'),
                ('%Y/%m/%d %H:%M', r'\d{4}/\d{2}/\d{2}\s*\d{2}:\d{2}'),
                ('%m-%d %H:%M', r'\d{2}-\d{2}\s*\d{2}:\d{2}'),
                ('%m/%d %H:%M', r'\d{2}/\d{2}\s*\d{2}:\d{2}'),
            ]
            
            for fmt, pattern in time_formats:
                match = re.search(pattern, publish_time)
                if match:
                    time_str = match.group(0)
                    time_str = re.sub(r'\s+', ' ', time_str).strip()
                    
                    try:
                        dt_obj = datetime.strptime(time_str, fmt)
                        # 如果年份是1900，说明格式不带年份，需要修正为当前年份
                        if dt_obj.year == 1900 or fmt in ['%m-%d %H:%M', '%m/%d %H:%M']:
                            now = datetime.now()
                            dt_obj = dt_obj.replace(year=now.year)
                            # 如果解析出的日期比当前日期晚，说明是去年的文章
                            if dt_obj > now:
                                dt_obj = dt_obj.replace(year=now.year - 1)

                        return dt_obj.strftime("%Y-%m-%d %H:%M:00")
                    except ValueError:
                        continue
        except:
            pass
        
        # 如果都失败了，返回一个当前时间作为备用
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _is_decorative_or_related_image(self, src: str, alt: str) -> bool:
        """判断是否为装饰性图片"""
        decorative_patterns = [
            r'logo', r'icon', r'avatar', r'banner', r'placeholder',
            r'loading', r'1x1|1\*1', r'\.gif$', r'ad[s]?[_\-]',
            r'share|social', r'button|btn', r'data:image/svg',
            r'thumb|thumbnail', r'small|sm\.', r'list\.|item\.',
        ]
        
        src_lower = src.lower()
        for pattern in decorative_patterns:
            if re.search(pattern, src_lower):
                return True
        
        return False

    def _is_irrelevant_content(self, text: str) -> bool:
        """判断是否为无关内容"""
        irrelevant_patterns = [
            r'^阅读原文$', r'^查看更多$', r'^展开.*%$',
            r'^点击.*查看$', r'^相关.*：$', r'^标签.*：$',
            r'^分享$', r'^收藏$', r'^点赞$', r'^评论$',
            r'^\d+$', r'^[<>\/\s]*$',
        ]
        
        stripped_text = text.strip()
        for pattern in irrelevant_patterns:
            if re.match(pattern, stripped_text, re.IGNORECASE):
                return True
        
        return len(stripped_text) < 10

    # 保持接口兼容性的方法
    async def get_news_detail(self, news_url: str) -> Optional[str]:
        """获取快讯详细内容（兼容性接口）"""
        # --- FIX START: 添加 try...finally 确保资源关闭 ---
        try:
            match = re.search(r'/news/(\d+)', news_url)
            if not match:
                return None
            
            await self.initialize_browser()
            news_id = int(match.group(1))
            html = await self._get_news_html_fast(news_id)
            if html:
                news_data = self._parse_news_from_html(news_id, html)
                return news_data.get('content') if news_data else None
            return None
        finally:
            await self.close_browser()
        # --- FIX END ---

    async def get_news_in_timerange(self, hours: int = 1) -> List[Dict]:
        """获取时间范围内的快讯（高速版本）"""
        # --- FIX START: 添加 try...finally 确保资源关闭 ---
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            
            # 注意：这里调用了 get_latest_news，它内部已经有 try/finally
            # 但为了代码的健壮性，调用方也应该有自己的资源管理，
            # 或者重构此方法以避免嵌套调用带来的复杂性。
            # 这里我们假设 get_latest_news 内部会处理好自己的资源。
            # 一个更优的结构是让 get_latest_news 不关闭 session，由最外层调用者关闭。
            # 但为了最小化改动，我们暂时保持原样。
            
            # 获取足够多的最新快讯
            news_list = await self.get_latest_news(limit=min(hours * 20, 200))
            
            result = []
            for news in news_list:
                try:
                    news_datetime = datetime.strptime(news['time'], "%Y-%m-%d %H:%M:%S")
                    if news_datetime >= cutoff_time:
                        result.append(news)
                    else:
                        break  # 由于是按时间倒序，可以直接break
                except ValueError:
                    continue
            
            logger.info(f"获取到最近{hours}小时内的快讯 {len(result)} 条")
            return result
        finally:
            # 由于 get_latest_news 已经关闭了资源，这里再次调用可能无害但非最优。
            # 一个健壮的 close_browser 应该能处理重复关闭。
            # 我已经在 close_browser 中加入了 `if self.session and not self.session.closed:` 判断。
            await self.close_browser()
        # --- FIX END ---