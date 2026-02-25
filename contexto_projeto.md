📑 Contexto de Migração: Do "Tarefas" para "UNIP Lab Manager"
1. Origem do Código
O projeto está sendo construído reaproveitando a estrutura de um "Organizador de Tarefas" anterior.

2. O que precisa ser adaptado (Refatoração):
Banco de Dados: Onde era Tarefa(id, descricao, status), agora deve ser ReservaLab(id, laboratorio, professor, disciplina, data, horario).

Rotas: A rota que listava tarefas agora deve listar as reservas dos laboratórios de informática.

Templates: O CSS e o Layout base serão mantidos, mas os formulários devem ser alterados de "Nova Tarefa" para "Nova Reserva".

3. Foco do MVP (Fase 1)
Público: Apenas Laboratórios de Informática da UNIP.

Funcionalidade: CRUD básico (Criar, Ler, Atualizar, Deletar) de reservas.

Pendência: Resolver o erro remote origin already exists no terminal do VSCode.