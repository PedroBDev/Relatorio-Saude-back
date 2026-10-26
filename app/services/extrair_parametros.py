"""Extrai o período (mês e ano) da frase do gestor.

O modelo de Machine Learning só descobre a INTENÇÃO ("relatorio_gestantes").
O mês e o ano são tirados da frase por regras simples, aqui.

Exemplos (considerando hoje = 25/10/2026):
    "gestantes de agosto"          -> {"mes": 8,  "ano": 2026}
    "gestantes de dezembro"        -> {"mes": 12, "ano": 2025}  (dezembro de 2026 ainda não chegou)
    "hipertensos de março de 2025" -> {"mes": 3,  "ano": 2025}
    "idosos 08/2026"               -> {"mes": 8,  "ano": 2026}
    "crianças do mês passado"      -> {"mes": 9,  "ano": 2026}
    "diabéticos deste mês"         -> {"mes": 10, "ano": 2026}
    "relatório das gestantes"      -> {"mes": None, "ano": None}  (o chatbot precisa perguntar)
"""
import re
import unicodedata
from datetime import date

# Nomes sem acento, porque a frase também é comparada sem acento ("março" -> "marco").
MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

NOMES_MESES = {numero: nome for nome, numero in MESES.items()}
NOMES_MESES[3] = "março"

# \b = limite de palavra: "maio" casa em "de maio", mas não dentro de outra palavra.
PADRAO_MES = re.compile(r"\b(" + "|".join(MESES) + r")\b")
PADRAO_ANO = re.compile(r"\b(\d{4})\b")
# 08/2026, 8/2026, 08-2026
PADRAO_MES_ANO_NUMERICO = re.compile(r"\b(0?[1-9]|1[0-2])\s*[/-]\s*(\d{4})\b")

EXPRESSOES_MES_PASSADO = ("mes passado", "ultimo mes", "mes anterior")
EXPRESSOES_MES_ATUAL = ("este mes", "esse mes", "neste mes", "nesse mes", "deste mes", "desse mes", "mes atual")


def _normalizar(texto: str) -> str:
    """Minúsculas e sem acentos: "Março" -> "marco", "mês" -> "mes"."""
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(letra for letra in texto if not unicodedata.combining(letra))


def _ano_mais_recente(mes: int, hoje: date) -> int:
    """Se a frase não diz o ano, usa a última vez que aquele mês aconteceu."""
    return hoje.year if mes <= hoje.month else hoje.year - 1


def extrair_periodo(texto: str, hoje: date | None = None) -> dict:
    """Devolve {"mes": int | None, "ano": int | None} encontrados na frase.

    `hoje` existe para os testes poderem fixar a data; no uso normal fica vazio.
    """
    hoje = hoje or date.today()
    frase = _normalizar(texto)

    # 1. Expressões relativas ("mês passado", "este mês")
    if any(expressao in frase for expressao in EXPRESSOES_MES_PASSADO):
        if hoje.month == 1:
            return {"mes": 12, "ano": hoje.year - 1}
        return {"mes": hoje.month - 1, "ano": hoje.year}

    if any(expressao in frase for expressao in EXPRESSOES_MES_ATUAL):
        return {"mes": hoje.month, "ano": hoje.year}

    # 2. Formato numérico (08/2026). Vem antes do ano solto, senão o "2026"
    # seria lido sozinho e o "08" ficaria perdido.
    numerico = PADRAO_MES_ANO_NUMERICO.search(frase)
    if numerico:
        return {"mes": int(numerico.group(1)), "ano": int(numerico.group(2))}

    # 3. Nome do mês e ano com 4 dígitos, cada um onde estiver na frase
    encontrado_mes = PADRAO_MES.search(frase)
    mes = MESES[encontrado_mes.group(1)] if encontrado_mes else None

    encontrado_ano = PADRAO_ANO.search(frase)
    if encontrado_ano:
        ano = int(encontrado_ano.group(1))
    elif "ano passado" in frase:
        ano = hoje.year - 1
    elif mes:
        ano = _ano_mais_recente(mes, hoje)
    else:
        ano = None

    return {"mes": mes, "ano": ano}


def montar_pergunta_faltante(parametros: dict) -> str | None:
    """Pergunta o que falta para gerar o relatório. Devolve None se não falta nada."""
    if not parametros.get("mes"):
        return "De qual mês você quer o relatório? Ex.: agosto, ou agosto de 2026."
    return None


def descrever_periodo(mes: int, ano: int) -> str:
    """Texto amigável do período: (8, 2026) -> "agosto de 2026"."""
    return f"{NOMES_MESES[mes]} de {ano}"
