---
# CONTEXTO ATUAL DO PROJETO (04/03/2026)

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
  - Turmas são criadas automaticamente no cadastro do aluno (busca ou cria)
- Migrações automáticas com Flask-Migrate (não apagar banco para evoluir)
- Templates separados para cada contexto (admin, coord, prof, aluno)
- Rotas protegidas por sessão e role
- Admin não pode ser editado como usuário acadêmico

## Como continuar
- Para evoluir o banco: flask db migrate -m "msg" && flask db upgrade
- Para rodar: python app.py
- Para criar admin: já criado automaticamente via inicializar_unidade() no app.py
- Para não subir este contexto: contexto_projeto.md está no .gitignore

## Arquivos principais
- app.py — rotas, lógica de negócio e inicialização
- models.py — Usuario, ReservaLab, Laboratorio, Turma, BloqueioLab
- templates/ — lista.html (painel), nova_reserva.html, coordenador_reservas.html, painel_aluno.html, cadastro.html, login.html, admin_bloqueios.html, relatorio_reservas.html
- static/css/style.css — identidade visual UNIP

## Correções realizadas em 04/03/2026
### Bugs corrigidos
- `coordenador_reservas.html`: `r.turma.nome` → `r.turma_rel.nome` (relacionamento correto)
- `coordenador_reservas.html`: `session['role']` → `usuario_logado.role` (role nunca era gravado na sessão)
- `coordenador_reservas.html`: loop de pendências usava `todas_reservas` (só tinha approved/rejected) → corrigido para `reservas_pendentes`
- `app.py` rota `coordenador_reservas`: passava `usuario_logado.nome` ao template → corrigido para passar o objeto `usuario`
- `app.py` rota `criar_turma`: não passava `semestre` (campo nullable=False) → corrigido para capturar e passar semestre
- `app.py` rota `/bloquear_lab`: usava campos antigos do model → rota removida (substituída por `/admin/bloqueios`)
- `lista.html`: `{{ usuario }}` exibia objeto → corrigido para `{{ usuario.nome }}`
- `app.py` rota `cadastro`: `redirect()` em caso de erro → `render_template()` para flash aparecer na página correta
- `app.py` rota `nova_reserva`: todos os `redirect()` de erro → `render_template()` com dados necessários
- `cadastro.html`: bloco de flash messages ausente → adicionado
- `nova_reserva.html`: bloco de flash messages ausente → adicionado

### Melhorias implementadas
- `app.py` rota `/api/eventos`: eventos agora retornam data em ISO (`YYYY-MM-DD`) + horário (`T19:00:00`) para exibição correta no calendário
- `/api/eventos`: bloqueios (`BloqueioLab`) agora incluídos como eventos de fundo vermelho, cobrindo todo o intervalo de datas
- `nova_reserva.html`: calendário JS customizado próprio (sem dependência do FullCalendar), com dots coloridos por status, tooltip de detalhes e seleção de data
- `lista.html`: mesmo calendário customizado aplicado no painel, com painel de detalhes do dia clicado exibido abaixo do calendário

## Próximos passos sugeridos
- Melhorar relatórios para coordenador (template existe mas está sem identidade visual)
- Adicionar logs de auditoria
- Filtrar lista de reservas ao clicar num dia do calendário (eliminar redundância)
- Validar campo RA/ID para aceitar apenas números no cadastro
- Refino de UX para mobile

---

📑 Histórico de origem
O projeto foi construído reaproveitando a estrutura de um "Organizador de Tarefas" anterior.
Os arquivos legados (autenticacao.py, main.py, lista.py, opcao_cadastro.py) não são mais usados pelo Flask e podem ser removidos com segurança.