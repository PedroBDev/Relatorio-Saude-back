# language: pt
@RF09
Funcionalidade: RF09 - Registrar os acessos aos relatórios (auditoria)
  Como secretaria municipal de saúde
  Quero saber quem pediu cada relatório, por onde e quando
  Para prestar contas do uso dos dados, conforme a LGPD

  Cenário: Registrar um relatório aberto pela tela
    Dado estar logado como gestor
    Quando abrir a tela do relatório de gestantes de agosto
    Então registrar na auditoria o relatório "relatorio_gestantes" pedido pela "api" com resultado "ok"

  Cenário: Registrar um relatório pedido pelo chat
    Dado estar logado como gestor
    Quando enviar a mensagem "relatório das gestantes de agosto"
    Então registrar na auditoria o relatório "relatorio_gestantes" pedido pelo "chat" com resultado "ok"

  Cenário: Registrar também o acesso negado
    Dado estar logado como um usuário sem município
    Quando abrir a tela do relatório de gestantes de agosto
    Então registrar na auditoria o relatório "relatorio_gestantes" pedido pela "api" com resultado "negado"
