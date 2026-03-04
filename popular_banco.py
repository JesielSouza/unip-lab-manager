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
    
    turma_ads = Turma.query.filter_by(nome="ADS1P30").first()

    usuarios_dados = [
        {"login": "coord", "nome": "Coordenador Teste", "role": "coordenador", "email": "coord@unip.br", "turma_id": None},
        {"login": "prof_jose", "nome": "Prof. José Silva", "role": "professor", "email": "jose@unip.br", "turma_id": None},
        {"login": "aluno_teste", "nome": "Aluno Teste", "role": "aluno", "email": "aluno@unip.br", "turma_id": turma_ads.id if turma_ads else None},
    ]

    for dado in usuarios_dados:
        if not Usuario.query.filter_by(login=dado["login"]).first():
            user = Usuario(
                login=dado["login"],
                nome=dado["nome"],
                email=dado["email"],
                senha_hash=senha_padrao,
                role=dado["role"],
                turma_id=dado["turma_id"],
                semestre="1º Semestre" if dado["role"] == "aluno" else None,
            )
            db.session.add(user)
    
    try:
        db.session.commit()
        print("\n✅ Banco populado com sucesso!")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao salvar: {e}")