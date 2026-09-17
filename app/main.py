from fastapi import FastAPI
from app.core.database import engine
from sqlalchemy import text


app = FastAPI(
    title="Saúde em Dados API",
    description="API do sistema Saúde em Dados",
    version="0.1.0"
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "API Saúde em Dados funcionando"
    }


@app.get("/health/database")
def database_health_check():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "connected"
    }