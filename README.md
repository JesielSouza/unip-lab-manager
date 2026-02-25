# 🏫 UNIP - Gestão de Laboratórios

Sistema para controle de ocupação de laboratórios de informática, permitindo o registro de aulas por professor, turma e disciplina.

## 📋 Funcionalidades
- **Agendamento por Período**: Manhã, Tarde e Noite.
- **Vínculo Acadêmico**: Registro completo com Professor, Turma e Disciplina.
- **Filtro por Laboratório**: Organização clara de qual sala está ocupada.

## 🛠️ Setup
1. Instale as dependências: `pip install -r requirements.txt`
2. Inicie o banco: `python -c "from app import db; db.create_all()"`
3. Execute: `python app.py`
