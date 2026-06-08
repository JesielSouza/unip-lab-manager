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

## Como rodar localmente

O banco SQLite local é artefato de desenvolvimento e não deve ser versionado. Use `DATABASE_URL` apontando para um arquivo ignorado, por exemplo `instance/dev.sqlite`.

1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Crie o diretório local de instância:
   ```bash
   mkdir -p instance
   ```

3. Defina o banco local ignorado:
   ```bash
   DB_PATH=$(python -c "from pathlib import Path; print(Path('instance/dev.sqlite').resolve().as_posix())")
   export DATABASE_URL="sqlite:///$DB_PATH"
   ```

4. Aplique as migrations sem o bootstrap automático do app:
   ```bash
   UNIP_SKIP_DB_AUTO_INIT=1 uv run --with-requirements requirements.txt flask --app app db upgrade
   ```

5. Popule dados mínimos de desenvolvimento:
   ```bash
   uv run --with-requirements requirements.txt python scripts/seed_dev.py
   ```

6. Execute o sistema:
   ```bash
   uv run --with-requirements requirements.txt python app.py
   ```

7. Acesse em: `http://localhost:5000`
   - Login padrão: `admin` / `admin123`
   - Logins dev adicionais criados pelo seed:
     - `coord_dev` / `unip123`
     - `prof_dev` / `unip123`
     - `aluno_dev` / `unip123`

### Observações sobre banco local

- `instance/app.sqlite` não é fonte de verdade do projeto.
- Produção deve usar `DATABASE_URL` próprio.
- Arquivos SQLite locais ficam ignorados por `.gitignore`.
- Para recriar o ambiente local, remova o SQLite ignorado e repita os passos de migration + seed.

## Utilitários

- `scripts/seed_dev.py` — popula banco local/ignorado com dados mínimos de desenvolvimento
- `popular_banco.py` — utilitário legado para popular dados de teste
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