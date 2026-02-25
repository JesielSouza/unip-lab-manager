from models import ReservaLab, db, Usuario
from flask import Flask, render_template, request, redirect, session, url_for
import json, os
import bcrypt

app = Flask(__name__)
app.secret_key = "chave-secreta-123"  # Necessário para usar sessões

# CONFIGURAÇÃO DO BANCO SQLite
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "instance", "app.sqlite")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# Inicia o banco com o app
from models import db, Usuario, Tarefa
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
        return redirect("/tarefas")
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
            return redirect("/tarefas")
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

        usuario_existente = Usuario.query.filter_by(login=login).first()
        if usuario_existente:
            return "⚠️ Usuário já existe", 400
        
        # Gerando o Hash da senha
        senha_hash = bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()
        
        novo_usuario = Usuario(
            login=login, 
            email=email, 
            senha_hash=senha_hash
        )

        db.session.add(novo_usuario)
        db.session.commit()

        session["usuario"] = login
        return redirect(url_for("tarefas"))
    
    # Se for GET (acesso normal), exibe a página
    return render_template("cadastro.html")

@app.route("/nova_reserva", methods=["GET", "POST"])
def nova_reserva():
    if "usuario" not in session:
        return redirect("/login")

    usuario = Usuario.query.filter_by(login=session["usuario"]).first()

    if request.method == "POST":
        laboratorio = request.form["laboratorio"]
        professor = request.form["professor"]
        turma = request.form["turma"]
        disciplina = request.form["disciplina"]
        data = request.form["data"]
        periodo = request.form["periodo"]

        nova = ReservaLab(
            laboratorio=laboratorio,
            professor=professor,
            turma=turma,
            disciplina=disciplina,
            data=data,
            periodo=periodo,
            usuario_id=usuario.id
        )

        db.session.add(nova)
        db.session.commit()

        return redirect("/painel_unip")

    return render_template("nova_reserva.html", tarefa=None)



@app.route("/tarefas")
def tarefas():
    if "usuario" not in session:
        return redirect("/login")

    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    tarefas = Tarefa.query.filter_by(usuario_id=usuario.id).all()

    return render_template("lista.html", tarefas=tarefas, usuario=usuario.login)

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar_tarefa(id):
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    tarefa = Tarefa.query.get_or_404(id)
    
    if request.method == "POST":
        tarefa.nome = request.form["nome"]
        tarefa.prazo = request.form["prazo"]
        tarefa.prioridade = request.form["prioridade"]
        tarefa.categoria = request.form["categoria"]
        
        db.session.commit()
        return redirect(url_for("tarefas"))
    
    # Reutilizamos o template 'nova.html', mas passando a tarefa existente
    return render_template("nova.html", tarefa=tarefa)

@app.route("/excluir/<int:id>")
def excluir(id):
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    tarefa = Tarefa.query.get(id)
    if tarefa:
        db.session.delete(tarefa)
        db.session.commit()
    
    return redirect(url_for("tarefas"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")



if __name__ == "__main__":
    app.run(port=5000, host='localhost', debug=True)