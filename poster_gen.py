import asyncio
import os
import logging
from datetime import datetime
from typing import Dict
from pathlib import Path
from playwright.async_api import async_playwright
from config import Config
from PIL import Image # 导入Pillow库

logger = logging.getLogger(__name__)

class PosterGenerator:
    def __init__(self):
        self.output_dir = Config.POSTERS_DIR
        os.makedirs(self.output_dir, exist_ok=True)
        # 更宽的海报展示尺寸
        self.viewport_size = {"width": 530, "height": 960}
        
        # --- 新增：配置您的Logo路径 ---
        # 请确保路径正确，Windows路径中的反斜杠'\'需要转义成'\\'或使用原始字符串 r"..."
        self.logo_path = "C:\\Users\\Administrator\\Desktop\\proctol\\01-金山 金山云logo-04.png" # 假设您的logo是png格式，如果不是请修改后缀
        if not os.path.exists(self.logo_path):
            logger.warning(f"Logo文件未找到，请检查路径: {self.logo_path}")
            self.logo_path = None # 如果Logo不存在，则不执行添加操作
        
    async def generate_poster_from_report(self, report_content: str, date: str, custom_html: str = None) -> Dict:
        """
        根据日报内容生成海报 JPG
        """
        try:
            logger.info(f"开始生成{date}的海报")
            
            if not custom_html:
                html_content = self._create_default_html(report_content, date)
            else:
                html_content = custom_html
            
            filename = f"ai_report_{date}.jpg"
            output_path = os.path.join(self.output_dir, filename)
            
            # 1. HTML 转 JPG
            success = await self._html_to_jpg(html_content, str(output_path))
            
            if success:
                # --- 新增：如果HTML转JPG成功，则添加Logo ---
                try:
                    if self.logo_path:
                        logger.info(f"开始为 {output_path} 添加Logo")
                        self._add_logo_to_image(str(output_path))
                        logger.info("Logo添加成功")
                    else:
                        logger.info("未配置或找不到Logo文件，跳过添加Logo步骤")
                except Exception as e:
                    logger.error(f"添加Logo时出错: {e}")
                    # 即使添加Logo失败，海报本身也已生成，所以这里只记录错误，不改变返回结果的状态
                # -----------------------------------------

                file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                logger.info(f"海报生成成功: {output_path} (大小: {file_size} bytes)")
                return {
                    'success': True,
                    'date': date,
                    'image_path': str(output_path),
                    'filename': filename,
                    'file_size': file_size,
                    'message': '海报生成成功 (已添加Logo)',
                    'generated_at': datetime.now().isoformat(),
                    'template_type': 'custom' if custom_html else 'default'
                }
            else:
                logger.error(f"海报生成失败: {date} - HTML转JPG失败")
                return {
                    'success': False,
                    'date': date,
                    'error': 'HTML转换为JPG图片失败，请检查Playwright配置'
                }
                
        except Exception as e:
            logger.error(f"生成海报时出错: {e}")
            return {
                'success': False,
                'date': date,
                'error': str(e)
            }

    def _add_logo_to_image(self, image_path: str):
        """
        在指定图片右上角添加Logo
        :param image_path: 背景图片的路径
        """
        # 打开背景海报和Logo图片
        poster = Image.open(image_path)
        logo = Image.open(self.logo_path)

        # --- 调整Logo尺寸 ---
        # 您希望Logo小一点，我们设定一个固定宽度（例如80像素），然后按比例缩放高度
        logo_width = 340
        aspect_ratio = logo.height / logo.width
        logo_height = int(logo_width * aspect_ratio)
        # 使用高质量的LANCZOS算法进行缩放
        logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)

        # --- 计算Logo位置 ---
        # 在右上角，并留出一些边距（例如30像素）
        margin = 30
        poster_width, poster_height = poster.size
        position = (poster_width - logo_width - margin, margin)

        # --- 粘贴Logo ---
        # 如果Logo图片有透明通道(RGBA)，则使用它作为遮罩，可以实现完美的透明背景粘贴
        if logo.mode == 'RGBA':
            poster.paste(logo, position, logo)
        else:
            # 如果没有透明通道，直接粘贴
            poster.paste(logo, position)

        # --- 保存覆盖原图 ---
        # 以较高的质量保存，避免压缩损失
        poster.save(image_path, quality=95)
        poster.close()
        logo.close()

    async def _html_to_jpg(self, html_content: str, output_path: str, quality: int = 95) -> bool:
        """
        使用 Playwright 将 HTML 渲染为 JPG
        """
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                try:
                    page = await browser.new_page(
                        viewport=self.viewport_size,
                        device_scale_factor=2
                    )
                    await page.set_content(html_content, wait_until='networkidle')
                    await page.wait_for_timeout(1000)
                    content_height = await page.evaluate("""
                        () => Math.max(
                            document.body.scrollHeight, document.body.offsetHeight,
                            document.documentElement.clientHeight, document.documentElement.scrollHeight,
                            document.documentElement.offsetHeight
                        )
                    """)
                    await page.set_viewport_size({
                        "width": self.viewport_size["width"],
                        "height": max(content_height, self.viewport_size["height"])
                    })
                    await page.screenshot(
                        path=output_path,
                        type='jpeg',
                        quality=quality,
                        full_page=True
                    )
                    logger.info(f"HTML 转 JPG 成功: {output_path}")
                    return True
                finally:
                    await browser.close()
        except Exception as e:
            logger.error(f"HTML 转 JPG 失败: {e}")
            if "playwright" in str(e).lower():
                logger.error("Playwright 可能未安装: 请运行 `playwright install chromium`")
            return False
    
    def _create_default_html(self, content: str, date: str) -> str:
        # ... (此部分代码保持不变)
        processed_content = self._process_markdown_content(content)
        
        html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI日报 - {date}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            width: 530px;
            min-height: 960px;
            background: #FFFFFF;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", system-ui, sans-serif;
            line-height: 1.6;
            color: #1D1D1F;
            padding: 60px 24px 40px;
            position: relative;
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 48px;
        }}
        
        .title {{
            font-size: 48px;
            font-weight: 600;
            color: #1D1D1F;
            margin-bottom: 12px;
            letter-spacing: -0.5px;
        }}
        
        .subtitle {{
            font-size: 24px;
            font-weight: 400;
            color: #86868B;
            margin-bottom: 8px;
        }}
        
        .date {{
            font-size: 18px;
            font-weight: 400;
            color: #007AFF;
        }}
        
        .content {{
            background: #FFFFFF;
            border-radius: 16px;
            padding: 32px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            margin-bottom: 24px;
        }}
        
        .content h2 {{
            font-size: 28px;
            font-weight: 600;
            color: #1D1D1F;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid #E5E5EA;
        }}
        
        .content h3 {{
            font-size: 22px;
            font-weight: 500;
            color: #1D1D1F;
            margin: 24px 0 16px;
        }}
        
        .content p {{
            font-size: 18px;
            font-weight: 400;
            color: #1D1D1F;
            margin-bottom: 16px;
            line-height: 1.6;
        }}
        
        .content ul, .content ol {{
            margin: 16px 0;
            padding-left: 24px;
        }}
        
        .content li {{
            font-size: 18px;
            color: #1D1D1F;
            margin-bottom: 8px;
            line-height: 1.6;
        }}
        
        .highlight {{
            background: #F0F8FF;
            padding: 16px;
            border-radius: 12px;
            margin: 16px 0;
            border-left: 4px solid #007AFF;
        }}
        
        .separator {{
            height: 1px;
            background: #E5E5EA;
            margin: 32px 0;
        }}
        
        .footer {{
            text-align: center;
            color: #86868B;
            font-size: 14px;
            font-weight: 400;
            margin-top: 40px;
        }}
        
        .footer-logo {{
            font-size: 20px;
            font-weight: 600;
            color: #007AFF;
            margin-bottom: 8px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="title">AI日报</div>
        <div class="subtitle">智能资讯摘要</div>
        <div class="date">{date}</div>
    </div>
    
    <div class="content">
        {processed_content}
    </div>
    
    <div class="footer">
        <div class="footer-logo">AI Daily Report</div>
        <div>由 AI 自动生成</div>
    </div>
</body>
</html>"""
        
        return html_template
    
    def _process_markdown_content(self, content: str) -> str:
        # ... (此部分代码保持不变)
        if not content:
            return "<p>（无内容）</p>"
        
        lines = content.split('\n')
        html_lines = []
        in_list = False
        
        for line in lines:
            line = line.strip()
            
            if not line:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append('<div class="separator"></div>')
                continue
            
            # 标题
            if line.startswith('# '):
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append(f'<h2>{line[2:].strip()}</h2>')
            elif line.startswith('## '):
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append(f'<h3>{line[3:].strip()}</h3>')
            # 列表
            elif line.startswith('- ') or line.startswith('* '):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                html_lines.append(f'<li>{line[2:].strip()}</li>')
            elif line[0:2].isdigit() and line[2:4] == '. ':
                if not in_list:
                    html_lines.append('<ol>')
                    in_list = True
                html_lines.append(f'<li>{line[3:].strip()}</li>')
            else:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                html_lines.append(f'<p>{line}</p>')
        
        if in_list:
            html_lines.append('</ul>')
        
        return "\n".join(html_lines)