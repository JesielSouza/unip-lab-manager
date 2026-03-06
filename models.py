from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
from datetime import datetime

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
    turma_rel = db.relationship('Turma', foreign_keys=[turma_id], backref='usuarios')
    semestre = db.Column(db.String(20), nullable=True) # Preenchido se Aluno
    cargo = db.Column(db.String(50), nullable=True)  # Preenchido se Colaborador (Prof/Coord)
    
    # Status de segurança (para evitar a 'sacanagem' de professores e coordenadores)
    ativo = db.Column(db.Boolean, default=True)

    # Reset de senha
    reset_token = db.Column(db.String(64), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)

class Laboratorio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    capacidade = db.Column(db.Integer, nullable=False) # Quantidade máxima de pessoas que o laboratório suporta
    status = db.Column(db.String(20), default='ativo', nullable=False) # ativo | em_manutencao

class Turma(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False) # Ex: ADS3A
    curso = db.Column(db.String(100), nullable=False)
    semestre = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='ativa', nullable=False) # ativa | arquivada
    coordenador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    coordenador = db.relationship('Usuario', foreign_keys=[coordenador_id], backref='turmas_coordenadas')

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

class LogAuditoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_login = db.Column(db.String(50), nullable=False)   # quem fez a ação
    acao = db.Column(db.String(50), nullable=False)            # LOGIN, LOGOUT, CRIAR_RESERVA, etc.
    descricao = db.Column(db.String(255), nullable=False)      # detalhe legível
    ip = db.Column(db.String(45), nullable=True)               # IPv4 ou IPv6