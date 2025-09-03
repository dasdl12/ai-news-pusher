"""
配置文件
"""
import os
from datetime import datetime

# 尝试加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # 如果没有安装python-dotenv，直接使用os.getenv
    pass

class Config:
    # 基础配置
    SECRET_KEY = 'your-secret-key-here'
    DEBUG = True
    HOST = '127.0.0.1'
    PORT = 5000
    
    # DeepSeek API配置
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    DEEPSEEK_BASE_URL = "https://api.deepseek.com"
    DEEPSEEK_MODEL = "deepseek-chat"
    
    # 金山文档Webhook配置
    KINGSOFT_WEBHOOK_URL = os.getenv('KINGSOFT_WEBHOOK_URL', '')
    
    # 爬虫配置
    CRAWLER_CONFIG = {
        'concurrent_limit': 4,
        'request_timeout': 30,
        'retry_count': 3,
        'delay_between_requests': 1
    }
    
    # 图片配置
    IMAGE_CONFIG = {
        'enabled': True,
        'max_images_per_news': 5,
        'processing_timeout': 30,
        'poster_width': 390,   # iPhone 14 Pro Max 标准宽度
        'poster_height': 844   # iPhone 14 Pro Max 标准高度，支持内容自适应
    }
    
    # 缓存配置
    CACHE_CONFIG = {
        'enabled': True,
        'expire_hours': 24,
        'max_cache_files': 100
    }
    
    # 目录配置
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CACHE_DIR = os.path.join(BASE_DIR, 'cache')
    EXPORTS_DIR = os.path.join(BASE_DIR, 'exports')
    REPORTS_DIR = os.path.join(EXPORTS_DIR, 'reports')
    POSTERS_DIR = os.path.join(EXPORTS_DIR, 'posters')
    STATIC_DIR = os.path.join(BASE_DIR, 'static')
    TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
    
    # 确保目录存在
    @staticmethod
    def ensure_dirs():
        dirs = [
            Config.CACHE_DIR,
            Config.EXPORTS_DIR,
            Config.REPORTS_DIR,
            Config.POSTERS_DIR,
            Config.STATIC_DIR,
            Config.TEMPLATES_DIR
        ]
        for dir_path in dirs:
            os.makedirs(dir_path, exist_ok=True)
    
    # 日报配置
    REPORT_CONFIG = {
        'min_articles': 5,
        'max_articles': 15,
        'min_score_threshold': 6,
        'tencent_weight': 8,
        'aibase_weight': 5
    }
    
    # AI处理提示词模板
    AI_PROMPT_TEMPLATE = """你是一位专业的AI资讯编辑，请根据以下采集的资讯生成今日AI日报。

资讯来源及评分标准：
1. 腾讯研究院AI速递（权重8分）- 深度内容，行业洞察
2. AIBase快讯（权重5分）- 实时动态，技术更新

内容质量评分标准：
- 高质量（8-10分）：重大技术突破、重要产品发布、行业趋势分析
- 中等质量（5-7分）：产品更新、公司动态、应用案例
- 低质量（2-4分）：重复信息、广告软文、无关内容

筛选要求：
- 保留综合评分≥6分的资讯（来源权重×内容质量）
- 优先保留腾讯研究院内容
- 去除重复和无关信息
- 最终保留8-12条核心资讯
- 按重要性排序

输出要求：
1. 生成精炼的AI日报，使用Markdown格式
2. 包含日报标题“AI前哨日报”（包含具体日期：{date}）
3. 分类整理：
   - 🔥 核心要闻（3-5条最重要的）
   - 🚀 技术动态（3-4条技术相关）
   - 👀 行业观察（2-3条趋势分析）
4. 每条资讯包含：标题、核心内容（2-3句话概括）
5. 适合金山文档群聊展示，简洁明了
6. 底部不要有类似“基于腾讯研究院AI速讯和AIBase快讯生成”的描述

采集时间：{date}
原始资讯内容：
{content}

请开始生成日报："""

# 环境变量配置示例
ENV_TEMPLATE = """# AI资讯采集系统环境变量配置
# 复制此文件为 .env 并填入实际值

# DeepSeek API密钥
DEEPSEEK_API_KEY=your-deepseek-api-key

# 金山文档Webhook URL
KINGSOFT_WEBHOOK_URL=your-kingsoft-webhook-url
"""