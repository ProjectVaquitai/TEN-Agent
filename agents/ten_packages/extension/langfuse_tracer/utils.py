import base64
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
# -*- coding=utf-8
from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client
import datetime
import uuid
import sys
import logging
from pathlib import Path


secret_id = os.getenv('COS_SECRET_ID')
secret_key = os.getenv('COS_SECRET_KEY')
region = 'ap-beijing' 

# 如果使用永久密钥不需要填入token，如果使用临时密钥需要填入，临时密钥生成和使用指引参见https://cloud.tencent.com/document/product/436/14048
token = None

config = CosConfig(Region=region, SecretId=secret_id,
                   SecretKey=secret_key, Token=token)
cos_client = CosS3Client(config)
bucket_name = 'datacentric-1316957999'


def base64_to_jpg(base64_str: str, save_dir: str = 'temp_images') -> Optional[str]:
    """
    将 base64 编码的 JPEG 图像保存为本地 jpg 文件

    Args:
        base64_str: base64 编码的图像字符串
        save_dir: 保存图像的目录

    Returns:
        str: 保存的图像文件路径，如果失败则返回 None
    """
    try:
        # 创建保存目录
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        # 如果 base64 字符串包含 header，需要去掉
        if 'base64,' in base64_str:
            base64_str = base64_str.split('base64,')[1]

        # 解码 base64 数据
        img_data = base64.b64decode(base64_str)

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        file_name = f'image_{timestamp}.jpg'
        file_path = str(Path(save_dir) / file_name)

        # 保存图像
        with open(file_path, 'wb') as f:
            f.write(img_data)

        print(f"图像已保存到: {file_path}")
        return file_path

    except Exception as e:
        print(f"保存图像时出错: {e}")
        return None


def upload_image_to_cos(local_file_path: str, bucket: str = 'datacentric-1316957999') -> Optional[str]:
    """
    将本地图像上传到腾讯云 COS

    Args:
        local_file_path: 本地图像文件路径
        cos_client: COS 客户端实例
        bucket: COS 存储桶名称

    Returns:
        str: 上传后的图像 URL，如果失败则返回 None
    """
    try:
        # 确保文件存在
        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f"文件不存在: {local_file_path}")

        # 生成 COS 路径
        file_name = Path(local_file_path).name
        date_time = datetime.datetime.now().strftime("%Y-%m-%d")
        cos_path = f'robot/images/{date_time}/{file_name}'
        # cos_path = f'robot/images/{file_name}'

        # 上传文件
        with open(local_file_path, 'rb') as f:
            cos_client.put_object(
                Bucket=bucket,
                Body=f,
                Key=cos_path,
                ContentType='image/jpeg'
            )

        # 生成 HTTPS URL
        cos_url = f'https://{bucket}.cos.ap-beijing.myqcloud.com/{cos_path}'
        print(f"图像已上传到: {cos_url}")
        return cos_url

    except Exception as e:
        print(f"上传图像时出错: {e}")
        return None

def upload_audio_to_cos(local_file_path: str, bucket: str = 'datacentric-1316957999') -> Optional[str]:
    """
    将本地音频文件上传到腾讯云 COS

    Args:
        local_file_path: 本地音频文件路径
        bucket: COS 存储桶名称

    Returns:
        str: 上传后的音频文件 URL，如果失败则返回 None
    """
    try:
        # 确保文件存在
        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f"文件不存在: {local_file_path}")

        # 生成 COS 路径
        file_name = Path(local_file_path).name
        # 获取文件名（不含扩展名）和扩展名
        name, ext = os.path.splitext(file_name)
        
        # 生成8位随机字符串
        random_suffix = str(uuid.uuid4())[:8]
        
        # 组合新的文件名：原文件名_随机字符串.扩展名
        new_file_name = f"{name}_{random_suffix}{ext}"
        
        # 生成完整的 COS 路径
        date_time = datetime.datetime.now().strftime("%Y-%m-%d")
        cos_path = f'robot/audios/{date_time}/{new_file_name}'

        # 获取文件的 MIME 类型
        mime_type = 'audio/wav'  # WAV 文件的 MIME 类型
        
        # 上传文件
        with open(local_file_path, 'rb') as f:
            cos_client.put_object(
                Bucket=bucket,
                Body=f,
                Key=cos_path,
                ContentType=mime_type  # 设置正确的内容类型
            )

        # 生成 HTTPS URL
        cos_url = f'https://{bucket}.cos.ap-beijing.myqcloud.com/{cos_path}'
        print(f"音频文件已上传到: {cos_url}")
        return cos_url

    except Exception as e:
        print(f"上传音频文件时出错: {e}")
        return None