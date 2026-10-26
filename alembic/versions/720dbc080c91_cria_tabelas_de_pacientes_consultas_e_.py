"""cria tabelas de pacientes, consultas e funcoes dos grupos

Revision ID: 720dbc080c91
Revises: aef97b179cbd
Create Date: 2026-10-21 09:50:41.198340

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '720dbc080c91'
down_revision: Union[str, Sequence[str], None] = 'aef97b179cbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Funções dos grupos: uma por grupo, no formato das telas do front.
#
# Cada função recebe um período [p_inicio, p_fim) — o p_fim NÃO entra — e
# devolve a situação dos pacientes NAQUELE período:
#   - quem estava no grupo (ex.: gestantes grávidas em julho, mesmo que já
#     tenham tido o bebê depois);
#   - idade no último dia do período;
#   - última medição, total de consultas e última consulta até o fim do período;
#   - atendido_no_periodo: se teve consulta do grupo dentro do período;
#   - risco calculado com esses valores.
#
# Exemplo: SELECT * FROM fn_gestantes('2026-07-01', '2026-08-01')  -> julho/2026
#
# As views vw_* chamam as funções com o dia de hoje, para consultar a
# situação atual sem precisar passar datas.
#
# As regras de risco seguem:
#   - Hipertensos: Diretriz Brasileira de Hipertensão Arterial 2025 (SBC)
#   - Diabéticos: meta de HbA1c < 7% da SBD; o corte de 9% para "alto" é uma simplificação
#   - Gestantes, crianças e idosos: regras simplificadas definidas para o projeto
#
# Os nomes dos parâmetros começam com p_ e todas as colunas usam o apelido da
# tabela (p.nome, c.grupo...) para o Postgres não confundir parâmetro com coluna.
# ---------------------------------------------------------------------------

# Idade completa em uma data (ex.: nasceu em 10/08/1966 -> em 31/07/2026 tem 59).
FN_IDADE_EM = """
CREATE FUNCTION idade_em(p_nascimento date, p_data date) RETURNS integer
LANGUAGE sql IMMUTABLE AS $$
    SELECT EXTRACT(YEAR FROM age(p_data, p_nascimento))::integer
$$
"""

# Gestantes. Uma linha por gestação que esteve ativa no período. Só contam as
# consultas daquela gestação (entre a inclusão no grupo e a saída/parto).
FN_GESTANTES = """
CREATE FUNCTION fn_gestantes(p_inicio date, p_fim date)
RETURNS TABLE (
    codigo text, paciente_id integer, nome varchar, idade integer,
    unidade_saude_id integer, unidade_saude varchar, municipio_id integer,
    semanas_gestacao smallint,
    total_consultas bigint, ultima_consulta date, atendido_no_periodo boolean, risco text
)
LANGUAGE sql STABLE AS $$
    SELECT
        'G-' || lpad(p.id::text, 4, '0'),
        p.id, p.nome, idade_em(p.data_nascimento, p_fim - 1),
        u.id, u.nome, u.municipio_id,
        ultima.semanas_gestacao,
        resumo.total_consultas,
        resumo.ultima_consulta,
        coalesce(resumo.ultima_consulta >= p_inicio, false),
        CASE
            WHEN idade_em(p.data_nascimento, p_fim - 1) < 15
              OR idade_em(p.data_nascimento, p_fim - 1) >= 40 THEN 'alto'
            WHEN primeira.semanas_gestacao > 12 THEN 'moderado'
            ELSE 'baixo'
        END
    FROM paciente_grupos pg
    JOIN pacientes p ON p.id = pg.paciente_id
    JOIN unidades_saude u ON u.id = p.unidade_saude_id
    CROSS JOIN LATERAL (
        SELECT count(*) AS total_consultas, max(c.data_consulta) AS ultima_consulta
        FROM consultas c
        WHERE c.paciente_id = pg.paciente_id AND c.grupo = 'gestante'
          AND c.data_consulta >= pg.data_inclusao
          AND (pg.data_saida IS NULL OR c.data_consulta <= pg.data_saida)
          AND c.data_consulta < p_fim
    ) resumo
    LEFT JOIN LATERAL (
        SELECT c.semanas_gestacao
        FROM consultas c
        WHERE c.paciente_id = pg.paciente_id AND c.grupo = 'gestante'
          AND c.data_consulta >= pg.data_inclusao
          AND (pg.data_saida IS NULL OR c.data_consulta <= pg.data_saida)
          AND c.data_consulta < p_fim
          AND c.semanas_gestacao IS NOT NULL
        ORDER BY c.data_consulta DESC
        LIMIT 1
    ) ultima ON true
    LEFT JOIN LATERAL (
        SELECT c.semanas_gestacao
        FROM consultas c
        WHERE c.paciente_id = pg.paciente_id AND c.grupo = 'gestante'
          AND c.data_consulta >= pg.data_inclusao
          AND (pg.data_saida IS NULL OR c.data_consulta <= pg.data_saida)
          AND c.semanas_gestacao IS NOT NULL
        ORDER BY c.data_consulta ASC
        LIMIT 1
    ) primeira ON true
    WHERE pg.grupo = 'gestante'
      AND pg.data_inclusao < p_fim
      AND (pg.data_saida IS NULL OR pg.data_saida >= p_inicio)
$$
"""

# Hipertensos: risco pela última pressão medida até o fim do período.
FN_HIPERTENSOS = """
CREATE FUNCTION fn_hipertensos(p_inicio date, p_fim date)
RETURNS TABLE (
    codigo text, paciente_id integer, nome varchar, idade integer,
    unidade_saude_id integer, unidade_saude varchar, municipio_id integer,
    pressao_sistolica smallint, pressao_diastolica smallint,
    total_consultas bigint, ultima_consulta date, atendido_no_periodo boolean, risco text
)
LANGUAGE sql STABLE AS $$
    SELECT
        'H-' || lpad(p.id::text, 4, '0'),
        p.id, p.nome, idade_em(p.data_nascimento, p_fim - 1),
        u.id, u.nome, u.municipio_id,
        ultima.pressao_sistolica, ultima.pressao_diastolica,
        resumo.total_consultas,
        resumo.ultima_consulta,
        coalesce(resumo.ultima_consulta >= p_inicio, false),
        CASE
            WHEN ultima.pressao_sistolica IS NULL THEN NULL
            WHEN ultima.pressao_sistolica >= 160 OR ultima.pressao_diastolica >= 100 THEN 'alto'
            WHEN ultima.pressao_sistolica >= 140 OR ultima.pressao_diastolica >= 90 THEN 'moderado'
            ELSE 'baixo'
        END
    FROM paciente_grupos pg
    JOIN pacientes p ON p.id = pg.paciente_id
    JOIN unidades_saude u ON u.id = p.unidade_saude_id
    CROSS JOIN LATERAL (
        SELECT count(*) AS total_consultas, max(c.data_consulta) AS ultima_consulta
        FROM consultas c
        WHERE c.paciente_id = pg.paciente_id AND c.grupo = 'hipertenso'
          AND c.data_consulta < p_fim
    ) resumo
    LEFT JOIN LATERAL (
        SELECT c.pressao_sistolica, c.pressao_diastolica
        FROM consultas c
        WHERE c.paciente_id = pg.paciente_id AND c.grupo = 'hipertenso'
          AND c.data_consulta < p_fim
          AND c.pressao_sistolica IS NOT NULL AND c.pressao_diastolica IS NOT NULL
        ORDER BY c.data_consulta DESC
        LIMIT 1
    ) ultima ON true
    WHERE pg.grupo = 'hipertenso'
      AND pg.data_inclusao < p_fim
      AND (pg.data_saida IS NULL OR pg.data_saida >= p_inicio)
$$
"""

# Diabéticos: risco pela última hemoglobina glicada até o fim do período.
FN_DIABETICOS = """
CREATE FUNCTION fn_diabeticos(p_inicio date, p_fim date)
RETURNS TABLE (
    codigo text, paciente_id integer, nome varchar, idade integer,
    unidade_saude_id integer, unidade_saude varchar, municipio_id integer,
    hemoglobina_glicada numeric,
    total_consultas bigint, ultima_consulta date, atendido_no_periodo boolean, risco text
)
LANGUAGE sql STABLE AS $$
    SELECT
        'D-' || lpad(p.id::text, 4, '0'),
        p.id, p.nome, idade_em(p.data_nascimento, p_fim - 1),
        u.id, u.nome, u.municipio_id,
        ultima.hemoglobina_glicada,
        resumo.total_consultas,
        resumo.ultima_consulta,
        coalesce(resumo.ultima_consulta >= p_inicio, false),
        CASE
            WHEN ultima.hemoglobina_glicada IS NULL THEN NULL
            WHEN ultima.hemoglobina_glicada > 9 THEN 'alto'
            WHEN ultima.hemoglobina_glicada >= 7 THEN 'moderado'
            ELSE 'baixo'
        END
    FROM paciente_grupos pg
    JOIN pacientes p ON p.id = pg.paciente_id
    JOIN unidades_saude u ON u.id = p.unidade_saude_id
    CROSS JOIN LATERAL (
        SELECT count(*) AS total_consultas, max(c.data_consulta) AS ultima_consulta
        FROM consultas c
        WHERE c.paciente_id = pg.paciente_id AND c.grupo = 'diabetico'
          AND c.data_consulta < p_fim
    ) resumo
    LEFT JOIN LATERAL (
        SELECT c.hemoglobina_glicada
        FROM consultas c
        WHERE c.paciente_id = pg.paciente_id AND c.grupo = 'diabetico'
          AND c.data_consulta < p_fim
          AND c.hemoglobina_glicada IS NOT NULL
        ORDER BY c.data_consulta DESC
        LIMIT 1
    ) ultima ON true
    WHERE pg.grupo = 'diabetico'
      AND pg.data_inclusao < p_fim
      AND (pg.data_saida IS NULL OR pg.data_saida >= p_inicio)
$$
"""

# Crianças: pacientes já nascidos e com menos de 12 anos (ECA) no fim do período.
# Risco pela vacinação e por tempo sem consulta.
FN_CRIANCAS = """
CREATE FUNCTION fn_criancas(p_inicio date, p_fim date)
RETURNS TABLE (
    codigo text, paciente_id integer, nome varchar, idade integer,
    unidade_saude_id integer, unidade_saude varchar, municipio_id integer,
    vacinacao_em_dia boolean,
    total_consultas bigint, ultima_consulta date, atendido_no_periodo boolean, risco text
)
LANGUAGE sql STABLE AS $$
    SELECT
        'C-' || lpad(p.id::text, 4, '0'),
        p.id, p.nome, idade_em(p.data_nascimento, p_fim - 1),
        u.id, u.nome, u.municipio_id,
        ultima.vacinacao_em_dia,
        resumo.total_consultas,
        resumo.ultima_consulta,
        coalesce(resumo.ultima_consulta >= p_inicio, false),
        CASE
            WHEN ultima.vacinacao_em_dia = false THEN 'alto'
            WHEN resumo.ultima_consulta IS NULL
              OR resumo.ultima_consulta < (p_fim - 1) - 90 THEN 'moderado'
            ELSE 'baixo'
        END
    FROM pacientes p
    JOIN unidades_saude u ON u.id = p.unidade_saude_id
    CROSS JOIN LATERAL (
        SELECT count(*) AS total_consultas, max(c.data_consulta) AS ultima_consulta
        FROM consultas c
        WHERE c.paciente_id = p.id AND c.grupo = 'crianca'
          AND c.data_consulta < p_fim
    ) resumo
    LEFT JOIN LATERAL (
        SELECT c.vacinacao_em_dia
        FROM consultas c
        WHERE c.paciente_id = p.id AND c.grupo = 'crianca'
          AND c.data_consulta < p_fim
          AND c.vacinacao_em_dia IS NOT NULL
        ORDER BY c.data_consulta DESC
        LIMIT 1
    ) ultima ON true
    WHERE p.data_nascimento < p_fim
      AND idade_em(p.data_nascimento, p_fim - 1) < 12
$$
"""

# Idosos: pacientes com 60 anos ou mais (Estatuto da Pessoa Idosa) no fim do período.
# Comorbidades = hipertensão/diabetes no período + outras condições cadastradas.
FN_IDOSOS = """
CREATE FUNCTION fn_idosos(p_inicio date, p_fim date)
RETURNS TABLE (
    codigo text, paciente_id integer, nome varchar, idade integer,
    unidade_saude_id integer, unidade_saude varchar, municipio_id integer,
    comorbidades bigint,
    total_consultas bigint, ultima_consulta date, atendido_no_periodo boolean, risco text
)
LANGUAGE sql STABLE AS $$
    SELECT
        'I-' || lpad(p.id::text, 4, '0'),
        p.id, p.nome, idade_em(p.data_nascimento, p_fim - 1),
        u.id, u.nome, u.municipio_id,
        comorb.total,
        resumo.total_consultas,
        resumo.ultima_consulta,
        coalesce(resumo.ultima_consulta >= p_inicio, false),
        CASE
            WHEN comorb.total >= 3 OR idade_em(p.data_nascimento, p_fim - 1) >= 80 THEN 'alto'
            WHEN comorb.total = 2 THEN 'moderado'
            ELSE 'baixo'
        END
    FROM pacientes p
    JOIN unidades_saude u ON u.id = p.unidade_saude_id
    CROSS JOIN LATERAL (
        SELECT count(*) AS total_consultas, max(c.data_consulta) AS ultima_consulta
        FROM consultas c
        WHERE c.paciente_id = p.id AND c.grupo = 'idoso'
          AND c.data_consulta < p_fim
    ) resumo
    CROSS JOIN LATERAL (
        SELECT
            (SELECT count(*) FROM paciente_grupos pg
              WHERE pg.paciente_id = p.id
                AND pg.grupo IN ('hipertenso', 'diabetico')
                AND pg.data_inclusao < p_fim
                AND (pg.data_saida IS NULL OR pg.data_saida >= p_inicio))
          + (SELECT count(*) FROM comorbidades cm
              WHERE cm.paciente_id = p.id) AS total
    ) comorb
    WHERE idade_em(p.data_nascimento, p_fim - 1) >= 60
$$
"""

GRUPOS = ["gestantes", "hipertensos", "diabeticos", "criancas", "idosos"]


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('unidades_saude',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nome', sa.String(length=100), nullable=False),
    sa.Column('tipo', sa.String(length=3), nullable=False),
    sa.Column('municipio_id', sa.Integer(), nullable=False),
    sa.CheckConstraint("tipo IN ('UBS', 'ESF')", name='ck_unidades_saude_tipo'),
    sa.ForeignKeyConstraint(['municipio_id'], ['municipios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('pacientes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nome', sa.String(length=100), nullable=False),
    sa.Column('data_nascimento', sa.Date(), nullable=False),
    sa.Column('sexo', sa.String(length=1), nullable=False),
    sa.Column('unidade_saude_id', sa.Integer(), nullable=False),
    sa.CheckConstraint("sexo IN ('F', 'M')", name='ck_pacientes_sexo'),
    sa.ForeignKeyConstraint(['unidade_saude_id'], ['unidades_saude.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('comorbidades',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('paciente_id', sa.Integer(), nullable=False),
    sa.Column('descricao', sa.String(length=100), nullable=False),
    sa.ForeignKeyConstraint(['paciente_id'], ['pacientes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('consultas',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('paciente_id', sa.Integer(), nullable=False),
    sa.Column('unidade_saude_id', sa.Integer(), nullable=False),
    sa.Column('grupo', sa.String(length=20), nullable=False),
    sa.Column('data_consulta', sa.Date(), nullable=False),
    sa.Column('pressao_sistolica', sa.SmallInteger(), nullable=True),
    sa.Column('pressao_diastolica', sa.SmallInteger(), nullable=True),
    sa.Column('hemoglobina_glicada', sa.Numeric(precision=4, scale=1), nullable=True),
    sa.Column('semanas_gestacao', sa.SmallInteger(), nullable=True),
    sa.Column('vacinacao_em_dia', sa.Boolean(), nullable=True),
    sa.CheckConstraint("grupo IN ('gestante', 'hipertenso', 'diabetico', 'crianca', 'idoso')", name='ck_consultas_grupo'),
    sa.ForeignKeyConstraint(['paciente_id'], ['pacientes.id'], ),
    sa.ForeignKeyConstraint(['unidade_saude_id'], ['unidades_saude.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_consultas_paciente_grupo_data', 'consultas', ['paciente_id', 'grupo', 'data_consulta'], unique=False)
    op.create_table('paciente_grupos',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('paciente_id', sa.Integer(), nullable=False),
    sa.Column('grupo', sa.String(length=20), nullable=False),
    sa.Column('data_inclusao', sa.Date(), nullable=False),
    sa.Column('data_saida', sa.Date(), nullable=True),
    sa.CheckConstraint("grupo IN ('gestante', 'hipertenso', 'diabetico')", name='ck_paciente_grupos_grupo'),
    sa.CheckConstraint('data_saida IS NULL OR data_saida >= data_inclusao', name='ck_paciente_grupos_periodo'),
    sa.ForeignKeyConstraint(['paciente_id'], ['pacientes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###

    op.execute(FN_IDADE_EM)
    for sql in (FN_GESTANTES, FN_HIPERTENSOS, FN_DIABETICOS, FN_CRIANCAS, FN_IDOSOS):
        op.execute(sql)

    # Views com a situação de hoje (período = só o dia atual).
    for grupo in GRUPOS:
        op.execute(
            f"CREATE VIEW vw_{grupo} AS "
            f"SELECT * FROM fn_{grupo}(current_date, current_date + 1)"
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Views e funções primeiro, porque dependem das tabelas.
    for grupo in GRUPOS:
        op.execute(f"DROP VIEW IF EXISTS vw_{grupo}")
        op.execute(f"DROP FUNCTION IF EXISTS fn_{grupo}(date, date)")
    op.execute("DROP FUNCTION IF EXISTS idade_em(date, date)")

    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('paciente_grupos')
    op.drop_index('ix_consultas_paciente_grupo_data', table_name='consultas')
    op.drop_table('consultas')
    op.drop_table('comorbidades')
    op.drop_table('pacientes')
    op.drop_table('unidades_saude')
    # ### end Alembic commands ###
