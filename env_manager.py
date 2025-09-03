"""
环境变量管理器
用于安全地读取和更新.env文件
"""
import os
import re
from typing import Dict, Optional


class EnvManager:
    """环境变量管理器"""
    
    def __init__(self, env_file: str = '.env'):
        self.env_file = env_file
        self._ensure_env_file_exists()
    
    def _ensure_env_file_exists(self):
        """确保.env文件存在"""
        if not os.path.exists(self.env_file):
            # 如果.env不存在，从.env.example复制
            example_file = '.env.example'
            if os.path.exists(example_file):
                with open(example_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                with open(self.env_file, 'w', encoding='utf-8') as f:
                    f.write(content)
            else:
                # 创建基础的.env文件
                self._create_default_env()
    
    def _create_default_env(self):
        """创建默认的.env文件"""
        default_content = """# AI资讯采集系统环境变量配置文件
# 复制此文件为 .env 并填入实际值

# DeepSeek API配置
DEEPSEEK_API_KEY=

# 金山文档Webhook URL
# 从金山文档群聊机器人管理页面获取
KINGSOFT_WEBHOOK_URL=

# 可选：自定义配置
# Flask调试模式（production环境请设为false）
DEBUG=true

# 服务器配置
HOST=127.0.0.1
PORT=5000

# 爬虫配置
CRAWLER_CONCURRENT_LIMIT=4
CRAWLER_REQUEST_TIMEOUT=30

# 缓存配置
CACHE_EXPIRE_HOURS=24
CACHE_MAX_FILES=100
"""
        with open(self.env_file, 'w', encoding='utf-8') as f:
            f.write(default_content)
    
    def read_env(self) -> Dict[str, str]:
        """读取.env文件内容"""
        env_vars = {}
        
        if not os.path.exists(self.env_file):
            return env_vars
        
        try:
            with open(self.env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    
                    # 跳过注释和空行
                    if not line or line.startswith('#'):
                        continue
                    
                    # 解析键值对
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        
                        # 移除值的引号
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]
                        
                        env_vars[key] = value
        
        except Exception as e:
            print(f"读取.env文件失败: {e}")
        
        return env_vars
    
    def update_env(self, updates: Dict[str, str]) -> bool:
        """
        更新.env文件中的变量
        Args:
            updates: 要更新的键值对
        Returns:
            是否更新成功
        """
        try:
            # 读取现有内容
            if os.path.exists(self.env_file):
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            else:
                lines = []
            
            # 处理更新
            updated_keys = set()
            new_lines = []
            
            for line in lines:
                original_line = line
                line = line.strip()
                
                # 保留注释和空行
                if not line or line.startswith('#'):
                    new_lines.append(original_line)
                    continue
                
                # 处理键值对
                if '=' in line:
                    key, old_value = line.split('=', 1)
                    key = key.strip()
                    
                    if key in updates:
                        # 更新值
                        new_value = updates[key]
                        new_lines.append(f"{key}={new_value}\n")
                        updated_keys.add(key)
                    else:
                        # 保持原值
                        new_lines.append(original_line)
                else:
                    new_lines.append(original_line)
            
            # 添加新的键值对
            for key, value in updates.items():
                if key not in updated_keys:
                    new_lines.append(f"{key}={value}\n")
            
            # 写入文件
            with open(self.env_file, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            
            # 更新os.environ
            for key, value in updates.items():
                os.environ[key] = value
            
            return True
        
        except Exception as e:
            print(f"更新.env文件失败: {e}")
            return False
    
    def get_value(self, key: str, default: str = '') -> str:
        """
        获取环境变量值
        Args:
            key: 变量名
            default: 默认值
        Returns:
            变量值
        """
        # 优先从os.environ获取
        value = os.environ.get(key)
        if value is not None:
            return value
        
        # 从.env文件获取
        env_vars = self.read_env()
        return env_vars.get(key, default)
    
    def set_value(self, key: str, value: str) -> bool:
        """
        设置单个环境变量
        Args:
            key: 变量名
            value: 变量值
        Returns:
            是否设置成功
        """
        return self.update_env({key: value})
    
    def get_masked_value(self, key: str, mask_length: int = 4) -> str:
        """
        获取脱敏后的环境变量值（用于显示）
        Args:
            key: 变量名
            mask_length: 保留的字符数量
        Returns:
            脱敏后的值
        """
        value = self.get_value(key)
        if not value:
            return ''
        
        if len(value) <= mask_length * 2:
            return '*' * len(value)
        
        return value[:mask_length] + '*' * (len(value) - mask_length * 2) + value[-mask_length:]
    
    def validate_config(self) -> Dict[str, bool]:
        """
        验证关键配置是否有效
        Returns:
            配置项的有效状态
        """
        config_status = {}
        
        # 检查DeepSeek API Key
        deepseek_key = self.get_value('DEEPSEEK_API_KEY')
        config_status['deepseek_configured'] = bool(deepseek_key and deepseek_key.startswith('sk-'))
        
        # 检查Webhook URL
        webhook_url = self.get_value('KINGSOFT_WEBHOOK_URL')
        config_status['webhook_configured'] = bool(webhook_url and webhook_url.startswith('http'))
        
        return config_status
    
    def get_display_config(self) -> Dict[str, str]:
        """
        获取用于显示的配置信息（敏感信息已脱敏）
        Returns:
            显示配置
        """
        return {
            'deepseek_api_key': self.get_masked_value('DEEPSEEK_API_KEY'),
            'webhook_url': self.get_masked_value('KINGSOFT_WEBHOOK_URL', 8),
            'debug': self.get_value('DEBUG', 'true'),
            'host': self.get_value('HOST', '127.0.0.1'),
            'port': self.get_value('PORT', '5000')
        }


# 全局实例
env_manager = EnvManager()