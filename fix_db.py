from app import app, db, ReservaLab

with app.app_context():
    # 1. Converte 'aprovado' para 'approved'
    reservas_aprovadas = ReservaLab.query.filter_by(status='aprovado').all()
    for r in reservas_aprovadas:
        r.status = 'approved'
    
    # 2. Garante que 'pendente' está escrito corretamente (minúsculo)
    reservas_pendentes = ReservaLab.query.filter_by(status='Pendente').all()
    for r in reservas_pendentes:
        r.status = 'pendente'

    db.session.commit()
    print("✅ Banco de dados sincronizado com o novo layout!")