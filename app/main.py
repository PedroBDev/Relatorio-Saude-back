from fastapi import FastAPI
from app.api.routes import auth
from app.api.routes import municipio

app = FastAPI(
    title="Saúde em Dados API",
    description="API do sistema Saúde em Dados",
    version="0.1.0"
)


app.include_router(auth.router)
app.include_router(municipio.router)
