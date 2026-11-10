# language: pt
@RF10
Funcionalidade: RF10 - Registrar as mensagens do chat para monitorar o modelo
  Como equipe de desenvolvimento
  Quero guardar o resultado de cada mensagem do chat
  Para perceber quando o modelo começar a errar mais (data drift)

  Cenário: Registrar a mensagem sem guardar o texto digitado
    Dado estar logado como gestor
    Quando enviar a mensagem "relatório das gestantes de agosto"
    Então registrar a mensagem com o resultado "relatorio" e a intenção "relatorio_gestantes"
    E não guardar o texto digitado

  Cenário: Registrar uma mensagem fora do escopo
    Dado estar logado como gestor
    Quando enviar a mensagem "me conta uma piada"
    Então registrar a mensagem com o resultado "mensagem" e a intenção "fora_do_escopo"
