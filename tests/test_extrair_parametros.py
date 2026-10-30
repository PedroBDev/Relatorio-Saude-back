"""Testes da extração de mês e ano. A data de "hoje" é fixada em 25/10/2026."""
from datetime import date

import pytest

from app.services.extrair_parametros import extrair_periodo, montar_pergunta_faltante

HOJE = date(2026, 10, 25)


@pytest.mark.parametrize("frase, esperado", [
    ("gestantes de agosto", {"mes": 8, "ano": 2026}),
    ("gestantes de dezembro", {"mes": 12, "ano": 2025}),       # dezembro de 2026 ainda não chegou
    ("hipertensos de março de 2025", {"mes": 3, "ano": 2025}),
    ("hipertensos de MARCO de 2025", {"mes": 3, "ano": 2025}),  # sem acento e em maiúsculas
    ("idosos 08/2026", {"mes": 8, "ano": 2026}),
    ("idosos 8-2026", {"mes": 8, "ano": 2026}),
    ("crianças do mês passado", {"mes": 9, "ano": 2026}),
    ("diabéticos deste mês", {"mes": 10, "ano": 2026}),
    ("relatório de junho do ano passado", {"mes": 6, "ano": 2025}),
    ("relatório das gestantes", {"mes": None, "ano": None}),
    ("gestantes de 2026", {"mes": None, "ano": 2026}),
    # meses abreviados
    ("gestantes de ago", {"mes": 8, "ano": 2026}),
    ("pd me mandar os hipertensos de set", {"mes": 9, "ano": 2026}),
    ("idosos de dez", {"mes": 12, "ano": 2025}),
    ("diabeticos de mar de 2025", {"mes": 3, "ano": 2025}),
    ("crianças ago/2026", {"mes": 8, "ano": 2026}),
    ("hipertensos set/25", {"mes": 9, "ano": 2025}),
    ("gestantes de abr.", {"mes": 4, "ano": 2026}),
    # abreviação não pode ser achada dentro de outra palavra
    ("quero marcar uma reunião", {"mes": None, "ano": None}),
    ("relatório de setembro", {"mes": 9, "ano": 2026}),
    ("outros relatórios", {"mes": None, "ano": None}),
])
def test_extrair_periodo(frase, esperado):
    assert extrair_periodo(frase, hoje=HOJE) == esperado


def test_mes_passado_em_janeiro_volta_para_dezembro_do_ano_anterior():
    assert extrair_periodo("mês passado", hoje=date(2026, 1, 10)) == {"mes": 12, "ano": 2025}


def test_pergunta_quando_falta_o_mes():
    assert montar_pergunta_faltante({"mes": None, "ano": 2026}) is not None
    assert montar_pergunta_faltante({"mes": 8, "ano": 2026}) is None
