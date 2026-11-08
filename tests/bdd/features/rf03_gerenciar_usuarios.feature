# language: pt
@RF03
Funcionalidade: RF03 - Gerenciar usuários
  Como administrador do sistema
  Quero listar, alterar e remover usuários
  Para manter os acessos atualizados

  Contexto:
    Dado estar logado como administrador

  Cenário: Listar os usuários sem mostrar as senhas
    Quando listar os usuários
    Então exibir o usuário "gestor.a@teste.com" na lista
    E não exibir a senha de nenhum usuário

  Cenário: Trocar a senha de um gestor
    Quando trocar a senha do usuário "gestor.a@teste.com" para "senha-nova"
    Então conseguir fazer login com o e-mail "gestor.a@teste.com" e a senha "senha-nova"

  Cenário: Remover um usuário
    Quando remover o usuário "gestor.a@teste.com"
    Então não encontrar mais o usuário "gestor.a@teste.com"
