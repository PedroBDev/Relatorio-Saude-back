"""Popula o banco com dados FALSOS para desenvolvimento.

Como rodar (na raiz do projeto, com o venv ativado):
    python -m app.seed            # só roda se ainda não houver pacientes
    python -m app.seed --limpar   # apaga os pacientes/consultas e gera tudo de novo

Os nomes, datas e medições são sorteados. Nenhum dado é real.
"""
import random
import sys
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, func, select

from app.core.database import SessionLocal
from app.models import (
    Comorbidade,
    Consulta,
    Municipio,
    Paciente,
    PacienteGrupo,
    UnidadeSaude,
)

# Semente fixa: toda vez que rodar, gera os mesmos dados (facilita comparar resultados).
random.seed(42)

HOJE = date.today()
TOTAL_PACIENTES = 1500

UNIDADES = [
    ("UBS Vila Nova", "UBS"),
    ("UBS Central", "UBS"),
    ("UBS Jardim das Flores", "UBS"),
    ("UBS São José", "UBS"),
    ("UBS Boa Vista", "UBS"),
    ("ESF Santa Rita", "ESF"),
]

NOMES_F = ["Ana", "Carla", "Tatiane", "Luciana", "Priscila", "Mariana", "Rafaela", "Aline",
           "Vitória", "Simone", "Vanessa", "Bruna", "Patrícia", "Beatriz", "Renata", "Juliana"]
NOMES_M = ["Paulo", "Rafael", "Carlos", "Bruno", "José", "Marcos", "Pedro", "Lucas",
           "João", "Antônio", "Francisco", "Gabriel", "Felipe", "Ricardo", "André", "Thiago"]
SOBRENOMES = ["Silva", "Santos", "Oliveira", "Souza", "Lima", "Pereira", "Ferreira", "Alves",
              "Ribeiro", "Martins", "Lopes", "Gomes", "Barbosa", "Rodrigues", "Vieira", "Costa"]

COMORBIDADES = ["Osteoporose", "Artrose", "DPOC", "Insuficiência cardíaca",
                "Doença renal crônica", "Depressão", "Hipotireoidismo"]


def sortear_nome(sexo: str) -> str:
    primeiro = random.choice(NOMES_F if sexo == "F" else NOMES_M)
    return f"{primeiro} {random.choice(SOBRENOMES)} {random.choice(SOBRENOMES)}"


def sortear_nascimento() -> date:
    # 20% crianças (0-11), 50% adultos (15-59), 30% idosos (60+)
    faixa = random.random()
    if faixa < 0.2:
        idade = random.randint(0, 11)
    elif faixa < 0.7:
        idade = random.randint(15, 59)
    else:
        # Mais idosos perto dos 60 do que dos 90, como na população real.
        idade = min(60 + int(random.expovariate(1 / 9)), 100)
    return HOJE - timedelta(days=idade * 365 + random.randint(0, 364))


def idade_em(nascimento: date, dia: date) -> int:
    return dia.year - nascimento.year - ((dia.month, dia.day) < (nascimento.month, nascimento.day))


def datas_mensais(probabilidade: float, inicio: date) -> list[date]:
    """Sorteia no máximo uma consulta por mês, do `inicio` até hoje."""
    datas = []
    dia = inicio
    while dia <= HOJE:
        sorteada = dia + timedelta(days=random.randint(0, 27))
        if sorteada <= HOJE and random.random() < probabilidade:
            datas.append(sorteada)
        dia += timedelta(days=30)
    return datas


def gerar_paciente(db, unidades: list[UnidadeSaude]) -> None:
    sexo = random.choice(["F", "M"])
    nascimento = sortear_nascimento()
    idade = idade_em(nascimento, HOJE)
    unidade = random.choice(unidades)

    paciente = Paciente(nome=sortear_nome(sexo), data_nascimento=nascimento,
                        sexo=sexo, unidade_saude_id=unidade.id)
    db.add(paciente)
    db.flush()  # gera o paciente.id sem fechar a transação

    um_ano_atras = HOJE - timedelta(days=365)

    def consulta(grupo: str, dia: date, **medicoes) -> Consulta:
        return Consulta(paciente_id=paciente.id, unidade_saude_id=unidade.id,
                        grupo=grupo, data_consulta=dia, **medicoes)

    def gerar_gestacao(inicio: date, ultima_semana: int, parto: date | None) -> None:
        """Uma gestação com consulta a cada ~4 semanas desde o início do pré-natal."""
        semana = random.randint(6, min(20, ultima_semana))  # semana da 1ª consulta
        db.add(PacienteGrupo(paciente_id=paciente.id, grupo="gestante",
                             data_inclusao=inicio + timedelta(weeks=semana), data_saida=parto))
        while semana <= ultima_semana:
            if random.random() < 0.85:  # às vezes ela falta
                db.add(consulta("gestante", inicio + timedelta(weeks=semana),
                                semanas_gestacao=semana))
            semana += 4

    # Gestantes: mulheres de 14 a 44 anos. Algumas estão grávidas hoje e outras
    # já tiveram o bebê (gestação encerrada, com data_saida), para os relatórios
    # de meses passados também terem gestantes.
    if sexo == "F" and 14 <= idade <= 44:
        sorteio = random.random()
        if sorteio < 0.3:
            semanas_hoje = random.randint(6, 40)
            gerar_gestacao(HOJE - timedelta(weeks=semanas_hoje), semanas_hoje, parto=None)
        elif sorteio < 0.55:
            parto = HOJE - timedelta(days=random.randint(15, 365))
            semanas_no_parto = random.randint(37, 41)
            gerar_gestacao(parto - timedelta(weeks=semanas_no_parto), semanas_no_parto, parto=parto)

    # Hipertensos e diabéticos: mais comuns com a idade.
    chance_hipertensao = 0.5 if idade >= 60 else 0.25 if idade >= 30 else 0
    chance_diabetes = 0.25 if idade >= 60 else 0.12 if idade >= 30 else 0

    if random.random() < chance_hipertensao:
        db.add(PacienteGrupo(paciente_id=paciente.id, grupo="hipertenso",
                             data_inclusao=um_ano_atras - timedelta(days=random.randint(0, 1500))))
        base_sist = random.gauss(138, 14)
        base_diast = random.gauss(86, 9)
        for dia in datas_mensais(0.5, um_ano_atras):
            db.add(consulta("hipertenso", dia,
                            pressao_sistolica=round(base_sist + random.gauss(0, 6)),
                            pressao_diastolica=round(base_diast + random.gauss(0, 4))))

    if random.random() < chance_diabetes:
        db.add(PacienteGrupo(paciente_id=paciente.id, grupo="diabetico",
                             data_inclusao=um_ano_atras - timedelta(days=random.randint(0, 1500))))
        base_glicada = random.gauss(7.6, 1.4)
        for dia in datas_mensais(0.4, um_ano_atras):
            valor = min(max(base_glicada + random.gauss(0, 0.4), 4.5), 14)
            db.add(consulta("diabetico", dia, hemoglobina_glicada=Decimal(f"{valor:.1f}")))

    # Crianças (menos de 12 anos): puericultura com registro da vacinação.
    if idade < 12:
        vacina_em_dia = random.random() < 0.85
        inicio = max(um_ano_atras, nascimento)
        for dia in datas_mensais(0.4, inicio):
            db.add(consulta("crianca", dia, vacinacao_em_dia=vacina_em_dia))

    # Idosos (60+): consulta de acompanhamento e outras comorbidades.
    if idade >= 60:
        for descricao in random.sample(COMORBIDADES, k=random.choice([0, 0, 1, 1, 2])):
            db.add(Comorbidade(paciente_id=paciente.id, descricao=descricao))
        for dia in datas_mensais(0.4, um_ano_atras):
            db.add(consulta("idoso", dia))


def main() -> None:
    limpar = "--limpar" in sys.argv
    db = SessionLocal()

    try:
        ja_tem_dados = db.scalar(select(func.count()).select_from(Paciente)) > 0
        if ja_tem_dados and not limpar:
            print("Já existem pacientes no banco. Use --limpar para apagar e gerar de novo.")
            return

        if limpar:
            # Ordem importa: primeiro quem aponta para pacientes, depois pacientes e unidades.
            for modelo in (Consulta, Comorbidade, PacienteGrupo, Paciente, UnidadeSaude):
                db.execute(delete(modelo))

        # Usa o primeiro município cadastrado, ou cria um.
        municipio = db.scalar(select(Municipio).order_by(Municipio.id))
        if not municipio:
            municipio = Municipio(nome="Recife", uf="PE")
            db.add(municipio)
            db.flush()

        unidades = [UnidadeSaude(nome=nome, tipo=tipo, municipio_id=municipio.id)
                    for nome, tipo in UNIDADES]
        db.add_all(unidades)
        db.flush()

        for _ in range(TOTAL_PACIENTES):
            gerar_paciente(db, unidades)

        db.commit()
        print(f"Pronto! {TOTAL_PACIENTES} pacientes falsos criados em {municipio.nome}/{municipio.uf}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
