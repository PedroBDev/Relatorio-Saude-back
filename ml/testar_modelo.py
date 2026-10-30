"""Testa o modelo treinado digitando frases no terminal.

Como rodar (na raiz do projeto, com o venv ativado, depois do treinar.py):
    python ml/testar_modelo.py

Digite uma frase e veja a intenção prevista e a confiança. Digite "sair" para encerrar.
"""
from pathlib import Path

import joblib

ARQUIVO_MODELO = Path(__file__).parent / "modelo.pkl"

# Abaixo dessa confiança, o chatbot não arrisca: pede para o gestor reformular.
# É melhor perguntar de novo do que entregar o relatório errado.
LIMITE_CONFIANCA = 0.60


def main() -> None:
    if not ARQUIVO_MODELO.exists():
        print(f"Modelo não encontrado em {ARQUIVO_MODELO}. Rode antes: python ml/treinar.py")
        return

    # joblib.load reconstrói o Pipeline (TF-IDF + Regressão Logística) salvo pelo treinar.py,
    # já treinado: não é preciso treinar de novo.
    modelo = joblib.load(ARQUIVO_MODELO)

    print("Digite uma frase para classificar (ou 'sair' para encerrar).\n")

    while True:
        try:
            frase = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+D ou Ctrl+C também encerram, sem mostrar erro.
            print()
            break

        if frase.lower() == "sair":
            break
        if not frase:
            continue

        # predict_proba devolve uma probabilidade para cada intenção (somam 100%).
        # modelo.classes_ tem os nomes das intenções, na mesma ordem.
        probabilidades = modelo.predict_proba([frase])[0]
        posicao = probabilidades.argmax()           # posição da maior probabilidade
        intencao = modelo.classes_[posicao]
        confianca = probabilidades[posicao]

        if confianca < LIMITE_CONFIANCA:
            print("Bot: Não entendi, pode reformular?")
            print(f"     (palpite: {intencao}, confiança {confianca:.0%})\n")
        else:
            print(f"Bot: intenção = {intencao}  |  confiança = {confianca:.0%}\n")

    print("Até mais!")


if __name__ == "__main__":
    main()
