from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash

db = SQLAlchemy()

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False) # aluno ou colaborador
    login = db.Column(db.String(20), unique=True, nullable=False) # RA ou ID
    email = db.Column(db.String(120), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    
    # Campos Específicos
    turma = db.Column(db.String(20), nullable=True)  # Preenchido se Aluno
    turma_id = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=True) # Relacionamento com Turma
    turma_rel = db.relationship('Turma', backref='usuarios') # Relacionamento para facilitar consultas
    semestre = db.Column(db.String(20), nullable=True) # Preenchido se Aluno
    cargo = db.Column(db.String(50), nullable=True)  # Preenchido se Colaborador (Prof/Coord)
    
    # Status de segurança (para evitar a 'sacanagem' de professores e coordenadores)
    ativo = db.Column(db.Boolean, default=True)

class Laboratorio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    capacidade = db.Column(db.Integer, nullable=False) # Quantidade máxima de pessoas que o laboratório suporta

class Turma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False) # Ex: 1A, 2B
    curso = db.Column(db.String(100), nullable=False)           # O que faltava
    semestre = db.Column(db.String(20), nullable=False)        # Tua observação: Semestre

class ReservaLab(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Agora usamos chaves estrangeiras para garantir dados limpos
    laboratorio_id = db.Column(db.Integer, db.ForeignKey('laboratorio.id'), nullable=False)
    turma_id = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=False)
    
    professor = db.Column(db.String(100))
    disciplina = db.Column(db.String(100))
    data = db.Column(db.String(10), nullable=False)
    
    # Novos campos de horário real (Ponto 3 e 5)
    horario_inicio = db.Column(db.String(5), nullable=False) # Ex: "19:30"
    horario_fim = db.Column(db.String(5), nullable=False)    # Ex: "21:30"
    
    # Status padronizado (pending, pre_approved, approved, rejected, blocked)
    status = db.Column(db.String(20), default='pending')
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

    # Relacionamentos para facilitar o uso no HTML
    lab = db.relationship('Laboratorio', backref='reservas')
    turma_rel = db.relationship('Turma', backref='reservas')

class BloqueioLab(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    laboratorio_id = db.Column(db.Integer, db.ForeignKey('laboratorio.id'))
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    motivo = db.Column(db.String(100), default="Período de Provas")

    # Relacionamento com Laboratorio para uso em templates (b.lab_rel.nome)
    lab_rel = db.relationship('Laboratorio', backref='bloqueios')