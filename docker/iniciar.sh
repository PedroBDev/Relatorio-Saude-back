#!/bin/sh
# Executado quando o container da API sobe.
set -e

# 1. Cria/atualiza as tabelas, funções e views do banco.
alembic upgrade head

# 2. Dados falsos e usuários de demonstração (só na primeira vez: depois ele vê que
# já existem pacientes e não faz nada). Para desligar: SEED=0 no docker-compose.yml.
if [ "${SEED:-1}" = "1" ]; then
    python -m app.seed
fi

# 3. Sobe a API. 0.0.0.0 para aceitar conexões de fora do container.
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
