"""Geração de relatórios: o único caminho até o banco para os relatórios.

Usado por:
  - POST /chat               (chat_service.py), com origem="chat"
  - GET  /relatorios/{nome}  (routes/relatorio.py), com origem="api"

Assim a tela e o chatbot seguem exatamente as mesmas regras e mostram os
mesmos números: permissão, município do usuário logado, consulta e auditoria.
"""
import logging
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.auditoria import AuditoriaRelatorio
from app.models.user import User
from app.services.consultas import CONSULTAS, executar_consulta
from app.services.permissoes import pode_acessar

logger = logging.getLogger(__name__)

SEM_MUNICIPIO = "Seu usuário não está vinculado a um município."
SEM_PERMISSAO = "Você não tem permissão para acessar este relatório."
ERRO_INTERNO = "Não foi possível gerar o relatório agora. Tente novamente em alguns minutos."

# Nome amigável de cada relatório, usado nas mensagens.
NOMES_RELATORIOS = {
    "relatorio_gestantes": "gestantes",
    "relatorio_hipertensos": "hipertensos",
    "relatorio_diabeticos": "diabéticos",
    "relatorio_criancas": "crianças",
    "relatorio_idosos": "idosos",
    "resumo_cobertura": "resumo de cobertura",
}
# Garante que toda consulta do consultas.py tenha um nome amigável.
assert set(NOMES_RELATORIOS) == set(CONSULTAS), "Atualize NOMES_RELATORIOS em relatorio_service.py"


class AcessoNegadoError(Exception):
    """Usuário sem permissão para o relatório ou sem município (vira HTTP 403)."""


class ErroInternoError(Exception):
    """Falha ao consultar o banco. A mensagem é genérica; o detalhe fica só no log (HTTP 500)."""


def relatorios_permitidos(usuario: User) -> list[str]:
    """Relatórios que o perfil do usuário pode pedir, na ordem do consultas.py."""
    return [nome for nome in CONSULTAS if pode_acessar(usuario.role, nome)]


def registrar_auditoria(db: Session, usuario: User, origem: str, relatorio: str,
                        mes: int | None, ano: int | None, resultado: str,
                        quantidade: int | None = None) -> None:
    """Grava quem pediu qual relatório. Nunca guarda dados de pacientes."""
    try:
        db.add(AuditoriaRelatorio(
            user_id=usuario.id,
            usuario_email=usuario.email,
            origem=origem,
            relatorio=relatorio,
            mes=mes,
            ano=ano,
            resultado=resultado,
            quantidade_registros=quantidade,
        ))
        db.commit()
    except SQLAlchemyError:
        # Falha na auditoria não pode derrubar a resposta ao usuário: fica no log.
        db.rollback()
        logger.exception("Falha ao gravar auditoria (usuário %s, %s)", usuario.id, relatorio)


def gerar_relatorio(db: Session, usuario: User, relatorio: str, mes: int, ano: int,
                    origem: str) -> list[dict]:
    """Confere o acesso, executa a consulta e registra na auditoria.

    Lança:
      AcessoNegadoError     -> sem permissão ou sem município (403)
      ConsultaInvalidaError -> relatório ou parâmetro inválido (400), vem do consultas.py
      ErroInternoError      -> falha no banco (500)
    """
    # 1. Permissão por perfil
    if not pode_acessar(usuario.role, relatorio):
        registrar_auditoria(db, usuario, origem, relatorio, mes, ano, "negado")
        raise AcessoNegadoError(SEM_PERMISSAO)

    # 2. Vínculo com município: sem ele não há como filtrar os dados
    if usuario.municipio_id is None:
        registrar_auditoria(db, usuario, origem, relatorio, mes, ano, "negado")
        raise AcessoNegadoError(SEM_MUNICIPIO)

    # 3. Consulta. O municipio_id vem SEMPRE do usuário logado (do token),
    # nunca do pedido: um gestor não consegue ver outro município.
    try:
        dados = executar_consulta(
            relatorio,
            {"mes": mes, "ano": ano, "municipio_id": usuario.municipio_id},
            db,
        )
    except SQLAlchemyError:
        # O detalhe do banco vai só para o log do servidor.
        logger.exception("Erro ao executar %s para o usuário %s", relatorio, usuario.id)
        db.rollback()
        registrar_auditoria(db, usuario, origem, relatorio, mes, ano, "erro")
        raise ErroInternoError(ERRO_INTERNO) from None

    registrar_auditoria(db, usuario, origem, relatorio, mes, ano, "ok", quantidade=len(dados))

    # O banco devolve números com casa decimal (glicada, cobertura) como Decimal, que
    # iria para o JSON como texto ("7.5"). Convertendo para float, o front recebe número.
    return [
        {coluna: float(valor) if isinstance(valor, Decimal) else valor for coluna, valor in linha.items()}
        for linha in dados
    ]
