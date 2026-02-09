from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_name: str
    base_url: str
    model_config = SettingsConfigDict(env_file="./.env")


settings = Settings()