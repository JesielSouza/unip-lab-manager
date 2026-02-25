---
# CONTEXTO ATUAL DO PROJETO (25/02/2026)

## Estrutura e Funcionalidades
- Sistema Flask para gestão de reservas de laboratório (UNIP Lab Manager)
- Usuários: Admin, Coordenador, Professor, Aluno
- Permissões:
  - Admin: controla tudo, não tem vínculo acadêmico, edita apenas login/email/senha
  - Coordenador: aprova/rejeita reservas, vê todas as turmas
  - Professor: solicita reservas, vê suas turmas, pode ver alunos de suas turmas
  - Aluno: só visualiza reservas aprovadas da sua turma
- Cadastro:
  - Campos Turma e Semestre só aparecem para alunos
  - Professores e coordenadores não preenchem esses campos
- Migrações automáticas com Flask-Migrate (não apagar banco para evoluir)
- Templates separados para cada contexto (admin, coord, prof, aluno)
- Rotas protegidas por sessão e role
- Admin não pode ser editado como usuário acadêmico
- README e requirements.txt atualizados

## Como continuar
- Para evoluir o banco: flask db migrate -m "msg" && flask db upgrade
- Para rodar: python app.py
- Para criar admin: já existe via setup_db.py
- Para não subir este contexto: contexto_projeto.md está no .gitignore

## Próximos passos sugeridos
- Melhorar relatórios para coordenador
- Adicionar logs de auditoria
- Permitir upload de arquivos (opcional)
- Refino de UX para mobile

---

📑 Contexto de Migração: Do "Tarefas" para "UNIP Lab Manager"
1. Origem do Código
O projeto está sendo construído reaproveitando a estrutura de um "Organizador de Tarefas" anterior.

2. O que precisa ser adaptado (Refatoração):
Banco de Dados: Onde era Tarefa(id, descricao, status), agora deve ser ReservaLab(id, laboratorio, professor, disciplina, data, horario).

Rotas: A rota que listava tarefas agora deve listar as reservas dos laboratórios de informática.

Templates: O CSS e o Layout base serão mantidos, mas os formulários devem ser alterados de "Nova Tarefa" para "Nova Reserva".

3. Foco do MVP (Fase 1)
Público: Apenas Laboratórios de Informática da UNIP.

Funcionalidade: CRUD básico (Criar, Ler, Atualizar, Deletar) de reservas.

Pendência: Resolver o erro remote origin already exists no terminal do VSCode.