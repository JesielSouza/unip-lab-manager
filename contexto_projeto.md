---
# CONTEXTO ATUAL DO PROJETO (10/04/2026)

## Estrutura e Funcionalidades
- Sistema Flask para gestão de reservas de laboratório (UNIP Lab Manager)
- Usuários: super_admin, admin, coordenador, professor, aluno
- Permissões:
  - super_admin: acesso total, gerencia logs de auditoria
  - admin: controla tudo (labs, turmas, usuários, bloqueios, equipamentos), não tem vínculo acadêmico
  - Coordenador: aprova/rejeita reservas apenas das suas turmas (via coordenador_id), vê relatórios
  - Professor: solicita reservas, vê suas turmas, pode ver alunos de suas turmas
  - Aluno: só visualiza reservas aprovadas da sua turma
- Cadastro:
  - Sigla gerada no padrão UNIP: CURSO + SEMESTRE + P + 34 (ex: DS3P34)
  - Campos Turma e Semestre só aparecem para alunos
  - Turmas são criadas automaticamente no cadastro do aluno
- Admin pode criar alunos diretamente (modal com campos de turma/semestre)
- Templates separados para cada contexto (admin, coord, prof, aluno)
- Rotas protegidas por sessão e role

## Como continuar
- Para rodar local: python app.py
- Cria banco e admin automaticamente via inicializar_unidade()
- Login padrão: admin / admin123
- Para não subir este contexto: contexto_projeto.md está no .gitignore

## Arquivos principais
- app.py — rotas, lógica de negócio e inicialização
- models.py — Usuario, ReservaLab, Laboratorio, Turma, BloqueioLab, LogAuditoria, Equipamento
- templates/ — todos os templates abaixo
- static/css/style.css — identidade visual UNIP

## Templates e status
- lista.html ✅ — painel principal com calendário; abas removidas, botões de navegação para Usuários/Labs&Turmas
- nova_reserva.html ✅ — formulário + calendário customizado com dots coloridos
- coordenador_reservas.html ✅ — aprovações pendentes + histórico (filtrado pelas turmas do coord)
- painel_aluno.html ✅ — reservas da turma + avisos de bloqueio
- cadastro.html ✅ — sigla no padrão UNIP corrigido (DS3P34), turno não entra na sigla
- login.html ✅ — copyright atualizado para 2026
- relatorio_reservas.html ✅ — relatório filtrável com estatísticas rápidas
- admin_bloqueios.html ✅ — gestão de bloqueios por período
- admin_config.html ✅ — configurações de labs e turmas (página dedicada)
- admin_perfil.html ✅ — perfil do admin
- admin_usuarios.html ✅ — listagem com modal de criar usuário (suporta aluno com turma)
- admin_equipamentos.html ✅ — gestão de equipamentos por laboratório (CRUD completo)
- admin_logs.html ✅ — visualização de logs de auditoria (super_admin only)
- editar_usuario.html ✅ — select de turmas, toggle de campos por role, campo nova_senha
- ver_alunos.html ✅ — alunos de uma turma específica
- ver_alunos_turmas.html ✅ — sidebar com turmas do professor
- dashboard.html ✅ — analytics: KPIs, top labs, horários de pico, professores ativos
- erro.html ✅ — página de erro genérica (400, 403, 404, 405, 500)
- esqueci_senha.html ✅ — solicitação de redefinição de senha
- redefinir_senha.html ✅ — formulário de nova senha via token

## Models atuais (models.py)
- Usuario: id, nome, role, login, email, senha_hash, turma, turma_id, turma_rel, semestre, cargo, ativo, reset_token, reset_token_expiry, dark_mode
- Laboratorio: id, nome, capacidade, status (ativo|em_manutencao)
- Turma: id, nome, curso, semestre, status (ativa|arquivada), coordenador_id, coordenador
- ReservaLab: id, laboratorio_id, turma_id, professor, disciplina, data, horario_inicio, horario_fim, status, usuario_id
- BloqueioLab: id, laboratorio_id, data_inicio, data_fim, motivo
- LogAuditoria: id, timestamp, usuario_login, acao, descricao, ip
- Equipamento: id, nome, tipo, patrimonio (unique), status (ativo|manutencao|indisponivel), laboratorio_id

## Segurança (revisado em 10/04/2026)
- SECRET_KEY via variável de ambiente
- DATABASE_URL via variável de ambiente
- FLASK_DEBUG via variável de ambiente (false por padrão)
- Login verifica usuario.ativo antes de autenticar
- Rate limiting de login: 5 tentativas / 5 min → bloqueio por 15 min por IP
- Sessão única com token por usuário (impede login simultâneo em múltiplos dispositivos)
- Timeout de inatividade: 20 minutos
- Todas as rotas protegidas com verificação de role
- CSRF via Flask-WTF em todos os formulários
- Senhas com bcrypt
- Fix postgres:// → postgresql:// para Railway

## Deploy (Railway)
- Procfile: web: gunicorn app:app
- runtime.txt: python-3.11.0
- requirements.txt: inclui gunicorn e psycopg2-binary
- .env.example: template de variáveis de ambiente (SECRET_KEY, DATABASE_URL, FLASK_DEBUG, PORT, MAIL_USER, MAIL_PASSWORD)

## Migrations (Alembic / Flask-Migrate)
- Cadeia atual: 2f8e476440bc → f744aaab77c2 → 1d529f18c290 → a3c1e2f5b8d9 (head)
- a3c1e2f5b8d9: cria tabela equipamento (adicionada em 10/04/2026)

## Utilitários
- popular_banco.py — popula banco com dados de teste
- reset_db.py — recria banco do zero
- fix_db.py — normaliza status legados (pode ser removido)

## Arquivos legados (podem ser deletados)
- autenticacao.py, main.py, lista.py, opcao_cadastro.py
- teste_senha.py, verificador_senha.py, migrate.py
- index.py + vercel.json — arquivos do Vercel

## Próximos passos sugeridos
- Validar campo RA para aceitar apenas números no cadastro (validação client-side)
- Refino de UX para mobile
- Deploy no Railway (verificar variáveis de ambiente)
- Testar vínculo coordenador → turma no admin_config e validar filtro
- Implementar dark mode (campo dark_mode já existe no modelo Usuario)
