"""Testes de robustez: como o modelo e o chat reagem a entradas ruins.

Duas partes:
  1. O modelo (ml/modelo.pkl) com frases "estragadas": erros de digitação,
     mudanças de formato, lixo, cumprimento misturado com pedido.
  2. A rota POST /chat com entradas estranhas, que não podem derrubar a API.

A regra mais importante: uma entrada sem sentido NUNCA pode virar relatório
com confiança. Ou o modelo diz fora_do_escopo, ou fica abaixo de 60% e o chat
responde "Não entendi". Errar com confiança é o pior caso (entregaria dados
que o gestor não pediu).

Rodar (na raiz do projeto, com o venv ativado):
    pytest tests/test_robustez.py -v
"""
import random

import joblib
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models import Paciente
from tests.conftest import cabecalho
from tests.test_modelo import FRASES_ESSENCIAIS

LIMITE_CONFIANCA = 0.60
INTENCOES_DE_RELATORIO = {
    "relatorio_gestantes", "relatorio_hipertensos", "relatorio_diabeticos",
    "relatorio_criancas", "relatorio_idosos", "resumo_cobertura",
}


@pytest.fixture(scope="module")
def modelo():
    if not settings.modelo_path.exists():
        pytest.skip(f"Modelo não encontrado em {settings.modelo_path}. Rode: python ml/treinar.py")
    return joblib.load(settings.modelo_path)


def prever(modelo, frase):
    probabilidades = modelo.predict_proba([frase])[0]
    posicao = probabilidades.argmax()
    return modelo.classes_[posicao], probabilidades[posicao]


def com_erros(frase: str, quantidade: int, sorteio: random.Random) -> str:
    """Erros de digitação: apaga, troca de lugar ou duplica uma letra."""
    letras = list(frase)
    for _ in range(quantidade):
        posicao = sorteio.randrange(len(letras) - 1)
        tipo = sorteio.choice(["apaga", "troca", "duplica"])
        if tipo == "apaga":
            letras.pop(posicao)
        elif tipo == "troca":
            letras[posicao], letras[posicao + 1] = letras[posicao + 1], letras[posicao]
        else:
            letras.insert(posicao, letras[posicao])
    return "".join(letras)


# --- 1. Modelo: erros de digitação ---------------------------------------------

@pytest.mark.parametrize("erros, acerto_minimo", [(1, 0.95), (2, 0.90)])
def test_erros_de_digitacao(modelo, erros, acerto_minimo):
    """5 versões com erros de cada frase essencial (semente fixa: sempre os mesmos erros)."""
    sorteio = random.Random(7)
    total = acertos = erradas_com_confianca = 0
    for frase, esperada in FRASES_ESSENCIAIS:
        for _ in range(5):
            prevista, confianca = prever(modelo, com_erros(frase, erros, sorteio))
            total += 1
            acertos += prevista == esperada
            erradas_com_confianca += prevista != esperada and confianca >= LIMITE_CONFIANCA

    assert acertos / total >= acerto_minimo, f"acerto de {acertos / total:.0%} com {erros} erro(s)"
    assert erradas_com_confianca / total <= 0.05, f"{erradas_com_confianca} respostas erradas com confiança"


# --- 1. Modelo: formato ----------------------------------------------------------

FORMATOS = {
    "MAIÚSCULAS": str.upper,
    "Primeira Letra Maiúscula": str.title,
    "espaços sobrando": lambda f: "   " + f.replace(" ", "   ") + "  ",
    "pontuação extra": lambda f: f + "!!!",
    "sem pontuação": lambda f: f.rstrip("?!."),
}


@pytest.mark.parametrize("nome_formato", FORMATOS)
def test_formato_nao_muda_a_intencao(modelo, nome_formato):
    transformar = FORMATOS[nome_formato]
    erradas = [
        (frase, prever(modelo, transformar(frase))[0])
        for frase, esperada in FRASES_ESSENCIAIS
        if prever(modelo, transformar(frase))[0] != esperada
    ]
    assert not erradas, f"{nome_formato}: {erradas}"


# --- 1. Modelo: lixo e textos sem sentido ------------------------------------------

LIXO = [
    "asdkjqwe", "123456", "🙂🙂🙂", "?????", "a", "xyz abc def", "........",
    "lorem ipsum dolor sit amet", "k" * 500, "qwerty" * 80,
    "'; DROP TABLE pacientes; --", "SELECT * FROM users",
]


@pytest.mark.parametrize("entrada", LIXO)
def test_lixo_nunca_vira_relatorio_com_confianca(modelo, entrada):
    prevista, confianca = prever(modelo, entrada)
    assert not (prevista in INTENCOES_DE_RELATORIO and confianca >= LIMITE_CONFIANCA), (
        f"{entrada[:30]!r} virou {prevista} com {confianca:.0%}"
    )


# --- 1. Modelo: cumprimento misturado com pedido -------------------------------------

@pytest.mark.parametrize("frase, esperada", [
    ("olá, tudo bem? queria a cobertura de setembro", "resumo_cobertura"),
    ("bom dia pessoal, tudo certo? gostaria de ver as crianças de abril", "relatorio_criancas"),
    ("oi, quero os hipertensos de julho", "relatorio_hipertensos"),
    ("boa tarde! me manda os idosos de maio", "relatorio_idosos"),
])
def test_cumprimento_com_pedido_vale_o_pedido(modelo, frase, esperada):
    prevista, confianca = prever(modelo, frase)
    assert prevista == esperada, f"{frase!r}: previu {prevista} ({confianca:.0%})"


def test_texto_longo_nao_erra_com_confianca(modelo):
    """Limitação conhecida: um cumprimento MUITO longo antes do pedido confunde o modelo.

    O que se exige é o comportamento seguro: acertar, ou ficar abaixo de 60%
    (o chat pede para reformular). Nunca responder outra coisa com confiança.
    """
    frase = ("olá, bom dia, espero que esteja tudo bem com você, estou aqui na secretaria e " * 5
             + "preciso do relatório das gestantes de agosto")
    prevista, confianca = prever(modelo, frase)
    assert prevista == "relatorio_gestantes" or confianca < LIMITE_CONFIANCA, (
        f"previu {prevista} com {confianca:.0%}"
    )


# --- 2. API: entradas estranhas no POST /chat ----------------------------------------

def enviar(client, usuario, mensagem):
    return client.post("/chat", json={"mensagem": mensagem}, headers=cabecalho(usuario))


@pytest.mark.parametrize("mensagem", ["🙂🙂🙂", "   ", "?????", "\n\t", "123456", "x" * 500])
def test_chat_aguenta_entradas_estranhas(client, dados, mensagem):
    resposta = enviar(client, dados["gestor_a"], mensagem)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] in {"mensagem", "pergunta"}  # nunca um relatório nem um erro interno
    assert corpo["dados"] == []


def test_chat_recusa_mensagem_vazia(client, dados):
    assert enviar(client, dados["gestor_a"], "").status_code == 422


def test_chat_recusa_mensagem_grande_demais(client, dados):
    assert enviar(client, dados["gestor_a"], "x" * 501).status_code == 422


@pytest.mark.parametrize("ataque", [
    "'; DROP TABLE pacientes; --",
    "gestantes de agosto'; DELETE FROM consultas; --",
    "1 OR 1=1",
])
def test_texto_com_sql_nao_afeta_o_banco(client, db, dados, ataque):
    """A mensagem nunca vira SQL: o banco continua igual, e a API não quebra."""
    pacientes_antes = db.scalar(select(func.count()).select_from(Paciente))

    resposta = enviar(client, dados["gestor_a"], ataque)

    assert resposta.status_code in {200, 403}  # nunca 500
    assert db.scalar(select(func.count()).select_from(Paciente)) == pacientes_antes
