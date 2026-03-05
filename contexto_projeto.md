---
# CONTEXTO ATUAL DO PROJETO (05/03/2026)

## Estrutura e Funcionalidades
- Sistema Flask para gestão de reservas de laboratório (UNIP Lab Manager)
- Usuários: Admin, Coordenador, Professor, Aluno
- Permissões:
  - Admin: controla tudo, não tem vínculo acadêmico
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
- models.py — Usuario, ReservaLab, Laboratorio, Turma, BloqueioLab
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
- editar_usuario.html ✅ — select de turmas, toggle de campos por role, campo nova_senha
- ver_alunos.html ✅ — alunos de uma turma específica
- ver_alunos_turmas.html ✅ — sidebar com turmas do professor

## Models atuais (models.py)
- Usuario: id, nome, role, login, email, senha_hash, turma, turma_id, turma_rel, semestre, cargo, ativo
- Laboratorio: id, nome, capacidade, status (ativo|em_manutencao)
- Turma: id, nome, curso, semestre, status (ativa|arquivada), coordenador_id, coordenador
- ReservaLab: id, laboratorio_id, turma_id, professor, disciplina, data, horario_inicio, horario_fim, status, usuario_id
- BloqueioLab: id, laboratorio_id, data_inicio, data_fim, motivo

## Segurança (revisado em 05/03/2026)
- SECRET_KEY via variável de ambiente
- DATABASE_URL via variável de ambiente
- FLASK_DEBUG via variável de ambiente (false por padrão)
- Login verifica usuario.ativo antes de autenticar
- Todas as rotas protegidas com verificação de role
- Senhas com bcrypt
- Fix postgres:// → postgresql:// para Railway

## Deploy (Railway)
- Procfile: web: gunicorn app:app
- runtime.txt: python-3.11.0
- requirements.txt: inclui gunicorn e psycopg2-binary
- .env.example: template de variáveis de ambiente

## Utilitários
- popular_banco.py — popula banco com dados de teste
- reset_db.py — recria banco do zero
- fix_db.py — normaliza status legados (pode ser removido)
- index.py + vercel.json — arquivos do Vercel (podem ser removidos)

## Arquivos legados (podem ser deletados)
- autenticacao.py, main.py, lista.py, opcao_cadastro.py
- teste_senha.py, verificador_senha.py, migrate.py

## Próximos passos sugeridos
- Testar vínculo coordenador → turma no admin_config e validar filtro
- Validar campo RA para aceitar apenas números no cadastro
- Logs de auditoria
- Refino de UX para mobile
- Deploy no Railway