# language: pt
@RF01
Funcionalidade: RF01 - Autenticar usuário
  Como gestor municipal de saúde
  Quero entrar no sistema com e-mail e senha
  Para acessar somente o que o meu perfil permite

  Cenário: Entrar com e-mail e senha corretos
    Dado existir o gestor "gestor.a@teste.com" com a senha "123"
    Quando fazer login com o e-mail "gestor.a@teste.com" e a senha "123"
    Então receber um token de acesso
    E identificar pelo token o usuário "gestor.a@teste.com"

  Cenário: Entrar com a senha errada
    Dado existir o gestor "gestor.a@teste.com" com a senha "123"
    Quando fazer login com o e-mail "gestor.a@teste.com" e a senha "senha-errada"
    Então recusar o login

  Cenário: Usar o sistema sem fazer login
    Dado não estar logado
    Quando enviar a mensagem "relatório das gestantes de agosto"
    Então pedir para fazer login
