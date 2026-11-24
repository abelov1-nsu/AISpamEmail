"""Settings source for the Open WebUI integration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openwebui_base_url: str = "http://localhost:3000"
    openwebui_api_key: str = "sk-c2d20f77328444ada57e26bc8bc19ee7"
    openwebui_model: str = "Qwen3.8-Flash-Next"


settings = Settings()
