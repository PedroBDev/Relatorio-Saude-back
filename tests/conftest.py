"""Configuração compartilhada dos testes (o pytest carrega este arquivo sozinho).

Os testes usam o mesmo banco do .env, mas NÃO deixam nada gravado:
cada teste roda dentro de uma transação que é desfeita (rollback) no final.
Mesmo os db.commit() do código viram "savepoints" dentro dessa transação.

Pré-requisitos:
    alembic upgrade head      (as tabelas e funções precisam existir)
    python ml/treinar.py      (o modelo.pkl precisa existir)
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import engine, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Consulta, Municipio, Paciente, PacienteGrupo, UnidadeSaude, User
from app.services import chat_service
from app.services.extrair_parametros import _ano_mais_recente

# Ano que o chatbot vai usar quando o teste disser só "agosto".
ANO_AGOSTO = _ano_mais_recente(8, date.today())


@pytest.fixture
def db():
    """Sessão do banco dentro de uma transação que é desfeita no final do teste."""
    conexao = engine.connect()
    transacao = conexao.begin()
    sessao = Session(bind=conexao, join_transaction_mode="create_savepoint")
    try:
        yield sessao
    finally:
        sessao.close()
        transacao.rollback()
        conexao.close()


@pytest.fixture
def client(db):
    """Cliente HTTP de teste, usando a sessão acima no lugar do get_db normal."""
    if not settings.modelo_path.exists():
        pytest.skip(f"Modelo não encontrado em {settings.modelo_path}. Rode: python ml/treinar.py")

    app.dependency_overrides[get_db] = lambda: db
    # O "with" executa o lifespan do main.py, que carrega o modelo.
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def limpar_contexto_do_chat():
    """Cada teste começa sem nenhuma pergunta pendente do chatbot."""
    chat_service._contextos.clear()
    yield
    chat_service._contextos.clear()


def _criar_gestante(db, nome: str, unidade: UnidadeSaude) -> Paciente:
    """Gestante de 25 anos com uma consulta de pré-natal em 10 de agosto."""
    paciente = Paciente(nome=nome, data_nascimento=date(ANO_AGOSTO - 25, 1, 1),
                        sexo="F", unidade_saude_id=unidade.id)
    db.add(paciente)
    db.flush()
    db.add(PacienteGrupo(paciente_id=paciente.id, grupo="gestante",
                         data_inclusao=date(ANO_AGOSTO, 6, 1)))
    db.add(Consulta(paciente_id=paciente.id, unidade_saude_id=unidade.id, grupo="gestante",
                    data_consulta=date(ANO_AGOSTO, 8, 10), semanas_gestacao=20))
    return paciente


@pytest.fixture
def dados(db):
    """Dois municípios, cada um com uma gestante atendida em agosto, e os usuários de teste."""
    municipio_a = Municipio(nome="Município Teste A", uf="PE")
    municipio_b = Municipio(nome="Município Teste B", uf="PE")
    db.add_all([municipio_a, municipio_b])
    db.flush()

    unidade_a = UnidadeSaude(nome="UBS Teste A", tipo="UBS", municipio_id=municipio_a.id)
    unidade_b = UnidadeSaude(nome="UBS Teste B", tipo="UBS", municipio_id=municipio_b.id)
    db.add_all([unidade_a, unidade_b])
    db.flush()

    gestante_a = _criar_gestante(db, "Gestante Teste A", unidade_a)
    gestante_b = _criar_gestante(db, "Gestante Teste B", unidade_b)

    gestor_a = User(nome="Gestor A", email="gestor.a@teste.com", senha_hash=hash_password("123"),
                    municipio_id=municipio_a.id, role="gestor")
    admin_sem_municipio = User(nome="Admin", email="admin@teste.com", senha_hash=hash_password("123"),
                               municipio_id=None, role="admin")
    db.add_all([gestor_a, admin_sem_municipio])
    # commit aqui vira um savepoint: os dados ficam "gravados" como no uso real (um
    # db.rollback() do código não os apaga), mas somem no rollback do fim do teste.
    db.commit()

    return {
        "gestor_a": gestor_a,
        "admin_sem_municipio": admin_sem_municipio,
        "codigo_gestante_a": f"G-{gestante_a.id:04d}",
        "codigo_gestante_b": f"G-{gestante_b.id:04d}",
    }


def cabecalho(usuario: User) -> dict:
    """Cabeçalho Authorization com um token válido para o usuário (como se tivesse feito login)."""
    return {"Authorization": f"Bearer {create_access_token(usuario.id)}"}
