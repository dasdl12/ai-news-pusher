import os
from PIL import Image

def add_logo_to_existing_image(base_image_path: str, logo_path: str, output_image_path: str):
    """
    在一个已有的图片上添加Logo。

    :param base_image_path: 基础图片（海报）的路径
    :param logo_path: Logo图片的路径
    :param output_image_path: 添加Logo后保存的新图片路径
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(base_image_path):
            print(f"错误: 基础图片未找到 -> {base_image_path}")
            return
        if not os.path.exists(logo_path):
            print(f"错误: Logo图片未找到 -> {logo_path}")
            return

        # 打开背景海报和Logo图片
        poster = Image.open(base_image_path)
        logo = Image.open(logo_path)

        print("成功打开图片和Logo。")

        # --- 调整Logo尺寸 ---
        # 设定Logo宽度为80像素，并按比例缩放
        logo_width = 340
        aspect_ratio = logo.height / logo.width
        logo_height = int(logo_width * aspect_ratio)
        logo = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
        print(f"Logo尺寸已调整为: {logo.size}")

        # --- 计算Logo位置 ---
        # 右上角，边距为30像素
        margin = 30
        poster_width, poster_height = poster.size
        position = (poster_width - logo_width - margin, margin)
        print(f"Logo将被放置在坐标: {position}")

        # --- 粘贴Logo ---
        # 检查Logo是否有透明通道
        if logo.mode == 'RGBA':
            # 使用透明通道作为遮罩进行粘贴
            poster.paste(logo, position, logo)
            print("使用RGBA模式粘贴Logo。")
        else:
            poster.paste(logo, position)
            print("使用RGB模式粘贴Logo。")

        # --- 保存为新文件 ---
        poster.save(output_image_path, quality=95)
        print(f"成功！带Logo的图片已保存到: {output_image_path}")

    except Exception as e:
        print(f"处理过程中发生错误: {e}")
    finally:
        # 关闭图片对象
        if 'poster' in locals():
            poster.close()
        if 'logo' in locals():
            logo.close()

if __name__ == "__main__":
    # --- 请在这里配置您的文件路径 ---
    
    # 1. 您想要添加Logo的基础图片路径
    base_image_file = r"C:\Users\Administrator\Desktop\crawler2\exports\posters\ai_report_2025-09-02.jpg"
    
    # 2. 您的Logo文件路径 (假设是PNG格式，如果文件名或格式不同请修改)
    # 路径中可能包含中文和空格，使用原始字符串 r"..." 是最稳妥的方式
    logo_file = r"C:\Users\Administrator\Desktop\proctol\01-金山 金山云logo-04.png"
    
    # 3. 添加Logo后新图片的保存路径
    output_image_file = r"C:\Users\Administrator\Desktop\crawler2\exports\posters\ai_report_2025-09-02_with_logo.jpg"

    print("--- 开始为图片添加Logo测试 ---")
    add_logo_to_existing_image(base_image_file, logo_file, output_image_file)
    print("--- 测试结束 ---")