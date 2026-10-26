from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.services.chat_service import processar_mensagem

router = APIRouter(
    prefix="/chat",
    tags=["chat"]
)


# Os códigos de erro também devolvem o formato ChatResponse (aparece assim no /docs).
@router.post(
    "",
    response_model=ChatResponse,
    responses={
        400: {"model": ChatResponse, "description": "Parâmetro inválido"},
        403: {"model": ChatResponse, "description": "Sem permissão ou sem município"},
        500: {"model": ChatResponse, "description": "Erro interno (detalhes só no log)"},
        503: {"model": ChatResponse, "description": "Modelo do chatbot indisponível"},
    },
)
def chat(
    dados: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    status, resposta = processar_mensagem(db, current_user, dados.mensagem)

    if status == 200:
        return resposta

    # jsonable_encoder converte datas e decimais para JSON, como o FastAPI faz no 200.
    return JSONResponse(status_code=status, content=jsonable_encoder(resposta))
