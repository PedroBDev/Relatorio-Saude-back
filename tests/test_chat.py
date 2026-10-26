"""Testes da rota POST /chat.

Rodar (na raiz do projeto, com o venv ativado):
    pytest -v
"""
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.models.auditoria import AuditoriaRelatorio
from app.services import chat_service, relatorio_service
from tests.conftest import ANO_AGOSTO, cabecalho

CAMPOS_PADRAO = {"tipo", "texto", "intencao", "parametros", "dados"}


def enviar(client, usuario, mensagem):
    return client.post("/chat", json={"mensagem": mensagem}, headers=cabecalho(usuario))


def auditorias(db, usuario):
    return db.scalars(select(AuditoriaRelatorio).where(AuditoriaRelatorio.user_id == usuario.id)).all()


# --- Autenticação ----------------------------------------------------------

def test_sem_login_retorna_401(client):
    resposta = client.post("/chat", json={"mensagem": "relatório das gestantes de agosto"})
    assert resposta.status_code == 401


def test_token_invalido_retorna_401(client):
    resposta = client.post("/chat", json={"mensagem": "oi"},
                           headers={"Authorization": "Bearer token-falso"})
    assert resposta.status_code == 401


# --- Relatório com permissão -----------------------------------------------

def test_gestor_recebe_relatorio_so_do_seu_municipio(client, db, dados):
    gestor = dados["gestor_a"]
    resposta = enviar(client, gestor, f"quero o relatório das gestantes de agosto de {ANO_AGOSTO}")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert set(corpo) == CAMPOS_PADRAO
    assert corpo["tipo"] == "relatorio"
    assert corpo["intencao"] == "relatorio_gestantes"
    assert corpo["parametros"] == {"mes": 8, "ano": ANO_AGOSTO}

    codigos = [linha["codigo"] for linha in corpo["dados"]]
    assert dados["codigo_gestante_a"] in codigos
    # A gestante do município B nunca aparece para o gestor do município A.
    assert dados["codigo_gestante_b"] not in codigos


def test_relatorio_fica_registrado_na_auditoria_sem_dados_de_paciente(client, db, dados):
    gestor = dados["gestor_a"]
    enviar(client, gestor, f"quero o relatório das gestantes de agosto de {ANO_AGOSTO}")

    registros = auditorias(db, gestor)
    assert len(registros) == 1
    registro = registros[0]
    assert registro.relatorio == "relatorio_gestantes"
    assert registro.origem == "chat"
    assert (registro.mes, registro.ano) == (8, ANO_AGOSTO)
    assert registro.resultado == "ok"
    assert registro.quantidade_registros == 1
    assert registro.usuario_email == gestor.email
    # A tabela não tem nenhuma coluna com nome ou dado de paciente.
    assert "nome" not in AuditoriaRelatorio.__table__.columns


def test_nao_aceita_municipio_no_pedido(client, dados):
    resposta = client.post(
        "/chat",
        json={"mensagem": "gestantes de agosto", "municipio_id": 999},
        headers=cabecalho(dados["gestor_a"]),
    )
    # Campo extra é recusado: não há como escolher outro município pela API.
    assert resposta.status_code == 422


# --- Relatório sem permissão -----------------------------------------------

def test_usuario_sem_municipio_recebe_403(client, db, dados):
    admin = dados["admin_sem_municipio"]
    resposta = enviar(client, admin, f"quero o relatório das gestantes de agosto de {ANO_AGOSTO}")

    assert resposta.status_code == 403
    corpo = resposta.json()
    assert set(corpo) == CAMPOS_PADRAO
    assert corpo["tipo"] == "erro"
    assert corpo["texto"] == "Seu usuário não está vinculado a um município."
    assert corpo["dados"] == []
    assert [r.resultado for r in auditorias(db, admin)] == ["negado"]


def test_perfil_sem_permissao_recebe_403(client, db, dados):
    gestor = dados["gestor_a"]
    gestor.role = "perfil_desconhecido"
    db.flush()

    resposta = enviar(client, gestor, f"quero o relatório das gestantes de agosto de {ANO_AGOSTO}")

    assert resposta.status_code == 403
    assert resposta.json()["texto"] == "Você não tem permissão para acessar este relatório."


# --- Mês faltando ----------------------------------------------------------

def test_pedido_sem_mes_pergunta_o_mes(client, dados):
    resposta = enviar(client, dados["gestor_a"], "quero o relatório das gestantes")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "pergunta"
    assert corpo["intencao"] == "relatorio_gestantes"
    assert "mês" in corpo["texto"]
    assert corpo["dados"] == []


def test_resposta_do_mes_continua_o_pedido_anterior(client, dados):
    gestor = dados["gestor_a"]
    enviar(client, gestor, "quero o relatório das gestantes")

    resposta = enviar(client, gestor, "agosto")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["tipo"] == "relatorio"
    assert corpo["intencao"] == "relatorio_gestantes"
    assert corpo["parametros"] == {"mes": 8, "ano": ANO_AGOSTO}
    assert dados["codigo_gestante_a"] in [linha["codigo"] for linha in corpo["dados"]]


def test_contexto_expirado_nao_e_usado(client, dados, monkeypatch):
    gestor = dados["gestor_a"]
    monkeypatch.setattr(chat_service.settings, "chat_contexto_minutos", -1)  # expira na hora
    enviar(client, gestor, "quero o relatório das gestantes")

    resposta = enviar(client, gestor, "agosto")

    # Sem contexto, "agosto" sozinho não é um pedido de relatório.
    assert resposta.json()["tipo"] != "relatorio"


def test_contexto_e_separado_por_usuario(client, dados):
    enviar(client, dados["gestor_a"], "quero o relatório das gestantes")

    resposta = enviar(client, dados["admin_sem_municipio"], "agosto")

    # O admin não tinha pergunta pendente: o "agosto" dele não usa o pedido do gestor.
    assert resposta.json()["tipo"] != "relatorio"


# --- Mensagens que não são relatório -----------------------------------------

def test_fora_do_escopo_responde_sem_consultar_banco(client, db, dados):
    gestor = dados["gestor_a"]
    resposta = enviar(client, gestor, "me conta uma piada")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert set(corpo) == CAMPOS_PADRAO
    assert corpo["tipo"] == "mensagem"
    assert corpo["intencao"] == "fora_do_escopo"
    assert corpo["dados"] == []
    assert auditorias(db, gestor) == []


def test_saudacao(client, dados):
    corpo = enviar(client, dados["gestor_a"], "bom dia").json()
    assert corpo["tipo"] == "mensagem"
    assert corpo["intencao"] == "saudacao"


def test_confianca_baixa_pede_para_reformular(client, dados, monkeypatch):
    # Força o modelo a responder com 30% de confiança.
    monkeypatch.setattr(chat_service, "_classificar", lambda mensagem: ("relatorio_gestantes", 0.30))

    corpo = enviar(client, dados["gestor_a"], "qualquer coisa").json()

    assert corpo["tipo"] == "mensagem"
    assert corpo["texto"] == "Não entendi, pode reformular?"


# --- Erros internos ----------------------------------------------------------

def test_erro_do_banco_nao_aparece_para_o_usuario(client, db, dados, monkeypatch):
    def consulta_quebrada(*args, **kwargs):
        raise OperationalError("SELECT ...", {}, Exception("senha do banco: segredo123"))

    monkeypatch.setattr(relatorio_service, "executar_consulta", consulta_quebrada)
    gestor = dados["gestor_a"]

    resposta = enviar(client, gestor, f"quero o relatório das gestantes de agosto de {ANO_AGOSTO}")

    assert resposta.status_code == 500
    corpo = resposta.json()
    assert corpo["tipo"] == "erro"
    assert "segredo123" not in resposta.text
    assert "SELECT" not in resposta.text
    assert [r.resultado for r in auditorias(db, gestor)] == ["erro"]
