from enum import StrEnum

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.relatorio_schema import RelatorioDisponivel, RelatorioResponse
from app.services.consultas import CONSULTAS, ConsultaInvalidaError
from app.services.relatorio_service import (
    AcessoNegadoError,
    ErroInternoError,
    gerar_relatorio,
    relatorios_permitidos,
)

router = APIRouter(
    prefix="/relatorios",
    tags=["relatorios"]
)

# Os nomes aceitos na URL são exatamente as consultas do consultas.py.
# Qualquer outro nome é recusado pelo FastAPI (422), e o /docs mostra a lista.
RelatorioNome = StrEnum("RelatorioNome", {nome: nome for nome in CONSULTAS})


@router.get("", response_model=list[RelatorioDisponivel])
def listar_relatorios(current_user: User = Depends(get_current_user)):
    """Relatórios que o usuário logado pode pedir (para o front montar o menu)."""
    return [
        RelatorioDisponivel(relatorio=nome, descricao=CONSULTAS[nome]["descricao"])
        for nome in relatorios_permitidos(current_user)
    ]


@router.get(
    "/{relatorio}",
    response_model=RelatorioResponse,
    responses={
        400: {"description": "Parâmetro inválido"},
        403: {"description": "Sem permissão ou sem município"},
        500: {"description": "Erro interno (detalhes só no log)"},
    },
)
def obter_relatorio(
    relatorio: RelatorioNome,
    mes: int = Query(ge=1, le=12, description="Mês, de 1 a 12"),
    ano: int = Query(ge=1000, le=9999, description="Ano com 4 dígitos"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dados de um relatório no mês/ano informados, sempre do município do usuário logado.

    Usa o mesmo service do POST /chat, então a tela e o chatbot mostram os mesmos números.
    """
    try:
        dados = gerar_relatorio(db, current_user, relatorio.value, mes, ano, origem="api")
    except AcessoNegadoError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ConsultaInvalidaError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ErroInternoError as e:
        raise HTTPException(status_code=500, detail=str(e))

    return RelatorioResponse(
        relatorio=relatorio.value,
        descricao=CONSULTAS[relatorio.value]["descricao"],
        mes=mes,
        ano=ano,
        total=len(dados),
        dados=dados,
    )
