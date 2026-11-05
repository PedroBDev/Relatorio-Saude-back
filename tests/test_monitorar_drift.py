"""Testes do relatório de monitoramento do modelo (app/monitorar_drift.py).

Rodar (na raiz do projeto, com o venv ativado):
    pytest tests/test_monitorar_drift.py -v
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete

from app.models.interacao_chat import InteracaoChat
from app.monitorar_drift import alertas, resumo_por_semana


@pytest.fixture(autouse=True)
def sem_historico(db):
    """Começa sem as interações reais do banco (o rollback do fim do teste as traz de volta)."""
    db.execute(delete(InteracaoChat))


def criar_semana(db, semanas_atras: int, taxa_nao_entendi: float, mensagens: int = 40):
    data = datetime.now(timezone.utc) - timedelta(weeks=semanas_atras)
    for i in range(mensagens):
        nao_entendeu = i < mensagens * taxa_nao_entendi
        db.add(InteracaoChat(intencao_prevista="relatorio_gestantes",
                             confianca=0.4 if nao_entendeu else 0.85,
                             resultado="nao_entendi" if nao_entendeu else "relatorio",
                             criado_em=data))
    db.flush()


def test_semanas_estaveis_nao_geram_alerta(db):
    for semanas_atras in (3, 2, 1, 0):
        criar_semana(db, semanas_atras, taxa_nao_entendi=0.10)

    assert alertas(resumo_por_semana(db, 8)) == []


def test_nao_entendi_subindo_gera_alerta(db):
    criar_semana(db, 2, taxa_nao_entendi=0.10)
    criar_semana(db, 1, taxa_nao_entendi=0.10)
    criar_semana(db, 0, taxa_nao_entendi=0.40)

    avisos = alertas(resumo_por_semana(db, 8))
    assert any("Não entendi" in aviso for aviso in avisos)
    assert any("Confiança média caiu" in aviso for aviso in avisos)


def test_semana_com_poucas_mensagens_nao_conta(db):
    criar_semana(db, 1, taxa_nao_entendi=0.10)
    criar_semana(db, 0, taxa_nao_entendi=0.90, mensagens=5)

    assert alertas(resumo_por_semana(db, 8)) == []
