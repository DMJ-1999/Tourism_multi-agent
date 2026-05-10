"""Configuration settings for the travel planning system."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


def find_env_file() -> Path:
    """查找.env文件路径"""
    # 从当前工作目录向上查找
    current = Path.cwd()
    for _ in range(5):
        env_path = current / ".env"
        if env_path.exists():
            return env_path
        if current.parent == current:
            break
        current = current.parent

    # 如果找不到，使用默认路径
    return Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # 通义千问API配置
    dashscope_api_key: str = ""  # 如果未配置，将使用模拟模式
    qwen_model: str = "qwen-plus"
    qwen_temperature: float = 0.7
    qwen_max_tokens: int = 2000

    # 高德地图API配置 (Web服务Key)
    amap_api_key: str = "7d516a18e74a0e0418ef7bcb48b52e74"
    amap_security_key: str = ""  # Web服务不需要安全密钥

    # 系统配置
    debug: bool = False
    max_retries: int = 3
    mock_mode: bool = False  # 模拟模式，不调用真实API

    class Config:
        env_file = str(find_env_file())
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
