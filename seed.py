"""from app import app, db
from models import Laboratorio, Turma

with app.app_context():
    # Cadastrando Laboratórios
    if not Laboratorio.query.first():
        labs = [
            Laboratorio(nome="Laboratório 01", capacidade=40),
            Laboratorio(nome="Laboratório 02", capacidade=30),
            Laboratorio(nome="Auditório Principal", capacidade=100)
        ]
        db.session.add_all(labs)
    
    # Cadastrando Turmas
    if not Turma.query.first():
        turmas = [
            Turma(nome="ADS 1A", curso="Análise de Sistemas", semestre="1º Semestre"),
            Turma(nome="DIR 3B", curso="Direito", semestre="3º Semestre"),
            Turma(nome="ADM 5A", curso="Administração", semestre="5º Semestre")
        ]
        db.session.add_all(turmas)
    
    db.session.commit()
    print("✅ Labs e Turmas cadastrados com sucesso!")"""