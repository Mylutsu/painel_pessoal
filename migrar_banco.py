import sqlite3

def atualizar_banco():
    conn = sqlite3.connect('painel_dados.db')
    cursor = conn.cursor()
    
    try:
        # Adiciona a coluna para saber se é modelo fixo
        cursor.execute("ALTER TABLE notas ADD COLUMN nota_modelo INTEGER DEFAULT 0")
        # Adiciona a coluna para o valor da conta
        cursor.execute("ALTER TABLE notas ADD COLUMN nota_custo REAL DEFAULT 0.0")
        conn.commit()
        print("✅ Banco atualizado com sucesso!")
    except sqlite3.OperationalError:
        print("⚠️ As colunas já existem ou o banco não foi encontrado.")
    finally:
        conn.close()

if __name__ == "__main__":
    atualizar_banco()