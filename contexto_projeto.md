---
# CONTEXTO ATUAL DO PROJETO (04/03/2026)

## Estrutura e Funcionalidades
- Sistema Flask para gestão de reservas de laboratório (UNIP Lab Manager)
- Usuários: Admin, Coordenador, Professor, Aluno
- Permissões:
  - Admin: controla tudo, não tem vínculo acadêmico, edita apenas login/email/senha
  - Coordenador: aprova/rejeita reservas, vê todas as turmas, acessa relatório
  - Professor: solicita reservas, vê suas turmas, pode ver alunos de suas turmas
  - Aluno: só visualiza reservas aprovadas da sua turma
- Cadastro:
  - Campos Turma e Semestre só aparecem para alunos
  - Professores e coordenadores não preenchem esses campos
  - Turmas são criadas automaticamente no cadastro do aluno (busca ou cria)
- Templates separados para cada contexto (admin, coord, prof, aluno)
- Rotas protegidas por sessão e role
- Admin não pode ser editado como usuário acadêmico

## Como continuar
- Para rodar: python app.py (cria banco e admin automaticamente via inicializar_unidade())
- Para não subir este contexto: contexto_projeto.md está no .gitignore
- Login padrão: admin / admin123

## Arquivos principais
- app.py — rotas, lógica de negócio e inicialização
- models.py — Usuario, ReservaLab, Laboratorio, Turma, BloqueioLab
- templates/ — todos os templates abaixo
- static/css/style.css — identidade visual UNIP

## Templates e status
- lista.html ✅ — painel principal com calendário, tabs de reservas/usuários, link para labs&turmas e relatório
- nova_reserva.html ✅ — formulário + calendário customizado com dots coloridos
- coordenador_reservas.html ✅ — aprovações pendentes + histórico
- painel_aluno.html ✅ — reservas da turma + avisos de bloqueio
- cadastro.html ✅ — cadastro com geração de sigla de turma (bug do turno corrigido)
- login.html ✅ — tela de login institucional
- relatorio_reservas.html ✅ — relatório filtrável com estatísticas rápidas
- admin_bloqueios.html ✅ — gestão de bloqueios por período
- admin_config.html ✅ — configurações de labs (editar/status manutenção) e turmas (coordenador/arquivar/alunos)
- admin_perfil.html ✅ — perfil do admin com identidade UNIP
- admin_usuarios.html ✅ — listagem de usuários com badges de role
- editar_usuario.html ✅ — edição de usuário com toggle de campos por role
- ver_alunos.html ✅ — alunos de uma turma específica
- ver_alunos_turmas.html ✅ — sidebar com todas as turmas do professor

## Models atuais (models.py)
- Usuario: id, nome, role, login, email, senha_hash, turma, turma_id, turma_rel, semestre, cargo, ativo
- Laboratorio: id, nome, capacidade, status (ativo|em_manutencao)
- Turma: id, nome, curso, semestre, status (ativa|arquivada), coordenador_id, coordenador
- ReservaLab: id, laboratorio_id, turma_id, professor, disciplina, data, horario_inicio, horario_fim, status, usuario_id
- BloqueioLab: id, laboratorio_id, data_inicio, data_fim, motivo

## Utilitários
- popular_banco.py — popula banco com dados de teste (atualizado para modelo atual)
- reset_db.py — recria banco do zero (emergência)
- fix_db.py — normaliza status legados (uso único, pode ser removido)

## Arquivos legados (podem ser deletados)
- autenticacao.py, main.py, lista.py, opcao_cadastro.py
- teste_senha.py, verificador_senha.py, migrate.py

## Próximos passos sugeridos
- Filtrar lista de reservas ao clicar num dia do calendário
- Validar campo RA/ID para aceitar apenas números no cadastro
- Logs de auditoria
- Refino de UX para mobile
- Testar fluxo completo após revisão de todos os templates