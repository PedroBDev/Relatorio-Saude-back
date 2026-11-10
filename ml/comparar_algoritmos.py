"""Compara algoritmos para classificar a intenção das frases do chatbot.

Como rodar (na raiz do projeto, com o venv ativado):
    python ml/comparar_algoritmos.py

Não altera o modelo.pkl: é só um experimento, para justificar a escolha do
algoritmo no artigo. Todos os algoritmos são avaliados nas mesmas condições:
  - mesma base (frases.csv) e mesma validação cruzada de 5 partes;
  - mesmo pré-processamento (TF-IDF de pedaços de 2 a 5 letras);
  - mesmo limite de confiança do chatbot (60%).

Além dos algoritmos de ML, entra um baseline SEM ML (regras de palavras-chave),
para mostrar o que se ganha usando Machine Learning.

Duas avaliações:
  1. Frases limpas: as frases da base como estão.
  2. Robustez: as mesmas frases de teste com 2 erros de digitação cada
     (letra apagada, trocada ou duplicada). O treino continua com frases limpas,
     simulando um gestor digitando rápido no celular.

Atenção: a coluna "Com erros" depende de QUAIS erros foram sorteados e varia
1 a 2 pontos entre sorteios. Na média de 10 sorteios (feita em 03/11/2026):
Regras 63,5% | Naive Bayes 83,3% | KNN 60,3% | Random Forest 84,7% | SVM 90,9% | Regressão Logística 90,8%.
Ou seja, SVM e Regressão Logística empatam; a escolha da Regressão Logística
vem das probabilidades nativas, da interpretabilidade e da velocidade.
"""
import random
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.naive_bayes import MultinomialNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

ARQUIVO_BASE = Path(__file__).parent / "frases.csv"
SEMENTE = 42
LIMITE_CONFIANCA = 0.60
ERROS_POR_FRASE = 2


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(letra for letra in texto if not unicodedata.combining(letra))


class Regras(BaseEstimator, ClassifierMixin):
    """Baseline sem Machine Learning: procura palavras-chave, na ordem.

    A primeira regra que encontrar uma palavra-chave decide a intenção; se
    nenhuma encontrar, é fora_do_escopo. Regra não tem "confiança": ou acha
    (100%) ou não acha. Observação: as palavras-chave foram escritas olhando a
    própria base, então este resultado é otimista para as regras.
    """

    REGRAS = [
        ("resumo_cobertura", ["cobertura", "resumo", "panorama", "visao geral", "consolidado", "geral", "dashboard", "meta"]),
        ("relatorio_gestantes", ["gestant", "gravid", "pre natal", "pre-natal", "prenatal", "gestac"]),
        ("relatorio_hipertensos", ["hipertens", "pressao", "has "]),
        ("relatorio_diabeticos", ["diabet", "glic", " dm "]),
        ("relatorio_criancas", ["crianc", "infantil", "puericultura", "vacin", "bebe", "pediatr"]),
        ("relatorio_idosos", ["idos", "terceira idade", "melhor idade", "velhinh", "60 anos"]),
        ("ajuda", ["ajuda", "como funciona", "o que voce", "o que posso", "como usar", "tutorial", "opcoes", "menu", "explica"]),
        ("saudacao", ["oi", "ola", "bom dia", "boa tarde", "boa noite", "tudo bem", "e ai", "eae", "opa", "salve"]),
    ]

    def fit(self, X, y):
        self.classes_ = np.array(sorted(set(y)))
        return self

    def _classificar(self, frase: str) -> str:
        frase = " " + _normalizar(frase) + " "
        for intencao, palavras in self.REGRAS:
            if any(palavra in frase for palavra in palavras):
                return intencao
        return "fora_do_escopo"

    def predict(self, X):
        return np.array([self._classificar(frase) for frase in X])

    def predict_proba(self, X):
        probabilidades = np.zeros((len(X), len(self.classes_)))
        for i, intencao in enumerate(self.predict(X)):
            probabilidades[i, list(self.classes_).index(intencao)] = 1.0
        return probabilidades


def _tfidf() -> TfidfVectorizer:
    """O mesmo pré-processamento do treinar.py, para a comparação ser justa."""
    return TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), strip_accents="unicode", sublinear_tf=True)


ALGORITMOS = {
    "Regras (sem ML)": lambda: Regras(),
    "Naive Bayes": lambda: Pipeline([("tfidf", _tfidf()), ("modelo", MultinomialNB(alpha=0.1))]),
    "KNN (5 vizinhos)": lambda: Pipeline([("tfidf", _tfidf()), ("modelo", KNeighborsClassifier(5, metric="cosine", weights="distance"))]),
    "Random Forest": lambda: Pipeline([("tfidf", _tfidf()), ("modelo", RandomForestClassifier(300, random_state=SEMENTE, n_jobs=-1))]),
    # O LinearSVC não calcula probabilidades: precisa de calibração extra para o limite de 60%.
    "SVM linear (calibrado)": lambda: Pipeline([("tfidf", _tfidf()), ("modelo", CalibratedClassifierCV(LinearSVC(C=1.0), cv=3))]),
    "Regressão Logística (atual)": lambda: Pipeline([("tfidf", _tfidf()), ("modelo", LogisticRegression(C=30, max_iter=2000))]),
}


def _com_erros(frase: str, sorteio: random.Random) -> str:
    """Coloca erros de digitação: apaga, troca de lugar ou duplica uma letra."""
    letras = list(frase)
    for _ in range(ERROS_POR_FRASE):
        if len(letras) < 2:
            break
        posicao = sorteio.randrange(len(letras) - 1)
        tipo = sorteio.choice(["apaga", "troca", "duplica"])
        if tipo == "apaga":
            letras.pop(posicao)
        elif tipo == "troca":
            letras[posicao], letras[posicao + 1] = letras[posicao + 1], letras[posicao]
        else:
            letras.insert(posicao, letras[posicao])
    return "".join(letras)


def avaliar(criar_modelo, frases, intencoes, classes):
    """Validação cruzada de 5 partes, com e sem erros de digitação."""
    divisao = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMENTE)
    sorteio = random.Random(SEMENTE)  # mesmos erros para todos os algoritmos
    probabilidades = np.zeros((len(frases), len(classes)))
    acertos_com_erros = 0

    for treino, teste in divisao.split(frases, intencoes):
        modelo = criar_modelo().fit(frases[treino], intencoes[treino])
        # alinha as colunas do modelo com a lista geral de intenções
        colunas = [list(classes).index(c) for c in modelo.classes_]
        probabilidades[np.ix_(teste, colunas)] = modelo.predict_proba(frases[teste])
        frases_com_erros = [_com_erros(frase, sorteio) for frase in frases[teste]]
        acertos_com_erros += (modelo.predict(frases_com_erros) == intencoes[teste]).sum()

    previstas = classes[probabilidades.argmax(axis=1)]
    confianca = probabilidades.max(axis=1)
    acertou = previstas == intencoes
    respondeu = confianca >= LIMITE_CONFIANCA

    # tempo de uma predição, com o modelo treinado na base toda
    modelo = criar_modelo().fit(frases, intencoes)
    inicio = time.perf_counter()
    for _ in range(100):
        modelo.predict_proba(["pd me enviar o relatorio de gestante de ago"])
    milissegundos = (time.perf_counter() - inicio) / 100 * 1000

    return {
        "acuracia": acertou.mean(),
        "respondidas_certas": (respondeu & acertou).mean(),
        "erradas_com_confianca": int((respondeu & ~acertou).sum()),
        "acuracia_com_erros": acertos_com_erros / len(frases),
        "ms_por_predicao": milissegundos,
    }


def main() -> None:
    base = pd.read_csv(ARQUIVO_BASE)
    frases = base["frase"].to_numpy()
    intencoes = base["intencao"].to_numpy()
    classes = np.array(sorted(set(intencoes)))

    print(f"Base: {len(frases)} frases, {len(classes)} intenções | "
          f"validação cruzada 5 partes | limite de confiança {LIMITE_CONFIANCA:.0%}\n")
    print(f"{'Algoritmo':<28} {'Acurácia':>9} {'Resp. certas':>13} {'Erradas c/ conf.':>17} "
          f"{'Com erros':>10} {'Queda':>7} {'1 predição':>11}")

    for nome, criar in ALGORITMOS.items():
        r = avaliar(criar, frases, intencoes, classes)
        queda = r["acuracia_com_erros"] - r["acuracia"]
        print(f"{nome:<28} {r['acuracia']:>9.1%} {r['respondidas_certas']:>13.0%} "
              f"{r['erradas_com_confianca']:>17} {r['acuracia_com_erros']:>10.1%} "
              f"{queda:>+7.1%} {r['ms_por_predicao']:>9.1f}ms")

    print("""
Como ler:
  Acurácia          % de frases classificadas certo (validação cruzada).
  Resp. certas      % de frases que o chatbot responderia certo (confiança >= 60%).
  Erradas c/ conf.  frases que o chatbot responderia ERRADO com confiança (o pior caso).
  Com erros         acurácia nas mesmas frases com 2 erros de digitação cada.
  1 predição        tempo para classificar uma frase.""")


if __name__ == "__main__":
    main()
