import os
import sqlite3
import smtplib
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Flask, render_template, request, redirect, url_for, jsonify
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

# ==============================================================================
# SEÇÃO 1: CONFIGURAÇÃO DA APLICAÇÃO E AMBIENTE
# ==============================================================================
load_dotenv()

app = Flask(__name__)

# ==============================================================================
# SEÇÃO 2: FUNÇÕES UTILITÁRIAS E MANIPULAÇÃO DE BANCO DE DADOS
# ==============================================================================
def conectar_banco():
    """Cria e retorna uma conexão com o banco SQLite ativando Chaves Estrangeiras."""
    conn = sqlite3.connect('painel_dados.db')
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def carregar_detalhes_nota(nota, cursor, hoje):
    """
    Processa metadados de uma nota: calcula prazos, status visual de alerta
    e consolida os itens de checklist com o percentual de progresso.
    """
    n_lista = list(nota)
    status_visual = ""
    
    # Processa data de vencimento e alerta (n[7] = data_vencimento, n[8] = dias_aviso)
    if n_lista[7]:
        try:
            data_v = datetime.strptime(n_lista[7], '%Y-%m-%d').date()
            diferenca = (data_v - hoje).days
            dias_aviso = int(n_lista[8]) if n_lista[8] and str(n_lista[8]).isdigit() else 3
            
            if diferenca < 0:
                status_visual = "vencido"
            elif diferenca <= dias_aviso:
                status_visual = "alerta"
            
            n_lista[7] = data_v.strftime('%d/%m/%Y')
        except ValueError:
            pass

    n_lista.append(status_visual)  # Índice 11: status_visual

    # Processa itens do checklist
    cursor.execute("SELECT id, texto, concluido FROM itens_checklist WHERE nota_id = ? ORDER BY id ASC", (n_lista[0],))
    itens = cursor.fetchall()
    
    total_itens = len(itens)
    concluidos = sum(1 for item in itens if item[2] == 1)
    progresso = int((concluidos / total_itens) * 100) if total_itens > 0 else 0

    n_lista.append(itens)         # Índice 12: lista de tuplas (id, texto, concluido)
    n_lista.append(progresso)     # Índice 13: % de progresso
    n_lista.append(total_itens)   # Índice 14: total de itens
    n_lista.append(concluidos)    # Índice 15: itens concluídos

    return n_lista


def limpar_lixeira_automatica(dias_limite=30):
    """Exclui permanentemente notas que estão na lixeira há mais de X dias."""
    with conectar_banco() as conn:
        cursor = conn.cursor()
        data_corte = (datetime.now() - timedelta(days=dias_limite)).strftime('%Y-%m-%d')
        cursor.execute("DELETE FROM notas WHERE status = 'lixeira' AND data_exclusao <= ?", (data_corte,))
        conn.commit()

# ==============================================================================
# SEÇÃO 3: AGENDADOR DE TAREFAS E NOTIFICAÇÕES POR E-MAIL
# ==============================================================================
def verificar_e_enviar_alertas():
    """Consulta compromissos e envia resumo HTML com os prazos prestes a vencer."""
    email_remetente = os.getenv("EMAIL_USUARIO")
    senha = os.getenv("EMAIL_SENHA")

    if not email_remetente or not senha:
        print("⚠️ Credenciais de e-mail não encontradas no .env")
        return

    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT titulo, data_vencimento, categoria 
            FROM notas 
            WHERE status = 'Ativo' AND data_vencimento IS NOT NULL AND data_vencimento != ''
        """)
        notas = cursor.fetchall()

    hoje = date.today()
    itens_html = []
    qtd_pendencias = 0

    for titulo, data_venc_str, categoria in notas:
        try:
            data_venc = datetime.strptime(data_venc_str, "%Y-%m-%d").date()
            dias_restantes = (data_venc - hoje).days
            cat_nome = categoria if categoria else "Geral"

            if dias_restantes < 0:
                qtd_pendencias += 1
                itens_html.append(f'''
                    <div class="item-card vencida">
                        <span class="badge badge-vencida">Vencida</span>
                        <strong>{titulo}</strong> <span class="categoria">({cat_nome})</span><br>
                        <small>Venceu há {abs(dias_restantes)} dia(s) — Data: {data_venc.strftime('%d/%m/%Y')}</small>
                    </div>
                ''')
            elif dias_restantes == 0:
                qtd_pendencias += 1
                itens_html.append(f'''
                    <div class="item-card hoje">
                        <span class="badge badge-hoje">Vence Hoje</span>
                        <strong>{titulo}</strong> <span class="categoria">({cat_nome})</span><br>
                        <small>Atenção! O vencimento está agendado para hoje.</small>
                    </div>
                ''')
            elif dias_restantes <= 2:
                qtd_pendencias += 1
                itens_html.append(f'''
                    <div class="item-card alerta">
                        <span class="badge badge-alerta">Em Breve</span>
                        <strong>{titulo}</strong> <span class="categoria">({cat_nome})</span><br>
                        <small>Vence em {dias_restantes} dia(s) — Data: {data_venc.strftime('%d/%m/%Y')}</small>
                    </div>
                ''')
        except ValueError:
            continue

    if qtd_pendencias > 0:
        msg = MIMEMultipart("alternative")
        msg["From"] = email_remetente
        msg["To"] = email_remetente
        msg["Subject"] = f"🔔 Alerta do Painel: {qtd_pendencias} conta(s)/tarefa(s) requerem atenção!"

        conteudo_cards = "".join(itens_html)

        corpo_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px; color: #1e293b; }}
                .container {{ max-width: 560px; background: #ffffff; margin: 0 auto; border-radius: 12px; padding: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }}
                .header {{ border-bottom: 2px solid #f1f5f9; padding-bottom: 16px; margin-bottom: 20px; }}
                .header h2 {{ margin: 0; color: #0f172a; font-size: 20px; }}
                .header p {{ color: #64748b; font-size: 13px; margin: 6px 0 0 0; }}
                .item-card {{ border-radius: 8px; padding: 12px 16px; margin-bottom: 12px; font-size: 14px; line-height: 1.5; }}
                .categoria {{ opacity: 0.75; font-weight: normal; font-size: 13px; }}
                .vencida {{ background-color: #fef2f2; border-left: 5px solid #ef4444; color: #991b1b; }}
                .hoje {{ background-color: #fff7ed; border-left: 5px solid #ea580c; color: #9a3412; }}
                .alerta {{ background-color: #fffbeb; border-left: 5px solid #f59e0b; color: #92400e; }}
                .badge {{ display: inline-block; font-weight: 700; font-size: 10px; padding: 3px 8px; border-radius: 12px; margin-right: 6px; text-transform: uppercase; letter-spacing: 0.5px; color: #ffffff; }}
                .badge-vencida {{ background-color: #ef4444; }}
                .badge-hoje {{ background-color: #ea580c; }}
                .badge-alerta {{ background-color: #f59e0b; }}
                .footer {{ margin-top: 28px; text-align: center; border-top: 1px solid #f1f5f9; padding-top: 20px; }}
                .btn {{ display: inline-block; background-color: #2563eb; color: #ffffff !important; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🔔 Resumo de Compromissos</h2>
                    <p>Abaixo estão os itens cadastrados no seu painel que precisam da sua atenção hoje:</p>
                </div>
                <div class="content">{conteudo_cards}</div>
                <div class="footer">
                    <a href="http://127.0.0.1:5000" class="btn">Abrir Meu Painel de Notas</a>
                </div>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(corpo_html, "html", "utf-8"))

        try:
            servidor = smtplib.SMTP("smtp.gmail.com", 587)
            servidor.starttls()
            servidor.login(email_remetente, senha)
            servidor.sendmail(email_remetente, email_remetente, msg.as_string())
            servidor.quit()
            print(f"✅ E-mail HTML enviado com sucesso com {qtd_pendencias} item(ns).")
        except Exception as e:
            print(f"❌ Erro ao enviar e-mail automático: {e}")


# Inicialização do agendador em segundo plano (Execução diária às 08:00)
scheduler = BackgroundScheduler()
scheduler.add_job(verificar_e_enviar_alertas, 'cron', hour=8, minute=0)
scheduler.start()

# ==============================================================================
# SEÇÃO 4: ROTAS DA PÁGINA PRINCIPAL E DASHBOARD
# ==============================================================================
@app.route('/')
def index():
    limpar_lixeira_automatica()

    conn = conectar_banco()
    cursor = conn.cursor()

    categoria_filtrada = request.args.get('categoria')
    prioridade_filtrada = request.args.get('prioridade')

    comando_sql = "SELECT * FROM notas WHERE status = 'Ativo'"
    parametros = []

    if categoria_filtrada and categoria_filtrada != 'Todas':
        comando_sql += " AND categoria = ?"
        parametros.append(categoria_filtrada)

    if prioridade_filtrada and prioridade_filtrada != 'Todas':
        comando_sql += " AND prioridade = ?"
        parametros.append(prioridade_filtrada)

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

    cursor.execute("SELECT * FROM notas WHERE status = 'Ativo'")
    todas_ativas = cursor.fetchall()
    total = len(todas_ativas)
    vencidas = 0
    alertas = 0
    hoje = date.today()

    for n in todas_ativas:
        if n[7]:
            try:
                data_v = datetime.strptime(n[7], '%Y-%m-%d').date()
                diferenca = (data_v - hoje).days
                dias_aviso = int(n[8]) if n[8] and str(n[8]).isdigit() else 3
                if diferenca < 0:
                    vencidas += 1
                elif diferenca <= dias_aviso:
                    alertas += 1
            except ValueError:
                pass

    cursor.execute("SELECT COUNT(*) FROM notas WHERE status = 'Concluido'")
    concluidas_total = cursor.fetchone()[0]

    notas_processadas = [carregar_detalhes_nota(n, cursor, hoje) for n in notas]

    cursor.execute("SELECT id, nome, emoji FROM categorias")
    lista_categorias = cursor.fetchall()

    conn.close()
    return render_template('index.html',
                           notas=notas_processadas,
                           total=total,
                           vencidas=vencidas,
                           alertas=alertas,
                           concluidas_total=concluidas_total,
                           categorias=lista_categorias,
                           categoria_ativa=categoria_filtrada or 'Todas',
                           prioridade_ativa=prioridade_filtrada or 'Todas')

# ==============================================================================
# SEÇÃO 5: ROTAS DE GESTÃO E EDIÇÃO DE NOTAS
# ==============================================================================
@app.route('/adicionar', methods=['POST'])
def adicionar():
    titulo = request.form.get('titulo')
    conteudo = request.form.get('conteudo')
    categoria = request.form.get('categoria')
    prioridade = request.form.get('prioridade')
    tipo = request.form.get('tipo') or 'texto'
    vencimento = request.form.get('data_vencimento') or None
    aviso = request.form.get('dias_aviso') or None

    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notas (titulo, conteudo, categoria, prioridade, tipo, data_vencimento, dias_aviso)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (titulo, conteudo, categoria, prioridade, tipo, vencimento, aviso))
        
        nota_id = cursor.lastrowid

        # Se for checklist, insere os itens iniciais informados
        itens_iniciais = request.form.getlist('itens_checklist[]')
        for item_texto in itens_iniciais:
            texto_limpo = item_texto.strip()
            if texto_limpo:
                cursor.execute("INSERT INTO itens_checklist (nota_id, texto) VALUES (?, ?)", (nota_id, texto_limpo))

        conn.commit()

    return redirect(url_for('index'))


@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    conn = conectar_banco()
    cursor = conn.cursor()

    if request.method == 'POST':
        titulo = request.form['titulo']
        conteudo = request.form['conteudo']
        categoria = request.form['categoria']
        prioridade = request.form['prioridade']
        tipo = request.form['tipo']
        data_vencimento = request.form['data_vencimento'] or None
        dias_aviso = request.form['dias_aviso'] or None

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

    cursor.execute("SELECT id, nome, emoji FROM categorias")
    lista_categorias = cursor.fetchall()

    conn.close()
    return render_template('editar.html', nota=nota, categorias=lista_categorias)


@app.route('/concluir/<int:id>')
def concluir(id):
    with conectar_banco() as conn:
        cursor = conn.cursor()
        concluido = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("UPDATE notas SET status = 'Concluido', data_criacao = ? WHERE id = ?", (concluido, id))
        conn.commit()
    return redirect(url_for('index'))


@app.route('/restaurar/<int:id>')
def restaurar(id):
    with conectar_banco() as conn:
        cursor = conn.cursor()
        restaurado = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("UPDATE notas SET status = 'Ativo', data_criacao = ? WHERE id = ?", (restaurado, id))
        conn.commit()
    return redirect(url_for('concluidas'))

# ==============================================================================
# SEÇÃO 6: ROTAS DE GERENCIAMENTO DE CHECKLIST (AJAX E ITENS)
# ==============================================================================
@app.route('/adicionar_item_checklist/<int:nota_id>', methods=['POST'])
def adicionar_item_checklist(nota_id):
    texto = request.form.get('texto', '').strip()
    if texto:
        with conectar_banco() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO itens_checklist (nota_id, texto) VALUES (?, ?)", (nota_id, texto))
            conn.commit()
    return redirect(request.referrer or url_for('index'))


@app.route('/toggle_item_checklist/<int:item_id>', methods=['POST'])
def toggle_item_checklist(item_id):
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE itens_checklist SET concluido = NOT concluido WHERE id = ?", (item_id,))
        conn.commit()
        
        cursor.execute("SELECT concluido, nota_id FROM itens_checklist WHERE id = ?", (item_id,))
        item = cursor.fetchone()
        
        novo_status = bool(item[0]) if item else False
        nota_id = item[1] if item else None

        progresso = 0
        total = 0
        concluidos = 0
        if nota_id:
            cursor.execute("SELECT id, concluido FROM itens_checklist WHERE nota_id = ?", (nota_id,))
            itens = cursor.fetchall()
            total = len(itens)
            concluidos = sum(1 for i in itens if i[1] == 1)
            progresso = int((concluidos / total) * 100) if total > 0 else 0

    return jsonify({
        'success': True, 
        'concluido': novo_status, 
        'progresso': progresso,
        'total': total,
        'concluidos': concluidos
    })


@app.route('/deletar_item_checklist/<int:item_id>', methods=['POST', 'GET'])
def deletar_item_checklist(item_id):
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM itens_checklist WHERE id = ?", (item_id,))
        conn.commit()
    return redirect(request.referrer or url_for('index'))

# ==============================================================================
# SEÇÃO 7: ROTAS DE CATEGORIAS
# ==============================================================================
@app.route('/adicionar_categoria', methods=['POST'])
def adicionar_categoria():
    nome = request.form['nome'].strip()
    emoji = request.form['emoji'].strip()
    
    if nome:
        with conectar_banco() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO categorias (nome, emoji) VALUES (?, ?)", (nome, emoji))
                conn.commit()
            except sqlite3.IntegrityError:
                pass
        
    return redirect(url_for('index'))


@app.route('/excluir_categoria/<int:id>')
def excluir_categoria(id):
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM categorias WHERE id = ?", (id,))
        conn.commit()
    return redirect(url_for('index'))

# ==============================================================================
# SEÇÃO 8: HISTÓRICO, LIXEIRA E EXCLUSÃO PERMANENTE
# ==============================================================================
@app.route('/concluidas')
def concluidas():
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notas WHERE status = 'Concluido' ORDER BY data_criacao DESC")
    notas = cursor.fetchall()
    hoje = date.today()

    notas_processadas = [carregar_detalhes_nota(n, cursor, hoje) for n in notas]
    conn.close()

    return render_template('concluidas.html', notas=notas_processadas)


@app.route('/lixeira')
def lixeira():
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notas WHERE status = 'lixeira' ORDER BY data_exclusao DESC")
    notas = cursor.fetchall()
    hoje = date.today()

    notas_processadas = []
    for n in notas:
        n_lista = carregar_detalhes_nota(n, cursor, hoje)
        if n[10]:
            try:
                data_ex = datetime.strptime(n[10], '%Y-%m-%d').date()
                n_lista[10] = data_ex.strftime('%d/%m/%Y')
            except ValueError:
                pass
        notas_processadas.append(n_lista)

    conn.close()
    return render_template('lixeira.html', notas=notas_processadas)


@app.route('/deletar_lixeira/<int:id>')
def deletar_lixeira(id):
    with conectar_banco() as conn:
        cursor = conn.cursor()
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("UPDATE notas SET status = 'lixeira', data_exclusao = ? WHERE id = ?", (data_hoje, id))
        conn.commit()
    return redirect(url_for('index'))


@app.route('/restaurar_lixeira/<int:id>')
def restaurar_lixeira(id):
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notas SET status = 'Ativo', data_exclusao = NULL WHERE id = ?", (id,))
        conn.commit()
    return redirect(url_for('lixeira'))


@app.route('/excluir_definitivo/<int:id>')
def excluir_definitivo(id):
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notas WHERE id = ?", (id,))
        conn.commit()
    return redirect(url_for('lixeira'))


@app.route('/esvaziar_lixeira')
def esvaziar_lixeira():
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notas WHERE status = 'lixeira'")
        conn.commit()
    return redirect(url_for('lixeira'))

# ==============================================================================
# SEÇÃO 9: CALENDÁRIO E API REST
# ==============================================================================
@app.route('/calendario')
def calendario():
    return render_template('calendario.html')


@app.route('/api/eventos')
def api_eventos():
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, titulo, data_vencimento, prioridade, status, tipo, categoria 
            FROM notas 
            WHERE data_vencimento IS NOT NULL AND data_vencimento != '' AND status != 'lixeira'
        """)
        notas = cursor.fetchall()

    eventos = []
    for n in notas:
        nota_id, titulo, vencimento, prioridade, status, tipo, categoria = n
        
        if status == 'Concluido':
            cor = '#64748b'
        elif prioridade == 'Alta':
            cor = '#ef4444'
        elif prioridade == 'Média':
            cor = '#f59e0b'
        else:
            cor = '#10b981'

        icone = "☑️ " if tipo == "checklist" else "📝 "
        cat_prefix = f"[{categoria}] " if categoria else ""

        eventos.append({
            'id': nota_id,
            'title': f"{icone}{cat_prefix}{titulo}",
            'start': vencimento,
            'backgroundColor': cor,
            'borderColor': cor,
            'textColor': '#ffffff'
        })

    return jsonify(eventos)

# ==============================================================================
# SEÇÃO 10: ROTAS PWA
# ==============================================================================

# Rotas de Suporte ao PWA
@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')

@app.route('/sw.js')
def service_worker():
    return app.send_static_file('sw.js')


# ==============================================================================
# EXECUÇÃO DO SERVIDOR
# ==============================================================================
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)