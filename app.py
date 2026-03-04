from sqlalchemy import or_
from models import ReservaLab, db, Usuario, Laboratorio, Turma, BloqueioLab
from flask import Flask, jsonify, render_template, request, redirect, session, url_for, flash
from datetime import datetime
import json, os
import bcrypt
from flask_migrate import Migrate

app = Flask(__name__)
app.secret_key = "chave-secreta-123"  # Necessário para usar sessões
app.config['JSON_AS_ASCII'] = False # Correção para exibir acentos corretamente no JSON

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
        {"nome": "Laboratório 2/Provas Online", "capacidade": 25},
        {"nome": "Laboratório 8", "capacidade": 25},
        {"nome": "Laboratório 9/Design de Moda", "capacidade": 26},
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

    # --- PARTE 2: ADMINISTRADOR (AJUSTADA COM O CAMPO NOME) ---
    if not Usuario.query.filter_by(login="admin").first():
        # Usando a lógica do seu padrão bcrypt
        senha_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        admin = Usuario(
            nome="Administrador Geral",  # <--- ADICIONADO PARA EVITAR O ERRO
            login="admin",
            email="admin@unip.br",
            senha_hash=senha_hash,
            role="admin",
            turma=None,
            semestre=None,
            cargo="administrador",
            ativo=True # Adicionado para garantir que ele consiga logar
        )
        db.session.add(admin)
        print("✅ Admin padrão criado!")

    try:
        db.session.commit()
        print("🚀 Sistema inicializado com sucesso!")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro na inicialização: {e}")

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
        login_form = request.form["usuario"]
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
        nome = request.form.get("nome") # Captura o nome do formulário
        login = request.form.get("login") 
        email = request.form.get("email")
        senha = request.form.get("senha")
        
        # 1. Verificação de existência
        if Usuario.query.filter_by(login=login).first():
            flash("Este RA/ID já está cadastrado!", "danger")
            return render_template('cadastro.html')

        # 2. Criptografia segura
        senha_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # 3. Instância do Usuário
        novo_usuario = Usuario(
            nome=nome,  # Agora o campo nome é obrigatório e preenchido
            login=login,
            email=email,
            senha_hash=senha_hash,
            role=role,
            ativo=True
        )

        # 4. Lógica de Turmas para Alunos
        if role == 'aluno':
            sigla_turma = request.form.get("turma") # Ex: "ADS3A"
            cod_curso = request.form.get("curso")
            semestre_val = request.form.get("semestre")

            cursos_nomes = {
                "ADS": "Análise e Desenvolvimento de Sistemas",
                "CC": "Ciência da Computação",
                "DIR": "Direito"
            }
            curso_completo = cursos_nomes.get(cod_curso, cod_curso)

            # Busca ou cria a turma para evitar duplicatas
            turma_existente = Turma.query.filter_by(nome=sigla_turma).first()
            
            if not turma_existente:
                turma_existente = Turma(
                    nome=sigla_turma, 
                    curso=curso_completo,
                    semestre=f"{semestre_val}º Semestre"
                )
                db.session.add(turma_existente)
                db.session.flush() # Gera o ID da turma antes do commit final

            novo_usuario.turma_id = turma_existente.id
            novo_usuario.turma = sigla_turma # Mantém a string para compatibilidade
            novo_usuario.semestre = semestre_val

        else:
            # Lógica para Professor/Coordenador/Admin
            cargo = request.form.get("cargo")
            novo_usuario.cargo = cargo
            if cargo in ['professor', 'coordenador', 'admin']:
                novo_usuario.role = cargo

        # 5. Commit Único (Atômico)
        try:
            db.session.add(novo_usuario)
            db.session.commit()
            flash("Cadastro realizado com sucesso!", "success")
            return redirect(url_for("login"))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar: {str(e)}", "danger")

    return render_template('cadastro.html')

@app.route("/api/eventos")
def api_eventos():
    try:
        from datetime import timedelta
        reservas = ReservaLab.query.filter(ReservaLab.status != 'rejected').all()
        eventos = []

        for r in reservas:
            cor = "#003366"  # Azul UNIP
            if r.status in ['pending', 'pre_approved']:
                cor = "#ffc107"  # Amarelo
            if (r.disciplina and "MANUTENÇÃO" in r.disciplina.upper()) or r.status == 'blocked':
                cor = "#dc3545"  # Vermelho

            nome_lab = r.lab.nome if r.lab else "Lab Indefinido"
            nome_turma = r.turma_rel.nome if r.turma_rel else "Sem Turma"
            periodo_formatado = f"{r.horario_inicio} - {r.horario_fim}"

            # Converte data de DD/MM/YYYY para YYYY-MM-DD para o FullCalendar
            try:
                data_iso = datetime.strptime(r.data, '%d/%m/%Y').strftime('%Y-%m-%d')
            except Exception:
                data_iso = r.data

            eventos.append({
                "id": r.id,
                "title": f"{nome_lab}",
                "start": f"{data_iso}T{r.horario_inicio}:00",
                "end": f"{data_iso}T{r.horario_fim}:00",
                "color": cor,
                "extendedProps": {
                    "professor": r.professor or "Não informado",
                    "disciplina": r.disciplina or "N/A",
                    "turma": nome_turma,
                    "periodo": periodo_formatado
                }
            })

        # Adiciona bloqueios como eventos de fundo vermelhos
        bloqueios = BloqueioLab.query.all()
        for b in bloqueios:
            nome_lab = b.lab_rel.nome if b.lab_rel else "Laboratório"
            # +1 dia pois o FullCalendar usa end exclusivo
            data_fim_exclusivo = (b.data_fim + timedelta(days=1)).strftime('%Y-%m-%d')
            eventos.append({
                "id": f"bloqueio_{b.id}",
                "title": f"🔒 {nome_lab}: {b.motivo}",
                "start": b.data_inicio.strftime('%Y-%m-%d'),
                "end": data_fim_exclusivo,
                "color": "#dc3545",
                "display": "background",
                "extendedProps": {
                    "tipo": "bloqueio",
                    "professor": "SISTEMA",
                    "disciplina": b.motivo,
                    "periodo": "Dia inteiro"
                }
            })

        return jsonify(eventos)
    except Exception as e:
        print(f"Erro na API de Eventos: {e}")
        return jsonify([])

@app.route("/nova_reserva", methods=["GET", "POST"])
def nova_reserva():
    if "usuario" not in session:
        return redirect("/login")
    
    # Busca o objeto completo do usuário logado
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()

    # TRAVA 1: Segurança de acesso (Apenas Professor, Coordenador e Admin reservam)
    if usuario_logado.role == 'aluno':
        flash("Alunos não possuem permissão para realizar reservas.", "danger")
        return redirect(url_for('painel_unip'))

    if request.method == "POST":
        data_str = request.form.get('data')
        lab_id = request.form.get('laboratorio_id')
        turma_id = request.form.get('turma_id')
        h_inicio = request.form.get('horario_inicio')
        h_fim = request.form.get('horario_fim')
        disciplina = request.form.get('disciplina')
        
        # Lógica de Professor Responsável:
        # Se for Admin/Coord, ele pode ter selecionado outro professor no select.
        # Se for Professor, ele reserva no próprio nome.
        prof_login = request.form.get('professor') if usuario_logado.role in ['admin', 'coordenador'] else usuario_logado.login
        
        # Buscamos o nome real do professor para salvar na reserva
        obj_professor = Usuario.query.filter_by(login=prof_login).first()
        nome_exibicao_prof = obj_professor.nome if obj_professor else prof_login

        # 1. Validar se a data foi enviada
        if not data_str:
            flash("Por favor, selecione uma data no calendário.", "warning")
            laboratorios = Laboratorio.query.all()
            turmas = Turma.query.all()
            todos_professores = Usuario.query.filter(Usuario.role.in_(["professor", "coordenador"])).all()
            return render_template("nova_reserva.html", laboratorios=laboratorios, turmas=turmas, usuario=usuario_logado, todos_professores=todos_professores)

        try:
            data_selecionada = datetime.strptime(data_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Formato de data inválido.", "danger")
            laboratorios = Laboratorio.query.all()
            turmas = Turma.query.all()
            todos_professores = Usuario.query.filter(Usuario.role.in_(["professor", "coordenador"])).all()
            return render_template("nova_reserva.html", laboratorios=laboratorios, turmas=turmas, usuario=usuario_logado, todos_professores=todos_professores)

        # TRAVA 2: Verificação de Bloqueios (Ex: Provas no Lab 2)
        bloqueio = BloqueioLab.query.filter(
            BloqueioLab.laboratorio_id == lab_id,
            BloqueioLab.data_inicio <= data_selecionada,
            BloqueioLab.data_fim >= data_selecionada
        ).first()

        if bloqueio:
            flash(f"O laboratório está interditado: {bloqueio.motivo}", "danger")
            laboratorios = Laboratorio.query.all()
            turmas = Turma.query.all()
            todos_professores = Usuario.query.filter(Usuario.role.in_(["professor", "coordenador"])).all()
            return render_template("nova_reserva.html", laboratorios=laboratorios, turmas=turmas, usuario=usuario_logado, todos_professores=todos_professores)

        # TRAVA 3: Conflito de Horário
        conflito = ReservaLab.query.filter(
            ReservaLab.laboratorio_id == lab_id,
            ReservaLab.data == data_selecionada.strftime('%d/%m/%Y'),
            ReservaLab.horario_inicio < h_fim,
            ReservaLab.horario_fim > h_inicio
        ).first()

        if conflito:
            flash(f"Conflito de horário! Este laboratório já está reservado para {conflito.disciplina}.", "warning")
            laboratorios = Laboratorio.query.all()
            turmas = Turma.query.all()
            todos_professores = Usuario.query.filter(Usuario.role.in_(["professor", "coordenador"])).all()
            return render_template("nova_reserva.html", laboratorios=laboratorios, turmas=turmas, usuario=usuario_logado, todos_professores=todos_professores)

        # DEFINIÇÃO RÍGIDA DE STATUS POR CARGO (Correção da Hierarquia)
        if usuario_logado.role == 'admin':
            status_inicial = 'approved'
        elif usuario_logado.role == 'coordenador':
            status_inicial = 'pre_approved'
        else:
            status_inicial = 'pending'

        # Salvar Reserva
        try:
            nova = ReservaLab(
                data=data_selecionada.strftime('%d/%m/%Y'), # Formato BR para o banco/exibição
                laboratorio_id=lab_id,
                turma_id=turma_id,
                horario_inicio=h_inicio,
                horario_fim=h_fim,
                disciplina=disciplina,
                professor=nome_exibicao_prof,
                status=status_inicial,
                usuario_id=usuario_logado.id
            )
            db.session.add(nova)
            db.session.commit()
            
            msg = "Agendamento solicitado! Aguardando aprovação." if status_inicial == 'pending' else "Reserva registrada com sucesso!"
            flash(msg, "success")
            return redirect(url_for('painel_unip'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar reserva: {str(e)}", "danger")

    # Dados para carregar os selects do HTML
    laboratorios = Laboratorio.query.all()
    turmas = Turma.query.all()
    todos_professores = Usuario.query.filter(Usuario.role.in_(["professor", "coordenador"])).all()

    return render_template("nova_reserva.html", 
                           laboratorios=laboratorios, 
                           turmas=turmas, 
                           usuario=usuario_logado, 
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
    if "usuario" not in session:
        return redirect("/login")
    
    admin_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not admin_logado or admin_logado.role != 'admin':
        return "Acesso Negado", 403

    # 3. Coleta os dados (Adicionamos o 'nome' aqui)
    nome_novo = request.form.get("nome") # <--- CAPTURA O NOME
    login_novo = request.form.get("login")
    email_novo = request.form.get("email")
    role_nova = request.form.get("role")
    senha_plana = request.form.get("senha")
    
    hash_senha = bcrypt.hashpw(senha_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # 5. Cria o objeto (Incluímos o campo 'nome')
    novo_user = Usuario(
        nome=nome_novo,      # <--- AGORA O BANCO ACEITA O INSERT
        login=login_novo,
        email=email_novo,
        senha_hash=hash_senha,
        role=role_nova,
        turma="PADRAO",  
        semestre="-",
        ativo=True           # É bom garantir que o user já nasça ativo
    )

    try:
        db.session.add(novo_user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return f"Erro ao criar usuário: {e}", 500

    return redirect("/painel_unip")

@app.route("/admin/editar_usuario/<int:id>", methods=["POST"])
def editar_usuario(id):
    if "usuario" not in session:
        return redirect("/login")
    
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario_logado or usuario_logado.role != 'admin':
        return "Acesso negado", 403

    user = Usuario.query.get_or_404(id)
    
    # Atualiza os dados básicos
    user.nome = request.form.get("nome") # Novo campo funcional
    user.login = request.form.get("login")
    user.email = request.form.get("email")
    user.role = request.form.get("role")
    
    # Se enviou senha, criptografa e atualiza. Se não, mantém a atual.
    nova_senha = request.form.get("senha")
    if nova_senha and nova_senha.strip() != "":
        user.senha_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        db.session.commit()
        flash("Usuário atualizado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao salvar: {e}", "danger")

    # Redireciona de volta para o painel (onde está a aba de usuários)
    return redirect(url_for("painel_unip"))

@app.route("/admin/excluir_usuario/<int:id>")
def excluir_usuario(id):
    if "usuario" not in session:
        return redirect("/login")
    
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario_logado or usuario_logado.role != 'admin':
        return "Acesso negado", 403
    
    user = Usuario.query.get(id)
    # Proteção para não deletar a si próprio ou outros admins por engano
    if user and user.role != 'admin': 
        db.session.delete(user)
        db.session.commit()
        flash("Usuário removido!", "success")
    
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
    semestre = request.form.get('semestre', '1º Semestre')
    
    nova_turma = Turma(nome=nome, curso=curso, semestre=semestre)
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
    if not usuario or usuario.role not in ['coordenador', 'admin']:
        return "Acesso negado", 403

    # O Admin e o Coordenador veem o que está pendente ou pré-aprovado
    reservas_pendentes = ReservaLab.query.filter(
        or_(ReservaLab.status == 'pending', ReservaLab.status == 'pre_approved')
    ).order_by(ReservaLab.data.asc()).all()

    # Histórico (finalizados)
    todas_reservas = ReservaLab.query.filter(
        or_(ReservaLab.status == 'approved', ReservaLab.status == 'rejected')
    ).order_by(ReservaLab.data.desc()).limit(50).all()

    return render_template("coordenador_reservas.html", 
                           reservas_pendentes=reservas_pendentes, 
                           todas_reservas=todas_reservas,
                           usuario_logado=usuario)

# ROTA DE APROVAÇÃO (CORRIGIDA PARA ADMIN FINALIZAR COORDENADOR)
@app.route("/aprovar_reserva/<int:id>")
def aprovar_reserva(id):
    if "usuario" not in session: return redirect("/login")
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    reserva = ReservaLab.query.get_or_404(id)
    
    if usuario.role == 'admin':
        # Admin sempre finaliza
        reserva.status = 'approved'
        flash("Reserva finalizada com sucesso!", "success")
    elif usuario.role == 'coordenador':
        # Coordenador só pode subir de pending para pre_approved
        if reserva.status == 'pending':
            reserva.status = 'pre_approved'
            flash("Pré-aprovação realizada! Aguardando Admin.", "info")
        else:
            flash("Você não tem permissão para aprovação final.", "warning")
    
    db.session.commit()
    return redirect(url_for("coordenador_reservas"))

@app.route("/rejeitar_reserva/<int:id>")
def rejeitar_reserva(id):
    if "usuario" not in session:
        return redirect("/login")
    
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario or usuario.role not in ['coordenador', 'admin']:
        return "Acesso negado", 403
    
    reserva = ReservaLab.query.get_or_404(id)
    reserva.status = 'rejected'
    db.session.commit()
    flash("Reserva rejeitada.", "warning")
    
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

    # Bloqueios continuam sendo úteis para todos (ex: avisar que lab está em manutenção)
    bloqueios = BloqueioLab.query.all()

    # --- VISÃO DO ALUNO ---
    if usuario_logado.role == 'aluno':
        # OTIMIZAÇÃO: Filtramos direto no banco usando o ID da turma do aluno
        # Só trazemos o que ele realmente precisa ver (Aprovadas da Turma dele)
        reservas_turma = ReservaLab.query.filter_by(
            turma_id=usuario_logado.turma_id, 
            status='approved'
        ).order_by(ReservaLab.data.desc()).all()
        
        return render_template("painel_aluno.html", 
                               usuario=usuario_logado, # Enviamos o objeto todo para o template
                               reservas=reservas_turma,
                               bloqueios=bloqueios)
    
    # --- VISÃO GESTÃO (Prof/Coord/Admin) ---
    # Para gestão, pegamos todas as reservas para auditoria
    reservas_todas = ReservaLab.query.order_by(ReservaLab.data.desc()).all()
    
    usuarios, todos_labs, todas_turmas = [], [], []
    if usuario_logado.role == 'admin':
        usuarios = Usuario.query.all()
        todos_labs = Laboratorio.query.all()
        todas_turmas = Turma.query.all()

    return render_template("lista.html", 
                           usuario=usuario_logado,
                           usuario_id=usuario_logado.id, 
                           role=usuario_logado.role, 
                           reservas=reservas_todas,
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

# Rota /bloquear_lab removida — use /admin/bloqueios (gerenciar_bloqueios)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        inicializar_unidade() # Garante que os labs existam
    app.run(host='localhost', port=5000, debug=True)