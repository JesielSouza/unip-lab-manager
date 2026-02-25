from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), nullable=False)
    senha_hash = db.Column(db.String(128), nullable=False)
    tarefas = db.relationship('Tarefa', backref='usuario', lazy=True)

class ReservaLab(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    laboratorio = db.Column(db.String(50), nullable=False)
    professor = db.Column(db.String(100), nullable=False)
    turma = db.Column(db.String(50), nullable=False)
    disciplina = db.Column(db.String(100), nullable=False)
    data = db.Column(db.String(10), nullable=False) # Armazena YYYY-MM-DD
    periodo = db.Column(db.String(20), nullable=False) # Manhã, Tarde, Noite
    
    # Vinculamos ao usuário que fez o registro
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))