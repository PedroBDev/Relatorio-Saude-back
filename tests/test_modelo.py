"""Testes do modelo de Machine Learning salvo (ml/modelo.pkl).

Complementam o teste de regressão do ml/treinar.py:
  - o modelo salvo atende à meta de qualidade;
  - o modelo está atualizado com o frases.csv (ninguém esqueceu de treinar);
  - frases essenciais, que NÃO estão na base de treino, continuam certas.

Rodar (na raiz do projeto, com o venv ativado):
    pytest tests/test_modelo.py -v
"""
import json

import joblib
import pandas as pd
import pytest

from app.core.config import RAIZ_PROJETO, settings

ARQUIVO_METRICAS = RAIZ_PROJETO / "ml" / "metricas.json"
ARQUIVO_BASE = RAIZ_PROJETO / "ml" / "frases.csv"

# Mesmos valores do treinar.py e do chatbot.
ACURACIA_MINIMA = 0.85
LIMITE_CONFIANCA = 0.60

# Frases que o chatbot precisa acertar sempre. Nenhuma está no frases.csv
# (há um teste que confere isso), então elas medem se o modelo generaliza.
FRASES_ESSENCIAIS = [
    ("preciso do relatório das gestantes de setembro", "relatorio_gestantes"),
    ("quantas grávidas foram acompanhadas em julho?", "relatorio_gestantes"),
    ("me mostra os hipertensos de agosto", "relatorio_hipertensos"),
    ("lista dos pacientes com pressão alta", "relatorio_hipertensos"),
    ("relatório dos diabéticos do mês passado", "relatorio_diabeticos"),
    ("quero ver a glicada dos pacientes", "relatorio_diabeticos"),
    ("relatório das crianças de outubro", "relatorio_criancas"),
    ("quais crianças estão com a vacina atrasada?", "relatorio_criancas"),
    ("relatório dos idosos de junho", "relatorio_idosos"),
    ("pacientes da terceira idade atendidos em maio", "relatorio_idosos"),
    ("qual foi a cobertura de cada grupo em agosto?", "resumo_cobertura"),
    ("me dá o resumo geral do mês", "resumo_cobertura"),
    ("bom dia, tudo bem?", "saudacao"),
    ("olá assistente", "saudacao"),
    ("o que você consegue fazer?", "ajuda"),
    ("como eu peço um relatório pra você?", "ajuda"),
    ("me recomenda uma série pra assistir", "fora_do_escopo"),
    ("qual a previsão do tempo pra amanhã?", "fora_do_escopo"),
]


@pytest.fixture(scope="module")
def modelo():
    if not settings.modelo_path.exists():
        pytest.skip(f"Modelo não encontrado em {settings.modelo_path}. Rode: python ml/treinar.py")
    return joblib.load(settings.modelo_path)


@pytest.fixture(scope="module")
def metricas():
    if not ARQUIVO_METRICAS.exists():
        pytest.fail("ml/metricas.json não existe. Rode: python ml/treinar.py")
    return json.loads(ARQUIVO_METRICAS.read_text(encoding="utf-8"))


def test_modelo_atende_a_meta_de_qualidade(metricas):
    assert metricas["acuracia_validacao_cruzada"] >= ACURACIA_MINIMA


def test_modelo_esta_atualizado_com_a_base(metricas):
    frases_na_base = len(pd.read_csv(ARQUIVO_BASE))
    assert metricas["frases"] == frases_na_base, (
        f"O modelo foi treinado com {metricas['frases']} frases, mas o frases.csv tem "
        f"{frases_na_base}. Rode: python ml/treinar.py"
    )


def test_frases_essenciais_nao_estao_na_base():
    base = set(pd.read_csv(ARQUIVO_BASE)["frase"].str.strip().str.lower())
    repetidas = [frase for frase, _ in FRASES_ESSENCIAIS if frase.lower() in base]
    assert not repetidas, f"Estas frases estão no frases.csv e não medem generalização: {repetidas}"


@pytest.mark.parametrize("frase, esperada", FRASES_ESSENCIAIS)
def test_frase_essencial(modelo, frase, esperada):
    probabilidades = modelo.predict_proba([frase])[0]
    posicao = probabilidades.argmax()
    prevista, confianca = modelo.classes_[posicao], probabilidades[posicao]

    assert prevista == esperada, f"{frase!r}: previu {prevista} ({confianca:.0%})"
    assert confianca >= LIMITE_CONFIANCA, f"{frase!r}: certo, mas com só {confianca:.0%} de confiança"
