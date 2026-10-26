"""Treina e avalia o modelo que classifica a intenção das frases do chatbot.

Como rodar (na raiz do projeto, com o venv ativado):
    python ml/treinar.py

O que ele faz:
  1. lê a base frases.csv;
  2. separa 80% para treino e 20% para teste;
  3. treina o modelo e mostra as métricas no conjunto de teste;
  4. faz uma validação cruzada com 5 partes;
  5. salva a matriz de confusão como imagem (matriz_confusao.png);
  6. treina o modelo final com 100% da base e salva em modelo.pkl.

O modelo é um Pipeline de duas etapas:
  - TF-IDF: transforma cada frase em um vetor de números, dando mais peso às
    palavras que aparecem muito naquela frase e pouco no resto da base
    (ex.: "gestantes" pesa muito; "de" e "o" pesam pouco).
  - Regressão Logística: aprende, a partir desses números, qual intenção é a
    mais provável para cada frase.
"""
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")  # gera a imagem sem precisar abrir janela (funciona em qualquer terminal)
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline

PASTA = Path(__file__).parent
ARQUIVO_BASE = PASTA / "frases.csv"
ARQUIVO_MODELO = PASTA / "modelo.pkl"
ARQUIVO_MATRIZ = PASTA / "matriz_confusao.png"

# Semente fixa: a separação treino/teste e a validação cruzada dão sempre o
# mesmo resultado, então quem rodar de novo encontra os mesmos números.
SEMENTE = 42

# Mesmo limite usado no testar_modelo.py: abaixo disso o chatbot pede para reformular.
LIMITE_CONFIANCA = 0.60


def criar_modelo() -> Pipeline:
    """Monta o Pipeline TF-IDF + Regressão Logística (ainda sem treinar)."""
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            ngram_range=(1, 2),       # palavras sozinhas ("gestantes") e pares ("pré natal", "pressão alta")
            lowercase=True,           # "Gestantes" e "gestantes" viram a mesma palavra
            strip_accents="unicode",  # "relatório" e "relatorio" viram a mesma palavra
        )),
        ("classificador", LogisticRegression(
            # C controla o quanto o modelo "confia" no que aprendeu. O padrão (C=1)
            # deixa as probabilidades muito baixas nesta base pequena com 9 intenções:
            # quase todo acerto ficava abaixo de 60% de confiança, e o chatbot
            # responderia "Não entendi" o tempo todo. Com C=30, a acurácia é a mesma,
            # mas a confiança dos acertos sobe. C maior = mais respostas, porém mais
            # erros com confiança alta; 30 foi o equilíbrio testado para esta base.
            C=30,
            max_iter=1000,  # número máximo de passos do treino (o padrão, 100, pode não bastar)
        )),
    ])


def main() -> None:
    base = pd.read_csv(ARQUIVO_BASE)
    frases = base["frase"]      # entrada: o texto que o gestor digita
    intencoes = base["intencao"]  # saída esperada: a resposta que o modelo deve aprender

    print(f"Base: {len(base)} frases, {intencoes.nunique()} intenções\n")

    # ------------------------------------------------------------------
    # 1. Separação treino / teste (80% / 20%)
    #
    # O modelo aprende só com o treino e é avaliado no teste, com frases que
    # ele nunca viu. Assim medimos se ele generaliza, e não se decorou a base.
    # stratify mantém a mesma proporção de cada intenção nas duas partes.
    # ------------------------------------------------------------------
    frases_treino, frases_teste, intencoes_treino, intencoes_teste = train_test_split(
        frases, intencoes,
        test_size=0.2,
        stratify=intencoes,
        random_state=SEMENTE,
    )
    print(f"Treino: {len(frases_treino)} frases | Teste: {len(frases_teste)} frases\n")

    modelo = criar_modelo()
    modelo.fit(frases_treino, intencoes_treino)
    previstas = modelo.predict(frases_teste)

    # ------------------------------------------------------------------
    # 2. Acurácia: de todas as frases de teste, quantas % o modelo acertou.
    # ------------------------------------------------------------------
    acuracia = accuracy_score(intencoes_teste, previstas)
    print("=" * 70)
    print(f"ACURÁCIA NO TESTE: {acuracia:.1%}")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 3. Classification report, por intenção:
    #   - precision (precisão): das vezes que o modelo disse "é X", quantas era X.
    #       Baixa = o modelo "chuta" X demais.
    #   - recall (revocação): das frases que eram X, quantas o modelo encontrou.
    #       Baixo = o modelo deixa escapar frases de X.
    #   - f1-score: média entre precision e recall (um resumo das duas).
    #   - support: quantas frases daquela intenção havia no teste.
    # As linhas "macro avg" e "weighted avg" são as médias entre as intenções
    # (a weighted pondera pelo support).
    # ------------------------------------------------------------------
    print("\nRELATÓRIO POR INTENÇÃO")
    print(classification_report(intencoes_teste, previstas, zero_division=0))

    # ------------------------------------------------------------------
    # 4. Matriz de confusão: linhas = intenção verdadeira, colunas = prevista.
    # A diagonal são os acertos. Qualquer número fora da diagonal é uma
    # confusão (ex.: linha "ajuda", coluna "saudacao" = frase de ajuda que o
    # modelo achou que era saudação).
    # ------------------------------------------------------------------
    nomes = sorted(intencoes.unique())
    matriz = confusion_matrix(intencoes_teste, previstas, labels=nomes)
    print("MATRIZ DE CONFUSÃO (linhas = verdadeira, colunas = prevista)")
    with pd.option_context("display.width", 250, "display.max_columns", None):
        print(pd.DataFrame(matriz, index=nomes, columns=nomes))

    # Mesma matriz em imagem, para o artigo.
    figura, eixo = plt.subplots(figsize=(10, 8))
    ConfusionMatrixDisplay(matriz, display_labels=nomes).plot(
        ax=eixo, cmap="Blues", xticks_rotation=45, colorbar=False
    )
    eixo.set_title("Matriz de confusão (conjunto de teste)")
    eixo.set_xlabel("Intenção prevista")
    eixo.set_ylabel("Intenção verdadeira")
    figura.tight_layout()
    figura.savefig(ARQUIVO_MATRIZ, dpi=200)
    plt.close(figura)
    print(f"\nImagem salva em: {ARQUIVO_MATRIZ}")

    # ------------------------------------------------------------------
    # 5. Efeito do limite de confiança (o "Não entendi" do testar_modelo.py).
    # predict_proba dá a probabilidade de cada intenção; a confiança é a maior.
    # ------------------------------------------------------------------
    probabilidades = modelo.predict_proba(frases_teste)
    confianca = probabilidades.max(axis=1)
    acertou = previstas == intencoes_teste.to_numpy()
    respondidas = confianca >= LIMITE_CONFIANCA

    print(f"\nCOM O LIMITE DE CONFIANÇA DE {LIMITE_CONFIANCA:.0%} (no conjunto de teste):")
    print(f"   respondidas e certas:      {(respondidas & acertou).sum():>3} frases")
    print(f"   respondidas e erradas:     {(respondidas & ~acertou).sum():>3} frases  <- o pior caso: resposta errada com confiança")
    print(f"   'Não entendi' (reformular): {(~respondidas).sum():>3} frases")

    # ------------------------------------------------------------------
    # 6. Validação cruzada (5 partes)
    #
    # Um único teste de 20% pode dar sorte ou azar dependendo de quais frases
    # caíram nele. A validação cruzada divide a base em 5 partes e repete o
    # treino 5 vezes, cada vez testando em uma parte diferente. A média mostra
    # o desempenho esperado; o desvio padrão mostra o quanto ele varia
    # (desvio pequeno = modelo estável).
    # ------------------------------------------------------------------
    divisao = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEMENTE)
    notas = cross_val_score(criar_modelo(), frases, intencoes, cv=divisao, scoring="accuracy")
    print("\nVALIDAÇÃO CRUZADA (5 partes)")
    print("   acurácia de cada parte: " + ", ".join(f"{nota:.1%}" for nota in notas))
    print(f"   média: {notas.mean():.1%}  |  desvio padrão: {notas.std():.1%}")

    # ------------------------------------------------------------------
    # 7. Modelo final com 100% da base
    #
    # A avaliação acima já mostrou o desempenho esperado. Agora o modelo que
    # vai ser usado de verdade aprende com todas as frases, inclusive as de teste.
    # ------------------------------------------------------------------
    modelo_final = criar_modelo()
    modelo_final.fit(frases, intencoes)
    joblib.dump(modelo_final, ARQUIVO_MODELO)
    print(f"\nModelo final (100% da base) salvo em: {ARQUIVO_MODELO}")


if __name__ == "__main__":
    main()
