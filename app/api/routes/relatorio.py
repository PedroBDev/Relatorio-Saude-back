from enum import StrEnum

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.models.municipio import Municipio
from app.models.user import User
from app.schemas.relatorio_schema import RelatorioDisponivel, RelatorioResponse
from app.services.consultas import CONSULTAS, ConsultaInvalidaError
from app.services.exportacao_service import gerar_excel, gerar_pdf
from app.services.extrair_parametros import NOMES_MESES
from app.services.relatorio_service import (
    NOMES_RELATORIOS,
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

RESPOSTAS_DE_ERRO = {
    400: {"description": "Parâmetro inválido"},
    403: {"description": "Sem permissão ou sem município"},
    500: {"description": "Erro interno (detalhes só no log)"},
}

# Formatos da exportação: função que monta o arquivo, extensão e tipo do arquivo.
FORMATOS = {
    "excel": (gerar_excel, "xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "pdf": (gerar_pdf, "pdf", "application/pdf"),
}
FormatoExportacao = StrEnum("FormatoExportacao", {formato: formato for formato in FORMATOS})


def _dados_do_relatorio(db: Session, usuario: User, relatorio: str, mes: int, ano: int) -> list[dict]:
    """Chama o service (o mesmo do chat) e troca os erros dele pelos códigos HTTP."""
    try:
        return gerar_relatorio(db, usuario, relatorio, mes, ano, origem="api")
    except AcessoNegadoError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ConsultaInvalidaError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ErroInternoError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=list[RelatorioDisponivel])
def listar_relatorios(current_user: User = Depends(get_current_user)):
    """Relatórios que o usuário logado pode pedir (para o front montar o menu)."""
    return [
        RelatorioDisponivel(relatorio=nome, descricao=CONSULTAS[nome]["descricao"])
        for nome in relatorios_permitidos(current_user)
    ]


@router.get("/{relatorio}", response_model=RelatorioResponse, responses=RESPOSTAS_DE_ERRO)
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
    dados = _dados_do_relatorio(db, current_user, relatorio.value, mes, ano)

    return RelatorioResponse(
        relatorio=relatorio.value,
        descricao=CONSULTAS[relatorio.value]["descricao"],
        mes=mes,
        ano=ano,
        total=len(dados),
        dados=dados,
    )


@router.get(
    "/{relatorio}/exportar/{formato}",
    response_class=StreamingResponse,
    responses={200: {"description": "Arquivo .xlsx ou .pdf para baixar"}, **RESPOSTAS_DE_ERRO},
)
def exportar_relatorio(
    relatorio: RelatorioNome,
    formato: FormatoExportacao,
    mes: int = Query(ge=1, le=12, description="Mês, de 1 a 12"),
    ano: int = Query(ge=1000, le=9999, description="Ano com 4 dígitos"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """O mesmo relatório do GET /relatorios/{relatorio}, em Excel ou PDF.

    Passa pelas mesmas regras (login, município do token, auditoria).
    """
    dados = _dados_do_relatorio(db, current_user, relatorio.value, mes, ano)

    # Aqui o usuário já tem município: sem ele, o service teria negado o acesso.
    municipio = db.get(Municipio, current_user.municipio_id)
    titulo = f"Relatório de {NOMES_RELATORIOS[relatorio.value]}"
    subtitulo = (f"{municipio.nome}/{municipio.uf} · {NOMES_MESES[mes]} de {ano} · "
                 f"{len(dados)} registro(s)")

    gerar_arquivo, extensao, tipo = FORMATOS[formato.value]
    arquivo = gerar_arquivo(dados, titulo, subtitulo)
    nome_arquivo = f"{relatorio.value}_{ano}-{mes:02d}.{extensao}"

    return StreamingResponse(
        arquivo,
        media_type=tipo,
        # attachment: o navegador baixa o arquivo em vez de abrir na tela.
        headers={"Content-Disposition": f'attachment; filename="{nome_arquivo}"'},
    )
