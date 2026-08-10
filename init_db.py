import sqlite3

def inicializar_banco():
    conn = sqlite3.connect('painel_dados.db')
    cursor = conn.cursor()

    # Habilita a verificação de Chaves Estrangeiras no SQLite
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. Tabela de Categorias
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            emoji TEXT DEFAULT '📁'
        )
    ''')

    # 2. Tabela de Notas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            conteudo TEXT,
            categoria TEXT,
            prioridade TEXT DEFAULT 'Média',
            tipo TEXT DEFAULT 'texto',
            data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
            data_vencimento TEXT,
            dias_aviso INTEGER DEFAULT 3,
            status TEXT DEFAULT 'Ativo',
            data_exclusao TEXT
        )
    ''')

    # 3. Nova Tabela: Itens do Checklist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itens_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nota_id INTEGER NOT NULL,
            texto TEXT NOT NULL,
            concluido INTEGER DEFAULT 0,
            FOREIGN KEY (nota_id) REFERENCES notas (id) ON DELETE CASCADE
        )
    ''')

    # Categorias padrão
    categorias_padrao = [
        ('Estudo', '📚'),
        ('Financeiro', '💰'),
        ('Trabalho', '💼'),
        ('Pessoal', '🏠'),
        ('Saúde', '🏥')
    ]

    for nome, emoji in categorias_padrao:
        try:
            cursor.execute("INSERT INTO categorias (nome, emoji) VALUES (?, ?)", (nome, emoji))
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    print("✅ Banco de dados e tabela de checklists inicializados com sucesso!")

if __name__ == "__main__":
    inicializar_banco()