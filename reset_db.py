from app import app, db
from models import Usuario
import bcrypt

with app.app_context():
    # O comando abaixo cria o arquivo .db do zero com a coluna turma_id
    db.create_all()

    # Agora sim ele tenta buscar ou criar
    if not Usuario.query.filter_by(login="admin").first():
        senha_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        admin = Usuario(
            login="admin",
            email="admin@unip.br",
            senha_hash=senha_hash,
            role="admin",
            turma=None,
            semestre=None,
            cargo="administrador"
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin criado com sucesso!")
    else:
        print("ℹ️ Admin já existe.")