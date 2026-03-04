# 🏫 UNIP Lab Manager

Sistema Flask para gestão de reservas de laboratórios de informática da UNIP.

## Funcionalidades
- Controle de usuários: Admin, Coordenador, Professor, Aluno
- Permissões por perfil (aprovação em dois níveis, visualização restrita)
- Cadastro de reservas por professores com aprovação do coordenador
- Alunos só visualizam reservas aprovadas da sua turma
- Admin gerencia usuários, laboratórios e turmas
- Calendário visual de reservas e bloqueios
- Relatório filtrável para coordenador
- Bloqueio de laboratórios por período (manutenção, provas)

## Como rodar

1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Execute o sistema (cria o banco e o admin automaticamente):
   ```bash
   python app.py
   ```

3. Acesse em: `http://localhost:5000`
   - Login padrão: `admin` / `admin123`

## Utilitários

- `popular_banco.py` — popula o banco com dados de teste (coord, professor, aluno)
- `reset_db.py` — recria o banco do zero e garante o admin (emergência)
- `fix_db.py` — normaliza status legados para o padrão atual (uso único)

## Estrutura principal

```
app.py          — rotas e lógica de negócio
models.py       — models: Usuario, ReservaLab, Laboratorio, Turma, BloqueioLab
templates/      — HTMLs por contexto (lista, nova_reserva, coordenador, aluno, admin)
static/css/     — identidade visual UNIP
```

## Perfis de acesso

| Perfil       | Pode fazer                                              |
|--------------|---------------------------------------------------------|
| Admin        | Gerencia usuários, labs, turmas e bloqueios             |
| Coordenador  | Aprova/rejeita reservas, vê relatórios                  |
| Professor    | Cria e acompanha suas reservas                          |
| Aluno        | Visualiza reservas aprovadas da sua turma               |

## Contribuindo
Consulte o `contexto_projeto.md` (não versionado) para histórico detalhado e próximos passos.