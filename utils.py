"""
工具函数模块
"""
import json
import os
import hashlib
from datetime import datetime, date
from typing import List, Dict, Optional
from config import Config

def save_cache(data: Dict, cache_key: str) -> bool:
    """
    保存数据到缓存
    Args:
        data: 要保存的数据
        cache_key: 缓存键名
    Returns:
        是否保存成功
    """
    try:
        cache_file = os.path.join(Config.CACHE_DIR, f"{cache_key}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'cache_key': cache_key
            }, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存缓存失败: {e}")
        return False

def load_cache(cache_key: str, max_age_hours: int = 24) -> Optional[Dict]:
    """
    从缓存加载数据
    Args:
        cache_key: 缓存键名
        max_age_hours: 最大缓存时间（小时）
    Returns:
        缓存的数据，如果过期或不存在则返回None
    """
    try:
        cache_file = os.path.join(Config.CACHE_DIR, f"{cache_key}.json")
        if not os.path.exists(cache_file):
            return None
            
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # 检查缓存是否过期
        cache_time = datetime.fromisoformat(cache_data['timestamp'])
        if (datetime.now() - cache_time).total_seconds() > max_age_hours * 3600:
            return None
            
        return cache_data['data']
    except Exception as e:
        print(f"加载缓存失败: {e}")
        return None

def generate_cache_key(date_str: str, sources: List[str]) -> str:
    """
    生成缓存键名
    Args:
        date_str: 日期字符串
        sources: 数据源列表
    Returns:
        缓存键名
    """
    sources_str = "_".join(sorted(sources))
    return f"articles_{date_str}_{sources_str}"

def format_date_for_filename(date_obj: date) -> str:
    """
    格式化日期用于文件名
    Args:
        date_obj: 日期对象
    Returns:
        格式化的日期字符串
    """
    return date_obj.strftime("%Y%m%d")

def clean_filename(filename: str) -> str:
    """
    清理文件名，移除非法字符
    Args:
        filename: 原始文件名
    Returns:
        清理后的文件名
    """
    import re
    # 移除非法字符
    cleaned = re.sub(r'[<>:"/\\|?*]', '', filename)
    # 限制长度
    if len(cleaned) > 100:
        cleaned = cleaned[:100]
    return cleaned

def calculate_file_hash(file_path: str) -> Optional[str]:
    """
    计算文件MD5哈希值
    Args:
        file_path: 文件路径
    Returns:
        MD5哈希值，失败返回None
    """
    try:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        print(f"计算文件哈希失败: {e}")
        return None

def ensure_directory(dir_path: str) -> bool:
    """
    确保目录存在
    Args:
        dir_path: 目录路径
    Returns:
        是否成功创建或已存在
    """
    try:
        os.makedirs(dir_path, exist_ok=True)
        return True
    except Exception as e:
        print(f"创建目录失败: {e}")
        return False

def get_file_size_human(file_path: str) -> str:
    """
    获取人类可读的文件大小
    Args:
        file_path: 文件路径
    Returns:
        格式化的文件大小
    """
    try:
        size = os.path.getsize(file_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    except Exception:
        return "未知"

def cleanup_old_cache(max_files: int = 100) -> int:
    """
    清理旧的缓存文件
    Args:
        max_files: 保留的最大文件数
    Returns:
        删除的文件数
    """
    try:
        if not os.path.exists(Config.CACHE_DIR):
            return 0
            
        # 获取所有缓存文件
        cache_files = []
        for filename in os.listdir(Config.CACHE_DIR):
            if filename.endswith('.json'):
                file_path = os.path.join(Config.CACHE_DIR, filename)
                mtime = os.path.getmtime(file_path)
                cache_files.append((file_path, mtime))
        
        # 按修改时间排序，保留最新的
        cache_files.sort(key=lambda x: x[1], reverse=True)
        
        deleted_count = 0
        if len(cache_files) > max_files:
            for file_path, _ in cache_files[max_files:]:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except Exception:
                    pass
                    
        return deleted_count
    except Exception as e:
        print(f"清理缓存失败: {e}")
        return 0

def validate_date_string(date_str: str) -> bool:
    """
    验证日期字符串格式
    Args:
        date_str: 日期字符串 (YYYY-MM-DD)
    Returns:
        是否为有效日期格式
    """
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def get_system_info() -> Dict:
    """
    获取系统信息
    Returns:
        系统信息字典
    """
    import platform
    import psutil
    
    try:
        info = {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'cpu_count': os.cpu_count(),
            'memory_total': f"{psutil.virtual_memory().total / 1024 / 1024 / 1024:.1f} GB",
            'disk_free': f"{psutil.disk_usage('.').free / 1024 / 1024 / 1024:.1f} GB",
            'current_time': datetime.now().isoformat()
        }
        return info
    except Exception as e:
        return {'error': str(e)}

def format_duration(seconds: float) -> str:
    """
    格式化时间间隔
    Args:
        seconds: 秒数
    Returns:
        格式化的时间字符串
    """
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分钟"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}小时"

def is_valid_url(url: str) -> bool:
    """
    验证URL格式
    Args:
        url: URL字符串
    Returns:
        是否为有效URL
    """
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return url_pattern.match(url) is not None

def extract_domain(url: str) -> Optional[str]:
    """
    从URL中提取域名
    Args:
        url: URL字符串
    Returns:
        域名，失败返回None
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return None

# 常用的日期格式转换
DATE_FORMATS = [
    '%Y-%m-%d',
    '%Y年%m月%d日',
    '%Y/%m/%d',
    '%m-%d',
    '%m月%d日',
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M'
]

def parse_date_flexible(date_str: str) -> Optional[date]:
    """
    灵活解析日期字符串
    Args:
        date_str: 日期字符串
    Returns:
        日期对象，失败返回None
    """
    if not date_str:
        return None
        
    for format_str in DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(date_str, format_str)
            # 如果只有月日，假设是当前年份
            if format_str in ['%m-%d', '%m月%d日']:
                parsed_date = parsed_date.replace(year=datetime.now().year)
            return parsed_date.date()
        except ValueError:
            continue
    
    return None