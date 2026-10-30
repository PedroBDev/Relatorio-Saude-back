"""Confere a base de treino do chatbot (frases.csv) antes de treinar o modelo.

Como rodar (na raiz do projeto, com o venv ativado):
    python ml/verificar_base.py

O que ele mostra:
  - quantas frases existem por intenção;
  - linhas vazias (frase ou intenção em branco);
  - frases duplicadas (exatamente iguais);
  - frases quase iguais (iguais depois de ignorar maiúsculas, acentos e pontuação);
  - intenções com menos frases que o mínimo combinado.
"""
import string
import sys
import unicodedata
from pathlib import Path

import pandas as pd

# O CSV fica na mesma pasta deste script, então funciona de qualquer diretório.
ARQUIVO = Path(__file__).parent / "frases.csv"

# Mínimo de frases por intenção que definimos para a base.
MINIMO_POR_INTENCAO = 40


def normalizar(frase: str) -> str:
    """Deixa a frase "crua" para achar quase-duplicatas.

    Ex.: "Gestantes de Março!" e "gestantes de marco" viram "gestantes de marco".
    """
    frase = frase.lower().strip()
    # Separa a letra do acento ("ç" vira "c" + cedilha) e joga o acento fora.
    frase = unicodedata.normalize("NFKD", frase)
    frase = "".join(letra for letra in frase if not unicodedata.combining(letra))
    # Remove pontuação e espaços repetidos.
    frase = frase.translate(str.maketrans("", "", string.punctuation))
    return " ".join(frase.split())


def main() -> None:
    # dtype=str: lê tudo como texto (sem isso, uma frase como "2026" viraria número).
    # keep_default_na=False: célula vazia vira "" em vez de NaN, fica mais fácil checar.
    base = pd.read_csv(ARQUIVO, dtype=str, keep_default_na=False)

    problemas = 0

    # 1. Colunas esperadas
    if list(base.columns) != ["frase", "intencao"]:
        print(f"ERRO: as colunas deveriam ser 'frase,intencao', mas são {list(base.columns)}")
        sys.exit(1)

    # Tira espaços sobrando no começo/fim, para "  oi" e "oi" contarem como iguais.
    base["frase"] = base["frase"].str.strip()
    base["intencao"] = base["intencao"].str.strip()

    print(f"Arquivo: {ARQUIVO}")
    print(f"Total de frases: {len(base)}\n")

    # 2. Linhas vazias. O +2 converte o índice do pandas no número da linha
    # do arquivo (o índice começa em 0 e a linha 1 é o cabeçalho).
    vazias = base[(base["frase"] == "") | (base["intencao"] == "")]
    if not vazias.empty:
        problemas += len(vazias)
        print(f"AVISO: {len(vazias)} linha(s) com frase ou intenção vazia:")
        for indice in vazias.index:
            print(f"   linha {indice + 2}")
        print()
        base = base.drop(vazias.index)

    # 3. Frases por intenção
    print("Frases por intenção:")
    contagem = base["intencao"].value_counts().sort_index()
    for intencao, quantidade in contagem.items():
        marcador = "" if quantidade >= MINIMO_POR_INTENCAO else f"   <- abaixo do mínimo de {MINIMO_POR_INTENCAO}"
        print(f"   {intencao:<25} {quantidade}{marcador}")
        if quantidade < MINIMO_POR_INTENCAO:
            problemas += 1
    print()

    # 4. Duplicadas exatas. keep=False marca TODAS as cópias, não só a segunda.
    duplicadas = base[base.duplicated(subset="frase", keep=False)]
    if not duplicadas.empty:
        problemas += len(duplicadas)
        print("AVISO: frases duplicadas:")
        for frase, grupo in duplicadas.groupby("frase"):
            linhas = ", ".join(str(i + 2) for i in grupo.index)
            intencoes = ", ".join(sorted(set(grupo["intencao"])))
            print(f"   {frase!r} -> linhas {linhas} ({intencoes})")
        print()

    # 5. Quase iguais: mesma frase normalizada, mas texto original diferente.
    base["normalizada"] = base["frase"].map(normalizar)
    quase = base[base.duplicated(subset="normalizada", keep=False)]
    quase = quase.groupby("normalizada").filter(lambda grupo: grupo["frase"].nunique() > 1)
    if not quase.empty:
        problemas += len(quase)
        print("AVISO: frases quase iguais (só mudam acento, maiúscula ou pontuação):")
        for _, grupo in quase.groupby("normalizada"):
            for indice, linha in grupo.iterrows():
                print(f"   linha {indice + 2}: {linha['frase']!r} ({linha['intencao']})")
            print()

    # Resultado final
    if problemas:
        print(f"Encontrados {problemas} problema(s). Corrija o frases.csv antes de treinar.")
        sys.exit(1)

    print("Base OK: nenhuma linha vazia, duplicada ou quase igual.")


if __name__ == "__main__":
    main()
