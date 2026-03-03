from sqlalchemy import or_
from models import ReservaLab, db, Usuario, Laboratorio, Turma, BloqueioLab
from flask import Flask, jsonify, render_template, request, redirect, session, url_for, flash
from datetime import datetime
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

def inicializar_unidade():
    # --- PARTE 1: LABORATÓRIOS ---
    labs_predefinidos = [
        {"nome": "Laboratório 1", "capacidade": 25},
        {"nome": "Laboratório 2", "capacidade": 25},
        {"nome": "Laboratório 8", "capacidade": 25},
        {"nome": "Laboratório 9", "capacidade": 26},
        {"nome": "Laboratório Elétrica 2", "capacidade": 9},
        {"nome": "Laboratório Elétrica 3", "capacidade": 18}
    ]
    
    nomes_oficiais = [l["nome"] for l in labs_predefinidos]

    # Limpa nomes que não deveriam estar lá (duplicatas)
    Laboratorio.query.filter(~Laboratorio.nome.in_(nomes_oficiais)).delete(synchronize_session=False)

    for lab_data in labs_predefinidos:
        lab = Laboratorio.query.filter_by(nome=lab_data["nome"]).first()
        if lab:
            if lab.capacidade != lab_data["capacidade"]:
                lab.capacidade = lab_data["capacidade"]
        else:
            db.session.add(Laboratorio(nome=lab_data["nome"], capacidade=lab_data["capacidade"]))

    # --- PARTE 2: ADMINISTRADOR (Baseado no seu create_admin.py) ---
    if not Usuario.query.filter_by(login="admin").first():
        # Usando a lógica do seu arquivo create_admin.py
        senha_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        admin = Usuario(
            login="admin",
            email="admin@unip.br",
            senha_hash=senha_hash,
            role="admin",
            turma=None,
            semestre=None,
            cargo="administrador"
        )
        db.session.add(admin)
        print("✅ Admin padrão criado!")

    db.session.commit()
    print("🚀 Sistema inicializado com sucesso!")

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
    status = request.form.get("status") if request.method == "POST" else None

    query = ReservaLab.query
    if turma:
        # Filtra pelo nome da turma associada
        query = query.join(ReservaLab.turma_rel).filter(Turma.nome.ilike(f"%{turma}%"))
    if disciplina:
        query = query.filter(ReservaLab.disciplina.ilike(f"%{disciplina}%"))
    if status:
        query = query.filter(ReservaLab.status == status)

    reservas = query.order_by(ReservaLab.data.desc()).all()

    # Para popular selects
    turmas = [t[0] for t in db.session.query(Turma.nome).join(ReservaLab, Turma.id == ReservaLab.turma_id).distinct().all() if t[0]]
    disciplinas = [d[0] for d in db.session.query(ReservaLab.disciplina).distinct().all() if d[0]]
    # Período antigo removido – agora usamos horário início/fim
    periodos = []
    # Status internos padronizados
    status_list = ["pending", "pre_approved", "approved", "rejected", "blocked"]

    return render_template(
        "relatorio_reservas.html",
        reservas=reservas,
        turmas=turmas,
        disciplinas=disciplinas,
        status_list=status_list,
        filtro_turma=turma or "",
        filtro_disciplina=disciplina or "",
        filtro_status=status or "",
        usuario_id=usuario.id,
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
        login_form = request.form["login"]
        senha_form = request.form["senha"]
        
        usuario = Usuario.query.filter_by(login=login_form).first()
        
        if not usuario:
            # Em vez de 404, podemos usar o flash para ficar mais bonito na tela
            flash("Usuário não encontrado", "danger")
            return render_template("login.html")

        if bcrypt.checkpw(senha_form.encode(), usuario.senha_hash.encode()):
            session.clear() # Limpa resquícios de sessões antigas/inválidas
            session["usuario"] = usuario.login
            return redirect("/painel_unip")
        else:
            flash("Senha Incorreta", "danger")
            return render_template("login.html")
            
    return render_template("login.html")

# Rota unificada de cadastro
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        role = request.form.get("role")
        login = request.form.get("login") # RA para alunos, ID para colab
        email = request.form.get("email")
        senha = request.form.get("senha")
        
        # 1. Verificar se o usuário já existe para evitar erros de banco
        if Usuario.query.filter_by(login=login).first():
            flash("Este RA/ID já está cadastrado!", "danger")
            return redirect(url_for("cadastro"))

        # 2. Criptografia da senha seguindo o seu padrão bcrypt
        senha_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # 3. Criação do Usuário Base
        novo_usuario = Usuario(
            login=login,
            email=email,
            senha_hash=senha_hash,
            role=role,
            ativo=True
        )

        # 4. Lógica Inteligente de Turmas (Exclusivo para Alunos)
        if role == 'aluno':
            sigla_turma = request.form.get("turma")
            cod_curso = request.form.get("curso") # Pega "ADS", "CC", etc.
            semestre_val = request.form.get("semestre")

            # Mapeamento para o nome não ir como sigla para o banco
            cursos_nomes = {
                "ADS": "Análise e Desenvolvimento de Sistemas",
                "CC": "Ciência da Computação",
                "DIR": "Direito"
            }
            curso_completo = cursos_nomes.get(cod_curso, cod_curso)

            turma_existente = Turma.query.filter_by(nome=sigla_turma).first()
            
            if not turma_existente:
                turma_existente = Turma(
                    nome=sigla_turma, 
                    curso=curso_completo, # Agora vai o nome cheio!
                    semestre=f"{semestre_val}º Semestre"
                )
                db.session.add(turma_existente)
                db.session.flush()

            novo_usuario.turma_id = turma_existente.id
            novo_usuario.turma = sigla_turma
            novo_usuario.semestre = semestre_val

        else:
            # Lógica para Professor/Coordenador
            cargo = request.form.get("cargo")
            novo_usuario.cargo = cargo
            # Ajusta a role específica baseada no cargo selecionado
            if cargo in ['professor', 'coordenador']:
                novo_usuario.role = cargo

        # 5. Salva tudo no banco
        try:
            db.session.add(novo_usuario)
            db.session.commit()
            flash("Cadastro realizado com sucesso! Faça login para continuar.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar no banco: {str(e)}", "danger")

    return render_template('cadastro.html')


@app.route("/processa_cadastro_aluno", methods=["POST"])
def cadastrar_aluno():
    # ... captura dados do formulário (nome, login, curso, periodo) ...
    curso_aluno = request.form.get('curso')
    periodo_aluno = request.form.get('periodo')
    nome_turma = f"{curso_aluno} - {periodo_aluno}"

    # Tenta achar a turma. Se não existir, cria.
    turma = Turma.query.filter_by(nome=nome_turma).first()
    if not turma:
        turma = Turma(nome=nome_turma, curso=curso_aluno)
        db.session.add(turma)
        db.session.commit() # Commit para gerar o ID da turma

    # Agora vincula o aluno à turma encontrada ou criada
    novo_usuario = Usuario(
        login=login,
        role='aluno',
        turma_id=turma.id, # Vinculo automático
        # ... outros campos ...
    )
    db.session.add(novo_usuario)
    db.session.commit()

@app.route("/api/eventos")
def api_eventos():
    # Buscamos todas as reservas que não foram rejeitadas
    reservas = ReservaLab.query.filter(ReservaLab.status != 'rejected').all()
    eventos = []
    
    for r in reservas:
        # Definimos a cor baseada no status ou se é um bloqueio
        # approved -> azul, pending / pre_approved -> amarelo, blocked / manutenção -> vermelho
        cor = "#003366"  # Azul UNIP (Aprovado)
        if r.status in ['pending', 'pre_approved']:
            cor = "#ffc107"  # Amarelo (Aguardando)
        if "MANUTENÇÃO" in (r.disciplina or "").upper() or r.status == 'blocked':
            cor = "#dc3545"  # Vermelho (Bloqueio Admin)

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
    
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()

    # TRAVA 1: Segurança de acesso (Anti-aluno)
    if usuario_logado.role == 'aluno':
        return redirect(url_for('painel_unip'))

    if request.method == "POST":
        data_str = request.form.get('data')
        lab_id = int(request.form.get('laboratorio_id'))
        turma_id = int(request.form.get('turma_id'))
        h_inicio = request.form.get('horario_inicio')
        h_fim = request.form.get('horario_fim')
        disciplina = request.form.get('disciplina')
        # Admin/Coord podem escolher o prof, Professor usa o próprio login
        prof_responsavel = request.form.get('professor') if usuario_logado.role in ['admin', 'coordenador'] else usuario_logado.login
        
        # 1. Validar Data
        data_selecionada = datetime.strptime(data_str, '%Y-%m-%d').date()

        # TRAVA 2: Período de Provas (Bloqueio do Lab 2)
        bloqueio = BloqueioLab.query.filter(
            BloqueioLab.laboratorio_id == lab_id,
            BloqueioLab.data_inicio <= data_selecionada,
            BloqueioLab.data_fim >= data_selecionada
        ).first()

        if bloqueio:
            flash(f"Impossível reservar: {bloqueio.motivo} ativo para o Lab {lab_id}", "danger")
            return redirect(url_for('nova_reserva'))

        # TRAVA 3: Conflito de Horário (Já existe reserva no lab nesse horário?)
        conflito = ReservaLab.query.filter(
            ReservaLab.laboratorio_id == lab_id,
            ReservaLab.data == data_selecionada,
            ReservaLab.horario_inicio < h_fim,
            ReservaLab.horario_fim > h_inicio
        ).first()

        if conflito:
            flash(f"Conflito: O Lab {lab_id} já está reservado por {conflito.professor} nesse horário.", "warning")
            return redirect(url_for('nova_reserva'))

        # Salvar Reserva
        nova = ReservaLab(
            data=data_selecionada.strftime('%Y-%m-%d'),
            laboratorio_id=lab_id,
            turma_id=turma_id,
            horario_inicio=h_inicio,
            horario_fim=h_fim,
            disciplina=disciplina,
            professor=prof_responsavel,
            status='pending'
        )
        db.session.add(nova)
        db.session.commit()
        flash("Reserva realizada com sucesso!", "success")
        return redirect(url_for('painel_unip'))

    # Dados para carregar os selects do HTML
    laboratorios = Laboratorio.query.all()
    turmas = Turma.query.all()
    todos_professores = Usuario.query.filter(Usuario.role.in_(["professor", "coordenador"])).all()
    horarios_unip = ["19:10", "20:00", "20:50", "21:00", "21:50", "22:40"]

    return render_template("nova_reserva.html", 
                           laboratorios=laboratorios, 
                           turmas=turmas, 
                           usuario=usuario_logado, 
                           horarios=horarios_unip,
                           todos_professores=todos_professores)

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    if "usuario" not in session:
        return redirect("/login")
    
    reserva = ReservaLab.query.get_or_404(id)
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()

    if request.method == "POST":
        # 1. Captura os novos dados do formulário (reaproveita campos de nova_reserva)
        data_str = request.form.get("data")
        lab_id = int(request.form.get("laboratorio_id"))
        turma_id = int(request.form.get("turma_id"))
        h_inicio = request.form.get("horario_inicio")
        h_fim = request.form.get("horario_fim")
        disciplina = request.form.get("disciplina")

        # 2. VALIDAÇÃO DE CONFLITO (Ignorando a própria reserva que está a ser editada)
        data_selecionada = datetime.strptime(data_str, "%Y-%m-%d").date()
        conflito = ReservaLab.query.filter(
            ReservaLab.id != id,
            ReservaLab.laboratorio_id == lab_id,
            ReservaLab.data == data_str,
            ReservaLab.horario_inicio < h_fim,
            ReservaLab.horario_fim > h_inicio,
            ReservaLab.status != "rejected",  # Ignora se o conflito for com uma já rejeitada
        ).first()

        if conflito:
            flash(
                f"Erro: O laboratório {conflito.lab.nome if conflito.lab else lab_id} já está ocupado nesta data/horário.",
                "danger",
            )
            # Recarrega dados auxiliares para o formulário
            laboratorios = Laboratorio.query.all()
            turmas = Turma.query.all()
            todos_professores = Usuario.query.filter(Usuario.role.in_(["professor", "coordenador"])).all()
            horarios_unip = ["19:10", "20:00", "20:50", "21:00", "21:50", "22:40"]
            return render_template(
                "nova_reserva.html",
                reserva=reserva,
                usuario=usuario_logado,
                laboratorios=laboratorios,
                turmas=turmas,
                horarios=horarios_unip,
                todos_professores=todos_professores,
            )

        # 3. ATUALIZAÇÃO DOS DADOS
        reserva.data = data_str
        reserva.laboratorio_id = lab_id
        reserva.turma_id = turma_id
        reserva.horario_inicio = h_inicio
        reserva.horario_fim = h_fim
        reserva.disciplina = disciplina

        # 4. LÓGICA DE STATUS NA EDIÇÃO
        # Se um professor editar, a reserva volta a ficar pendente para nova análise
        if usuario_logado.role == "professor":
            reserva.status = "pending"
        # Se um admin editar, mantemos como approved
        elif usuario_logado.role == "admin":
            reserva.status = "approved"

        db.session.commit()
        flash("Reserva atualizada com sucesso!", "success")
        return redirect(url_for("painel_unip"))

    # No GET: Abre o formulário com os dados atuais, incluindo selects
    laboratorios = Laboratorio.query.all()
    turmas = Turma.query.all()
    todos_professores = Usuario.query.filter(Usuario.role.in_(["professor", "coordenador"])).all()
    horarios_unip = ["19:10", "20:00", "20:50", "21:00", "21:50", "22:40"]
    return render_template(
        "nova_reserva.html",
        reserva=reserva,
        usuario=usuario_logado,
        laboratorios=laboratorios,
        turmas=turmas,
        horarios=horarios_unip,
        todos_professores=todos_professores,
    )

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

@app.route("/admin/criar_usuario", methods=["POST"])
def criar_usuario():
    # 1. Segurança: Verifica se o usuário está logado
    if "usuario" not in session:
        return redirect("/login")
    
    # 2. Verifica se quem está logado é realmente um Admin
    admin_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not admin_logado or admin_logado.role != 'admin':
        return "Acesso Negado", 403

    # 3. Coleta os dados do formulário (vêm do Modal do lista.html)
    login_novo = request.form.get("login")
    email_novo = request.form.get("email")
    role_nova = request.form.get("role")
    senha_plana = request.form.get("senha")
    
    # 4. Criptografa a senha antes de salvar
    hash_senha = bcrypt.hashpw(senha_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # 5. Cria o objeto Usuario (usando apenas as colunas que você tem no models.py)
    novo_user = Usuario(
        login=login_novo,
        email=email_novo,
        senha_hash=hash_senha,
        role=role_nova,
        turma="PADRAO",  # Valores padrão para não dar erro de nullable=False
        semestre="-"
    )

    try:
        db.session.add(novo_user)
        db.session.commit()
        # Se você tiver configurado o flash messages no HTML:
        # flash("Usuário criado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        return f"Erro ao criar usuário: {e}", 500

    # 6. Redireciona de volta para o painel
    return redirect("/painel_unip")

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
    
    # Após exclusão, mantém o admin no painel principal (aba Usuários)
    return redirect(url_for("painel_unip"))

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

@app.route("/admin/criar_laboratorio", methods=["POST"])
def criar_laboratorio():
    if "usuario" not in session or Usuario.query.filter_by(login=session["usuario"]).first().role != 'admin':
        return redirect("/login")
    
    nome = request.form.get('nome')
    capacidade = request.form.get('capacidade')
    
    novo_lab = Laboratorio(nome=nome, capacidade=int(capacidade))
    db.session.add(novo_lab)
    db.session.commit()
    flash("Laboratório criado!", "success")
    return redirect(url_for('painel_unip'))

@app.route("/admin/excluir_laboratorio/<int:id>")
def excluir_laboratorio(id):
    # (Adicione a mesma trava de segurança de admin aqui)
    lab = Laboratorio.query.get(id)
    if lab:
        db.session.delete(lab)
        db.session.commit()
    return redirect(url_for('painel_unip'))

@app.route("/admin/criar_turma", methods=["POST"])
def criar_turma():
    if "usuario" not in session or Usuario.query.filter_by(login=session["usuario"]).first().role != 'admin':
        return redirect("/login")
    
    nome = request.form.get('nome')
    curso = request.form.get('curso')
    
    nova_turma = Turma(nome=nome, curso=curso)
    db.session.add(nova_turma)
    db.session.commit()
    flash("Turma criada!", "success")
    return redirect(url_for('painel_unip'))


@app.route("/admin/bloqueios", methods=["GET", "POST"])
def gerenciar_bloqueios():
    if "usuario" not in session:
        return redirect("/login")
    
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if usuario_logado.role not in ['admin', 'coordenador']:
        return redirect(url_for('painel_unip'))

    if request.method == "POST":
        # Captura os dados do formulário
        lab_id = request.form.get('laboratorio_id')
        inicio_str = request.form.get('data_inicio')
        fim_str = request.form.get('data_fim')
        motivo = request.form.get('motivo')

        # Converte strings para objetos date
        inicio = datetime.strptime(inicio_str, '%Y-%m-%d').date()
        fim = datetime.strptime(fim_str, '%Y-%m-%d').date()

        novo_bloqueio = BloqueioLab(
            laboratorio_id=int(lab_id),
            data_inicio=inicio,
            data_fim=fim,
            motivo=motivo
        )
        db.session.add(novo_bloqueio)
        db.session.commit()
        return redirect(url_for('gerenciar_bloqueios'))

    # IMPORTANTE: Busca os dados para preencher o SELECT e a TABELA
    bloqueios = BloqueioLab.query.all()
    lista_laboratorios = Laboratorio.query.all() # Certifica-te que esta linha existe!

    # ... dentro da def gerenciar_bloqueios ...
    lista_laboratorios = Laboratorio.query.all()
    print(f"DEBUG: Encontrados {len(lista_laboratorios)} laboratórios no banco.")
    for l in lista_laboratorios:
        print(f"ID: {l.id} | Nome: {l.nome}")
    
    return render_template("admin_bloqueios.html", 
                           bloqueios=bloqueios, 
                           laboratorios=lista_laboratorios) # Passa para o HTML

@app.route("/admin/excluir_bloqueio/<int:id>")
def excluir_bloqueio(id):
    if "usuario" not in session: return redirect("/login")
    
    # Apenas Admin/Coord podem excluir bloqueios
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if usuario.role in ['admin', 'coordenador']:
        bloqueio = BloqueioLab.query.get(id)
        if bloqueio:
            db.session.delete(bloqueio)
            db.session.commit()
            flash("Bloqueio removido com sucesso!", "success")
            
    return redirect(url_for('gerenciar_bloqueios'))

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
    
    reservas_pendentes = ReservaLab.query.filter_by(status='pending').all()
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
        reserva.status = 'approved'
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
        reserva.status = 'rejected'
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
    
    # 1. Busca as turmas onde o professor tem reservas (via relacionamento com Turma)
    turmas_query = (
        db.session.query(Turma.nome)
        .join(ReservaLab, Turma.id == ReservaLab.turma_id)
        .filter(ReservaLab.usuario_id == usuario.id)
        .distinct()
        .all()
    )
    lista_turmas = [t[0] for t in turmas_query if t[0]]
    
    # 2. Se o professor escolheu uma turma, buscamos os alunos daquela turma
    alunos_da_turma = []
    if turma_selecionada:
        alunos_da_turma = Usuario.query.filter_by(role='aluno', turma=turma_selecionada).all()
    
    return render_template("ver_alunos_turmas.html", 
                           turmas=lista_turmas, 
                           alunos=alunos_da_turma, 
                           turma_ativa=turma_selecionada)

@app.route("/painel_unip")
def painel_unip():
    if "usuario" not in session:
        return redirect("/login")
    
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario_logado:
        session.clear()
        return redirect("/login")

    # Reservas e Bloqueios são comuns a ambos
    reservas = ReservaLab.query.order_by(ReservaLab.data.desc()).all()
    bloqueios = BloqueioLab.query.all()

    # --- VISÃO DO ALUNO ---
    if usuario_logado.role == 'aluno':
        # Filtramos as reservas para mostrar apenas o que é da turma do aluno
        # e que já estejam aprovadas (status final)
        reservas_turma = [
            r for r in reservas
            if r.turma_id == usuario_logado.turma_id and r.status == 'approved'
        ]
        
        return render_template("painel_aluno.html", 
                               usuario=usuario_logado.login,
                               reservas=reservas_turma,
                               bloqueios=bloqueios)
    
    # --- VISÃO GESTÃO (Prof/Coord/Admin) ---
    usuarios, todos_labs, todas_turmas = [], [], []
    if usuario_logado.role == 'admin':
        usuarios = Usuario.query.all()
        todos_labs = Laboratorio.query.all()
        todas_turmas = Turma.query.all()

    return render_template("lista.html", 
                           usuario=usuario_logado.login,
                           usuario_id=usuario_logado.id, 
                           role=usuario_logado.role, 
                           reservas=reservas,
                           usuarios=usuarios,
                           laboratorios=todos_labs,
                           turmas=todas_turmas,
                           bloqueios=bloqueios)


# --- NOVAS ROTAS DE APROVAÇÃO (DOUBLE CHECK) ---

@app.route("/pre_aprovar_reserva/<int:id>")
def pre_aprovar_reserva(id):
    if "usuario" not in session: return redirect("/login")
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if usuario.role not in ['coordenador', 'admin']: return "Acesso negado", 403
    
    reserva = ReservaLab.query.get_or_404(id)
    reserva.status = 'pre_approved' # Status intermediário
    db.session.commit()
    flash("Reserva pré-aprovada! Aguarda confirmação do Admin.", "warning")
    return redirect(url_for("painel_unip"))

@app.route("/confirmar_reserva/<int:id>")
def confirmar_reserva(id):
    if "usuario" not in session: return redirect("/login")
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if usuario.role != 'admin': return "Acesso negado", 403
    
    reserva = ReservaLab.query.get_or_404(id)
    reserva.status = 'approved' # Status final
    db.session.commit()
    flash("Reserva confirmada e publicada!", "success")
    return redirect(url_for("painel_unip"))

# Rota para o Admin bloquear o laboratório
@app.route("/bloquear_lab", methods=["POST"])
def admin_bloquear():
    if "usuario" not in session: return redirect("/login")
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if usuario.role != 'admin': return "Acesso negado", 403

    bloqueio = ReservaLab(
        laboratorio=request.form.get("laboratorio"),
        professor="SISTEMA",
        turma="INTERDIÇÃO",
        disciplina=f"BLOQUEIO: {request.form.get('motivo')}",
        data=request.form.get("data"),
        periodo=request.form.get("periodo"),
        status='blocked', # Novo status para o CSS
        usuario_id=usuario.id
    )
    db.session.add(bloqueio)
    db.session.commit()
    return redirect(url_for("painel_unip"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        inicializar_unidade() # Garante que os labs existam
    app.run(host='localhost', port=5000, debug=True)