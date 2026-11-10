# language: pt
@RF08
Funcionalidade: RF08 - Restringir os dados ao município do usuário
  Como secretaria municipal de saúde
  Quero que cada gestor veja somente os dados do próprio município
  Para proteger os dados dos pacientes, conforme a LGPD

  Cenário: Não exibir pacientes de outro município
    Dado estar logado como gestor
    E existir uma gestante atendida em agosto em outro município
    Quando enviar a mensagem "relatório das gestantes de agosto"
    Então receber o relatório de "gestantes" de agosto
    Mas não exibir a gestante do outro município no relatório

  Cenário: Negar relatórios a um usuário sem município
    Dado estar logado como um usuário sem município
    Quando enviar a mensagem "relatório das gestantes de agosto"
    Então negar o acesso com a mensagem "não está vinculado a um município"
    E não enviar nenhum dado de paciente

  Cenário: Ignorar comando de banco de dados escrito na mensagem
    Dado estar logado como gestor
    Quando enviar a mensagem "'; DROP TABLE pacientes; --"
    Então não apagar nenhum paciente do banco
