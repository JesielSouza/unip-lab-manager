# 🏫 UNIP Lab Manager

Sistema Flask para gestão de reservas de laboratórios de informática da UNIP.

## Funcionalidades
- Controle de usuários: Admin, Coordenador, Professor, Aluno
- Permissões por perfil (CRUD, aprovação, visualização)
- Cadastro de reservas por professores (com aprovação do coordenador)
- Alunos só visualizam reservas da sua turma
- Admin não tem vínculo acadêmico, só gerencia usuários e sistema
- Migrações automáticas de banco com Flask-Migrate
- Templates separados por contexto
- Segurança de sessão e roles

## Como rodar
1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure o banco (primeira vez):
   ```bash
   flask db upgrade
   python setup_db.py  # Cria admin inicial
   ```
3. Execute o sistema:
   ```bash
   python app.py
   ```

## Como evoluir o banco
- Para adicionar/remover campos:
  ```bash
  flask db migrate -m "sua mensagem"
  flask db upgrade
  ```

## Como contribuir
- Consulte o arquivo `contexto_projeto.md` (não versionado) para histórico e próximos passos.
- Siga as permissões e regras de cada perfil.

## Próximos passos sugeridos
- Relatórios para coordenador
- Logs de auditoria
- Upload de arquivos
- Refino de UX para mobile

---
> Projeto em desenvolvimento contínuo. Para dúvidas, consulte o contexto ou abra uma issue.
