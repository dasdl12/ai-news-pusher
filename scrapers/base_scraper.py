from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
from datetime import datetime, date
import logging
import asyncio
import platform
import sys

# 修复Windows下的asyncio问题
if platform.system() == 'Windows':
    if sys.version_info >= (3, 8):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except:
            pass

class Article:
    def __init__(self, title: str, date: str, content: str, url: str = "", summary: str = ""):
        self.title = title
        self.date = date
        self.content = content
        self.url = url
        self.summary = summary or content  # 显示完整内容而不是摘要
        
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "date": self.date,
            "content": self.content,
            "url": self.url,
            "summary": self.summary
        }

class BaseScraper(ABC):
    def __init__(self, name: str, base_url: str):
        self.name = name
        self.base_url = base_url
        self.logger = logging.getLogger(f"scraper.{name}")
        
    @abstractmethod
    async def get_article_list(self, start_date: date, end_date: date) -> List[Dict]:
        """获取文章列表"""
        pass
        
    @abstractmethod
    async def get_article_detail(self, article_url: str, list_date: str = "") -> Optional[Article]:
        """获取文章详细内容
        Args:
            article_url: 文章URL
            list_date: 列表页获取的日期，优先使用这个日期
        """
        pass
        
    async def scrape_articles(self, start_date: date, end_date: date, 
                            progress_callback=None) -> Tuple[List[Article], List[str]]:
        """
        爬取指定日期范围内的文章
        返回: (成功的文章列表, 错误信息列表)
        """
        articles = []
        errors = []
        
        try:
            self.logger.info(f"开始爬取 {self.name} 网站文章，日期范围: {start_date} 到 {end_date}")
            
            # 获取文章列表
            article_list = await self.get_article_list(start_date, end_date)
            total = len(article_list)
            
            if progress_callback:
                progress_callback(f"{self.name}: 找到 {total} 篇文章", 0, total)
            
            # 使用信号量限制并发数，提高效率
            semaphore = asyncio.Semaphore(4)  # 最多4个并发
            
            async def fetch_article(article_info, index):
                async with semaphore:
                    try:
                        article = await self.get_article_detail(
                            article_info.get('url', ''), 
                            article_info.get('date', '')
                        )
                        if article:
                            self.logger.info(f"成功爬取文章: {article.title}")
                            return article, None
                        else:
                            error = f"无法获取文章详情: {article_info.get('title', '未知')}"
                            return None, error
                    except Exception as e:
                        error = f"爬取文章失败 {article_info.get('title', '未知')}: {str(e)}"
                        self.logger.error(error)
                        return None, error
            
            # 使用asyncio.gather并发获取所有文章
            tasks = [fetch_article(article_info, i) for i, article_info in enumerate(article_list)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理结果
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    error_msg = f"并发爬取异常: {str(result)}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)
                elif result:
                    article, error = result
                    if article:
                        articles.append(article)
                    if error:
                        errors.append(error)
                        
                if progress_callback and (i + 1) % 5 == 0:  # 每5个更新一次进度
                    progress_callback(f"{self.name}: 处理中...", i + 1, len(results))
                    
        except Exception as e:
            error_msg = f"{self.name} 爬取过程出现错误: {str(e)}"
            self.logger.error(error_msg)
            errors.append(error_msg)
            
        self.logger.info(f"{self.name} 爬取完成，成功 {len(articles)} 篇，错误 {len(errors)} 个")
        return articles, errors
        
    def is_date_in_range(self, article_date: str, start_date: date, end_date: date) -> bool:
        """检查文章日期是否在指定范围内"""
        try:
            # 尝试解析各种日期格式
            for date_format in ["%Y-%m-%d", "%Y年%m月%d日", "%Y/%m/%d", "%m-%d", "%m/%d"]:
                try:
                    parsed_date = datetime.strptime(article_date, date_format).date()
                    # 如果只有月日，假设是当前年份
                    if date_format in ["%m-%d", "%m/%d"]:
                        parsed_date = parsed_date.replace(year=datetime.now().year)
                    return start_date <= parsed_date <= end_date
                except ValueError:
                    continue
            return False
        except Exception:
            return False