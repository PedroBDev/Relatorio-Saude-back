from pathlib import Path

from pydantic_settings import BaseSettings

# Raiz do projeto (a pasta que tem app/ e ml/), para achar arquivos de qualquer diretório.
RAIZ_PROJETO = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "Saúde em Dados API"
    app_version: str = "0.1.0"
    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # Endereços do front que podem chamar a API pelo navegador (CORS).
    # No .env: CORS_ORIGINS=["http://localhost:3000","https://meu-front.com"]
    cors_origins: list[str] = ["http://localhost:3000"]

    # Modelo do chatbot gerado por ml/treinar.py.
    modelo_path: Path = RAIZ_PROJETO / "ml" / "modelo.pkl"
    # Quanto tempo o chatbot lembra da pergunta "de qual mês?" de cada usuário.
    chat_contexto_minutos: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
