from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth
from app.api.routes import chat
from app.api.routes import municipio
from app.api.routes import relatorio
from app.api.routes import user
from app.core.config import settings
from app.services.chat_service import carregar_modelo


# Roda uma vez quando o servidor sobe: carrega o modelo do chatbot na memória.
@asynccontextmanager
async def lifespan(app: FastAPI):
    carregar_modelo(settings.modelo_path)
    yield


app = FastAPI(
    title="Saúde em Dados API",
    description="API do sistema Saúde em Dados",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: libera o front em Next.js (http://localhost:3000 por padrão) a chamar a API
# pelo navegador. A lista fica em CORS_ORIGINS no .env.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)
app.include_router(municipio.router)
app.include_router(user.router)
app.include_router(chat.router)
app.include_router(relatorio.router)
