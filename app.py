from sqlalchemy import or_
from models import ReservaLab, db, Usuario
from flask import Flask, jsonify, render_template, request, redirect, session, url_for, flash
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

# Rota de relatório/filtro para coordenador e admin
@app.route("/relatorio_reservas", methods=["GET", "POST"])
def relatorio_reservas():
    if "usuario" not in session:
        return redirect("/login")
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario:
        session.clear()
        return redirect("/login")
    if usuario.role not in ["coordenador", "admin"]:
        return "Acesso negado", 403

    # Filtros
    turma = request.form.get("turma") if request.method == "POST" else None
    disciplina = request.form.get("disciplina") if request.method == "POST" else None
    periodo = request.form.get("periodo") if request.method == "POST" else None
    status = request.form.get("status") if request.method == "POST" else None

    query = ReservaLab.query
    if turma:
        query = query.filter(ReservaLab.turma.ilike(f"%{turma}%"))
    if disciplina:
        query = query.filter(ReservaLab.disciplina.ilike(f"%{disciplina}%"))
    if periodo:
        query = query.filter(ReservaLab.periodo == periodo)
    if status:
        query = query.filter(ReservaLab.status == status)

    reservas = query.order_by(ReservaLab.data.desc()).all()

    # Para popular selects
    turmas = [t[0] for t in db.session.query(ReservaLab.turma).distinct().all() if t[0]]
    disciplinas = [d[0] for d in db.session.query(ReservaLab.disciplina).distinct().all() if d[0]]
    periodos = [p[0] for p in db.session.query(ReservaLab.periodo).distinct().all() if p[0]]
    status_list = ["pendente", "aprovado", "rejeitado"]

    return render_template(
        "relatorio_reservas.html",
        reservas=reservas,
        turmas=turmas,
        disciplinas=disciplinas,
        periodos=periodos,
        status_list=status_list,
        filtro_turma=turma or "",
        filtro_disciplina=disciplina or "",
        filtro_periodo=periodo or "",
        filtro_status=status or "",
        usuario_logado=usuario.login
    )


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

        # Só loga automaticamente se não estiver autenticado (ou seja, não é admin criando)
        if "usuario" not in session:
            session["usuario"] = login
            return redirect(url_for("painel_unip"))
        else:
            # Se for admin criando, volta para a lista de usuários
            return redirect(url_for("admin_usuarios"))
    # Se for GET (acesso normal), exibe a página
    return render_template("cadastro.html")

@app.route("/api/eventos")
def api_eventos():
    # Buscamos todas as reservas que não foram rejeitadas
    reservas = ReservaLab.query.filter(ReservaLab.status != 'rejeitado').all()
    eventos = []
    
    for r in reservas:
        # Definimos a cor baseada no status ou se é um bloqueio
        cor = "#003366" # Azul UNIP (Aprovado)
        if r.status == 'pendente':
            cor = "#ffc107" # Amarelo (Aguardando)
        if "MANUTENÇÃO" in r.disciplina.upper() or r.status == 'bloqueado':
            cor = "#dc3545" # Vermelho (Bloqueio Admin)

        eventos.append({
            "id": r.id,
            "title": f"{r.laboratorio} - {r.turma}",
            "start": r.data,
            "color": cor,
            "extendedProps": {
                "professor": r.professor,
                "disciplina": r.disciplina,
                "periodo": r.periodo
            }
        })
    return jsonify(eventos)


@app.route("/nova_reserva", methods=["GET", "POST"])
def nova_reserva():
    if "usuario" not in session:
        return redirect("/login")
    
    # Busca o usuário para saber o Role (Admin, Coordenador ou Professor)
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()

    if request.method == "POST":
        laboratorio = request.form.get("laboratorio")
        data = request.form.get("data")
        periodo = request.form.get("periodo")
        turma = request.form.get("turma")
        disciplina = request.form.get("disciplina")

        # 1. VALIDAÇÃO DE CONFLITO (Cruzamento de dados)
        conflito = ReservaLab.query.filter_by(
            laboratorio=laboratorio,
            data=data,
            periodo=periodo
        ).first()

        if conflito:
            return render_template("nova_reserva.html", 
                                 erro=f"Atenção: O {laboratorio} já está ocupado em {data} ({periodo}).", 
                                 usuario=usuario_logado, # Corrigido para bater com o template
                                 reserva=None)

        # 2. DIFERENCIAÇÃO DE STATUS (Admin já nasce aprovado)
        status_inicial = 'pendente'
        if usuario_logado.role == 'admin':
            status_inicial = 'aprovado' # Ou 'confirmado', como preferir chamar

        # 3. CRIAÇÃO DA RESERVA
        nova = ReservaLab(
            laboratorio=laboratorio,
            professor=usuario_logado.login,
            turma=turma,
            disciplina=disciplina,
            data=data,
            periodo=periodo,
            usuario_id=usuario_logado.id,
            status=status_inicial
        )
        
        db.session.add(nova)
        db.session.commit()
        
        flash("Reserva solicitada com sucesso!", "success")
        return redirect("/painel_unip")

    return render_template("nova_reserva.html", reserva=None, usuario=usuario_logado)

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
        # Preencher professor conforme perfil
        if usuario_logado.role == 'professor':
            reserva.professor = usuario_logado.login
            # Sempre que o professor editar, volta para pendente
            reserva.status = 'pendente'
        else:
            reserva.professor = request.form.get("professor", reserva.professor)
            # Coordenador/admin mantém status atual
        reserva.turma = request.form["turma"]
        reserva.disciplina = request.form["disciplina"]
        reserva.data = request.form["data"]
        reserva.periodo = request.form["periodo"]
        db.session.commit()
        return redirect(url_for("painel_unip"))
    
    # Reutilizamos o template 'nova_reserva.html', mas passando a reserva existente
    return render_template("nova_reserva.html", reserva=reserva, usuario=usuario_logado)

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
@app.route("/ver_alunos_turmas/<turma_selecionada>")
def ver_alunos_turmas(turma_selecionada=None):
    if "usuario" not in session:
        return redirect("/login")
    
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if usuario.role != 'professor':
        return "Acesso negado", 403
    
    # 1. Busca as turmas onde o professor tem reservas confirmadas ou pendentes
    turmas_query = db.session.query(ReservaLab.turma).filter_by(usuario_id=usuario.id).distinct().all()
    lista_turmas = [t[0] for t in turmas_query if t[0]]
    
    # 2. Se o professor escolheu uma turma, buscamos os alunos daquela turma
    alunos_da_turma = []
    if turma_selecionada:
        alunos_da_turma = Usuario.query.filter_by(role='aluno', turma=turma_selecionada).all()
    
    return render_template("ver_alunos_turmas.html", 
                           turmas=lista_turmas, 
                           alunos=alunos_da_turma, 
                           turma_ativa=turma_selecionada)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(port=5000, host='localhost', debug=True)