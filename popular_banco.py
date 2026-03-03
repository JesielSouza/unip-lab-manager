from app import app, db, Usuario, Laboratorio, Turma
import bcrypt

def gerar_senha(senha_plana):
    return bcrypt.hashpw(senha_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

with app.app_context():
    print("Iniciando a carga de dados...")

    # 1. Criar Laboratórios
    if not Laboratorio.query.first():
        labs = [
            Laboratorio(nome="Laboratório de Informática 01", capacidade=40),
            Laboratorio(nome="Laboratório de Informática 02", capacidade=30),
            Laboratorio(nome="Auditório Alpha", capacidade=120)
        ]
        db.session.add_all(labs)
        print("- Laboratórios criados.")

    # 2. Criar Turmas
    if not Turma.query.first():
        turmas = [
            Turma(nome="ADS1P30", curso="Análise e Desenv. de Sistemas", semestre="1º Semestre"),
            Turma(nome="CC3A18", curso="Ciência da Computação", semestre="3º Semestre"),
            Turma(nome="DIR5B10", curso="Direito", semestre="5º Semestre")
        ]
        db.session.add_all(turmas)
        print("- Turmas criadas.")

    # 3. Criar Usuários (Removido o campo 'nome' que não existe no seu model)
    senha_padrao = gerar_senha("unip123")
    
    usuarios_dados = [
        {"login": "coord", "role": "coordenador", "email": "coord@unip.br", "turma": "COORDENACAO", "semestre": "-"},
        {"login": "prof_jose", "role": "professor", "email": "jose@unip.br", "turma": "DOCENTE", "semestre": "-"},
        {"login": "aluno_teste", "role": "aluno", "email": "aluno@unip.br", "turma": "ADS1P30", "semestre": "1"}
    ]

    for dado in usuarios_dados:
        if not Usuario.query.filter_by(login=dado["login"]).first():
            user = Usuario(
                login=dado["login"],
                email=dado["email"],
                senha_hash=senha_padrao,
                role=dado["role"],
                turma=dado["turma"],
                semestre=dado["semestre"]
            )
            db.session.add(user)
    
    try:
        db.session.commit()
        print("\n✅ Banco populado com sucesso!")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao salvar: {e}")