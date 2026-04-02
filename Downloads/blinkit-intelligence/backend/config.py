from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str
    SYPHOON_PRODUCT_KEY: str
    SYPHOON_CATEGORY_KEY: str
    SYPHOON_KEYWORD_KEY: str
    SYPHOON_API_URL: str = "https://api.syphoon.com"
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5500,http://127.0.0.1:5500"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
