# Saúde em Dados — API

Backend do sistema **Saúde em Dados**, para gestores municipais de saúde acompanharem cinco grupos da população: **gestantes, hipertensos, diabéticos, crianças e idosos**.

A API guarda os pacientes e as consultas, calcula os relatórios de cada grupo (inclusive de meses passados) e oferece um conjunto fechado de consultas para o chatbot, que transforma pedidos como *"quero o relatório das gestantes de julho"* em relatórios.

> ⚠️ **Todos os dados de pacientes são falsos**, gerados pelo script `app/seed.py`. Nenhum dado real é usado.

**Stack:** Python 3.13 · FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL · JWT

---

## Sumário

- [Como rodar](#como-rodar)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Modelo de dados](#modelo-de-dados)
- [Relatórios por período (histórico)](#relatórios-por-período-histórico)
- [Regras de risco](#regras-de-risco)
- [Consultas permitidas do chatbot](#consultas-permitidas-do-chatbot)
- [Endpoints de relatório e chat](#endpoints-de-relatório-e-chat)
- [Modelo de Machine Learning](#modelo-de-machine-learning)
- [Testes](#testes)
- [Migrations](#migrations)
- [Limitações conhecidas](#limitações-conhecidas)

---

## Como rodar

### 1. Ambiente Python

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

No Ubuntu/Debian, se o `venv` reclamar de `ensurepip`, instale antes: `sudo apt install python3.13-venv`.

### 2. Banco de dados

```bash
sudo -u postgres psql -c "CREATE USER saude WITH PASSWORD 'saude123';" -c "CREATE DATABASE saude OWNER saude;"
```

### 3. Arquivo `.env`

Copie o `.env.example` para `.env` e preencha:

```
DATABASE_URL=postgresql+psycopg://saude:saude123@localhost:5432/saude
JWT_SECRET_KEY=<gere com: python -c "import secrets; print(secrets.token_hex(32))">
```

`DATABASE_URL` e `JWT_SECRET_KEY` são obrigatórias: sem elas a API não sobe. O projeto tem os dois drivers do Postgres instalados, então a URL pode começar com `postgresql+psycopg://` (psycopg 3) ou `postgresql://` (psycopg2).

### 4. Tabelas e dados falsos

```bash
alembic upgrade head      # cria tabelas, funções e views
python -m app.seed        # gera 1500 pacientes falsos e um ano de consultas
```

Para apagar os dados falsos e gerar de novo: `python -m app.seed --limpar`.

### 5. Modelo do chatbot

```bash
python ml/treinar.py      # gera ml/modelo.pkl (cada pessoa gera o seu)
```

Sem o `modelo.pkl` a API sobe normalmente, mas o `POST /chat` responde 503.

### 6. Subir a API

```bash
uvicorn app.main:app --reload
```

A documentação interativa fica em **http://localhost:8000/docs**. Para testar rotas protegidas, faça login em `POST /auth/login`, copie o `access_token` e cole no botão **Authorize**.

---

## Estrutura do projeto

```
app/
├── main.py                 # cria o app FastAPI e registra as rotas
├── seed.py                 # gera dados falsos para desenvolvimento
├── api/
│   ├── dependencies.py     # get_current_user / get_current_admin (leem o token JWT)
│   └── routes/             # auth, municipios, users, chat, relatorios
├── core/
│   ├── config.py           # lê o .env
│   ├── database.py         # conexão e get_db
│   └── security.py         # hash de senha e criação do JWT
├── models/                 # tabelas (SQLAlchemy)
├── schemas/                # formatos de entrada/saída da API (Pydantic)
└── services/
    ├── auth_service.py
    ├── user_service.py
    ├── municipio_service.py
    ├── consultas.py        # consultas SQL permitidas (único ponto que lê os relatórios no banco)
    ├── relatorio_service.py  # permissão + município + consulta + auditoria (usado por /chat e /relatorios)
    ├── chat_service.py     # fluxo do chatbot (modelo, contexto, mensagens fixas)
    ├── extrair_parametros.py # extrai mês/ano da frase ("agosto", "mês passado", "08/2026")
    └── permissoes.py       # quais perfis podem pedir cada relatório
ml/                         # base de frases, treino e teste do modelo do chatbot
tests/                      # testes automatizados (pytest)
alembic/versions/           # migrations
```

O fluxo de uma requisição é: **rota** (recebe e responde) → **schema** (valida) → **service** (regra de negócio) → **model** (banco).

---

## Modelo de dados

```mermaid
erDiagram
    municipios ||--o{ unidades_saude : tem
    municipios ||--o{ users : "gestor de"
    unidades_saude ||--o{ pacientes : acompanha
    unidades_saude ||--o{ consultas : realiza
    pacientes ||--o{ paciente_grupos : "participa de"
    pacientes ||--o{ consultas : tem
    pacientes ||--o{ comorbidades : tem

    unidades_saude {
        int id
        string nome
        string tipo "UBS ou ESF"
        int municipio_id
    }
    pacientes {
        int id
        string nome
        date data_nascimento
        string sexo "F ou M"
        int unidade_saude_id
    }
    paciente_grupos {
        int id
        int paciente_id
        string grupo "gestante, hipertenso, diabetico"
        date data_inclusao
        date data_saida "vazio = continua no grupo"
    }
    consultas {
        int id
        int paciente_id
        int unidade_saude_id
        string grupo "gestante, hipertenso, diabetico, crianca, idoso"
        date data_consulta
        int pressao_sistolica
        int pressao_diastolica
        decimal hemoglobina_glicada
        int semanas_gestacao
        bool vacinacao_em_dia
    }
    comorbidades {
        int id
        int paciente_id
        string descricao
    }
```

### Decisões de modelagem

**Uma tabela de pacientes, não uma por grupo.** A mesma pessoa pode estar em vários grupos (ex.: um idoso hipertenso e diabético). Com uma tabela por grupo, nome, nascimento e unidade ficariam repetidos e poderiam ficar diferentes entre si. Cada informação fica em um lugar só, e as **funções/views de cada grupo** (abaixo) montam os dados no formato das telas.

**Criança e idoso são definidos pela idade**, não por cadastro:
- criança: menos de 12 anos (ECA);
- idoso: 60 anos ou mais (Estatuto da Pessoa Idosa).

Gestante, hipertenso e diabético são cadastrados em `paciente_grupos`.

**A idade não é guardada**, é calculada a partir de `data_nascimento`, senão ficaria errada no aniversário.

**`data_saida` em vez de "ativo sim/não".** Com a data dá para saber quem estava no grupo em qualquer mês. Uma mesma mulher tem uma linha de `gestante` por gestação, e `data_saida` é a data do parto.

**As medições ficam na consulta.** Cada consulta preenche só o campo do seu grupo (pressão para hipertensos, glicada para diabéticos etc.). Assim, toda medição tem data, e a tabela `consultas` é o histórico completo.

**Comorbidades dos idosos** = hipertensão/diabetes (de `paciente_grupos`) + outras condições (de `comorbidades`). Hipertensão e diabetes não são cadastradas duas vezes.

**A tabela `categorias`** veio da primeira versão do projeto e foi mantida, mas não é usada pelos relatórios.

---

## Relatórios por período (histórico)

Cada grupo tem uma **função no Postgres** que recebe um período e devolve a situação dos pacientes **naquele período**:

```sql
SELECT * FROM fn_gestantes('2026-07-01', '2026-08-01');   -- julho/2026
```

| Função | Coluna específica do grupo | Código |
|---|---|---|
| `fn_gestantes(inicio, fim)` | `semanas_gestacao` | G-0001 |
| `fn_hipertensos(inicio, fim)` | `pressao_sistolica`, `pressao_diastolica` | H-0001 |
| `fn_diabeticos(inicio, fim)` | `hemoglobina_glicada` | D-0001 |
| `fn_criancas(inicio, fim)` | `vacinacao_em_dia` | C-0001 |
| `fn_idosos(inicio, fim)` | `comorbidades` | I-0001 |

Todas devolvem também: `codigo`, `paciente_id`, `nome`, `idade`, `unidade_saude_id`, `unidade_saude`, `municipio_id`, `total_consultas`, `ultima_consulta`, `atendido_no_periodo` e `risco`.

O período é **`[inicio, fim)`**: o dia `fim` não entra. Para julho, `fim` é 1º de agosto.

Dentro do período, tudo é calculado **até o fim dele**:
- **quem estava no grupo:** a gestante grávida em julho aparece no relatório de julho, mesmo que já tenha tido o bebê;
- **idade** no último dia do período (quem fez 60 anos em agosto não é idoso em julho);
- **última medição, total de consultas e última consulta** sem contar consultas posteriores;
- **`atendido_no_periodo`**: se teve consulta do grupo dentro do período (é o "298 **de** 387" das telas);
- **risco** calculado com esses valores.

Para a situação de **hoje**, existem views que chamam as funções com o dia atual: `vw_gestantes`, `vw_hipertensos`, `vw_diabeticos`, `vw_criancas`, `vw_idosos`.

```sql
SELECT * FROM vw_hipertensos WHERE risco = 'alto';
```

---

## Regras de risco

O risco é **calculado** pelas funções, não digitado. Assim, ele sempre corresponde à última medição.

### Hipertensos — última pressão arterial

Baseado na Diretriz Brasileira de Hipertensão Arterial 2025 (SBC). Basta **um** dos dois valores (sistólica **ou** diastólica) atingir a faixa.

| Risco | Pressão |
|---|---|
| Baixo | abaixo de 140/90 (controlada) |
| Moderado | 140–159 ou 90–99 (estágio 1) |
| Alto | ≥ 160 ou ≥ 100 (estágios 2 e 3) |

### Diabéticos — última hemoglobina glicada (HbA1c)

Baseado na meta geral da Sociedade Brasileira de Diabetes (HbA1c < 7%).

| Risco | HbA1c |
|---|---|
| Baixo | < 7% (dentro da meta) |
| Moderado | 7% a 9% |
| Alto | > 9% |

O corte de 9% para "alto" é uma **simplificação do projeto**: não há regra nacional única, e cada município define suas faixas.

### Gestantes, crianças e idosos — regras simplificadas do projeto

| Grupo | Alto | Moderado | Baixo |
|---|---|---|---|
| Gestantes | idade < 15 ou ≥ 40 | 1ª consulta após a 12ª semana | demais |
| Crianças | vacinação atrasada | sem consulta há mais de 90 dias | demais |
| Idosos | 3+ comorbidades ou 80+ anos | 2 comorbidades | 0 ou 1 |

O critério da 12ª semana vem do indicador de pré-natal do Ministério da Saúde (1ª consulta até a 12ª semana). As demais regras foram definidas para o projeto e podem ser trocadas nas funções da migration.

Quando não há medição (ex.: hipertenso sem nenhuma pressão registrada), o risco fica vazio (`NULL`).

**Fontes:**
- [SBC 2025 — Diretriz Brasileira de Hipertensão Arterial (resumo Afya)](https://portal.afya.com.br/saude/sbc-2025-nova-diretriz-brasileira-de-hipertensao-arterial-sistemica)
- [SBD — Metas no tratamento do diabetes](https://diretriz.diabetes.org.br/metas-no-tratamento-do-diabetes/)
- [Nota técnica Previne Brasil — indicadores de pré-natal e diabetes](https://www.saude.mg.gov.br/wp-content/uploads/2025/01/nota_tecnica_7_2022.pdf)

---

## Consultas permitidas do chatbot

Arquivo: [`app/services/consultas.py`](app/services/consultas.py)

O chatbot **nunca gera SQL**. O modelo de Machine Learning só escolhe uma intenção e extrai os parâmetros; o backend executa a consulta já escrita.

### Intenções disponíveis

| Intenção | Devolve |
|---|---|
| `relatorio_gestantes` | gestantes atendidas no mês |
| `relatorio_hipertensos` | hipertensos atendidos no mês |
| `relatorio_diabeticos` | diabéticos atendidos no mês |
| `relatorio_criancas` | crianças atendidas no mês |
| `relatorio_idosos` | idosos atendidos no mês |
| `resumo_cobertura` | por grupo: cadastrados, atendidos e % de cobertura (sem dados pessoais) |

Todas exigem os parâmetros `mes`, `ano` e `municipio_id`. O `municipio_id` **não vem do chatbot**: deve vir do usuário logado (`current_user.municipio_id`), para cada gestor ver só o seu município.

### Uso

```python
from app.services.consultas import executar_consulta, ConsultaInvalidaError

try:
    linhas = executar_consulta(
        "relatorio_gestantes",
        {"mes": 7, "ano": 2026, "municipio_id": 1},
        db,  # sessão do SQLAlchemy (nas rotas: Depends(get_db))
    )
except ConsultaInvalidaError as erro:
    print(erro)  # ex.: "Mês inválido: 13. Use um número de 1 a 12."
```

Retorno: lista de dicionários, uma linha por paciente:

```python
[{'codigo': 'G-0032', 'nome': '...', 'idade': 41, 'unidade_saude': 'ESF Santa Rita',
  'semanas_gestacao': 15, 'total_consultas': 1, 'ultima_consulta': date(2026, 7, 8), 'risco': 'alto'}, ...]
```

Para ver um exemplo completo, com erros incluídos: `python -m app.services.consultas`.

### Segurança

- **Lista fechada:** só as intenções do dicionário `CONSULTAS` podem ser executadas.
- **Sem SQL Injection:** os valores entram por parâmetros (`:inicio`, `:municipio_id`), nunca concatenados no SQL. Além disso, `mes`, `ano` e `municipio_id` precisam ser números inteiros.
- **Somente leitura:** ao carregar o módulo, toda consulta é conferida (precisa começar com `SELECT` ou `WITH`). Em produção, o ideal é o banco usar um usuário com permissão só de `SELECT` para o chatbot.
- **LGPD — princípio da necessidade:** cada consulta devolve só as colunas que o relatório mostra. Não há `SELECT *`, e ficam de fora id interno, sexo e município.

### Como adicionar um relatório

1. Escreva o `SELECT` usando uma das funções `fn_*` (ou crie uma nova função em uma migration).
2. Adicione uma entrada em `CONSULTAS` com `descricao`, `parametros` e `sql`.
3. Se usar um parâmetro novo, adicione a validação dele em `_validar_parametros`.

---

## Endpoints de relatório e chat

Todos exigem login (`Authorization: Bearer <token>` do `POST /auth/login`).

| Endpoint | Para que serve |
|---|---|
| `GET /relatorios` | lista os relatórios que o usuário pode pedir |
| `GET /relatorios/{relatorio}?mes=7&ano=2026` | dados de um relatório, para as telas do front |
| `POST /chat` | chatbot: recebe `{"mensagem": "..."}` em linguagem natural |

As duas formas usam o **mesmo** `relatorio_service.gerar_relatorio`, então a tela e o chatbot sempre mostram os mesmos números:

```
GET /relatorios/{relatorio} ──┐
                              ├──> relatorio_service ──> consultas.py ──> PostgreSQL
POST /chat ── modelo de ML ───┘    (permissão, município, auditoria)
```

**O modelo de Machine Learning não acessa o banco.** Ele só recebe o texto e devolve o nome da intenção (ex.: `relatorio_hipertensos`). Quem acessa o banco é o `consultas.py`, e só com as consultas já escritas nele. O modelo roda no próprio servidor: nenhuma mensagem é enviada para serviços externos.

### Regras de acesso

- O município é **sempre o do usuário logado** (vem do token). O `POST /chat` só aceita o campo `mensagem` (campo extra = erro 422), e no `GET /relatorios` um `municipio_id` na URL é ignorado.
- Perfis `admin` e `gestor` veem todos os relatórios (`app/services/permissoes.py`).
- Usuário sem município recebe **403**: "Seu usuário não está vinculado a um município."
- Erros do banco vão para o log do servidor; o usuário recebe uma mensagem genérica (500).

### Fluxo do `POST /chat`

1. Se o chatbot tinha perguntado o mês e a mensagem traz um mês ("agosto"), continua o pedido anterior. O contexto fica em memória por usuário e expira em 5 minutos.
2. O modelo classifica a intenção. Confiança abaixo de 60% → "Não entendi, pode reformular?".
3. `saudacao`, `ajuda` e `fora_do_escopo` → resposta fixa, sem consultar o banco.
4. Relatório sem mês → pergunta "De qual mês você quer o relatório?".
5. Gera o relatório pelo `relatorio_service`.

Resposta, sempre com os mesmos campos:

```json
{"tipo": "mensagem | pergunta | relatorio | erro", "texto": "...", "intencao": "...", "parametros": {"mes": 7, "ano": 2026}, "dados": [...]}
```

### Auditoria

Cada pedido de relatório, pela tela ou pelo chat, vira uma linha em `auditoria_relatorios`: quem pediu, a origem (`chat` ou `api`), o relatório, o mês e ano, o resultado (`ok`, `negado` ou `erro`), a quantidade de registros e a data e hora. **Não guarda dados de pacientes nem o texto digitado.**

### Testando pelo `/docs`

1. `POST /auth/login` → copie o `access_token`.
2. Botão **Authorize** → cole o token.
3. `POST /chat` com `{"mensagem": "quero o relatório dos hipertensos"}` e depois `{"mensagem": "julho"}`.
4. `GET /relatorios/relatorio_hipertensos` com `mes=7` e `ano=2026`.

---

## Modelo de Machine Learning

Pasta `ml/`. Classifica a intenção da frase com **TF-IDF + Regressão Logística** (scikit-learn).

```bash
python ml/verificar_base.py   # confere o frases.csv (duplicadas, vazias, quase iguais)
python ml/treinar.py          # treina, mostra as métricas, salva matriz_confusao.png e modelo.pkl
python ml/testar_modelo.py    # digite frases no terminal ("sair" encerra)
```

- `frases.csv`: base de treino (`frase,intencao`), com 9 intenções.
- O `modelo.pkl` depende da versão do scikit-learn: cada pessoa gera o seu com `treinar.py`.
- Para melhorar o modelo: acrescente frases ao `frases.csv` e rode `treinar.py` de novo.

---

## Testes

```bash
pytest -v
```

Os testes usam o banco do `.env`, mas cada teste roda dentro de uma transação desfeita no final: **nada fica gravado**. Precisam de `alembic upgrade head` e do `ml/modelo.pkl`.

- `tests/test_chat.py`: acesso sem login, relatório com e sem permissão, isolamento por município, pedido sem mês, resposta do mês na mensagem seguinte, contexto expirado, fora do escopo, confiança baixa e erro de banco.
- `tests/test_relatorios.py`: os endpoints `/relatorios`, incluindo que tela e chat devolvem os mesmos dados.
- `tests/test_extrair_parametros.py`: a extração de mês e ano.

---

## Migrations

As migrations ficam em `alembic/versions/` e são aplicadas em ordem:

| Revisão | O que faz |
|---|---|
| `754bf13d9d61` | cria `municipios`, `categorias` e `users` |
| `b1851e0099c1` | adiciona `role` ao usuário |
| `aef97b179cbd` | torna o município do usuário opcional |
| `720dbc080c91` | cria `unidades_saude`, `pacientes`, `paciente_grupos`, `consultas`, `comorbidades`, a função `idade_em`, as funções `fn_*` e as views `vw_*` |
| `7d0426390fbf` | cria `auditoria_relatorios` |

### Comandos

```bash
alembic upgrade head        # aplica tudo que falta
alembic downgrade -1        # desfaz a última
alembic current             # mostra em qual revisão o banco está
alembic check               # confere se os models e o banco estão iguais
```

### Criando uma migration nova

```bash
# 1. altere/crie o model em app/models/ (e importe em app/models/__init__.py)
alembic revision --autogenerate -m "descricao da mudanca"
# 2. revise o arquivo gerado em alembic/versions/
alembic upgrade head
```

O `--autogenerate` só enxerga **tabelas, colunas e índices**. **Funções e views não são detectadas**: para mudá-las, escreva o SQL à mão na migration com `op.execute(...)`, como na `720dbc080c91`. Para alterar uma função existente, use `CREATE OR REPLACE FUNCTION` no `upgrade` e restaure a versão anterior no `downgrade`.

Uma migration que **já foi enviada** para o repositório não deve ser editada. Qualquer mudança vira uma migration nova.

---

## Limitações conhecidas

- **Comorbidades sem data:** a tabela `comorbidades` não tem data de diagnóstico. No relatório de idosos de um mês passado, comorbidades cadastradas depois também são contadas.
- **Dados falsos com histórico de um ano:** o seed gera consultas dos últimos 12 meses. Relatórios de períodos anteriores vêm vazios.
- **Correções alteram o passado:** como os relatórios são calculados a partir das consultas, corrigir uma consulta antiga muda o relatório daquele mês. Se for preciso "congelar" o relatório como foi entregue (auditoria), a ideia é criar uma tabela de fechamento mensal que salve o resultado das funções.
- **Banco sem usuário somente leitura (melhoria futura):** hoje toda a API conecta com o mesmo usuário do Postgres, dono do banco. Quem garante que os relatórios só leem dados é o código (`consultas.py` só aceita `SELECT`). A melhoria planejada é criar um usuário do Postgres só com `SELECT` nas tabelas e `EXECUTE` nas funções `fn_*`, e fazer o `consultas.py` usar uma conexão separada com ele. Assim o próprio banco recusaria qualquer escrita vinda dos relatórios e do chatbot.
- **Contexto do chat em memória:** some se o servidor reiniciar e não funciona com vários processos do servidor ao mesmo tempo. Suficiente para o projeto acadêmico.
- **Rotas `/users` devolvem `senha_hash`:** elas não usam `response_model`. Corrigir com `UserResponse`.
- **Ainda não implementado:** geração do PDF e integração com o front-end.
