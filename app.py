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

    #captura a categoria da URL (se existir)
    categoria_filtrada = request.args.get('categoria')

    # 1. Filtro de exibição (Apenas Ativas)
    comando_sql = "SELECT * FROM notas WHERE status = 'Ativo'"
    parametros = []

    #se houver filtro e não for "Todas", adicionamos o WHERE
    if categoria_filtrada and categoria_filtrada != 'Todas':
        comando_sql += " AND categoria = ?"
        parametros.append(categoria_filtrada)

    # Explicando a nova consulta SQL:
    # Usamos o CASE para dar um "peso" numérico para cada texto:
    # Se for Alta, vale 1; Se for Média, vale 2; Se for Baixa, vale 3.
    # Assim, ao ordenar por esse 'peso', as Altas (1) aparecem primeiro!
    comando_sql += """
        ORDER BY 
            CASE prioridade
                WHEN 'Alta' THEN 1
                WHEN 'Média' THEN 2
                WHEN 'Baixa' THEN 3
                ELSE 4
            END, 
            data_criacao DESC
    """
    
    cursor.execute(comando_sql, parametros)
    notas = cursor.fetchall()

    # --- Lógica do Dashboard (Mantemos global para você ver o total geral) ---
    # 2. Lógica do Dashboard (Cálculos baseados em todas as Ativas)
    cursor.execute("SELECT * FROM notas WHERE status = 'Ativo'")
    todas_ativas = cursor.fetchall()
    total = len(todas_ativas)
    vencidas = 0
    alertas = 0
    hoje = date.today()

    for n in todas_ativas:
        if n[7]:
            data_v = datetime.strptime(n[7], '%Y-%m-%d').date()
            diferenca = (data_v - hoje).days
            if diferenca < 0:
                vencidas += 1
            elif diferenca <= (n[8] or 3): #contagem para alerta de aviso ou popar alerta em 3 dias
                alertas +=1
    # 3. Contagem de Concluídas para o Dashboard
    cursor.execute("SELECT COUNT (*) FROM notas WHERE status = 'Concluido'")
    concluidas_total = cursor.fetchone()[0]

    # 4. Processamento para exibição no HTML
    notas_processadas = []
    for n in notas:
        n_lista = list(n)
        status_visual = ""
        
        if n[7]: # Se tiver uma data de vencimento
            data_v = datetime.strptime(n[7], '%Y-%m-%d').date()
            diferenca = (data_v - hoje).days
            if diferenca < 0: status_visual = "vencido"
            elif diferenca <= (n[8] or 3): status_visual = "alerta"
            n_lista[7] = data_v.strftime('%d/%m/%Y') #formatação para data brasileira

        n_lista.append(status_visual)
        notas_processadas.append(n_lista)

    conn.close()
    return render_template('index.html',
                           notas = notas_processadas,
                           total = total,
                           vencidas = vencidas,
                           alertas = alertas,
                           concluidas_total=concluidas_total,
                           categoria_ativa = categoria_filtrada or 'Todas')

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
    vencimento = request.form.get('data_vencimento') # Pode vir vazio
    aviso = request.form.get('dias_aviso') # Pode vir vazio

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

# Rota para excluir (deletar) uma nota
# O <int:id> captura o número da nota que queremos apagar
@app.route('/concluir/<int:id>')
def concluir(id):
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # O comando SQL para remover a linha específica do banco
    cursor.execute("UPDATE notas SET status = 'Concluido' WHERE id = ?", (id,))
    
    conn.commit()
    conn.close()
    
    # Após concluir a nota, redireciona para a página inicial para atualizar a lista
    return redirect(url_for('index'))


@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    conn = sqlite3.connect('painel_dados.db') # Nome correto do seu banco
    cursor = conn.cursor()

    if request.method == 'POST':
        titulo = request.form['titulo']
        conteudo = request.form['conteudo']
        categoria = request.form['categoria']
        prioridade = request.form['prioridade']
        tipo = request.form['tipo'] # Coluna que você tem no banco
        data_vencimento = request.form['data_vencimento']
        dias_aviso = request.form['dias_aviso'] # Nome correto da coluna

        cursor.execute("""
            UPDATE notas 
            SET titulo = ?, conteudo = ?, categoria = ?, prioridade = ?, tipo = ?, data_vencimento = ?, dias_aviso = ?
            WHERE id = ?
        """, (titulo, conteudo, categoria, prioridade, tipo, data_vencimento, dias_aviso, id))
        
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    cursor.execute("SELECT * FROM notas WHERE id = ?", (id,))
    nota = cursor.fetchone()
    conn.close()
    return render_template('editar.html', nota=nota)


@app.route('/concluidas')
def concluidas():
    conn = conectar_banco()
    cursor = conn.cursor()
    
    # Busca apenas as que marcamos como Concluído
    cursor.execute("SELECT * FROM notas WHERE status = 'Concluido' ORDER BY data_criacao DESC")
    notas = cursor.fetchall()


    notas_processadas = []
    for n in notas:
        n_lista = list(n)
        if n[7]:
            data_v = datetime.strptime(n[7], '%Y-%m-%d').date()
            n_lista[7] = data_v.strftime('%d/%m/%Y')
        notas_processadas.append(n_lista)

    conn.close()
    
    return render_template('concluidas.html', notas=notas_processadas)

if __name__ == "__main__":
    app.run(debug=True)