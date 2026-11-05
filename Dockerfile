# Imagem da API (FastAPI + modelo do chatbot). O banco roda em outro container,
# veja o docker-compose.yml.
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# As dependências vêm antes do código: assim o Docker reaproveita essa etapa
# (a mais demorada) quando só o código muda.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["sh", "docker/iniciar.sh"]
