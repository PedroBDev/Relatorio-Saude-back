"""Fluxo do chatbot: da mensagem do gestor até o relatório.

Ordem do processamento (função processar_mensagem):
  1. Se o chatbot tinha perguntado "de qual mês?" e a mensagem traz um mês,
     continua o pedido anterior (sem passar pelo modelo).
  2. Classifica a intenção com o modelo (TF-IDF + Regressão Logística).
  3. A mensagem tem um mês, mas nenhum relatório reconhecido (ex.: só "agosto de
     2026") -> pergunta qual relatório e guarda o período por alguns minutos.
  4. Confiança abaixo de 60% -> pede para reformular.
  5. saudacao / ajuda / fora_do_escopo -> resposta fixa, sem consultar o banco.
  6. Relatório sem mês -> usa o período guardado no passo 3, se houver; senão,
     pergunta o mês e guarda a intenção por alguns minutos.
  7. Gera o relatório pelo relatorio_service (o mesmo dos endpoints /relatorios):
     confere permissão e município (403 se não puder), executa a consulta e
     registra na auditoria.

O município usado é SEMPRE o do usuário logado (current_user.municipio_id).
Nada que venha do pedido muda isso, então um gestor não vê outro município.

Toda mensagem fica registrada na tabela interacoes_chat (intenção prevista,
confiança e tipo de resposta, NUNCA o texto), para monitorar o modelo.
"""
import json
import logging
import threading
import time
from pathlib import Path

import joblib
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.interacao_chat import InteracaoChat
from app.models.user import User
from app.schemas.chat_schema import ChatResponse
from app.services.consultas import ConsultaInvalidaError
from app.services.extrair_parametros import descrever_periodo, extrair_periodo, montar_pergunta_faltante
from app.services.relatorio_service import (
    NOMES_RELATORIOS,
    AcessoNegadoError,
    ErroInternoError,
    gerar_relatorio,
)

logger = logging.getLogger(__name__)

LIMITE_CONFIANCA = 0.60
NAO_ENTENDI = "Não entendi, pode reformular?"

# Respostas fixas: não precisam de banco de dados.
MENSAGENS_FIXAS = {
    "saudacao": (
        "Olá! Sou o assistente do Saúde em Dados. Posso gerar relatórios de gestantes, "
        "hipertensos, diabéticos, crianças e idosos, além do resumo de cobertura. "
        "Experimente: \"relatório das gestantes de agosto\"."
    ),
    "ajuda": (
        "Você pode me pedir relatórios mensais de: gestantes, hipertensos, diabéticos, "
        "crianças e idosos, ou o resumo de cobertura de todos os grupos. "
        "Diga o grupo e o mês, por exemplo: \"hipertensos de março de 2026\" ou "
        "\"resumo de cobertura do mês passado\"."
    ),
    "fora_do_escopo": (
        "Desculpe, só consigo ajudar com os relatórios de acompanhamento da saúde do "
        "seu município. Digite \"ajuda\" para ver o que posso fazer."
    ),
}

# Pergunta usada quando o gestor informa só o período (ex.: "agosto de 2026").
PERGUNTA_RELATORIO = (
    "De qual relatório você quer os dados de {periodo}? Posso gerar: gestantes, "
    "hipertensos, diabéticos, crianças, idosos ou o resumo de cobertura."
)

# ---------------------------------------------------------------------------
# Modelo de Machine Learning
#
# Carregado uma única vez, quando o servidor sobe (veja o lifespan em main.py).
# Carregar a cada requisição deixaria cada mensagem bem mais lenta.
# ---------------------------------------------------------------------------
_modelo = None
_versao_modelo = None  # data do treino, lida do metricas.json (vai para a interacoes_chat)


def carregar_modelo(caminho: Path) -> None:
    """Lê o modelo.pkl gerado pelo ml/treinar.py e guarda na memória."""
    global _modelo, _versao_modelo
    if not caminho.exists():
        # O servidor sobe mesmo assim; só o /chat fica indisponível.
        logger.warning("Modelo do chatbot não encontrado em %s. Rode: python ml/treinar.py", caminho)
        _modelo = None
        return
    _modelo = joblib.load(caminho)
    try:
        _versao_modelo = json.loads(caminho.with_name("metricas.json").read_text(encoding="utf-8"))["data"]
    except (OSError, ValueError, KeyError):
        _versao_modelo = None
    logger.info("Modelo do chatbot carregado de %s (treino de %s)", caminho, _versao_modelo)


def _classificar(mensagem: str) -> tuple[str, float]:
    """Devolve (intenção mais provável, confiança de 0 a 1)."""
    probabilidades = _modelo.predict_proba([mensagem])[0]
    posicao = probabilidades.argmax()
    return _modelo.classes_[posicao], float(probabilidades[posicao])


# ---------------------------------------------------------------------------
# Contexto da conversa em memória
#
# Guarda o que ficou faltando na conversa de cada usuário, para a próxima
# mensagem completar o pedido. São dois casos:
#   - o chat perguntou "de qual mês?"      -> guarda a INTENÇÃO ("relatorio_gestantes")
#   - o chat perguntou "de qual relatório?" -> guarda o PERÍODO ({"mes": 8, "ano": 2026})
# É um dicionário simples: some se o servidor reiniciar e não é compartilhado
# entre vários processos, o que é suficiente para o projeto acadêmico.
# O Lock evita que duas requisições mexam no dicionário ao mesmo tempo.
# ---------------------------------------------------------------------------
_contextos: dict[int, tuple[dict, float]] = {}  # user_id -> ({"intencao" ou "periodo": ...}, expira_em)
_trava = threading.Lock()


def _guardar_contexto(user_id: int, intencao: str | None = None, periodo: dict | None = None) -> None:
    expira_em = time.monotonic() + settings.chat_contexto_minutos * 60
    with _trava:
        _contextos[user_id] = ({"intencao": intencao, "periodo": periodo}, expira_em)


def _obter_contexto(user_id: int) -> dict:
    """O que está pendente para o usuário: {"intencao": ..., "periodo": ...} (vazio se nada ou expirado)."""
    with _trava:
        contexto = _contextos.get(user_id)
        if contexto and contexto[1] < time.monotonic():
            del _contextos[user_id]
            contexto = None
    return contexto[0] if contexto else {"intencao": None, "periodo": None}


def _limpar_contexto(user_id: int) -> None:
    with _trava:
        _contextos.pop(user_id, None)


# ---------------------------------------------------------------------------
# Monitoramento (data drift)
# ---------------------------------------------------------------------------
def _registrar_interacao(db: Session, usuario: User, classificacao: dict, resposta: ChatResponse) -> None:
    """Grava o que o modelo decidiu nesta mensagem. Nunca grava o texto digitado."""
    resultado = "nao_entendi" if resposta.texto == NAO_ENTENDI else resposta.tipo
    try:
        db.add(InteracaoChat(
            user_id=usuario.id,
            intencao_prevista=classificacao["intencao"],
            confianca=classificacao["confianca"],
            resultado=resultado,
            versao_modelo=_versao_modelo,
        ))
        db.commit()
    except SQLAlchemyError:
        # Igual à auditoria: falha no monitoramento não pode derrubar a resposta.
        db.rollback()
        logger.exception("Falha ao gravar interação do chat (usuário %s)", usuario.id)


# ---------------------------------------------------------------------------
# Fluxo principal
# ---------------------------------------------------------------------------
def processar_mensagem(db: Session, usuario: User, mensagem: str) -> tuple[int, ChatResponse]:
    """Processa uma mensagem e devolve (status HTTP, resposta no formato padrão)."""
    # _responder preenche a classificação quando usa o modelo; depois ela vai para o registro.
    classificacao = {"intencao": None, "confianca": None}
    status, resposta = _responder(db, usuario, mensagem, classificacao)
    _registrar_interacao(db, usuario, classificacao, resposta)
    return status, resposta


def _responder(db: Session, usuario: User, mensagem: str, classificacao: dict) -> tuple[int, ChatResponse]:
    periodo = extrair_periodo(mensagem)
    pendente = _obter_contexto(usuario.id)

    # 1. Resposta a uma pergunta anterior ("agosto" depois de "de qual mês?")
    if pendente["intencao"] and periodo["mes"]:
        _limpar_contexto(usuario.id)
        return _gerar_relatorio(db, usuario, pendente["intencao"], periodo)

    if _modelo is None:
        return 503, ChatResponse(
            tipo="erro",
            texto="O assistente está indisponível no momento. Tente novamente mais tarde.",
        )

    # 2. Classificação da intenção
    intencao, confianca = _classificar(mensagem)
    classificacao.update(intencao=intencao, confianca=confianca)

    # 3. Só o período, sem relatório reconhecido ("agosto de 2026", "set/26", "mês passado"):
    # em vez de "não entendi", pergunta qual relatório e guarda o período.
    if periodo["mes"] and (confianca < LIMITE_CONFIANCA or intencao == "fora_do_escopo"):
        _guardar_contexto(usuario.id, periodo=periodo)
        texto = PERGUNTA_RELATORIO.format(periodo=descrever_periodo(periodo["mes"], periodo["ano"]))
        return 200, ChatResponse(tipo="pergunta", texto=texto,
                                 parametros={"mes": periodo["mes"], "ano": periodo["ano"]})

    # 4. Confiança baixa: melhor perguntar de novo do que entregar o relatório errado.
    # O contexto pendente (se houver) é mantido, para o usuário ainda poder responder.
    if confianca < LIMITE_CONFIANCA:
        return 200, ChatResponse(tipo="mensagem", texto=NAO_ENTENDI)

    # A partir daqui é um pedido novo: esquece qualquer pergunta pendente
    # (o período pendente já foi lido acima, em "pendente").
    _limpar_contexto(usuario.id)

    # 5. Intenções que não são relatório
    if intencao in MENSAGENS_FIXAS:
        return 200, ChatResponse(tipo="mensagem", texto=MENSAGENS_FIXAS[intencao], intencao=intencao)

    # 6. Relatório sem mês na mensagem: usa o período informado antes ("agosto de 2026"
    # seguido de "gestantes"); se não houver, pergunta o mês e guarda a intenção.
    if not periodo["mes"] and pendente["periodo"]:
        periodo = pendente["periodo"]

    pergunta = montar_pergunta_faltante(periodo)
    if pergunta:
        _guardar_contexto(usuario.id, intencao=intencao)
        return 200, ChatResponse(tipo="pergunta", texto=pergunta, intencao=intencao)

    return _gerar_relatorio(db, usuario, intencao, periodo)


def _gerar_relatorio(db: Session, usuario: User, intencao: str, periodo: dict) -> tuple[int, ChatResponse]:
    """Passo 7: gera o relatório e transforma o resultado (ou o erro) em resposta do chat."""
    mes, ano = periodo["mes"], periodo["ano"]
    parametros_resposta = {"mes": mes, "ano": ano}

    try:
        dados = gerar_relatorio(db, usuario, intencao, mes, ano, origem="chat")
    except AcessoNegadoError as erro:
        return 403, ChatResponse(tipo="erro", texto=str(erro), intencao=intencao,
                                 parametros=parametros_resposta)
    except ConsultaInvalidaError as erro:
        # Mensagens escritas por nós (ex.: "Mês inválido: 13"), seguras para mostrar.
        return 400, ChatResponse(tipo="erro", texto=str(erro), intencao=intencao,
                                 parametros=parametros_resposta)
    except ErroInternoError as erro:
        return 500, ChatResponse(tipo="erro", texto=str(erro), intencao=intencao,
                                 parametros=parametros_resposta)

    nome = NOMES_RELATORIOS[intencao]
    descricao = descrever_periodo(mes, ano)
    if intencao == "resumo_cobertura":
        texto = f"Resumo de cobertura de {descricao}."
    else:
        texto = f"Relatório de {nome} de {descricao}: {len(dados)} paciente(s) atendido(s)."

    return 200, ChatResponse(tipo="relatorio", texto=texto, intencao=intencao,
                             parametros=parametros_resposta, dados=dados)
