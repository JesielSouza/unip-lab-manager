from models import ReservaLab, db, Usuario
from flask import Flask, render_template, request, redirect, session, url_for
import json, os
import bcrypt
from flask_migrate import Migrate

app = Flask(__name__)
app.secret_key = "chave-secreta-123"  # Necessário para usar sessões

# CONFIGURAÇÃO DO BANCO SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "instance", "app.sqlite")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

migrate = Migrate(app, db)

# Inicia o banco com o app
from models import db, Usuario
db.init_app(app)

def sugerir_categoria(nome_tarefa):
    nome = nome_tarefa.lower()
    if any(palavra in nome for palavra in ["pagar", "comprar", "boleto", "dinheiro", "cartão"]):
        return "Financeiro", "Alta"
    if any(palavra in nome for palavra in ["estudar", "ler", "curso", "prova", "faculdade"]):
        return "Estudos", "Média"
    if any(palavra in nome for palavra in ["treino", "academia", "correr", "médico", "saúde"]):
        return "Saúde", "Alta"
    return "Geral", "Baixa"


# Utilitário: carregar usuários
def carregar_usuarios():
    try:
        with open("usuarios.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Utilitário: salvar usuários
def salvar_usuarios(usuarios):
    with open("usuarios.json", "w", encoding="utf-8") as f:
        json.dump(usuarios, f, indent=4, ensure_ascii=False)

@app.route("/")
def index():
    if "usuario" in session:
        return redirect("/painel_unip")
    return redirect("/login")

# Rota de login (GET e POST)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login = request.form["login"]
        senha = request.form["senha"]
        usuario = Usuario.query.filter_by(login=login).first()
        if not usuario:
            return "Usuário não encontrado", 404

        if bcrypt.checkpw(senha.encode(), usuario.senha_hash.encode()):
            session["usuario"] = usuario.login
            return redirect("/painel_unip")
        else:
            return "Senha Incorreta", 401
    return render_template("login.html")

# Rota unificada de cadastro
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        login = request.form["login"]
        email = request.form["email"]
        senha = request.form["senha"]
        role = request.form.get("role", "aluno")  # Default to aluno
        turma = request.form.get("turma")
        semestre = request.form.get("semestre")

        usuario_existente = Usuario.query.filter_by(login=login).first()
        if usuario_existente:
            return "⚠️ Usuário já existe", 400
        
        # Gerando o Hash da senha
        senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
        
        novo_usuario = Usuario(
            login=login, 
            email=email, 
            senha_hash=senha_hash,
            role=role,
            turma=turma,
            semestre=semestre
        )

        db.session.add(novo_usuario)
        db.session.commit()

        session["usuario"] = login
        return redirect(url_for("painel_unip"))
    
    # Se for GET (acesso normal), exibe a página
    return render_template("cadastro.html")

@app.route("/nova_reserva", methods=["GET", "POST"])
def nova_reserva():
    if "usuario" not in session:
        return redirect("/login")

    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario:
        session.clear()
        return redirect("/login")

    # Alunos não podem criar reservas
    if usuario.role == 'aluno':
        return "Acesso negado: Alunos não podem solicitar reservas.", 403

    if request.method == "POST":
        laboratorio = request.form["laboratorio"]
        professor = request.form["professor"]
        turma = request.form["turma"]
        disciplina = request.form["disciplina"]
        data = request.form["data"]
        periodo = request.form["periodo"]

        # Status baseado no role: coordenadores e admins aprovam automaticamente
        status = 'aprovado' if usuario.role in ['coordenador', 'admin'] else 'pendente'

        nova = ReservaLab(
            laboratorio=laboratorio,
            professor=professor,
            turma=turma,
            disciplina=disciplina,
            data=data,
            periodo=periodo,
            status=status,
            usuario_id=usuario.id
        )

        db.session.add(nova)
        db.session.commit()

        return redirect("/painel_unip")

    return render_template("nova_reserva.html", reserva=None)



@app.route("/painel_unip")
def painel_unip():
    if "usuario" not in session:
        return redirect("/login")

    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario:
        session.clear()
        return redirect("/login")

    if usuario.role == 'aluno':
        # Alunos veem apenas suas reservas aprovadas da sua turma
        reservas = ReservaLab.query.filter_by(status='aprovado', turma=usuario.turma).all()
    elif usuario.role == 'professor':
        # Professores veem suas próprias reservas
        reservas = ReservaLab.query.filter_by(usuario_id=usuario.id).all()
    else:  # coordenador ou admin
        # Veem todas as reservas
        reservas = ReservaLab.query.all()

    return render_template("lista.html", reservas=reservas, usuario=usuario.login, role=usuario.role, usuario_id=usuario.id)

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar_reserva(id):
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario_logado:
        session.clear()
        return redirect("/login")
    
    reserva = ReservaLab.query.get_or_404(id)
    
    # Verificar permissões: coordenadores/admin podem editar qualquer, professores apenas suas
    if usuario_logado.role not in ['coordenador', 'admin'] and reserva.usuario_id != usuario_logado.id:
        return "Acesso negado", 403
    
    if request.method == "POST":
        reserva.laboratorio = request.form["laboratorio"]
        reserva.professor = request.form["professor"]
        reserva.turma = request.form["turma"]
        reserva.disciplina = request.form["disciplina"]
        reserva.data = request.form["data"]
        reserva.periodo = request.form["periodo"]
        
        db.session.commit()
        return redirect(url_for("painel_unip"))
    
    # Reutilizamos o template 'nova_reserva.html', mas passando a reserva existente
    return render_template("nova_reserva.html", reserva=reserva)

@app.route("/excluir/<int:id>")
def excluir(id):
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario_logado:
        session.clear()
        return redirect("/login")
    
    reserva = ReservaLab.query.get(id)
    if reserva:
        # Verificar permissões
        if usuario_logado.role not in ['coordenador', 'admin'] and reserva.usuario_id != usuario_logado.id:
            return "Acesso negado", 403
        db.session.delete(reserva)
        db.session.commit()
    
    return redirect(url_for("painel_unip"))

@app.route("/admin/usuarios")
def admin_usuarios():
    if "usuario" not in session:
        return redirect("/login")
    
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario:
        session.clear()
        return redirect("/login")
    
    if usuario.role != 'admin':
        return "Acesso negado", 403
    
    usuarios = Usuario.query.all()
    return render_template("admin_usuarios.html", usuarios=usuarios, usuario_logado=usuario.login)
    
    user = Usuario.query.get_or_404(id)
    
    if request.method == "POST":
        user.login = request.form["login"]
        user.email = request.form["email"]
        user.role = request.form["role"]
        user.turma = request.form.get("turma")
        user.semestre = request.form.get("semestre")
        db.session.commit()
        return redirect(url_for("admin_usuarios"))
    
    return render_template("editar_usuario.html", user=user, usuario_logado=usuario_logado.login)

@app.route("/admin/excluir_usuario/<int:id>")
def excluir_usuario(id):
    if "usuario" not in session:
        return redirect("/login")
    
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario_logado:
        session.clear()
        return redirect("/login")
    
    if usuario_logado.role != 'admin':
        return "Acesso negado", 403
    
    user = Usuario.query.get(id)
    if user and user.role != 'admin':  # Não excluir admin
        db.session.delete(user)
        db.session.commit()
    
    return redirect(url_for("admin_usuarios"))

@app.route("/admin/editar_usuario/<int:id>", methods=["GET", "POST"])
def editar_usuario(id):
    if "usuario" not in session:
        return redirect("/login")
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario_logado:
        session.clear()
        return redirect("/login")
    if usuario_logado.role != 'admin':
        return "Acesso negado", 403
    user = Usuario.query.get_or_404(id)
    if request.method == "POST":
        user.login = request.form["login"]
        user.email = request.form["email"]
        user.role = request.form["role"]
        user.turma = request.form.get("turma")
        user.semestre = request.form.get("semestre")
        db.session.commit()
        return redirect(url_for("admin_usuarios"))
    return render_template("editar_usuario.html", user=user, usuario_logado=usuario_logado.login)

@app.route("/admin/perfil", methods=["GET", "POST"])
def admin_perfil():
    if "usuario" not in session:
        return redirect("/login")
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario or usuario.role != 'admin':
        session.clear()
        return redirect("/login")
    if request.method == "POST":
        usuario.login = request.form["login"]
        usuario.email = request.form["email"]
        nova_senha = request.form.get("nova_senha")
        if nova_senha:
            usuario.senha_hash = bcrypt.hashpw(nova_senha.encode(), bcrypt.gensalt()).decode()
        db.session.commit()
        return redirect(url_for("admin_perfil"))
    return render_template("admin_perfil.html", usuario=usuario)

@app.route("/coordenador/reservas")
def coordenador_reservas():
    if "usuario" not in session:
        return redirect("/login")
    
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario:
        session.clear()
        return redirect("/login")
    
    if usuario.role not in ['coordenador', 'admin']:
        return "Acesso negado", 403
    
    reservas_pendentes = ReservaLab.query.filter_by(status='pendente').all()
    todas_reservas = ReservaLab.query.all()
    
    return render_template("coordenador_reservas.html", reservas_pendentes=reservas_pendentes, todas_reservas=todas_reservas, usuario_logado=usuario.login)

@app.route("/aprovar_reserva/<int:id>")
def aprovar_reserva(id):
    if "usuario" not in session:
        return redirect("/login")
    
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario:
        session.clear()
        return redirect("/login")
    
    if usuario.role not in ['coordenador', 'admin']:
        return "Acesso negado", 403
    
    reserva = ReservaLab.query.get(id)
    if reserva:
        reserva.status = 'aprovado'
        db.session.commit()
    
    return redirect(url_for("coordenador_reservas"))

@app.route("/rejeitar_reserva/<int:id>")
def rejeitar_reserva(id):
    if "usuario" not in session:
        return redirect("/login")
    
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario:
        session.clear()
        return redirect("/login")
    
    if usuario.role not in ['coordenador', 'admin']:
        return "Acesso negado", 403
    
    reserva = ReservaLab.query.get(id)
    if reserva:
        reserva.status = 'rejeitado'
        db.session.commit()
    
    return redirect(url_for("coordenador_reservas"))

@app.route("/ver_alunos_turmas")
def ver_alunos_turmas():
    if "usuario" not in session:
        return redirect("/login")
    
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario:
        session.clear()
        return redirect("/login")
    
    if usuario.role != 'professor':
        return "Acesso negado", 403
    
    # Obter turmas únicas das reservas do professor
    turmas = db.session.query(ReservaLab.turma).filter_by(usuario_id=usuario.id).distinct().all()
    turmas = [t[0] for t in turmas if t[0]]
    
    return render_template("ver_alunos_turmas.html", turmas=turmas, usuario_logado=usuario.login)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(port=5000, host='localhost', debug=True)