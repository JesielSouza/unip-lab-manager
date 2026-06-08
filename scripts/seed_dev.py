"""Seed textual para ambiente local/dev do UNIP Lab Manager.

Uso recomendado:
    DATABASE_URL="sqlite:///$PWD/instance/dev.sqlite" \
      uv run --with-requirements requirements.txt python scripts/seed_dev.py

Segurança:
- Requer DATABASE_URL explícito.
- Recusa executar contra instance/app.sqlite para evitar sujar banco legado.
- Cria apenas dados dev idempotentes.
"""
from pathlib import Path
from urllib.parse import unquote, urlparse
import os
import sys


def _sqlite_path_from_url(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite:///"):
        return None
    parsed = urlparse(database_url)
    raw_path = unquote(parsed.path)
    # SQLAlchemy accepts sqlite:///C:/... on Windows; urlparse exposes it as /C:/...
    if len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        raw_path = raw_path[1:]
    # Em Git Bash, sqlite:////c/... chega como /c/...
    return Path(raw_path).resolve()


def _guard_database_url() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERRO: defina DATABASE_URL explicitamente para um banco local/ignorado.", file=sys.stderr)
        sys.exit(2)

    sqlite_path = _sqlite_path_from_url(database_url)
    if sqlite_path is None:
        return

    repo_root = Path(__file__).resolve().parents[1]
    legacy_path = (repo_root / "instance" / "app.sqlite").resolve()
    if sqlite_path == legacy_path:
        print("ERRO: scripts/seed_dev.py não executa contra instance/app.sqlite.", file=sys.stderr)
        print("Use um banco ignorado, por exemplo instance/dev.sqlite.", file=sys.stderr)
        sys.exit(2)


_guard_database_url()

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import bcrypt  # noqa: E402
from app import app, db  # noqa: E402
from models import Equipamento, Laboratorio, Turma, Usuario  # noqa: E402


def gerar_senha(senha_plana: str) -> str:
    return bcrypt.hashpw(senha_plana.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def get_or_create(model, defaults=None, **filters):
    obj = model.query.filter_by(**filters).first()
    if obj:
        return obj, False
    values = dict(filters)
    if defaults:
        values.update(defaults)
    obj = model(**values)
    db.session.add(obj)
    return obj, True


with app.app_context():
    senha_padrao = gerar_senha("unip123")

    turma_ads, _ = get_or_create(
        Turma,
        nome="ADS1P30",
        defaults={"curso": "Análise e Desenvolvimento de Sistemas", "semestre": "1º Semestre", "status": "ativa"},
    )
    get_or_create(
        Turma,
        nome="CC3A18",
        defaults={"curso": "Ciência da Computação", "semestre": "3º Semestre", "status": "ativa"},
    )

    lab_1, _ = get_or_create(Laboratorio, nome="Laboratório 1", defaults={"capacidade": 25, "status": "ativo"})
    lab_2, _ = get_or_create(Laboratorio, nome="Laboratório 2/Provas Online", defaults={"capacidade": 25, "status": "ativo"})

    usuarios = [
        {
            "login": "coord_dev",
            "nome": "Coordenador Dev",
            "email": "coord.dev@example.local",
            "role": "coordenador",
            "cargo": "coordenador",
        },
        {
            "login": "prof_dev",
            "nome": "Professor Dev",
            "email": "prof.dev@example.local",
            "role": "professor",
            "cargo": "professor",
        },
        {
            "login": "aluno_dev",
            "nome": "Aluno Dev",
            "email": "aluno.dev@example.local",
            "role": "aluno",
            "turma": turma_ads.nome,
            "turma_id": turma_ads.id,
            "semestre": turma_ads.semestre,
        },
    ]

    for dados in usuarios:
        login = dados.pop("login")
        get_or_create(
            Usuario,
            login=login,
            defaults={"senha_hash": senha_padrao, "ativo": True, "dark_mode": False, **dados},
        )

    get_or_create(
        Equipamento,
        patrimonio="DEV-CPU-001",
        defaults={"nome": "Desktop Dev 01", "tipo": "Desktop", "status": "ativo", "laboratorio_id": lab_1.id},
    )
    get_or_create(
        Equipamento,
        patrimonio="DEV-NB-001",
        defaults={"nome": "Notebook Dev 01", "tipo": "Notebook", "status": "ativo", "laboratorio_id": lab_2.id},
    )

    db.session.commit()

print("Seed dev concluído.")
print("Logins dev:")
print("- admin / admin123 (criado pelo bootstrap do app)")
print("- coord_dev / unip123")
print("- prof_dev / unip123")
print("- aluno_dev / unip123")
