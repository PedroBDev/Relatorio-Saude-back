"""Consultas permitidas para o chatbot.

O chatbot NUNCA escreve SQL. O modelo de Machine Learning só escolhe uma das
intenções do dicionário CONSULTAS (ex.: "relatorio_gestantes") e extrai os
parâmetros do pedido (ex.: mes=8, ano=2026). Este módulo confere tudo e executa
a consulta já escrita aqui.

Por que isso é seguro:
  - Só existem as consultas deste arquivo: não há como o usuário "inventar" outra.
  - Os valores entram por parâmetros (:mes, :ano...), nunca colados no texto do
    SQL, então não há SQL Injection.
  - Todas são SELECT (somente leitura); isso é conferido quando o módulo carrega.
  - Cada consulta devolve só as colunas que o relatório mostra (LGPD: princípio
    da necessidade). Nada de SELECT *.

Como rodar o exemplo do final do arquivo:
    python -m app.services.consultas
"""
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session


class ConsultaInvalidaError(ValueError):
    """Erro com mensagem clara para quando a intenção ou os parâmetros estão errados.

    Herda de ValueError para seguir o padrão do projeto: as rotas já
    transformam ValueError em erro HTTP 400 (veja app/api/routes/auth.py).
    """


# ---------------------------------------------------------------------------
# Como os relatórios funcionam
#
# Cada grupo tem uma função no banco (criada na migration 720dbc080c91):
#     fn_gestantes(inicio, fim), fn_hipertensos(inicio, fim), ...
# Ela devolve a situação dos pacientes NAQUELE período: quem estava no grupo,
# idade, última medição, consultas e risco calculados até o fim do período.
# Por isso o relatório de julho mostra os dados como estavam em julho, mesmo
# que o paciente tenha tido consultas depois.
#
# :inicio e :fim não vêm do chatbot: são calculados a partir de mes e ano
# (ex.: julho/2026 -> inicio=2026-07-01, fim=2026-08-01; o fim não entra).
#
# As telas listam só quem teve consulta no mês ("298 de 387 cadastradas"),
# por isso os relatórios filtram por atendido_no_periodo.
#
# :municipio_id garante que o gestor só vê os pacientes do município dele.
# ---------------------------------------------------------------------------

CONSULTAS = {
    "relatorio_gestantes": {
        "descricao": "Gestantes que tiveram consulta de pré-natal no mês e ano informados.",
        "parametros": ["mes", "ano", "municipio_id"],
        "sql": """
            SELECT codigo, nome, idade, unidade_saude,
                   semanas_gestacao, total_consultas, ultima_consulta, risco
            FROM fn_gestantes(:inicio, :fim)
            WHERE municipio_id = :municipio_id AND atendido_no_periodo
            ORDER BY codigo
        """,
    },
    "relatorio_hipertensos": {
        "descricao": "Hipertensos que tiveram consulta no mês e ano informados, com a última pressão medida.",
        "parametros": ["mes", "ano", "municipio_id"],
        "sql": """
            SELECT codigo, nome, idade, unidade_saude,
                   pressao_sistolica, pressao_diastolica,
                   total_consultas, ultima_consulta, risco
            FROM fn_hipertensos(:inicio, :fim)
            WHERE municipio_id = :municipio_id AND atendido_no_periodo
            ORDER BY codigo
        """,
    },
    "relatorio_diabeticos": {
        "descricao": "Diabéticos que tiveram consulta no mês e ano informados, com a última hemoglobina glicada.",
        "parametros": ["mes", "ano", "municipio_id"],
        "sql": """
            SELECT codigo, nome, idade, unidade_saude,
                   hemoglobina_glicada, total_consultas, ultima_consulta, risco
            FROM fn_diabeticos(:inicio, :fim)
            WHERE municipio_id = :municipio_id AND atendido_no_periodo
            ORDER BY codigo
        """,
    },
    "relatorio_criancas": {
        "descricao": "Crianças (até 11 anos) que tiveram consulta no mês e ano informados, com a situação da vacinação.",
        "parametros": ["mes", "ano", "municipio_id"],
        "sql": """
            SELECT codigo, nome, idade, unidade_saude,
                   vacinacao_em_dia, total_consultas, ultima_consulta, risco
            FROM fn_criancas(:inicio, :fim)
            WHERE municipio_id = :municipio_id AND atendido_no_periodo
            ORDER BY codigo
        """,
    },
    "relatorio_idosos": {
        "descricao": "Idosos (60 anos ou mais) que tiveram consulta no mês e ano informados, com o número de comorbidades.",
        "parametros": ["mes", "ano", "municipio_id"],
        "sql": """
            SELECT codigo, nome, idade, unidade_saude,
                   comorbidades, total_consultas, ultima_consulta, risco
            FROM fn_idosos(:inicio, :fim)
            WHERE municipio_id = :municipio_id AND atendido_no_periodo
            ORDER BY codigo
        """,
    },
    # Resumo sem dados pessoais: só números. Alimenta o cabeçalho das telas
    # ("298 de 387 cadastradas, cobertura de 77%").
    "resumo_cobertura": {
        "descricao": "Por grupo: pacientes cadastrados, quantos tiveram consulta no mês e a cobertura em %.",
        "parametros": ["mes", "ano", "municipio_id"],
        "sql": """
            WITH grupos AS (
                SELECT 'gestante' AS grupo, atendido_no_periodo FROM fn_gestantes(:inicio, :fim) WHERE municipio_id = :municipio_id
                UNION ALL
                SELECT 'hipertenso', atendido_no_periodo FROM fn_hipertensos(:inicio, :fim) WHERE municipio_id = :municipio_id
                UNION ALL
                SELECT 'diabetico', atendido_no_periodo FROM fn_diabeticos(:inicio, :fim) WHERE municipio_id = :municipio_id
                UNION ALL
                SELECT 'crianca', atendido_no_periodo FROM fn_criancas(:inicio, :fim) WHERE municipio_id = :municipio_id
                UNION ALL
                SELECT 'idoso', atendido_no_periodo FROM fn_idosos(:inicio, :fim) WHERE municipio_id = :municipio_id
            )
            SELECT grupo,
                   count(*) AS cadastrados,
                   count(*) FILTER (WHERE atendido_no_periodo) AS atendidos,
                   round(100.0 * count(*) FILTER (WHERE atendido_no_periodo) / count(*), 1) AS cobertura_percentual
            FROM grupos
            GROUP BY grupo
            ORDER BY grupo
        """,
    },
}


# Conferência feita uma vez, quando o módulo é importado: se alguém adicionar
# uma consulta que não seja SELECT (ou WITH ... SELECT), o sistema nem sobe.
# É uma rede de segurança para erros de programação. A proteção mais forte é
# o banco: em produção, o usuário do chatbot deve ter só permissão de SELECT.
for _nome, _consulta in CONSULTAS.items():
    _inicio_sql = _consulta["sql"].lstrip().upper()
    if not _inicio_sql.startswith(("SELECT", "WITH")):
        raise RuntimeError(f"A consulta '{_nome}' não é somente leitura.")


def _validar_inteiro(nome: str, valor) -> int:
    """Converte o valor para int. O modelo de ML pode mandar "8" (texto) em vez de 8."""
    # bool é um tipo de int em Python (True == 1), então é recusado de propósito.
    if isinstance(valor, bool):
        raise ConsultaInvalidaError(f"O parâmetro '{nome}' deve ser um número inteiro.")
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise ConsultaInvalidaError(f"O parâmetro '{nome}' deve ser um número inteiro, recebido: {valor!r}.")


def _validar_parametros(parametros: dict, exigidos: list[str]) -> dict:
    """Confere se todos os parâmetros exigidos vieram e se os valores fazem sentido.

    Devolve um dicionário só com os parâmetros que a consulta usa. Qualquer
    parâmetro extra que o chatbot mandar é ignorado.
    """
    faltando = [nome for nome in exigidos if nome not in parametros]
    if faltando:
        raise ConsultaInvalidaError(f"Parâmetros obrigatórios não informados: {', '.join(faltando)}.")

    validados = {}

    if "mes" in exigidos:
        mes = _validar_inteiro("mes", parametros["mes"])
        if not 1 <= mes <= 12:
            raise ConsultaInvalidaError(f"Mês inválido: {mes}. Use um número de 1 a 12.")
        validados["mes"] = mes

    if "ano" in exigidos:
        ano = _validar_inteiro("ano", parametros["ano"])
        if not 1000 <= ano <= 9999:
            raise ConsultaInvalidaError(f"Ano inválido: {ano}. Use um ano com 4 dígitos (ex.: 2026).")
        validados["ano"] = ano

    if "municipio_id" in exigidos:
        municipio_id = _validar_inteiro("municipio_id", parametros["municipio_id"])
        if municipio_id <= 0:
            raise ConsultaInvalidaError(f"Município inválido: {municipio_id}.")
        validados["municipio_id"] = municipio_id

    return validados


def _periodo_do_mes(mes: int, ano: int) -> tuple[date, date]:
    """Primeiro dia do mês e primeiro dia do mês seguinte (o fim não entra no período)."""
    inicio = date(ano, mes, 1)
    fim = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
    return inicio, fim


def executar_consulta(intencao: str, parametros: dict, conexao: Session) -> list[dict]:
    """Executa uma das consultas permitidas e devolve as linhas como lista de dicionários.

    intencao:   nome da consulta escolhida pelo chatbot (ex.: "relatorio_gestantes").
    parametros: valores extraídos do pedido (ex.: {"mes": 8, "ano": 2026, "municipio_id": 1}).
    conexao:    sessão do SQLAlchemy (nas rotas, a que vem de Depends(get_db)).

    Lança ConsultaInvalidaError se a intenção não existir ou se os parâmetros
    estiverem faltando ou inválidos.
    """
    # 1. A intenção precisa existir no dicionário. Nada fora dele é executado.
    if intencao not in CONSULTAS:
        disponiveis = ", ".join(sorted(CONSULTAS))
        raise ConsultaInvalidaError(f"Relatório '{intencao}' não existe. Disponíveis: {disponiveis}.")

    consulta = CONSULTAS[intencao]

    # 2 e 3. Parâmetros obrigatórios presentes e com valores válidos.
    valores = _validar_parametros(parametros, consulta["parametros"])

    # mes/ano viram um intervalo de datas (:inicio e :fim) usado no SQL.
    if "mes" in valores and "ano" in valores:
        valores["inicio"], valores["fim"] = _periodo_do_mes(valores.pop("mes"), valores.pop("ano"))

    # 4. Executa. O text() marca o SQL como fixo, e o dicionário `valores`
    # preenche os :placeholders de forma segura (o driver trata cada valor
    # como dado, nunca como parte do comando SQL).
    resultado = conexao.execute(text(consulta["sql"]), valores)

    # .mappings() faz cada linha se comportar como dicionário {coluna: valor}.
    return [dict(linha) for linha in resultado.mappings()]


# ---------------------------------------------------------------------------
# Exemplo de uso
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        # Simula o que o modelo de ML devolveria para o pedido
        # "quero o relatório das gestantes de julho de 2026".
        # O municipio_id não vem do chatbot: virá do usuário logado.
        linhas = executar_consulta(
            "relatorio_gestantes",
            {"mes": 7, "ano": 2026, "municipio_id": 1},
            db,
        )
        print(f"relatorio_gestantes: {len(linhas)} gestantes atendidas em 07/2026")
        for linha in linhas[:3]:
            print("  ", linha)

        print("\nresumo_cobertura (07/2026):")
        for linha in executar_consulta("resumo_cobertura", {"mes": 7, "ano": 2026, "municipio_id": 1}, db):
            print("  ", linha)

        # Exemplos de erro: cada um gera uma mensagem clara.
        print("\nErros:")
        for intencao, params in [
            ("relatorio_vacinas", {"mes": 9, "ano": 2026, "municipio_id": 1}),
            ("relatorio_idosos", {"mes": 9, "municipio_id": 1}),
            ("relatorio_idosos", {"mes": 13, "ano": 2026, "municipio_id": 1}),
            ("relatorio_idosos", {"mes": 9, "ano": 26, "municipio_id": 1}),
            ("relatorio_idosos", {"mes": "1; DROP TABLE pacientes", "ano": 2026, "municipio_id": 1}),
        ]:
            try:
                executar_consulta(intencao, params, db)
            except ConsultaInvalidaError as erro:
                print(f"   {intencao} {params} -> {erro}")
    finally:
        db.close()
