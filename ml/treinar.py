"""Treina e avalia o modelo que classifica a intenção das frases do chatbot.

Como rodar (na raiz do projeto, com o venv ativado):
    python ml/treinar.py

O que ele faz:
  1. lê a base frases.csv;
  2. separa 80% para treino e 20% para teste;
  3. treina o modelo e mostra as métricas no conjunto de teste;
  4. faz uma validação cruzada com 5 partes;
  5. salva a matriz de confusão como imagem (matriz_confusao.png);
  6. confere se o modelo novo não ficou pior que o anterior (teste de regressão);
  7. treina o modelo final com 100% da base e salva em modelo.pkl e metricas.json.

Se o modelo novo ficar pior, o modelo.pkl antigo é mantido. Para aceitar a piora
mesmo assim (ex.: a base mudou de propósito), rode:
    python ml/treinar.py --aceitar-piora

O modelo é um Pipeline de duas etapas:
  - TF-IDF de pedaços de palavras: quebra cada palavra em pedaços de 2 a 5 letras
    ("gestantes" -> "ge", "ges", "gest", "esta", "tant"...) e transforma a frase
    em um vetor de números, dando mais peso aos pedaços que aparecem muito naquela
    frase e pouco no resto da base.
  - Regressão Logística: aprende, a partir desses números, qual intenção é a
    mais provável para cada frase.

Por que pedaços e não palavras inteiras: com palavras inteiras, "hipertenso" e
"hipertensos" (ou o erro "hipertenços") são palavras diferentes, e o modelo só
reconhece a forma exata que viu no treino. Com pedaços, as três formas
compartilham "hiper", "pert", "ertens"... e são reconhecidas como parecidas.
Comparação feita com esta base (validação cruzada, 5 partes, C=30):
    palavras inteiras (1 a 2 palavras):  acurácia 85,9% | 66% respondidas certas
    pedaços de palavras (2 a 5 letras):  acurácia 93,7% | 82% respondidas certas
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
import sklearn
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
# Métricas do último modelo aceito: servem de referência para o próximo treino.
ARQUIVO_METRICAS = PASTA / "metricas.json"

# Requisito de qualidade do modelo: acurácia mínima na validação cruzada.
ACURACIA_MINIMA = 0.85
# Quanto a acurácia pode cair em relação ao modelo anterior sem contar como piora
# (1 ponto percentual: variações menores que isso são ruído de uma base pequena).
TOLERANCIA_QUEDA = 0.01

# Semente fixa: a separação treino/teste e a validação cruzada dão sempre o
# mesmo resultado, então quem rodar de novo encontra os mesmos números.
SEMENTE = 42

# Mesmo limite usado no testar_modelo.py: abaixo disso o chatbot pede para reformular.
LIMITE_CONFIANCA = 0.60


def criar_modelo() -> Pipeline:
    """Monta o Pipeline TF-IDF + Regressão Logística (ainda sem treinar)."""
    return Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="char_wb",       # pedaços de letras dentro de cada palavra (veja o topo do arquivo)
            ngram_range=(2, 5),       # pedaços de 2 a 5 letras
            lowercase=True,           # "Gestantes" e "gestantes" viram a mesma coisa
            strip_accents="unicode",  # "relatório" e "relatorio" viram a mesma coisa
            sublinear_tf=True,        # um pedaço repetido na frase não ganha peso demais
        )),
        ("classificador", LogisticRegression(
            # C controla o quanto o modelo "confia" no que aprendeu. O padrão (C=1)
            # deixa as probabilidades muito baixas nesta base pequena com 9 intenções:
            # quase todo acerto ficava abaixo de 60% de confiança, e o chatbot
            # responderia "Não entendi" o tempo todo. C maior = mais respostas, porém
            # mais erros com confiança alta. Testado nesta base:
            #   C=10: 73% respondidas certas, 4 erradas com confiança
            #   C=30: 82% respondidas certas, 5 erradas com confiança  <- escolhido
            #   C=100: 87% respondidas certas, 8 erradas com confiança
            C=30,
            max_iter=2000,  # número máximo de passos do treino (o padrão, 100, pode não bastar)
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

    # A imagem da matriz (para o artigo) só é salva no fim, se o modelo for aceito.

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

    metricas = {
        "data": datetime.now().isoformat(timespec="seconds"),
        "frases": len(base),
        "intencoes": int(intencoes.nunique()),
        "acuracia_validacao_cruzada": round(float(notas.mean()), 4),
        "desvio_validacao_cruzada": round(float(notas.std()), 4),
        "acuracia_teste": round(float(acuracia), 4),
        "respondidas_certas_teste": int((respondidas & acertou).sum()),
        "erradas_com_confianca_teste": int((respondidas & ~acertou).sum()),
        "nao_entendi_teste": int((~respondidas).sum()),
        "scikit_learn": sklearn.__version__,
    }

    # ------------------------------------------------------------------
    # 7. Teste de regressão de desempenho
    #
    # Garante que um treino novo não piora o modelo sem ninguém perceber.
    # Compara a validação cruzada com a meta mínima e com o último modelo aceito
    # (metricas.json). Se piorar, o modelo.pkl antigo é mantido.
    # ------------------------------------------------------------------
    problemas = verificar_regressao(metricas)
    if problemas:
        print("\n" + "!" * 70)
        print("O MODELO NOVO FICOU PIOR:")
        for problema in problemas:
            print(f"   - {problema}")
        if "--aceitar-piora" not in sys.argv:
            print("O modelo.pkl anterior foi MANTIDO. Revise as frases que mudaram, ou, se a")
            print("piora for esperada, rode: python ml/treinar.py --aceitar-piora")
            print("!" * 70)
            sys.exit(1)
        print("--aceitar-piora informado: o modelo novo será salvo mesmo assim.")
        print("!" * 70)
    else:
        print("\nTESTE DE REGRESSÃO: ok, o modelo novo não ficou pior que o anterior.")

    # ------------------------------------------------------------------
    # 8. Modelo final com 100% da base
    #
    # A avaliação acima já mostrou o desempenho esperado. Agora o modelo que
    # vai ser usado de verdade aprende com todas as frases, inclusive as de teste.
    # ------------------------------------------------------------------
    modelo_final = criar_modelo()
    modelo_final.fit(frases, intencoes)
    joblib.dump(modelo_final, ARQUIVO_MODELO)
    ARQUIVO_METRICAS.write_text(json.dumps(metricas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    salvar_matriz(matriz, nomes)
    print(f"\nModelo final (100% da base) salvo em: {ARQUIVO_MODELO}")
    print(f"Métricas salvas em: {ARQUIVO_METRICAS} (referência para o próximo treino)")
    print(f"Imagem da matriz de confusão salva em: {ARQUIVO_MATRIZ}")


def salvar_matriz(matriz, nomes) -> None:
    """Salva a matriz de confusão do conjunto de teste como imagem, para o artigo."""
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


def verificar_regressao(metricas: dict) -> list[str]:
    """Lista o que piorou em relação à meta e ao último modelo aceito (vazia = tudo ok)."""
    problemas = []
    nova = metricas["acuracia_validacao_cruzada"]

    if nova < ACURACIA_MINIMA:
        problemas.append(f"acurácia {nova:.1%} abaixo da meta mínima de {ACURACIA_MINIMA:.0%}")

    if ARQUIVO_METRICAS.exists():
        anterior = json.loads(ARQUIVO_METRICAS.read_text(encoding="utf-8"))
        antiga = anterior["acuracia_validacao_cruzada"]
        print(f"\nMODELO ANTERIOR ({anterior['data']}, {anterior['frases']} frases): "
              f"acurácia {antiga:.1%}  ->  agora: {nova:.1%}")
        if nova < antiga - TOLERANCIA_QUEDA:
            problemas.append(f"acurácia caiu de {antiga:.1%} para {nova:.1%} "
                             f"(mais que a tolerância de {TOLERANCIA_QUEDA:.0%})")
    else:
        print("\nPrimeiro treino com teste de regressão: as métricas de agora viram a referência.")

    return problemas


if __name__ == "__main__":
    main()
