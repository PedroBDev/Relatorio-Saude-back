"""Exportação dos relatórios para Excel (.xlsx) e PDF.

Recebe as mesmas linhas que o GET /relatorios/{relatorio} devolve e monta o
arquivo na memória (BytesIO), sem gravar nada no disco do servidor.
O título e o subtítulo dizem qual relatório, de qual mês e de qual município.
"""
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

VERDE = "217346"
SEM_REGISTROS = "Nenhum registro encontrado."

# Nome das colunas como aparecem no arquivo. Coluna fora da lista: "nome_da_coluna" -> "Nome da coluna".
NOMES_COLUNAS = {
    "codigo": "Código",
    "nome": "Nome",
    "idade": "Idade",
    "unidade_saude": "Unidade de saúde",
    "semanas_gestacao": "Semanas de gestação",
    "pressao_sistolica": "Pressão sistólica",
    "pressao_diastolica": "Pressão diastólica",
    "hemoglobina_glicada": "Hemoglobina glicada",
    "vacinacao_em_dia": "Vacinação em dia",
    "comorbidades": "Comorbidades",
    "total_consultas": "Total de consultas",
    "ultima_consulta": "Última consulta",
    "risco": "Risco",
    "grupo": "Grupo",
    "cadastrados": "Cadastrados",
    "atendidos": "Atendidos",
    "cobertura_percentual": "Cobertura (%)",
}


def _nome_coluna(coluna: str) -> str:
    return NOMES_COLUNAS.get(coluna, coluna.replace("_", " ").capitalize())


def _formatar(valor) -> str:
    """Valor como texto para o PDF: data no formato brasileiro e Sim/Não."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def gerar_excel(dados: list[dict], titulo: str, subtitulo: str) -> BytesIO:
    arquivo = BytesIO()

    workbook = Workbook()
    planilha = workbook.active
    planilha.title = "Relatório"

    # Linhas 1 e 2: título e subtítulo. Linha 3 em branco. Tabela a partir da linha 4.
    planilha.append([titulo])
    planilha.append([subtitulo])
    planilha.append([])
    planilha["A1"].font = Font(bold=True, size=14)
    planilha["A2"].font = Font(italic=True, color="555555")

    if not dados:
        planilha.append([SEM_REGISTROS])
    else:
        colunas = list(dados[0].keys())

        # Cabeçalho
        planilha.append([_nome_coluna(coluna) for coluna in colunas])
        for celula in planilha[4]:
            celula.font = Font(bold=True, color="FFFFFF")
            celula.fill = PatternFill(fill_type="solid", fgColor=VERDE)
            celula.alignment = Alignment(horizontal="center")

        # Dados. As datas continuam datas (dá para ordenar e filtrar no Excel).
        for item in dados:
            linha = []
            for coluna in colunas:
                valor = item.get(coluna)
                linha.append(("Sim" if valor else "Não") if isinstance(valor, bool) else valor)
            planilha.append(linha)
            for celula in planilha[planilha.max_row]:
                if isinstance(celula.value, date):
                    celula.number_format = "DD/MM/YYYY"

        # Ajuste de largura, só pela tabela (o título é largo e ocuparia a coluna A).
        for coluna in planilha.iter_cols(min_row=4):
            largura = max(len(_formatar(celula.value)) for celula in coluna)
            planilha.column_dimensions[coluna[0].column_letter].width = min(largura + 3, 40)

        planilha.freeze_panes = "A5"
        planilha.auto_filter.ref = f"A4:{planilha.cell(row=planilha.max_row, column=len(colunas)).coordinate}"

    workbook.save(arquivo)
    arquivo.seek(0)

    return arquivo


def gerar_pdf(dados: list[dict], titulo: str, subtitulo: str) -> BytesIO:
    arquivo = BytesIO()

    documento = SimpleDocTemplate(
        arquivo,
        pagesize=landscape(A4),
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=titulo,
    )

    estilos = getSampleStyleSheet()
    estilo_subtitulo = ParagraphStyle("Subtitulo", parent=estilos["Normal"], alignment=TA_CENTER)

    elementos = [
        Paragraph(titulo, estilos["Title"]),
        Paragraph(subtitulo, estilo_subtitulo),
        Spacer(1, 0.5 * cm),
    ]

    if not dados:
        elementos.append(Paragraph(SEM_REGISTROS, estilos["Normal"]))
    else:
        colunas = list(dados[0].keys())

        tabela_dados = [[_nome_coluna(coluna) for coluna in colunas]]
        for item in dados:
            tabela_dados.append([_formatar(item.get(coluna)) for coluna in colunas])

        # repeatRows=1: o cabeçalho se repete em cada página.
        tabela = Table(tabela_dados, repeatRows=1)

        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{VERDE}")),
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
