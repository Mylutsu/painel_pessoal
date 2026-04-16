# Importamos as ferramentas necessárias do Flask para lidar com o site
# request: captura o que o usuário digita no formulário
# redirect/url_for: fazem o navegador pular de uma página para outra
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, date
import sqlite3

app = Flask(__name__)

# Criamos uma função padrão para conectar ao banco. 
# Isso evita que a gente tenha que digitar 'sqlite3.connect' em todo lugar.
def conectar_banco():
    return sqlite3.connect('painel_dados.db')

# --- ROTA PRINCIPAL (MOSTRAR OS DADOS) ---
@app.route('/')
def index():
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # Explicando a nova consulta SQL:
    # Usamos o CASE para dar um "peso" numérico para cada texto:
    # Se for Alta, vale 1; Se for Média, vale 2; Se for Baixa, vale 3.
    # Assim, ao ordenar por esse 'peso', as Altas (1) aparecem primeiro!
    comando_sql = """
        SELECT * FROM notas 
        ORDER BY 
            CASE prioridade
                WHEN 'Alta' THEN 1
                WHEN 'Média' THEN 2
                WHEN 'Baixa' THEN 3
                ELSE 4
            END, 
            data_criacao DESC
    """
    
    cursor.execute(comando_sql)
    notas_do_banco = cursor.fetchall()
    conn.close()

    hoje = date.today() #pega a data atual
    notas_processadas = []

    for n in notas_do_banco:
        # Transformamos a tupla em lista para podermos adicionar informações novas
        nota = list(n)
        alerta = False

        # Verificamos se existe uma data de vencimento (n[7]) e dias de aviso (n[8])
        if n[7] and n[8]:
            # Convertemos a data que vem do banco (texto) em um objeto de data real
            data_venc = datetime.strptime(n[7], '%Y-%m-%d').date()
            
            # Calculamos a diferença de dias
            diferenca = (data_venc - hoje).days
            
            # Se a diferença for menor ou igual aos dias de aviso escolhidos, ativa o alerta!
            if diferenca <= n[8] and diferenca >= 0:
                alerta = True
        
        # Adicionamos essa nova informação de "alerta" no final da nossa lista da nota
        nota.append(alerta)
        notas_processadas.append(nota)
    
    return render_template('index.html', notas=notas_processadas)

# --- ROTA DE AÇÃO (SALVAR OS DADOS) ---
# 'methods=['POST']' indica que esta rota recebe dados enviados por um formulário
@app.route('/adicionar', methods=['POST'])
def adicionar():
    # O comando 'request.form.get' vai buscar o que foi digitado no 'name' do HTML
    titulo = request.form.get('titulo')
    conteudo = request.form.get('conteudo')
    categoria = request.form.get('categoria')
    prioridade = request.form.get('prioridade')
    tipo = request.form.get('tipo')
    vencimento = request.form.get('vencimento') # Pode vir vazio
    aviso = request.form.get('aviso') # Pode vir vazio

    conn = conectar_banco()
    cursor = conn.cursor()
    
    # O comando SQL INSERT coloca as informações nas colunas certas.
    # Usamos '?' por segurança (evita que invasores mandem comandos SQL pelo formulário)
    cursor.execute('''
        INSERT INTO notas (titulo, conteudo, categoria, prioridade, tipo, data_vencimento, dias_aviso)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (titulo, conteudo, categoria, prioridade, tipo, vencimento, aviso))
    
    # 6. Salvamos a alteração no arquivo .db
    conn.commit()
    conn.close()
    
    # 7. Após salvar, mandamos o usuário de volta para a página inicial
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)