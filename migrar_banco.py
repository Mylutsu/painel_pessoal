import sqlite3

def atualizar_banco():
    conn = sqlite3.connect('painel_dados.db')
    cursor = conn.cursor()
    
    try:
        # Colunas que você já tem (garantindo que não dê erro se rodar de novo)
        cursor.execute("ALTER TABLE notas ADD COLUMN nota_modelo INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE notas ADD COLUMN nota_custo REAL DEFAULT 0.0")
    except:
        pass

    try:
        # NOVA COLUNA: mes_referencia (Ex: "04-2026")
        cursor.execute("ALTER TABLE notas ADD COLUMN mes_referencia TEXT")
        conn.commit()
        print("✅ Coluna 'mes_referencia' adicionada!")
    except sqlite3.OperationalError:
        print("⚠️ A coluna já existe.")
    finally:
        conn.close()

if __name__ == "__main__":
    atualizar_banco()