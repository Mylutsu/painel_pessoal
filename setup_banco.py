import sqlite3

def conectar():
    return sqlite3.connect('painel_dados.db')

def criar_estrutura():
    conexao = conectar()
    cursor = conexao.cursor()

    #limpar tabelas caso necessário
    cursor.execute("DROP TABLE IF EXISTS notas")
    cursor.execute("DROP TABLE IF EXISTS categorias")

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
            status TEXT DEFAULT 'Ativo', -- Ex: Ativo ou Concluído
            data_exclusao DATE -- Dia que uma nota foi excluída
        )
    ''')

    #Nova tabela para categorias
    cursor.execute('''
        CREATE TABLE categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            emoji TEXT
        )
    ''')
    # Inserir categorias padrão
    categorias_padrao = [
        ('Estudo', '📚'),
        ('Financeiro', '💰'),
        ('Trabalho', '💼'),
        ('Pessoal', '🏠'),
        ('Saúde', '⚕️')
    ]
    cursor.executemany('INSERT OR IGNORE INTO categorias (nome, emoji) VALUES (?, ?)', categorias_padrao)

    conexao.commit()
    conexao.close()
    print("Banco de dados do Painel Pessoal configurado com sucesso!")

if __name__ == "__main__":
    criar_estrutura()