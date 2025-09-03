"""
金山文档Webhook推送模块
支持文本、Markdown、图片等消息类型的推送
根据官方API文档优化，修正markdown字段名为text
"""
import asyncio
import aiohttp
import json
import logging
from typing import Dict, Optional, Union
from datetime import datetime
import base64
import os
from config import Config

logger = logging.getLogger(__name__)

class KingsoftWebhook:
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or Config.KINGSOFT_WEBHOOK_URL
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
    async def _upload_image_to_catbox(self, image_path: str) -> Optional[str]:
        """
        将本地图片上传到Catbox.moe图床，并返回公网URL。
        Args:
            image_path: 本地图片文件的路径。
        Returns:
            成功则返回图片URL字符串，失败则返回None。
        """
        if not os.path.exists(image_path):
            logger.error(f"[Catbox] 图片文件不存在: {image_path}")
            return None

        logger.info(f"[Catbox] 开始上传图片: {image_path}")
        try:
            data = aiohttp.FormData()
            data.add_field('reqtype', 'fileupload')
            data.add_field('fileToUpload',
                           open(image_path, 'rb'),
                           filename=os.path.basename(image_path))
            
            # 使用独立的session post来上传，避免干扰主session
            async with aiohttp.ClientSession() as upload_session:
                async with upload_session.post('https://catbox.moe/user/api.php', data=data, timeout=120) as response:
                    if response.status == 200:
                        image_url = await response.text()
                        logger.info(f"[Catbox] 图片上传成功，URL: {image_url}")
                        return image_url
                    else:
                        response_text = await response.text()
                        logger.error(f"[Catbox] 图片上传失败。状态码: {response.status}, 响应: {response_text}")
                        return None
        except Exception as e:
            logger.error(f"[Catbox] 上传过程中发生意外错误: {e}")
            return None
    async def send_text(self, content: str) -> Dict:
        """发送纯文本消息"""
        payload = { "msgtype": "text", "text": { "content": content } }
        return await self._send_message(payload, "文本消息")
    
    async def send_markdown(self, content: str, title: str = None) -> Dict:
        """发送Markdown消息"""
        if not content or not content.strip():
            return {'success': False, 'error': 'Markdown内容不能为空'}
        
        send_content = f"# {title}\n\n{content.strip()}" if title else content.strip()
        
        payload = { "msgtype": "markdown", "markdown": { "text": send_content } }
        return await self._send_message(payload, "Markdown消息")
    
    async def send_image_by_url(self, image_url: str, description: str = None) -> Dict:
        """通过URL发送图片（使用markdown格式）"""
        if not image_url:
            return {'success': False, 'error': '图片URL不能为空'}
        
        try:
            desc_text = description or "图片"
            content = f"## 📷 {desc_text}\n\n![{desc_text}]({image_url})"
            return await self.send_markdown(content)
        except Exception as e:
            logger.error(f"发送图片URL时出错: {e}")
            return {'success': False, 'error': str(e)}
    
    async def send_image(self, image_path: str = None, image_url: str = None, description: str = None) -> Dict:
        """
        发送图片消息。
        - 如果提供了 image_url，则直接使用该URL。
        - 如果提供了 image_path，则会自动上传到图床，然后使用返回的URL。
        
        Args:
            image_path: 本地图片路径 (会自动上传)。
            image_url: 图片的公网URL (优先级更高)。
            description: 图片描述。
        Returns:
            发送结果。
        """
        final_image_url = image_url

        try:
            # 1. 决定最终的图片URL
            # 如果没有直接提供URL，但提供了本地路径，则尝试上传
            if not final_image_url and image_path:
                final_image_url = await self._upload_image_to_catbox(image_path)
                if not final_image_url:
                    return {
                        'success': False,
                        'error': f'图片上传失败: {image_path}'
                    }
            
            # 2. 如果最终还是没有URL，则报错
            if not final_image_url:
                return {
                    'success': False,
                    'error': '未提供有效的图片数据 (URL或本地路径)'
                }

            # 3. 使用最终的URL发送图片
            return await self.send_image_by_url(final_image_url, description)
            
        except Exception as e:
            logger.error(f"发送图片消息时出错: {e}")
            return {'success': False, 'error': str(e)}
    
    async def send_daily_report(self, report_content: str, date: str, use_markdown: bool = True) -> Dict:
        """
        发送AI日报
        Args:
            report_content: 日报内容
            date: 日期
            use_markdown: 是否使用markdown格式（默认True）
        Returns:
            发送结果
        """
        try:
            if use_markdown:
                # 使用markdown格式发送日报
                formatted_content = self._format_daily_report_markdown(report_content, date)
                return await self.send_markdown(formatted_content)
            else:
                # 使用纯文本格式
                formatted_content = f"""🤖 AI资讯日报 | {date}

{report_content}

---
📅 发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔗 由AI资讯采集系统自动生成"""
                
                return await self.send_text(formatted_content)
            
        except Exception as e:
            logger.error(f"发送日报时出错: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _format_daily_report_markdown(self, content: str, date: str) -> str:
        """
        格式化日报内容为标准的markdown格式
        Args:
            content: 原始内容
            date: 日期
        Returns:
            格式化后的markdown内容
        """
        # 创建markdown格式的日报
        formatted_lines = [
        ]
        
        # 处理原始内容，增强markdown格式
        content_lines = content.strip().split('\n')
        
        for line in content_lines:
            line = line.strip()
            if not line:
                formatted_lines.append("")
                continue
                
            # 增强标题格式
            if line.startswith('# '):
                formatted_lines.append(f"## 📊 {line[2:].strip()}")
            elif line.startswith('## '):
                formatted_lines.append(f"### 🔸 {line[3:].strip()}")
            elif line.startswith('### '):
                formatted_lines.append(f"#### ▪️ {line[4:].strip()}")
            # 增强列表项
            elif line.startswith('- ') or line.startswith('* '):
                formatted_lines.append(f"- **{line[2:].strip()}**")
            elif line.startswith(tuple(f'{i}. ' for i in range(1, 10))):
                # 处理有序列表
                dot_index = line.find('. ')
                if dot_index != -1:
                    number = line[:dot_index + 1]
                    content_part = line[dot_index + 2:].strip()
                    formatted_lines.append(f"{number} **{content_part}**")
            else:
                formatted_lines.append(line)
        
        # 添加footer
        formatted_lines.extend([
            "",
            "---",
            "",
            "🔗 **由AI资讯采集系统自动生成**",
            "",
            "*更多AI资讯，敬请关注后续更新*"
        ])
        
        return '\n'.join(formatted_lines)
    
    async def send_poster_only(self, image_path: str = None, image_url: str = None, date: str = None) -> Dict:
        """
        只发送海报图片（不包含文字版本）
        Args:
            image_path: 海报图片路径
            image_url: 海报图片URL（推荐）
            date: 日期
        Returns:
            发送结果
        """
        try:
            # 只发送图片
            image_result = await self.send_image(
                image_path=image_path,
                image_url=image_url,
                description=f"AI日报海报 - {date or datetime.now().strftime('%Y-%m-%d')}"
            )
            
            if image_result.get('success', False):
                return {
                    'success': True,
                    'message': '海报发送成功',
                    'result': image_result
                }
            else:
                return {
                    'success': False,
                    'error': image_result.get('error', '海报发送失败'),
                    'result': image_result
                }
            
        except Exception as e:
            logger.error(f"发送海报时出错: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def send_poster_with_report(self, report_content: str, image_path: str = None, image_url: str = None, date: str = None) -> Dict:
        """
        发送日报海报（图片+文字版本）
        Args:
            report_content: 日报文字内容
            image_path: 海报图片路径
            image_url: 海报图片URL（推荐）
            date: 日期
        Returns:
            发送结果
        """
        try:
            results = {}
            

            image_result = await self.send_image(
                image_path=image_path,
                description=f"AI日报海报 - {date or datetime.now().strftime('%Y-%m-%d')}"
            )
            
            results['image_result'] = image_result
            
            # 等待1秒避免消息过快
            await asyncio.sleep(1)
            
            # 2. 发送详细的文字版本
            text_result = await self.send_daily_report(
                report_content, 
                date or datetime.now().strftime('%Y-%m-%d'),
                use_markdown=True
            )
            results['text_result'] = text_result
            
            # 综合结果
            image_success = image_result.get('success', False)
            text_success = text_result.get('success', False)
            
            if image_success and text_success:
                message = "海报和日报都发送成功"
                success = True
            elif text_success:
                message = "日报发送成功，海报发送失败"
                success = True  # 文字版本成功就算成功
            elif image_success:
                message = "海报发送成功，日报发送失败"
                success = False
            else:
                message = "海报和日报都发送失败"
                success = False
            
            return {
                'success': success,
                'message': message,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"发送海报时出错: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def send_poster_info(self, image_path: str, date: str) -> Dict:
        """
        发送海报生成信息（使用markdown格式）
        Args:
            image_path: 图片路径
            date: 日期
        Returns:
            发送结果
        """
        return await self.send_image(image_path=image_path, description=f"AI日报海报 - {date}")
    
    async def _send_message(self, payload: Dict, msg_type: str) -> Dict:
        """
        发送消息到Webhook
        Args:
            payload: 消息载荷
            msg_type: 消息类型（用于日志）
        Returns:
            发送结果
        """
        if not self.webhook_url:
            return {
                'success': False,
                'error': 'Webhook URL未配置'
            }
        
        try:
            await self._ensure_session()
            
            headers = {
                'Content-Type': 'application/json; charset=utf-8'
            }
            
            logger.info(f"开始发送{msg_type}到金山文档...")
            logger.debug(f"发送内容: {json.dumps(payload, ensure_ascii=False)}")
            
            async with self.session.post(
                self.webhook_url, 
                json=payload, 
                headers=headers,
                timeout=30
            ) as response:
                
                response_text = await response.text()
                
                if response.status == 200:
                    # 金山文档的成功响应通常是200状态码
                    logger.info(f"{msg_type}发送成功: {response_text}")
                    return {
                        'success': True,
                        'message': f'{msg_type}发送成功',
                        'response': response_text
                    }
                else:
                    logger.error(f"{msg_type}发送失败，状态码: {response.status}, 响应: {response_text}")
                    return {
                        'success': False,
                        'error': f'HTTP {response.status}: {response_text}'
                    }
                    
        except asyncio.TimeoutError:
            logger.error(f"{msg_type}发送超时")
            return {
                'success': False,
                'error': '发送超时'
            }
        except Exception as e:
            logger.error(f"发送{msg_type}时出错: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def test_webhook(self) -> Dict:
        """
        测试Webhook连接
        Returns:
            测试结果
        """
        # 使用markdown格式的测试消息
        test_content = f"""## 🧪 金山文档机器人连接测试

**测试时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

### ✅ 测试项目
- 文本发送
- Markdown格式
- 连接稳定性

> 如果您看到这条消息，说明连接正常！

---
*测试完成*"""
        
        result = await self.send_markdown(test_content)
        
        if result.get('success'):
            result['message'] = 'Webhook连接测试成功'
        else:
            result['message'] = 'Webhook连接测试失败'
            
        return result


# 工具函数
async def send_report_to_kingsoft(report_content: str, date: str, webhook_url: str = None, use_markdown: bool = True) -> Dict:
    """
    便捷函数：发送日报到金山文档
    Args:
        report_content: 日报内容
        date: 日期
        webhook_url: webhook URL
        use_markdown: 是否使用markdown格式
    """
    webhook = KingsoftWebhook(webhook_url)
    try:
        result = await webhook.send_daily_report(report_content, date, use_markdown)
        return result
    finally:
        await webhook.close_session()


async def send_poster_to_kingsoft(report_content: str, image_path: str = None, image_url: str = None, date: str = None, webhook_url: str = None) -> Dict:
    """
    便捷函数：发送海报到金山文档
    Args:
        report_content: 日报内容
        image_path: 本地图片路径
        image_url: 图片URL（推荐）
        date: 日期
        webhook_url: webhook URL
    """
    webhook = KingsoftWebhook(webhook_url)
    try:
        result = await webhook.send_poster_with_report(report_content, image_path, image_url, date)
        return result
    finally:
        await webhook.close_session()


async def test_kingsoft_webhook(webhook_url: str = None) -> Dict:
    """
    便捷函数：测试金山文档Webhook
    """
    webhook = KingsoftWebhook(webhook_url)
    try:
        result = await webhook.test_webhook()
        return result
    finally:
        await webhook.close_session()


# 上下文管理器支持
class KingsoftWebhookContext:
    """金山文档Webhook上下文管理器"""
    
    def __init__(self, webhook_url: str = None):
        self.webhook = KingsoftWebhook(webhook_url)
    
    async def __aenter__(self):
        return self.webhook
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.webhook.close_session()


# 测试代码
if __name__ == "__main__":
    async def test():
        # 测试连接
        print("测试基础连接...")
        result = await test_kingsoft_webhook()
        print(f"测试结果: {result}")
        
        # 测试markdown日报
        print("\n测试markdown日报...")
        test_content = """## 今日要闻

### OpenAI发布新模型
**OpenAI**宣布推出最新的GPT-5模型。

### Google AI突破
- 蛋白质折叠预测
- 量子计算进展
- 自动驾驶技术

> 更多详情请关注官方发布"""
        
        async with KingsoftWebhookContext() as webhook:
            result = await webhook.send_daily_report(test_content, "2025-09-01")
            print(f"日报发送结果: {result}")
    
    asyncio.run(test())