from app import app, db, ReservaLab


"""
Script de normalização de status legado para o novo padrão interno:

- 'aprovado'      -> 'approved'
- 'rejeitado'     -> 'rejected'
- 'pendente'/'Pendente' -> 'pending'
- 'bloqueado'     -> 'blocked'
"""

with app.app_context():
    alteracoes = 0

    # 1. Converte 'aprovado' -> 'approved'
    for r in ReservaLab.query.filter_by(status="aprovado").all():
        r.status = "approved"
        alteracoes += 1

    # 2. Converte 'rejeitado' -> 'rejected'
    for r in ReservaLab.query.filter_by(status="rejeitado").all():
        r.status = "rejected"
        alteracoes += 1

    # 3. Converte 'pendente' e 'Pendente' -> 'pending'
    for r in ReservaLab.query.filter(ReservaLab.status.in_(["pendente", "Pendente"])).all():
        r.status = "pending"
        alteracoes += 1

    # 4. Converte 'bloqueado' -> 'blocked'
    for r in ReservaLab.query.filter_by(status="bloqueado").all():
        r.status = "blocked"
        alteracoes += 1

    db.session.commit()
    print(f"✅ Banco sincronizado. Registros atualizados: {alteracoes}")