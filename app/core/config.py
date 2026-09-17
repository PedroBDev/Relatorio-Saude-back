from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Saúde em Dados API"
    app_version: str = "0.1.0"
    database_url: str

    class Config:
        env_file = ".env"


settings = Settings()