# language: pt
@RF02
Funcionalidade: RF02 - Cadastrar usuário
  Como administrador do sistema
  Quero cadastrar os gestores de cada município
  Para que só pessoas autorizadas acessem os relatórios

  Cenário: Cadastrar um gestor
    Dado estar logado como administrador
    Quando cadastrar o gestor "novo.gestor@teste.com" no município do gestor A
    Então concluir o cadastro
    E não exibir a senha na resposta

  Cenário: Cadastrar um e-mail que já existe
    Dado estar logado como administrador
    Quando cadastrar o gestor "gestor.a@teste.com" no município do gestor A
    Então recusar o cadastro com a mensagem "Email já cadastrado"

  Cenário: Impedir o gestor de cadastrar usuários
    Dado estar logado como gestor
    Quando cadastrar o gestor "novo.gestor@teste.com" no município do gestor A
    Então negar o acesso
