"""Testes da exportação dos relatórios para Excel e PDF.

Rodar (na raiz do projeto, com o venv ativado):
    pytest tests/test_exportacao.py -v
"""
from io import BytesIO

from openpyxl import load_workbook
from sqlalchemy import select

from app.models.auditoria import AuditoriaRelatorio
from tests.conftest import ANO_AGOSTO, cabecalho

AGOSTO = {"mes": 8, "ano": ANO_AGOSTO}


def exportar(client, usuario, formato, relatorio="relatorio_gestantes", params=AGOSTO):
    cabecalhos = cabecalho(usuario) if usuario else {}
    return client.get(f"/relatorios/{relatorio}/exportar/{formato}", params=params, headers=cabecalhos)


def test_excel_tem_titulo_cabecalho_e_so_o_municipio_do_gestor(client, dados):
    resposta = exportar(client, dados["gestor_a"], "excel")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert f'filename="relatorio_gestantes_{ANO_AGOSTO}-08.xlsx"' in resposta.headers["content-disposition"]

    planilha = load_workbook(BytesIO(resposta.content)).active
    assert planilha["A1"].value == "Relatório de gestantes"
    assert planilha["A2"].value.startswith(f"Município Teste A/PE · agosto de {ANO_AGOSTO}")
    cabecalho_tabela = [celula.value for celula in planilha[4]]
    assert cabecalho_tabela[:2] == ["Código", "Nome"]
    assert "Última consulta" in cabecalho_tabela
    codigos = [linha[0] for linha in planilha.iter_rows(min_row=5, values_only=True)]
    assert codigos == [dados["codigo_gestante_a"]]


def test_pdf_e_um_pdf(client, dados):
    resposta = exportar(client, dados["gestor_a"], "pdf")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    assert resposta.content.startswith(b"%PDF")


def test_mes_sem_dados_gera_arquivo_com_aviso(client, dados):
    resposta = exportar(client, dados["gestor_a"], "excel", params={"mes": 1, "ano": 2000})

    planilha = load_workbook(BytesIO(resposta.content)).active
    assert planilha["A4"].value == "Nenhum registro encontrado."


def test_exportar_sem_login(client, dados):
    assert exportar(client, None, "pdf").status_code == 401


def test_exportar_sem_municipio(client, dados):
    assert exportar(client, dados["admin_sem_municipio"], "excel").status_code == 403


def test_formato_desconhecido(client, dados):
    assert exportar(client, dados["gestor_a"], "csv").status_code == 422


def test_exportacao_fica_na_auditoria(client, db, dados):
    exportar(client, dados["gestor_a"], "pdf")

    registro = db.scalars(select(AuditoriaRelatorio)
                          .where(AuditoriaRelatorio.user_id == dados["gestor_a"].id)).one()
    assert (registro.relatorio, registro.origem, registro.resultado) == ("relatorio_gestantes", "api", "ok")
