from app import app
from models import db, Usuario
import bcrypt

with app.app_context():
    db.create_all()
    
    # Verificar se já existe um admin
    admin_existente = Usuario.query.filter_by(role='admin').first()
    if not admin_existente:
        # Criar admin inicial
        senha_hash = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt()).decode()
        admin = Usuario(
            login='admin',
            email='admin@unip.com',
            senha_hash=senha_hash,
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin criado: login=admin, senha=admin123")
    else:
        print("Admin já existe.")
    
    print("Banco criado com sucesso!")
