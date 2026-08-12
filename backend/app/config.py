"""全局配置：从环境变量读取，Demo 不依赖任何真实密钥。"""
from __future__ import annotations

from typing import List, Optional

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

    # —— LLM（智能导诊 SubAgent）——
    # provider: "mock" 走本地关键词规则（默认，无密钥依赖）
    # provider: "openai_compatible" 走 OpenAI 兼容接口，兼容：
    #   · 通义千问 DashScope（base_url=https://dashscope.aliyuncs.com/compatible-mode/v1）
    #   · 智谱 GLM（base_url=https://open.bigmodel.cn/api/paas/v4）
    #   · DeepSeek（base_url=https://api.deepseek.com/v1）
    #   · 开源医疗模型 Ollama/vLLM 本地部署（base_url=http://localhost:11434/v1）
    llm_provider: str = "mock"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model: str = "qwen-plus"
    llm_timeout: int = 30
    # 导诊 SubAgent 用不用真 LLM（=True 时 llm_provider 不能是 mock）
    llm_enable_triage_real: int = 0

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
