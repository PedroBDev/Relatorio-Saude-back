"Exportação de dados para Excel"

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment


def gerar_excel(dados: list[dict]) -> BytesIO:
    arquivo = BytesIO()

    workbook = Workbook()
    planilha = workbook.active
    planilha.title = "Relatório de Saúde"

    if not dados:
        planilha.append(["Nenhum registro encontrado"])
    else:
        colunas = list(dados[0].keys())

        # Cabeçalho
        planilha.append(colunas)

        for celula in planilha[1]:
            celula.font = Font(bold=True, color="FFFFFF")
            celula.fill = PatternFill(
                fill_type="solid",
                fgColor="217346"
            )
            celula.alignment = Alignment(horizontal="center")

        # Dados
        for item in dados:
            planilha.append([
                item.get(coluna) for coluna in colunas
            ])

        # Ajuste de largura
        for coluna in planilha.columns:
            largura = max(
                len(str(celula.value or ""))
                for celula in coluna
            )

            planilha.column_dimensions[
                coluna[0].column_letter
            ].width = min(largura + 3, 40)

        planilha.freeze_panes = "A2"
        planilha.auto_filter.ref = planilha.dimensions

    workbook.save(arquivo)
    arquivo.seek(0)

    return arquivo


"Exportação de dados para pdf:"

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)


def gerar_pdf(dados: list[dict]) -> BytesIO:
    arquivo = BytesIO()

    documento = SimpleDocTemplate(
        arquivo,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    estilos = getSampleStyleSheet()

    elementos = [
        Paragraph(
            "Relatório de Indicadores de Saúde",
            estilos["Title"]
        ),
        Spacer(1, 0.5 * cm)
    ]

    if not dados:
        elementos.append(
            Paragraph("Nenhum registro encontrado.", estilos["Normal"])
        )
    else:
        colunas = list(dados[0].keys())

        tabela_dados = [colunas]

        for item in dados:
            tabela_dados.append([
                str(item.get(coluna, ""))
                for coluna in colunas
            ])

        tabela = Table(
            tabela_dados,
            repeatRows=1
        )

        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#217346")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
        ]))

        elementos.append(tabela)

    documento.build(elementos)

    arquivo.seek(0)

    return arquivo