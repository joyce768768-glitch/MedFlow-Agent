"""全局配置：从环境变量读取，Demo 不依赖任何真实密钥。"""
from __future__ import annotations

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置（Demo 简化版）。"""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 服务
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # JWT
    jwt_secret: str = "medical-agent-demo-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 12

    # 跨域
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # SubAgent 默认开关
    default_enable_emr_subagent: int = 1
    default_enable_lab_subagent: int = 1

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
