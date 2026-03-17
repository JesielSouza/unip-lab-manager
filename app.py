from sqlalchemy import or_
from models import ReservaLab, db, Usuario, Laboratorio, Turma, BloqueioLab, LogAuditoria
from flask import Flask, jsonify, render_template, request, redirect, session, url_for, flash
from datetime import datetime
import os
import bcrypt
import re
from flask_migrate import Migrate
import smtplib
from datetime import timedelta
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import time
from collections import defaultdict
from flask_wtf.csrf import CSRFProtect

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-troque-em-producao")
csrf = CSRFProtect(app)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=20)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Armazena token ativo por login (sessão única)
_sessoes_ativas = {}



# ── RATE LIMITING DE LOGIN ────────────────────────────────────
# { ip: [timestamp, timestamp, ...] }
_tentativas_login = defaultdict(list)
LIMITE_TENTATIVAS = 5      # máximo de tentativas
JANELA_SEGUNDOS   = 300    # janela de 5 minutos
BLOQUEIO_SEGUNDOS = 900    # bloqueio por 15 minutos após exceder

def _ip_bloqueado(ip):
    """Retorna (bloqueado, segundos_restantes) para o IP."""
    agora = time.time()
    tentativas = _tentativas_login[ip]
    # Remove tentativas fora da janela
    _tentativas_login[ip] = [t for t in tentativas if agora - t < JANELA_SEGUNDOS]
    tentativas = _tentativas_login[ip]
    if len(tentativas) >= LIMITE_TENTATIVAS:
        mais_recente = max(tentativas)
        restante = int(BLOQUEIO_SEGUNDOS - (agora - mais_recente))
        if restante > 0:
            return True, restante
    return False, 0

# ── FUNÇÃO DE EMAIL ──────────────────────────────────────────
def _enviar_email_worker(destinatario, assunto, corpo_html):
    """Worker interno que envia o email. Roda em thread separada."""
    mail_user = os.environ.get("MAIL_USER")
    mail_pass = os.environ.get("MAIL_PASSWORD")
    if not mail_user or not mail_pass or not destinatario:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = f"UNIP Lab Manager <{mail_user}>"
        msg["To"] = destinatario
        msg.attach(MIMEText(corpo_html, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(mail_user, mail_pass)
            server.sendmail(mail_user, destinatario, msg.as_string())
        print(f"[EMAIL] Enviado para {destinatario}")
    except Exception as e:
        import traceback
        print(f"[EMAIL] Erro ao enviar para {destinatario}: {e}")
        print(f"[EMAIL] Traceback: {traceback.format_exc()}")

def enviar_email(destinatario, assunto, corpo_html):
    """Envia email em thread separada para não bloquear a requisição."""
    t = threading.Thread(target=_enviar_email_worker, args=(destinatario, assunto, corpo_html), daemon=True)
    t.start()
app.config['JSON_AS_ASCII'] = False # Correção para exibir acentos corretamente no JSON

# CONFIGURAÇÃO DO BANCO — usa DATABASE_URL em produção, SQLite em dev
basedir = os.path.abspath(os.path.dirname(__file__))
default_db = "sqlite:///" + os.path.join(basedir, "instance", "app.sqlite")
database_url = os.environ.get("DATABASE_URL", default_db)
# Railway gera URLs com "postgres://" mas SQLAlchemy exige "postgresql://"
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
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

    # Limpa labs não oficiais: primeiro remove bloqueios associados, depois o lab
    labs_para_remover = Laboratorio.query.filter(~Laboratorio.nome.in_(nomes_oficiais)).all()
    for lab in labs_para_remover:
        BloqueioLab.query.filter_by(laboratorio_id=lab.id).delete(synchronize_session=False)
        db.session.delete(lab)

    for lab_data in labs_predefinidos:
        lab = Laboratorio.query.filter_by(nome=lab_data["nome"]).first()
        if lab:
            if lab.capacidade != lab_data["capacidade"]:
                lab.capacidade = lab_data["capacidade"]
        else:
            db.session.add(Laboratorio(nome=lab_data["nome"], capacidade=lab_data["capacidade"]))

    # --- PARTE 2: SUPER_ADMIN ---
    if not Usuario.query.filter_by(login="admin").first():
        senha_hash = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
        admin = Usuario(
            nome="Administrador Geral",
            login="admin",
            email="admin@unip.br",
            senha_hash=senha_hash,
            role="super_admin",
            turma=None,
            semestre=None,
            cargo="administrador",
            ativo=True
        )
        db.session.add(admin)
        print("✅ Super Admin padrão criado!")
    else:
        # Migração: se já existe com role='admin', promove para super_admin
        admin_existente = Usuario.query.filter_by(login="admin").first()
        if admin_existente and admin_existente.role == "admin":
            admin_existente.role = "super_admin"
            print("✅ Admin promovido a super_admin!")

    try:
        db.session.commit()
        print("🚀 Sistema inicializado com sucesso!")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro na inicialização: {e}")

# ── HELPERS DE ROLE ──────────────────────────────────────────────────────────
def is_admin(usuario):
    """Retorna True para admin e super_admin."""
    return usuario and usuario.role in ['admin', 'super_admin']

def is_super_admin(usuario):
    """Retorna True apenas para super_admin."""
    return usuario and usuario.role == 'super_admin'

def login_aluno_valido(login):
    """Aluno deve usar RA com apenas dígitos."""
    return bool(re.fullmatch(r'\d+', (login or '').strip()))

def senha_minima_valida(senha, tamanho_minimo=6):
    """Garante validaÃ§Ã£o server-side de senha mÃ­nima."""
    senha = (senha or "").strip()
    return len(senha) >= tamanho_minimo
# ─────────────────────────────────────────────────────────────────────────────

# ── CONTROLE DE SESSÃO ───────────────────────────────────────────────────────
@app.before_request
def verificar_sessao():
    """Verifica timeout de inatividade e sessão única."""
    rotas_livres = ['login', 'cadastro', 'static']
    if request.endpoint in rotas_livres:
        return

    if 'usuario' not in session:
        return

    # Timeout por inatividade (20 min)
    ultimo_acesso = session.get('ultimo_acesso')
    agora = datetime.utcnow().timestamp()
    if ultimo_acesso and (agora - ultimo_acesso) > 1200:  # 1200s = 20 min
        login_expirado = session.get('usuario')
        session.clear()
        _sessoes_ativas.pop(login_expirado, None)
        flash("Sua sessão expirou por inatividade. Faça login novamente.", "warning")
        return redirect(url_for('login'))

    session['ultimo_acesso'] = agora
    session.modified = True

    # Sessão única — verifica se o token ainda é válido
    login_atual = session.get('usuario')
    token_sessao = session.get('token_sessao')
    if login_atual and token_sessao:
        token_ativo = _sessoes_ativas.get(login_atual)
        if token_ativo and token_ativo != token_sessao:
            session.clear()
            flash("Sua conta foi acessada em outro dispositivo. Sessão encerrada.", "danger")
            return redirect(url_for('login'))
# ─────────────────────────────────────────────────────────────────────────────

# ── AUDITORIA ────────────────────────────────────────────────────────────────
def registrar_log(acao, descricao):
    """Registra uma ação de auditoria e limpa logs com mais de 30 dias."""
    from datetime import timedelta
    try:
        log = LogAuditoria(
            usuario_login=session.get("usuario", "sistema"),
            acao=acao,
            descricao=descricao,
            ip=request.remote_addr
        )
        db.session.add(log)

        # Limpeza automática de logs com mais de 30 dias
        limite = datetime.utcnow() - timedelta(days=30)
        LogAuditoria.query.filter(LogAuditoria.timestamp < limite).delete()

        db.session.commit()
    except Exception as e:
        print(f"Erro ao registrar log: {e}")
# ─────────────────────────────────────────────────────────────────────────────

# Rota de relatório/filtro para coordenador e admin
@app.route("/relatorio_reservas", methods=["GET", "POST"])
def relatorio_reservas():
    if "usuario" not in session:
        return redirect("/login")
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario:
        session.clear()
        return redirect("/login")
    if usuario.role not in ["coordenador", "admin", "super_admin"]:
        return "Acesso negado", 403

    # Redireciona POST para GET preservando filtros como query string
    if request.method == "POST":
        from flask import redirect, url_for
        return redirect(url_for("relatorio_reservas",
                                turma=request.form.get("turma", ""),
                                disciplina=request.form.get("disciplina", ""),
                                status=request.form.get("status", ""),
                                page=1))

    # Filtros via GET
    turma = request.args.get("turma", "").strip()
    disciplina = request.args.get("disciplina", "").strip()
    status = request.args.get("status", "").strip()
    page_rel = request.args.get("page", 1, type=int)
    PER_PAGE_REL = 20

    query = ReservaLab.query
    if turma:
        query = query.join(ReservaLab.turma_rel).filter(Turma.nome.ilike(f"%{turma}%"))
    if disciplina:
        query = query.filter(ReservaLab.disciplina.ilike(f"%{disciplina}%"))
    if status:
        query = query.filter(ReservaLab.status == status)

    query = query.order_by(ReservaLab.data.desc())
    total_rel = query.count()
    total_pages_rel = max(1, (total_rel + PER_PAGE_REL - 1) // PER_PAGE_REL)
    page_rel = max(1, min(page_rel, total_pages_rel))
    reservas = query.offset((page_rel - 1) * PER_PAGE_REL).limit(PER_PAGE_REL).all()

    # Para popular selects
    turmas = [t[0] for t in db.session.query(Turma.nome).join(ReservaLab, Turma.id == ReservaLab.turma_id).distinct().all() if t[0]]
    disciplinas = [d[0] for d in db.session.query(ReservaLab.disciplina).distinct().all() if d[0]]
    status_list = ["pending", "pre_approved", "approved", "rejected", "blocked"]

    return render_template(
        "relatorio_reservas.html",
        reservas=reservas,
        turmas=turmas,
        disciplinas=disciplinas,
        status_list=status_list,
        filtro_turma=turma,
        filtro_disciplina=disciplina,
        filtro_status=status,
        usuario_id=usuario.id,
        usuario_logado=usuario.login,
        page=page_rel,
        total_pages=total_pages_rel,
        total_rel=total_rel
    )


@app.route("/relatorio_reservas/exportar_csv")
def exportar_csv():
    if "usuario" not in session:
        return redirect("/login")
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario or usuario.role not in ["coordenador", "admin", "super_admin"]:
        return "Acesso negado", 403

    import csv, io
    from datetime import datetime as dt

    turma      = request.args.get("turma", "").strip()
    disciplina = request.args.get("disciplina", "").strip()
    status     = request.args.get("status", "").strip()

    query = ReservaLab.query
    if turma:
        query = query.join(ReservaLab.turma_rel).filter(Turma.nome.ilike(f"%{turma}%"))
    if disciplina:
        query = query.filter(ReservaLab.disciplina.ilike(f"%{disciplina}%"))
    if status:
        query = query.filter(ReservaLab.status == status)
    reservas = query.order_by(ReservaLab.data.desc()).all()

    status_labels = {
        'approved': 'Aprovada', 'pending': 'Pendente',
        'pre_approved': 'Pré-aprovada', 'rejected': 'Rejeitada', 'blocked': 'Bloqueio'
    }

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Laboratório', 'Professor', 'Turma', 'Disciplina', 'Data', 'Início', 'Fim', 'Status'])
    for r in reservas:
        writer.writerow([
            r.lab.nome if r.lab else '',
            r.professor or '',
            r.turma_rel.nome if r.turma_rel else '',
            r.disciplina or '',
            r.data or '',
            r.horario_inicio or '',
            r.horario_fim or '',
            status_labels.get(r.status, r.status),
        ])

    output.seek(0)
    filename = f"reservas_{dt.now().strftime('%Y%m%d_%H%M')}.csv"
    from flask import Response
    return Response(
        '\ufeff' + output.getvalue(),  # BOM UTF-8 para Excel abrir corretamente
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.route("/")
def index():
    if "usuario" in session:
        return redirect("/painel_unip")
    return redirect("/login")

# Rota de login (GET e POST)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        bloqueado, restante = _ip_bloqueado(ip)

        if bloqueado:
            minutos = restante // 60
            segundos = restante % 60
            flash(f"Muitas tentativas incorretas. Tente novamente em {minutos}m {segundos}s.", "danger")
            return render_template("login.html")

        login_form = request.form["usuario"]
        senha_form = request.form["senha"]
        
        usuario = Usuario.query.filter_by(login=login_form).first()
        
        if not usuario:
            _tentativas_login[ip].append(time.time())
            flash("Usuário não encontrado", "danger")
            return render_template("login.html")

        if not usuario.ativo:
            flash("Conta desativada. Entre em contato com o administrador.", "danger")
            return render_template("login.html")

        if bcrypt.checkpw(senha_form.encode(), usuario.senha_hash.encode()):
            # Login bem-sucedido — limpa tentativas do IP
            _tentativas_login[ip] = []
            session.clear()
            token = secrets.token_hex(32)
            session["usuario"] = usuario.login
            session["token_sessao"] = token
            session["ultimo_acesso"] = datetime.utcnow().timestamp()
            session.permanent = True
            _sessoes_ativas[usuario.login] = token
            registrar_log("LOGIN", f"Login realizado por {usuario.nome} ({usuario.role})")
            return redirect("/painel_unip")
        else:
            _tentativas_login[ip].append(time.time())
            tentativas_restantes = LIMITE_TENTATIVAS - len(_tentativas_login[ip])
            if tentativas_restantes > 0:
                flash(f"Senha incorreta. {tentativas_restantes} tentativa(s) restante(s).", "danger")
            else:
                flash("Muitas tentativas incorretas. Acesso bloqueado por 15 minutos.", "danger")
            return render_template("login.html")
            
    return render_template("login.html")

# Rota unificada de cadastro
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        # Whitelist: o cadastro público só permite criar contas de aluno.
        # Qualquer valor enviado pelo formulário para 'role' é ignorado.
        role = 'aluno'
        nome = request.form.get("nome") # Captura o nome do formulário
        login = (request.form.get("login") or "").strip()
        email = request.form.get("email")
        senha = request.form.get("senha")
        if not senha_minima_valida(senha):
            flash("A senha deve ter pelo menos 6 caracteres.", "danger")
            return render_template('cadastro.html')

        if not login_aluno_valido(login):
            flash("O RA deve conter apenas números.", "danger")
            return render_template('cadastro.html')
        
        # 1. Verificação de existência
        if Usuario.query.filter_by(login=login).first():
            flash("Este RA/ID já está cadastrado!", "danger")
            return render_template('cadastro.html')

        # 2. Criptografia segura
        senha_hash = bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # 3. Instância do Usuário
        novo_usuario = Usuario(
            nome=nome,
            login=login,
            email=email,
            senha_hash=senha_hash,
            role=role,
            ativo=True
        )

        # 4. Lógica de Turmas
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

@app.route("/api/notificacoes")
def api_notificacoes():
    """Retorna contagem de pendências e lista resumida para polling em tempo real."""
    if "usuario" not in session:
        return jsonify({"erro": "nao_autenticado"}), 401

    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario or not is_admin(usuario):
        return jsonify({"erro": "sem_permissao"}), 403

    pendentes = ReservaLab.query.filter_by(status='pending').count()
    pre_aprovadas = ReservaLab.query.filter_by(status='pre_approved').count()
    total = pendentes + pre_aprovadas

    # Lista resumida das reservas pendentes
    reservas_raw = ReservaLab.query.filter(
        ReservaLab.status.in_(['pending', 'pre_approved'])
    ).order_by(ReservaLab.id.desc()).limit(10).all()

    reservas = [{
        "id": r.id,
        "lab": r.lab.nome,
        "professor": r.professor,
        "data": r.data,
        "status": r.status
    } for r in reservas_raw]

    return jsonify({
        "total": total,
        "pendentes": pendentes,
        "pre_aprovadas": pre_aprovadas,
        "reservas": reservas
    })


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
        prof_login = request.form.get('professor') if is_admin(usuario_logado) or usuario_logado.role == 'coordenador' else usuario_logado.login
        
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
        if is_admin(usuario_logado):
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
            
            registrar_log("CRIAR_RESERVA", f"Reserva criada: {disciplina} em {nome_exibicao_prof} — {data_selecionada.strftime('%d/%m/%Y')}")
            msg = "Agendamento solicitado! Aguardando aprovação." if status_inicial == 'pending' else "Reserva registrada com sucesso!"
            flash(msg, "success")
            return redirect(url_for('painel_unip'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao salvar reserva: {str(e)}", "danger")

    # Dados para carregar os selects do HTML — só ativos/ativas
    laboratorios = Laboratorio.query.filter_by(status='ativo').all()
    turmas = Turma.query.filter_by(status='ativa').all()
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
        elif is_admin(usuario_logado):
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

@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    if "usuario" not in session:
        return redirect(url_for("login"))

    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario_logado:
        session.clear()
        return redirect("/login")

    reserva = ReservaLab.query.get(id)
    if not reserva:
        return redirect(url_for("painel_unip"))
    if not is_admin(usuario_logado) and usuario_logado.role != 'coordenador' and reserva.usuario_id != usuario_logado.id:
        return "Acesso negado", 403
    db.session.delete(reserva)
    db.session.commit()
    registrar_log("EXCLUIR_RESERVA", f"Reserva #{id} excluída")
    return redirect(url_for("painel_unip"))

@app.route("/admin/usuarios")
def admin_usuarios():
    if "usuario" not in session:
        return redirect("/login")
    
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario:
        session.clear()
        return redirect("/login")
    
    if not is_admin(usuario):
        return "Acesso negado", 403

    busca       = request.args.get('q', '').strip()
    filtro_role = request.args.get('role', '').strip()
    page        = request.args.get('page', 1, type=int)
    PER_PAGE    = 20

    # Base da query — admin comum não vê super_admin
    base_q = Usuario.query if is_super_admin(usuario) else Usuario.query.filter(Usuario.role != 'super_admin')
    if busca:
        base_q = base_q.filter(
            db.or_(Usuario.nome.ilike(f'%{busca}%'), Usuario.login.ilike(f'%{busca}%'), Usuario.email.ilike(f'%{busca}%'))
        )

    # Contadores por role (para os cards) — sem filtro de role
    count_total = base_q.count()
    count_admin = base_q.filter(Usuario.role.in_(['admin', 'super_admin'])).count()
    count_coord = base_q.filter(Usuario.role == 'coordenador').count()
    count_prof  = base_q.filter(Usuario.role == 'professor').count()
    count_aluno = base_q.filter(Usuario.role == 'aluno').count()

    # Aplica filtro de role depois dos contadores
    if filtro_role:
        base_q = base_q.filter(Usuario.role == filtro_role)

    total       = base_q.count()
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page        = max(1, min(page, total_pages))
    usuarios    = base_q.order_by(Usuario.nome).offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()

    turmas = Turma.query.filter_by(status='ativa').order_by(Turma.nome).all()

    # Conta reservas FUTURAS para os usuários da página atual
    from datetime import date as _date
    def _parse_data(d):
        try:
            if '-' in d: return _date.fromisoformat(d)
            return _date(int(d[6:10]), int(d[3:5]), int(d[0:2]))
        except: return _date(2000, 1, 1)
    hoje_d = _date.today()
    todas_reservas_futuras = [r for r in ReservaLab.query.all() if _parse_data(r.data) >= hoje_d]
    reservas_por_usuario = {}
    for u in usuarios:
        total_r = sum(1 for r in todas_reservas_futuras if r.usuario_id == u.id)
        if u.turma_id:
            total_r += sum(1 for r in todas_reservas_futuras if r.turma_id == u.turma_id and r.usuario_id != u.id)
        reservas_por_usuario[u.id] = total_r

    return render_template("admin_usuarios.html",
                           usuarios=usuarios,
                           usuario_logado=usuario,
                           turmas=turmas,
                           reservas_por_usuario=reservas_por_usuario,
                           page=page,
                           total_pages=total_pages,
                           total=total,
                           filtro_role=filtro_role,
                           busca=busca,
                           count_total=count_total,
                           count_admin=count_admin,
                           count_coord=count_coord,
                           count_prof=count_prof,
                           count_aluno=count_aluno)

@app.route("/admin/criar_usuario", methods=["POST"])
def criar_usuario():
    if "usuario" not in session:
        return redirect("/login")
    
    admin_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not is_admin(admin_logado):
        return "Acesso Negado", 403

    # Admin comum não pode criar super_admin ou admin
    role_nova_check = request.form.get("role")
    if not is_super_admin(admin_logado) and role_nova_check in ['admin', 'super_admin']:
        return "Acesso Negado", 403

    # 3. Coleta os dados (Adicionamos o 'nome' aqui)
    nome_novo = request.form.get("nome") # <--- CAPTURA O NOME
    login_novo = (request.form.get("login") or "").strip()
    email_novo = request.form.get("email")
    role_nova = request.form.get("role")
    senha_plana = request.form.get("senha")
    if not senha_minima_valida(senha_plana):
        flash("A senha deve ter pelo menos 6 caracteres.", "danger")
        return redirect(url_for("admin_usuarios"))

    if role_nova == 'aluno' and not login_aluno_valido(login_novo):
        flash("Para alunos, o campo login deve conter apenas números no RA.", "danger")
        return redirect(url_for("admin_usuarios"))
    
    hash_senha = bcrypt.hashpw(senha_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    novo_user = Usuario(
        nome=nome_novo,
        login=login_novo,
        email=email_novo,
        senha_hash=hash_senha,
        role=role_nova,
        ativo=True
    )

    # Se for aluno, vincula turma
    if role_nova == 'aluno':
        turma_id = request.form.get("turma_id")
        semestre = request.form.get("semestre")
        if turma_id:
            turma = Turma.query.get(int(turma_id))
            if turma:
                novo_user.turma_id = turma.id
                novo_user.turma = turma.nome
        novo_user.semestre = semestre or None

    try:
        db.session.add(novo_user)
        db.session.commit()
        registrar_log("CRIAR_USUARIO", f"Usuário '{login_novo}' ({role_nova}) criado")
        flash("Usuário criado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao criar usuário: {e}", "danger")

    return redirect(url_for("admin_usuarios"))

@app.route("/admin/editar_usuario/<int:id>", methods=["GET", "POST"])
def editar_usuario(id):
    if "usuario" not in session:
        return redirect("/login")
    
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not is_admin(usuario_logado):
        return "Acesso negado", 403

    user = Usuario.query.get_or_404(id)

    # Admin comum não pode editar super_admin ou admin
    if not is_super_admin(usuario_logado) and user.role in ['super_admin', 'admin']:
        return "Acesso negado", 403

    if request.method == "GET":
        turmas = Turma.query.filter_by(status='ativa').order_by(Turma.nome).all()
        return render_template("editar_usuario.html", user=user, turmas=turmas)

    # POST: Atualiza os dados
    user.nome = request.form.get("nome", user.nome)
    user.login = request.form.get("login", user.login)
    user.email = request.form.get("email", user.email)
    user.role = request.form.get("role", user.role)

    # Se for aluno, vincula turma pelo ID
    if user.role == 'aluno':
        turma_id = request.form.get("turma_id")
        if turma_id:
            turma = Turma.query.get(int(turma_id))
            if turma:
                user.turma_id = turma.id
                user.turma = turma.nome
        user.semestre = request.form.get("semestre") or None
    else:
        # Não-alunos não têm turma
        user.turma_id = None
        user.turma = None
        user.semestre = None

    # Se enviou nova_senha, criptografa e atualiza. Se não, mantém a atual.
    nova_senha = request.form.get("nova_senha")
    if nova_senha and nova_senha.strip() != "":
        if not senha_minima_valida(nova_senha):
            flash("A senha deve ter pelo menos 6 caracteres.", "danger")
            turmas = Turma.query.filter_by(status='ativa').order_by(Turma.nome).all()
            return render_template("editar_usuario.html", user=user, turmas=turmas)
        user.senha_hash = bcrypt.hashpw(nova_senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        db.session.commit()
        registrar_log("EDITAR_USUARIO", f"Usuário '{user.login}' editado")
        flash("Usuário atualizado com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao salvar: {e}", "danger")

    return redirect(url_for("admin_usuarios"))

@app.route("/admin/excluir_usuario/<int:id>", methods=["POST"])
def excluir_usuario(id):
    if "usuario" not in session:
        return redirect("/login")
    
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not is_admin(usuario_logado):
        return "Acesso negado", 403

    user = Usuario.query.get(id)
    # super_admin nunca pode ser deletado
    if user and user.role == 'super_admin':
        flash("O super admin não pode ser removido.", "danger")
        return redirect(url_for('admin_usuarios'))
    # Admin comum não pode deletar outros admins
    if user and not is_super_admin(usuario_logado) and user.role == 'admin':
        flash("Apenas o super admin pode remover administradores.", "danger")
        return redirect(url_for('admin_usuarios'))
    if user and user.role not in ['admin', 'super_admin']:
        nome_removido = user.nome
        # Remove reservas vinculadas antes para evitar ForeignKeyViolation
        ReservaLab.query.filter_by(usuario_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        registrar_log("EXCLUIR_USUARIO", f"Usuário '{nome_removido}' removido")
        flash(f"Usuário '{nome_removido}' removido com sucesso.", "success")

    return redirect(url_for("admin_usuarios"))

@app.route("/admin/perfil", methods=["GET", "POST"])
def admin_perfil():
    if "usuario" not in session:
        return redirect("/login")
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not is_admin(usuario):
        session.clear()
        return redirect("/login")
    if request.method == "POST":
        novo_login = request.form["login"]
        novo_email = request.form["email"]
        nova_senha = request.form.get("nova_senha")
        if nova_senha and not senha_minima_valida(nova_senha):
            flash("A senha deve ter pelo menos 6 caracteres.", "danger")
            return render_template("admin_perfil.html", usuario=usuario)
        usuario.login = novo_login
        usuario.email = novo_email
        if nova_senha:
            usuario.senha_hash = bcrypt.hashpw(nova_senha.encode(), bcrypt.gensalt()).decode()
        db.session.commit()
        return redirect(url_for("admin_perfil"))
    return render_template("admin_perfil.html", usuario=usuario)

@app.route("/admin/criar_laboratorio", methods=["POST"])
def criar_laboratorio():
    u = Usuario.query.filter_by(login=session.get("usuario")).first()
    if not is_admin(u):
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
    if "usuario" not in session:
        return redirect("/login")
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not is_admin(usuario_logado):
        return "Acesso negado", 403

    lab = Laboratorio.query.get(id)
    if lab:
        db.session.delete(lab)
        db.session.commit()
        flash("Laboratório removido!", "success")
    return redirect(url_for('painel_unip'))

@app.route("/admin/config")
def admin_config():
    if "usuario" not in session:
        return redirect("/login")
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not is_admin(usuario_logado):
        return redirect(url_for('painel_unip'))

    laboratorios = Laboratorio.query.order_by(Laboratorio.nome).all()
    turmas = Turma.query.order_by(Turma.nome).all()
    coordenadores = Usuario.query.filter(Usuario.role.in_(['coordenador', 'admin', 'super_admin'])).all()

    return render_template("admin_config.html",
                           usuario=usuario_logado,
                           laboratorios=laboratorios,
                           turmas=turmas,
                           coordenadores=coordenadores)

@app.route("/admin/editar_laboratorio/<int:id>", methods=["POST"])
def editar_laboratorio(id):
    if "usuario" not in session:
        return redirect("/login")
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not is_admin(usuario_logado):
        return redirect(url_for('painel_unip'))

    lab = Laboratorio.query.get_or_404(id)
    lab.nome = request.form.get('nome', lab.nome)
    lab.capacidade = int(request.form.get('capacidade', lab.capacidade))
    lab.status = request.form.get('status', lab.status)
    db.session.commit()

    # Se entrou em manutenção, cria um BloqueioLab automático para hoje em diante
    if lab.status == 'em_manutencao':
        from datetime import date, timedelta
        # Verifica se já existe bloqueio ativo para esse lab
        bloqueio_existente = BloqueioLab.query.filter(
            BloqueioLab.laboratorio_id == lab.id,
            BloqueioLab.data_fim >= date.today()
        ).first()
        if not bloqueio_existente:
            bloqueio = BloqueioLab(
                laboratorio_id=lab.id,
                data_inicio=date.today(),
                data_fim=date.today() + timedelta(days=365),
                motivo="Laboratório em manutenção"
            )
            db.session.add(bloqueio)
            db.session.commit()
            flash(f"{lab.nome} em manutenção! Bloqueio automático criado.", "warning")
    else:
        flash(f"{lab.nome} atualizado com sucesso!", "success")

    return redirect(url_for('admin_config'))

@app.route("/admin/editar_turma/<int:id>", methods=["POST"])
def editar_turma(id):
    if "usuario" not in session:
        return redirect("/login")
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not is_admin(usuario_logado):
        return redirect(url_for('painel_unip'))

    turma = Turma.query.get_or_404(id)
    turma.status = request.form.get('status', turma.status)
    coord_id = request.form.get('coordenador_id')
    turma.coordenador_id = int(coord_id) if coord_id else None
    db.session.commit()
    flash(f"Turma {turma.nome} atualizada!", "success")
    return redirect(url_for('admin_config'))

@app.route("/admin/criar_turma", methods=["POST"])
def criar_turma():
    u = Usuario.query.filter_by(login=session.get("usuario")).first()
    if not is_admin(u):
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
    if not is_admin(usuario_logado) and usuario_logado.role != 'coordenador':
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
        registrar_log("CRIAR_BLOQUEIO", f"Bloqueio criado: Lab #{lab_id} de {inicio_str} a {fim_str} — {motivo}")
        return redirect(url_for('gerenciar_bloqueios'))

    bloqueios = BloqueioLab.query.all()
    lista_laboratorios = Laboratorio.query.all()
    
    return render_template("admin_bloqueios.html", 
                           bloqueios=bloqueios, 
                           laboratorios=lista_laboratorios) # Passa para o HTML

@app.route("/admin/excluir_bloqueio/<int:id>")
def excluir_bloqueio(id):
    if "usuario" not in session: return redirect("/login")
    
    # Apenas Admin/Coord podem excluir bloqueios
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if is_admin(usuario) or usuario.role == 'coordenador':
        bloqueio = BloqueioLab.query.get(id)
        if bloqueio:
            db.session.delete(bloqueio)
            db.session.commit()
            registrar_log("EXCLUIR_BLOQUEIO", f"Bloqueio #{id} removido")
            flash("Bloqueio removido com sucesso!", "success")

    return redirect(url_for('gerenciar_bloqueios'))

@app.route("/coordenador/reservas")
def coordenador_reservas():
    if "usuario" not in session:
        return redirect("/login")

    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario or usuario.role not in ['coordenador', 'admin', 'super_admin']:
        return "Acesso negado", 403

    # Filtros do histórico
    filtro_lab    = request.args.get('lab', '').strip()
    filtro_status = request.args.get('status', '').strip()
    filtro_de     = request.args.get('de', '').strip()
    filtro_ate    = request.args.get('ate', '').strip()
    hist_page     = request.args.get('hpage', 1, type=int)
    PER_PAGE      = 20

    # Base de pendentes e histórico
    if is_admin(usuario):
        q_pendentes = ReservaLab.query.filter(
            or_(ReservaLab.status == 'pending', ReservaLab.status == 'pre_approved')
        )
        q_hist = ReservaLab.query
    else:
        turmas_do_coord = [t.id for t in Turma.query.filter_by(coordenador_id=usuario.id).all()]
        q_pendentes = ReservaLab.query.filter(
            or_(ReservaLab.status == 'pending', ReservaLab.status == 'pre_approved'),
            ReservaLab.turma_id.in_(turmas_do_coord)
        )
        q_hist = ReservaLab.query.filter(ReservaLab.turma_id.in_(turmas_do_coord))

    reservas_pendentes = q_pendentes.order_by(ReservaLab.data.asc()).all()

    # Aplica filtros ao histórico
    if filtro_lab:
        lab_obj = Laboratorio.query.filter_by(nome=filtro_lab).first()
        if lab_obj:
            q_hist = q_hist.filter(ReservaLab.laboratorio_id == lab_obj.id)
        else:
            q_hist = q_hist.filter(db.false())
    if filtro_status:
        q_hist = q_hist.filter(ReservaLab.status == filtro_status)
    if filtro_de:
        try:
            from datetime import datetime as _dt
            de_iso = _dt.strptime(filtro_de, '%Y-%m-%d').strftime('%d/%m/%Y')
            q_hist = q_hist.filter(ReservaLab.data >= de_iso)
        except: pass
    if filtro_ate:
        try:
            from datetime import datetime as _dt
            ate_iso = _dt.strptime(filtro_ate, '%Y-%m-%d').strftime('%d/%m/%Y')
            q_hist = q_hist.filter(ReservaLab.data <= ate_iso)
        except: pass

    hist_total     = q_hist.count()
    hist_pages     = max(1, (hist_total + PER_PAGE - 1) // PER_PAGE)
    hist_page      = max(1, min(hist_page, hist_pages))
    todas_reservas = q_hist.order_by(ReservaLab.data.desc()).offset((hist_page - 1) * PER_PAGE).limit(PER_PAGE).all()

    labs = Laboratorio.query.order_by(Laboratorio.nome).all()

    return render_template("coordenador_reservas.html",
                           reservas_pendentes=reservas_pendentes,
                           todas_reservas=todas_reservas,
                           usuario_logado=usuario,
                           labs=labs,
                           filtro_lab=filtro_lab,
                           filtro_status=filtro_status,
                           filtro_de=filtro_de,
                           filtro_ate=filtro_ate,
                           hist_page=hist_page,
                           hist_pages=hist_pages,
                           hist_total=hist_total)

# ROTA DE APROVAÇÃO (CORRIGIDA PARA ADMIN FINALIZAR COORDENADOR)
@app.route("/aprovar_reserva/<int:id>", methods=["POST"])
def aprovar_reserva(id):
    if "usuario" not in session: return redirect("/login")
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    reserva = ReservaLab.query.get_or_404(id)
    
    if is_admin(usuario):
        # Revalidar conflito antes de aprovar
        conflito = ReservaLab.query.filter(
            ReservaLab.id != id,
            ReservaLab.laboratorio_id == reserva.laboratorio_id,
            ReservaLab.data == reserva.data,
            ReservaLab.horario_inicio < reserva.horario_fim,
            ReservaLab.horario_fim > reserva.horario_inicio,
            ReservaLab.status == 'approved'
        ).first()
        if conflito:
            flash(f"Conflito detectado! {conflito.lab.nome} já está aprovado para {conflito.professor} neste horário. Aprovação bloqueada.", "danger")
            db.session.rollback()
            return redirect(url_for("coordenador_reservas"))

        reserva.status = 'approved'
        registrar_log("APROVAR_RESERVA", f"Reserva #{id} aprovada definitivamente")
        flash("Reserva finalizada com sucesso!", "success")
        # Notificar professor por email
        prof = Usuario.query.filter_by(nome=reserva.professor).first()
        if prof and prof.email:
            enviar_email(
                prof.email,
                f"✅ Reserva aprovada — {reserva.lab.nome}",
                f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
                    <div style="background:#003366;padding:20px;text-align:center">
                        <h2 style="color:#f5b915;margin:0">UNIP Lab Manager</h2>
                    </div>
                    <div style="padding:24px;background:#f8f9fa">
                        <h3 style="color:#198754">✅ Sua reserva foi aprovada!</h3>
                        <p>Olá, <strong>{prof.nome}</strong>!</p>
                        <p>Sua reserva foi <strong>aprovada</strong> com sucesso.</p>
                        <table style="width:100%;border-collapse:collapse;margin:16px 0">
                            <tr><td style="padding:8px;background:#e9ecef"><strong>Laboratório</strong></td><td style="padding:8px">{reserva.lab.nome}</td></tr>
                            <tr><td style="padding:8px;background:#e9ecef"><strong>Data</strong></td><td style="padding:8px">{reserva.data}</td></tr>
                            <tr><td style="padding:8px;background:#e9ecef"><strong>Horário</strong></td><td style="padding:8px">{reserva.horario_inicio} - {reserva.horario_fim}</td></tr>
                            <tr><td style="padding:8px;background:#e9ecef"><strong>Disciplina</strong></td><td style="padding:8px">{reserva.disciplina}</td></tr>
                        </table>
                        <p style="color:#6c757d;font-size:0.85rem">UNIP Lab Manager — Sistema de Gestão de Laboratórios</p>
                    </div>
                </div>"""
            )
    elif usuario.role == 'coordenador':
        if reserva.status == 'pending':
            # Revalidar conflito antes de pré-aprovar
            conflito = ReservaLab.query.filter(
                ReservaLab.id != id,
                ReservaLab.laboratorio_id == reserva.laboratorio_id,
                ReservaLab.data == reserva.data,
                ReservaLab.horario_inicio < reserva.horario_fim,
                ReservaLab.horario_fim > reserva.horario_inicio,
                ReservaLab.status.in_(['approved', 'pre_approved'])
            ).first()
            if conflito:
                flash(f"Conflito detectado! {conflito.lab.nome} já tem uma reserva aprovada neste horário para {conflito.professor}. Pré-aprovação bloqueada.", "danger")
                return redirect(url_for("coordenador_reservas"))

            reserva.status = 'pre_approved'
            registrar_log("PRE_APROVAR_RESERVA", f"Reserva #{id} pré-aprovada")
            flash("Pré-aprovação realizada! Aguardando Admin.", "info")
            # Notificar professor sobre pré-aprovação
            prof = Usuario.query.filter_by(nome=reserva.professor).first()
            if prof and prof.email:
                enviar_email(
                    prof.email,
                    f"🔵 Reserva pré-aprovada — {reserva.lab.nome}",
                    f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
                        <div style="background:#003366;padding:20px;text-align:center">
                            <h2 style="color:#f5b915;margin:0">UNIP Lab Manager</h2>
                        </div>
                        <div style="padding:24px;background:#f8f9fa">
                            <h3 style="color:#0d6efd">🔵 Sua reserva foi pré-aprovada!</h3>
                            <p>Olá, <strong>{prof.nome}</strong>!</p>
                            <p>Sua reserva foi <strong>pré-aprovada</strong> pelo coordenador e aguarda aprovação final do administrador.</p>
                            <table style="width:100%;border-collapse:collapse;margin:16px 0">
                                <tr><td style="padding:8px;background:#e9ecef"><strong>Laboratório</strong></td><td style="padding:8px">{reserva.lab.nome}</td></tr>
                                <tr><td style="padding:8px;background:#e9ecef"><strong>Data</strong></td><td style="padding:8px">{reserva.data}</td></tr>
                                <tr><td style="padding:8px;background:#e9ecef"><strong>Horário</strong></td><td style="padding:8px">{reserva.horario_inicio} - {reserva.horario_fim}</td></tr>
                                <tr><td style="padding:8px;background:#e9ecef"><strong>Disciplina</strong></td><td style="padding:8px">{reserva.disciplina}</td></tr>
                            </table>
                            <p style="color:#6c757d;font-size:0.85rem">UNIP Lab Manager — Sistema de Gestão de Laboratórios</p>
                        </div>
                    </div>"""
                )
        else:
            flash("Você não tem permissão para aprovação final.", "warning")

    db.session.commit()
    return redirect(url_for("coordenador_reservas"))

@app.route("/rejeitar_reserva/<int:id>", methods=["POST"])
def rejeitar_reserva(id):
    if "usuario" not in session:
        return redirect("/login")
    
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario or (not is_admin(usuario) and usuario.role != 'coordenador'):
        return "Acesso negado", 403

    reserva = ReservaLab.query.get_or_404(id)
    reserva.status = 'rejected'
    db.session.commit()
    registrar_log("REJEITAR_RESERVA", f"Reserva #{id} rejeitada")
    flash("Reserva rejeitada.", "warning")
    # Notificar professor sobre rejeição
    prof = Usuario.query.filter_by(nome=reserva.professor).first()
    if prof and prof.email:
        enviar_email(
            prof.email,
            f"❌ Reserva rejeitada — {reserva.lab.nome}",
            f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
                <div style="background:#003366;padding:20px;text-align:center">
                    <h2 style="color:#f5b915;margin:0">UNIP Lab Manager</h2>
                </div>
                <div style="padding:24px;background:#f8f9fa">
                    <h3 style="color:#dc3545">❌ Sua reserva foi rejeitada</h3>
                    <p>Olá, <strong>{prof.nome}</strong>!</p>
                    <p>Infelizmente sua reserva foi <strong>rejeitada</strong>.</p>
                    <table style="width:100%;border-collapse:collapse;margin:16px 0">
                        <tr><td style="padding:8px;background:#e9ecef"><strong>Laboratório</strong></td><td style="padding:8px">{reserva.lab.nome}</td></tr>
                        <tr><td style="padding:8px;background:#e9ecef"><strong>Data</strong></td><td style="padding:8px">{reserva.data}</td></tr>
                        <tr><td style="padding:8px;background:#e9ecef"><strong>Horário</strong></td><td style="padding:8px">{reserva.horario_inicio} - {reserva.horario_fim}</td></tr>
                        <tr><td style="padding:8px;background:#e9ecef"><strong>Disciplina</strong></td><td style="padding:8px">{reserva.disciplina}</td></tr>
                    </table>
                    <p>Em caso de dúvidas, entre em contato com a coordenação.</p>
                    <p style="color:#6c757d;font-size:0.85rem">UNIP Lab Manager — Sistema de Gestão de Laboratórios</p>
                </div>
            </div>"""
        )

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
    
    # 2. Se o professor escolheu uma turma, buscamos os alunos pelo turma_id
    alunos_da_turma = []
    if turma_selecionada:
        turma_obj = Turma.query.filter_by(nome=turma_selecionada).first()
        if turma_obj:
            alunos_da_turma = Usuario.query.filter_by(role='aluno', turma_id=turma_obj.id).all()
    
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
        from datetime import date
        hoje = date.today()
        # Busca aprovadas da turma e filtra por data futura em Python (campo data pode ser DD/MM/YYYY ou YYYY-MM-DD)
        reservas_todas_turma = ReservaLab.query.filter_by(
            turma_id=usuario_logado.turma_id,
            status='approved'
        ).all()
        def parse_data(d):
            try:
                if '-' in d: return date.fromisoformat(d)
                return date(int(d[6:10]), int(d[3:5]), int(d[0:2]))
            except: return date(2000,1,1)
        reservas_turma = sorted(
            [r for r in reservas_todas_turma if parse_data(r.data) >= hoje],
            key=lambda r: parse_data(r.data)
        )
        
        return render_template("painel_aluno.html", 
                               usuario=usuario_logado, # Enviamos o objeto todo para o template
                               reservas=reservas_turma,
                               bloqueios=bloqueios)
    
    # --- VISÃO GESTÃO (Prof/Coord/Admin) ---
    from datetime import date
    hoje_str = date.today().strftime('%d/%m/%Y')

    # Reservas ativas (hoje ou futuras) — sem paginação, geralmente poucas
    reservas_ativas = [r for r in ReservaLab.query.order_by(ReservaLab.data.asc()).all()
                       if r.data >= hoje_str]

    # ── FILTROS DO HISTÓRICO ──────────────────────────────────
    historico_page      = request.args.get('hpage', 1, type=int)
    filtro_hist_lab     = request.args.get('hlab', '').strip()
    filtro_hist_status  = request.args.get('hstatus', '').strip()
    filtro_hist_data_de = request.args.get('hde', '').strip()
    filtro_hist_data_ate= request.args.get('hate', '').strip()

    PER_PAGE = 10

    # Parte de todas as reservas vencidas como base
    todas_vencidas_query = [r for r in ReservaLab.query.order_by(ReservaLab.data.desc()).all()
                            if r.data < hoje_str]

    # Aplica filtros em Python (compatível com datas em string DD/MM/YYYY)
    if filtro_hist_lab:
        todas_vencidas_query = [r for r in todas_vencidas_query
                                if r.lab and str(r.lab.id) == filtro_hist_lab]
    if filtro_hist_status:
        todas_vencidas_query = [r for r in todas_vencidas_query
                                if r.status == filtro_hist_status]
    if filtro_hist_data_de:
        try:
            de_str = datetime.strptime(filtro_hist_data_de, '%Y-%m-%d').strftime('%d/%m/%Y')
            todas_vencidas_query = [r for r in todas_vencidas_query if r.data >= de_str]
        except ValueError:
            pass
    if filtro_hist_data_ate:
        try:
            ate_str = datetime.strptime(filtro_hist_data_ate, '%Y-%m-%d').strftime('%d/%m/%Y')
            todas_vencidas_query = [r for r in todas_vencidas_query if r.data <= ate_str]
        except ValueError:
            pass

    total_vencidas  = len(todas_vencidas_query)
    total_pages     = max(1, (total_vencidas + PER_PAGE - 1) // PER_PAGE)
    historico_page  = max(1, min(historico_page, total_pages))
    offset          = (historico_page - 1) * PER_PAGE
    reservas_vencidas = todas_vencidas_query[offset: offset + PER_PAGE]
    # ─────────────────────────────────────────────────────────

    usuarios, todos_labs, todas_turmas = [], [], []
    # Labs sempre carregados — necessário para o filtro do histórico em todos os roles
    todos_labs = Laboratorio.query.order_by(Laboratorio.nome).all()
    if is_admin(usuario_logado):
        usuarios = Usuario.query.all()
        todas_turmas = Turma.query.all()

    # super_admin herda visual de admin no painel
    role_display = 'admin' if usuario_logado.role == 'super_admin' else usuario_logado.role
    return render_template("lista.html", 
                           usuario=usuario_logado,
                           usuario_id=usuario_logado.id, 
                           role=role_display,
                           is_super_admin=is_super_admin(usuario_logado),
                           reservas=reservas_ativas,
                           reservas_vencidas=reservas_vencidas,
                           historico_page=historico_page,
                           historico_total_pages=total_pages,
                           historico_total=total_vencidas,
                           filtro_hist_lab=filtro_hist_lab,
                           filtro_hist_status=filtro_hist_status,
                           filtro_hist_data_de=filtro_hist_data_de,
                           filtro_hist_data_ate=filtro_hist_data_ate,
                           usuarios=usuarios,
                           laboratorios=todos_labs,
                           turmas=todas_turmas,
                           bloqueios=bloqueios,
                           now=datetime.utcnow() - __import__('datetime').timedelta(hours=3))


# Rota /bloquear_lab removida — use /admin/bloqueios (gerenciar_bloqueios)
# Rotas /pre_aprovar_reserva e /confirmar_reserva removidas — use /aprovar_reserva (com lógica de role)


@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        return redirect("/login")
    usuario_logado = Usuario.query.filter_by(login=session["usuario"]).first()
    if not usuario_logado or not is_admin(usuario_logado):
        flash("Acesso restrito.", "danger")
        return redirect("/painel_unip")

    from datetime import date
    from sqlalchemy import func

    # KPIs gerais
    total_reservas   = ReservaLab.query.count()
    total_aprovadas  = ReservaLab.query.filter_by(status='approved').count()
    total_pendentes  = ReservaLab.query.filter_by(status='pending').count()
    total_rejeitadas = ReservaLab.query.filter_by(status='rejected').count()
    total_usuarios   = Usuario.query.count()
    total_labs       = Laboratorio.query.count()
    taxa_aprovacao   = round((total_aprovadas / total_reservas * 100), 1) if total_reservas else 0

    # Labs mais usados
    labs_mais_usados = (
        db.session.query(Laboratorio.nome, func.count(ReservaLab.id).label('total'))
        .join(ReservaLab, ReservaLab.laboratorio_id == Laboratorio.id)
        .filter(ReservaLab.status == 'approved')
        .group_by(Laboratorio.id, Laboratorio.nome)
        .order_by(func.count(ReservaLab.id).desc())
        .limit(6).all()
    )

    # Horários de pico
    horarios_pico = (
        db.session.query(ReservaLab.horario_inicio, func.count(ReservaLab.id).label('total'))
        .filter(ReservaLab.status == 'approved')
        .group_by(ReservaLab.horario_inicio)
        .order_by(func.count(ReservaLab.id).desc())
        .limit(8).all()
    )

    # Distribuição por status
    status_counts = (
        db.session.query(ReservaLab.status, func.count(ReservaLab.id).label('total'))
        .group_by(ReservaLab.status)
        .all()
    )

    # Professores mais ativos
    professores_ativos = (
        db.session.query(ReservaLab.professor, func.count(ReservaLab.id).label('total'))
        .filter(ReservaLab.status == 'approved')
        .group_by(ReservaLab.professor)
        .order_by(func.count(ReservaLab.id).desc())
        .limit(5).all()
    )

    # Turmas mais ativas
    turmas_ativas = (
        db.session.query(Turma.nome, func.count(ReservaLab.id).label('total'))
        .join(ReservaLab, ReservaLab.turma_id == Turma.id)
        .filter(ReservaLab.status == 'approved')
        .group_by(Turma.id, Turma.nome)
        .order_by(func.count(ReservaLab.id).desc())
        .limit(5).all()
    )

    # Últimas reservas aprovadas
    ultimas_reservas = (
        ReservaLab.query.filter_by(status='approved')
        .order_by(ReservaLab.id.desc())
        .limit(5).all()
    )

    return render_template("dashboard.html",
        usuario=usuario_logado,
        total_reservas=total_reservas,
        total_aprovadas=total_aprovadas,
        total_pendentes=total_pendentes,
        total_rejeitadas=total_rejeitadas,
        total_usuarios=total_usuarios,
        total_labs=total_labs,
        taxa_aprovacao=taxa_aprovacao,
        labs_mais_usados=labs_mais_usados,
        horarios_pico=horarios_pico,
        status_counts=status_counts,
        professores_ativos=professores_ativos,
        turmas_ativas=turmas_ativas,
        ultimas_reservas=ultimas_reservas,
    )


@app.route("/admin/logs")
def admin_logs():
    if "usuario" not in session:
        return redirect("/login")
    usuario = Usuario.query.filter_by(login=session["usuario"]).first()
    if not is_super_admin(usuario):
        return "Acesso negado", 403

    busca_log = request.args.get("q", "").strip()
    filtro_acao = request.args.get("acao", "").strip()
    page_log = request.args.get("page", 1, type=int)
    PER_PAGE_LOG = 25

    query_logs = LogAuditoria.query
    if busca_log:
        query_logs = query_logs.filter(
            db.or_(LogAuditoria.acao.ilike(f"%{busca_log}%"), LogAuditoria.descricao.ilike(f"%{busca_log}%"))
        )
    if filtro_acao:
        query_logs = query_logs.filter(LogAuditoria.acao == filtro_acao)

    query_logs = query_logs.order_by(LogAuditoria.timestamp.desc())
    total_logs = query_logs.count()
    total_pages_log = max(1, (total_logs + PER_PAGE_LOG - 1) // PER_PAGE_LOG)
    page_log = max(1, min(page_log, total_pages_log))
    logs = query_logs.offset((page_log - 1) * PER_PAGE_LOG).limit(PER_PAGE_LOG).all()

    acoes_disponiveis = [a[0] for a in db.session.query(LogAuditoria.acao).distinct().order_by(LogAuditoria.acao).all() if a[0]]

    return render_template("admin_logs.html",
                           logs=logs,
                           usuario=usuario,
                           page=page_log,
                           total_pages=total_pages_log,
                           total_logs=total_logs,
                           busca=busca_log,
                           filtro_acao=filtro_acao,
                           acoes_disponiveis=acoes_disponiveis)

@app.route("/esqueci_senha", methods=["GET", "POST"])
def esqueci_senha():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        usuario = Usuario.query.filter_by(email=email).first()

        # Resposta genérica para não vazar se email existe
        msg_generica = "Se este email estiver cadastrado, você receberá as instruções. Caso não receba, entre em contato com o administrador."

        if usuario:
            token = secrets.token_urlsafe(32)
            usuario.reset_token = token
            usuario.reset_token_expiry = datetime.utcnow() + __import__('datetime').timedelta(hours=2)
            db.session.commit()
            registrar_log("RESET_SENHA_SOLICITADO", f"Solicitação de reset para {email}")

            # Tenta enviar email
            link = url_for('redefinir_senha', token=token, _external=True)
            enviado = False
            try:
                enviado = enviar_email(
                    email,
                    "🔑 Redefinição de senha — UNIP Lab Manager",
                    f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
                        <div style="background:#003366;padding:20px;text-align:center">
                            <h2 style="color:#f5b915;margin:0">UNIP Lab Manager</h2>
                        </div>
                        <div style="padding:24px;background:#f8f9fa">
                            <h3 style="color:#003366">Redefinição de Senha</h3>
                            <p>Olá, <strong>{usuario.nome}</strong>!</p>
                            <p>Clique no botão abaixo para redefinir sua senha. O link expira em <strong>2 horas</strong>.</p>
                            <div style="text-align:center;margin:24px 0">
                                <a href="{link}" style="background:#003366;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold">
                                    Redefinir Senha
                                </a>
                            </div>
                            <p style="color:#6c757d;font-size:0.85rem">Se não solicitou, ignore este email.</p>
                        </div>
                    </div>"""
                )
            except:
                pass

            if not enviado:
                # SMTP bloqueado — orientar contato com admin
                flash(f"Email não pôde ser enviado automaticamente. Entre em contato com o administrador informando seu login para que ele redefina sua senha.", "warning")
                return render_template("login.html")

        flash(msg_generica, "info")
        return redirect(url_for("login"))

    return render_template("esqueci_senha.html")


@app.route("/redefinir_senha/<token>", methods=["GET", "POST"])
def redefinir_senha(token):
    usuario = Usuario.query.filter_by(reset_token=token).first()

    if not usuario or not usuario.reset_token_expiry:
        flash("Link inválido ou expirado.", "danger")
        return redirect(url_for("login"))

    if datetime.utcnow() > usuario.reset_token_expiry:
        usuario.reset_token = None
        usuario.reset_token_expiry = None
        db.session.commit()
        flash("Este link expirou. Solicite um novo.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        nova_senha = request.form.get("nova_senha", "")
        confirmar = request.form.get("confirmar_senha", "")

        if len(nova_senha) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "danger")
            return render_template("redefinir_senha.html", token=token)

        if nova_senha != confirmar:
            flash("As senhas não coincidem.", "danger")
            return render_template("redefinir_senha.html", token=token)

        usuario.senha_hash = bcrypt.hashpw(nova_senha.encode(), bcrypt.gensalt()).decode()
        usuario.reset_token = None
        usuario.reset_token_expiry = None
        db.session.commit()
        registrar_log("RESET_SENHA_CONCLUIDO", f"Senha redefinida para {usuario.login}")
        flash("Senha redefinida com sucesso! Faça login.", "success")
        return redirect(url_for("login"))

    return render_template("redefinir_senha.html", token=token)



@app.route("/logout")
def logout():
    registrar_log("LOGOUT", f"Logout realizado")
    login_saindo = session.get('usuario')
    _sessoes_ativas.pop(login_saindo, None)
    session.clear()
    return redirect("/login")



# -- ERROR HANDLERS --
@app.errorhandler(400)
def erro_400(e):
    return render_template('erro.html', codigo=400,
        titulo='Requisicao Invalida',
        mensagem='Token de seguranca invalido ou expirado. Recarregue a pagina e tente novamente.',
        icone='bi-shield-exclamation'), 400

@app.errorhandler(403)
def erro_403(e):
    return render_template('erro.html', codigo=403,
        titulo='Acesso Negado',
        mensagem='Voce nao tem permissao para acessar esta pagina.',
        icone='bi-shield-lock-fill'), 403

@app.errorhandler(404)
def erro_404(e):
    return render_template('erro.html', codigo=404,
        titulo='Pagina Nao Encontrada',
        mensagem='A pagina que voce esta procurando nao existe ou foi movida.',
        icone='bi-compass'), 404

@app.errorhandler(500)
def erro_500(e):
    db.session.rollback()
    return render_template('erro.html', codigo=500,
        titulo='Erro Interno',
        mensagem='Algo deu errado no servidor. Tente novamente em instantes.',
        icone='bi-exclamation-triangle-fill'), 500

@app.errorhandler(405)
def erro_405(e):
    return render_template('erro.html', codigo=405,
        titulo='Metodo nao permitido',
        mensagem='Esta acao nao pode ser realizada desta forma.',
        icone='bi-slash-circle'), 405

# Inicializa o banco ao subir com gunicorn ou diretamente
with app.app_context():
    db.create_all()
    inicializar_unidade()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
