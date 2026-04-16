import sqlite3

def criar_estrutura():
    conexao = sqlite3.connect('painel_dados.db')
    cursor = conexao.cursor()

    # Criando a tabela de anotações e lembretes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            conteudo TEXT,
            categoria TEXT, -- Ex: Estudo, Financeiro, Trabalho
            prioridade TEXT, -- Ex: Alta, Média, Baixa
            tipo TEXT, -- Ex: Nota ou Lembrete
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_vencimento DATE, -- Para os lembretes de conta
            dias_aviso INTEGER, -- Quantos dias antes avisar
            status TEXT DEFAULT 'Ativo' -- Ex: Ativo ou Concluído
        )
    ''')

    conexao.commit()
    conexao.close()
    print("Banco de dados do Painel Pessoal configurado com sucesso!")

if __name__ == "__main__":
    criar_estrutura()