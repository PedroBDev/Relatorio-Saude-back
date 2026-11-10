"""Relatório de monitoramento do modelo do chatbot (data drift).

Lê a tabela interacoes_chat (uma linha por mensagem do POST /chat, sem o texto)
e mostra, semana a semana:
  - quantas mensagens chegaram;
  - a taxa de "não entendi" (confiança abaixo de 60%);
  - a confiança média do modelo;
  - a taxa de fora_do_escopo.

Se o jeito de escrever dos gestores mudar (palavras novas, pedidos novos), o
modelo fica menos seguro: o "não entendi" sobe e a confiança cai. Quando isso
acontece, é hora de juntar frases novas no ml/frases.csv e retreinar.

Como rodar (na raiz do projeto, com o venv ativado):
    python -m app.monitorar_drift              # últimas 8 semanas
    python -m app.monitorar_drift --semanas 12
"""
import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select

from app.core.database import SessionLocal
from app.models.interacao_chat import InteracaoChat

# Alertas: a última semana comparada com a média das semanas anteriores.
AUMENTO_MAXIMO_NAO_ENTENDI = 0.10  # +10 pontos percentuais
QUEDA_MAXIMA_CONFIANCA = 0.10      # -0,10 na confiança média
# Com poucas mensagens a taxa oscila demais para tirar conclusão.
MINIMO_MENSAGENS_POR_SEMANA = 20


def resumo_por_semana(db, semanas: int) -> list[dict]:
    inicio = datetime.now(timezone.utc) - timedelta(weeks=semanas)
    semana = func.date_trunc("week", InteracaoChat.criado_em).label("semana")
    # Só as mensagens que passaram pelo modelo (as que completam uma pergunta não passam).
    pelo_modelo = InteracaoChat.confianca.is_not(None)

    consulta = (
        select(
            semana,
            func.count().filter(pelo_modelo).label("mensagens"),
            func.avg(case((InteracaoChat.resultado == "nao_entendi", 1.0), else_=0.0))
                .filter(pelo_modelo).label("nao_entendi"),
            func.avg(InteracaoChat.confianca).label("confianca_media"),
            func.avg(case((InteracaoChat.intencao_prevista == "fora_do_escopo", 1.0), else_=0.0))
                .filter(pelo_modelo).label("fora_do_escopo"),
        )
        .where(InteracaoChat.criado_em >= inicio)
        .group_by(semana)
        .order_by(semana)
    )
    return [linha._asdict() for linha in db.execute(consulta)]


def alertas(linhas: list[dict]) -> list[str]:
    """Compara a última semana com a média das anteriores."""
    validas = [linha for linha in linhas if linha["mensagens"] >= MINIMO_MENSAGENS_POR_SEMANA]
    if len(validas) < 2:
        return []

    *anteriores, ultima = validas
    media_nao_entendi = sum(linha["nao_entendi"] for linha in anteriores) / len(anteriores)
    media_confianca = sum(linha["confianca_media"] for linha in anteriores) / len(anteriores)

    avisos = []
    if ultima["nao_entendi"] - media_nao_entendi > AUMENTO_MAXIMO_NAO_ENTENDI:
        avisos.append(f"\"Não entendi\" subiu de {media_nao_entendi:.0%} para {ultima['nao_entendi']:.0%}.")
    if media_confianca - ultima["confianca_media"] > QUEDA_MAXIMA_CONFIANCA:
        avisos.append(f"Confiança média caiu de {media_confianca:.2f} para {ultima['confianca_media']:.2f}.")
    return avisos


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitoramento do modelo do chatbot")
    parser.add_argument("--semanas", type=int, default=8)
    semanas = parser.parse_args().semanas

    with SessionLocal() as db:
        linhas = resumo_por_semana(db, semanas)

    if not linhas:
        print(f"Nenhuma mensagem no chat nas últimas {semanas} semanas.")
        return

    print(f"{'Semana':<12}{'Mensagens':>10}{'Não entendi':>13}{'Confiança':>11}{'Fora do escopo':>16}")
    for linha in linhas:
        confianca = f"{linha['confianca_media']:.2f}" if linha["confianca_media"] is not None else "-"
        print(f"{linha['semana']:%d/%m/%Y}  {linha['mensagens']:>10}"
              f"{linha['nao_entendi'] or 0:>13.0%}{confianca:>11}{linha['fora_do_escopo'] or 0:>16.0%}")

    avisos = alertas(linhas)
    print()
    if avisos:
        print("ATENÇÃO: possível data drift.")
        for aviso in avisos:
            print(f"  - {aviso}")
        print("Junte frases novas no ml/frases.csv e retreine (python ml/treinar.py).")
    else:
        print(f"Sem sinal de drift (o alerta precisa de 2 semanas com {MINIMO_MENSAGENS_POR_SEMANA}+ mensagens).")


if __name__ == "__main__":
    main()
