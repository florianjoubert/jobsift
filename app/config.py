"""Centralised configuration: secrets loaded from .env via Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # LLM
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-nano"

    # France Travail (OAuth) - optional: connector is disabled if absent
    france_travail_client_id: str = ""
    france_travail_client_secret: str = ""

    # Adzuna - optional
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    # Email (Gmail SMTP)
    email_address: str = ""
    email_password: str = ""
    email_to: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
