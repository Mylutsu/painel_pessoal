import os
import sqlite3
import smtplib
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import generate_password_hash, check_password_hash

# ==============================================================================
# SEÇÃO 1: CONFIGURAÇÃO DA APLICAÇÃO E AMBIENTE
# ==============================================================================
load_dotenv()

app = Flask(__name__)
app.secret_key = 'teste_de_senha_super_secreta' # mude para uma chave aleatoria em produção

# ==============================================================================
# SEÇÃO 2: FUNÇÕES UTILITÁRIAS E MANIPULAÇÃO DE BANCO DE DADOS
# ==============================================================================
def conectar_banco():
    """Cria e retorna uma conexão com o banco SQLite ativando Chaves Estrangeiras."""
    conn = sqlite3.connect('painel_dados.db')
    conn.row_factory = sqlite3.Row
    return conn


def carregar_detalhes_nota(nota, cursor, hoje):
    """
    Processa metadados de uma nota: calcula prazos, status visual de alerta
    e consolida os itens de checklist com o percentual de progresso.
    """
    n_dict = dict(nota)
    status_visual = ""
    
    # Processa data usando o nome criado no DB
    data_venc_str = n_dict.get('data_vencimento')
    dias_aviso_val = n_dict.get('dias_aviso')

    if data_venc_str:
        try:
            data_v = datetime.strptime(data_venc_str, '%Y-%m-%d').date()
            diferenca = (data_v - hoje).days
            dias_aviso = int(dias_aviso_val) if dias_aviso_val and str(dias_aviso_val).isdigit() else 3
            
            if diferenca < 0:
                status_visual = "vencido"
            elif diferenca <= dias_aviso:
                status_visual = "alerta"
            
            n_dict['data_vencimento_formatada'] = data_v.strftime('%d/%m/%Y')
        except ValueError:
            pass

    n_dict['status_visual'] = status_visual

    # Processa itens do checklist
    cursor.execute("SELECT id, texto, concluido FROM itens_checklist WHERE nota_id = ? ORDER BY id ASC", (n_dict['id'],))
    itens = cursor.fetchall()
    
    total_itens = len(itens)
    concluidos = sum(1 for item in itens if item['concluido'] == 1)
    progresso = int((concluidos / total_itens) * 100) if total_itens > 0 else 0

    # Adiciona os atributos no dicionário
    n_dict['itens'] = itens
    n_dict['progresso'] = progresso
    n_dict['total_itens'] = total_itens
    n_dict['concluidos'] = concluidos

    return n_dict


def limpar_lixeira_automatica(dias_limite=30):
    """Exclui permanentemente notas que estão na lixeira há mais de X dias."""
    with conectar_banco() as conn:
        cursor = conn.cursor()
        data_corte = (datetime.now() - timedelta(days=dias_limite)).strftime('%Y-%m-%d')
        cursor.execute("DELETE FROM notas WHERE status = 'lixeira' AND data_exclusao <= ?", (data_corte,))
        conn.commit()

def calcular_proximo_vencimento(data_str, recorrencia):
    """Calcula a próxima data de vencimento (AAAA-MM-DD) conforme a recorrência selecionada."""
    if not data_str or not recorrencia or recorrencia == 'Nenhuma':
        return None
    try:
        dt = datetime.strptime(data_str, '%Y-%m-%d').date()
        if recorrencia == 'Semanal':
            prox_dt = dt + timedelta(days=7)
        elif recorrencia == 'Mensal':
            ano = dt.year + (dt.month // 12)
            mes = (dt.month % 12) + 1
            max_dias = [31, 29 if (ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            dia = min(dt.day, max_dias[mes - 1])
            prox_dt = date(ano, mes, dia)
        elif recorrencia == 'Anual':
            ano = dt.year + 1
            mes = dt.month
            dia = 28 if (mes == 2 and dt.day == 29 and not (ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0))) else dt.day
            prox_dt = date(ano, mes, dia)
        else:
            return None
        return prox_dt.strftime('%Y-%m-%d')
    except ValueError:
        return None

# ==============================================================================
# SEÇÃO 3: AGENDADOR DE TAREFAS E NOTIFICAÇÕES POR E-MAIL (MULTI-USUÁRIO)
# ==============================================================================
def verificar_e_enviar_alertas():
    """Consulta compromissos de CADA usuário e envia e-mail personalizado com os alertas e vencidos."""
    email_remetente = os.getenv("EMAIL_USUARIO")
    senha = os.getenv("EMAIL_SENHA")

    if not email_remetente or not senha:
        print("⚠️ Credenciais de e-mail não encontradas no .env")
        return

    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, email FROM usuarios")
        usuarios = cursor.fetchall()

        hoje = date.today()

        for u_id, u_nome, u_email in usuarios:
            cursor.execute("""
                SELECT titulo, data_vencimento, categoria, COALESCE(dias_aviso, 3) 
                FROM notas 
                WHERE status = 'Ativo' AND usuario_id = ? AND data_vencimento IS NOT NULL AND data_vencimento != ''
            """, (u_id,))
            notas = cursor.fetchall()

            if not notas:
                continue

            itens_html = []
            qtd_pendencias = 0

            for titulo, data_venc_str, categoria, dias_aviso in notas:
                try:
                    data_venc = datetime.strptime(data_venc_str, "%Y-%m-%d").date()
                    dias_restantes = (data_venc - hoje).days
                    cat_nome = categoria if categoria else "Geral"
                    limite_alerta = int(dias_aviso) if dias_aviso is not None else 3

                    # 1. NOTAS VENCIDAS
                    if dias_restantes < 0:
                        qtd_pendencias += 1
                        itens_html.append(f'''
                            <div class="item-card vencida">
                                <span class="badge badge-vencida">Vencida</span>
                                <strong>{titulo}</strong> <span class="categoria">({cat_nome})</span><br>
                                <small>Venceu há {abs(dias_restantes)} dia(s) — Data: {data_venc.strftime('%d/%m/%Y')}</small>
                            </div>
                        ''')
                    # 2. NOTAS QUE VENCEM HOJE
                    elif dias_restantes == 0:
                        qtd_pendencias += 1
                        itens_html.append(f'''
                            <div class="item-card hoje">
                                <span class="badge badge-hoje">Vence Hoje</span>
                                <strong>{titulo}</strong> <span class="categoria">({cat_nome})</span><br>
                                <small>Atenção! O vencimento está agendado para hoje.</small>
                            </div>
                        ''')
                    # 3. NOTAS EM ALERTA
                    elif dias_restantes <= limite_alerta:
                        qtd_pendencias += 1
                        itens_html.append(f'''
                            <div class="item-card alerta">
                                <span class="badge badge-alerta">Em Alerta</span>
                                <strong>{titulo}</strong> <span class="categoria">({cat_nome})</span><br>
                                <small>Vence em {dias_restantes} dia(s) — Data: {data_venc.strftime('%d/%m/%Y')}</small>
                            </div>
                        ''')
                except ValueError:
                    continue

            if qtd_pendencias > 0:
                msg = MIMEMultipart("alternative")
                msg["From"] = email_remetente
                msg["To"] = u_email
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
                            <h2>Olá, {u_nome}! 🔔</h2>
                            <p>Abaixo estão os seus compromissos que precisam de atenção hoje:</p>
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
                    servidor.sendmail(email_remetente, u_email, msg.as_string())
                    servidor.quit()
                    print(f"✅ E-mail enviado para {u_email} com {qtd_pendencias} alerta(s).")
                except Exception as e:
                    print(f"❌ Erro ao enviar e-mail para {u_email}: {e}")

# Inicialização do agendador em segundo plano (Execução diária às 08:00)
scheduler = BackgroundScheduler()
scheduler.add_job(verificar_e_enviar_alertas, 'cron', hour=8, minute=0)
scheduler.start()

# ==============================================================================
# SEÇÃO 4: ROTAS DE AUTENTICAÇÃO E SEGURANÇA GLOBAL
# ==============================================================================
@app.before_request
def verificar_autenticacao_global():
    """Bloqueia páginas internas para usuários não autenticados."""
    rotas_publicas = ['login', 'cadastro', 'static', 'manifest', 'service_worker']
    if 'usuario_id' not in session and request.endpoint and request.endpoint not in rotas_publicas:
        flash('Por favor, faça login para acessar o sistema.', 'warning')
        return redirect(url_for('login'))


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        senha = request.form.get('senha')

        senha_hash = generate_password_hash(senha)

        try:
            with conectar_banco() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)",
                    (nome, email, senha_hash)
                )
                conn.commit()
            flash('Cadastro realizado com sucesso! Faça login para continuar.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Este e-mail já está cadastrado. Tente outro.', 'danger')

    return render_template('cadastro.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')

        with conectar_banco() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome, senha FROM usuarios WHERE email = ?", (email,))
            usuario = cursor.fetchone()

        if usuario and check_password_hash(usuario[2], senha):
            session['usuario_id'] = usuario[0]
            session['usuario_nome'] = usuario[1]
            flash(f'Bem-vindo(a) de volta, {usuario[1]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('E-mail ou senha incorretos.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'info')
    return redirect(url_for('login'))

@app.before_request
def verificar_usuario_existente():
    """Se o usuário tiver um cookie de sessão antigo mas não existir no BD, desconecta automaticamente."""
    u_id = session.get('usuario_id')
    if u_id:
        with conectar_banco() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE id = ?", (u_id,))
            if not cursor.fetchone():
                session.clear()

# ==============================================================================
# SEÇÃO 5: ROTAS DA PÁGINA PRINCIPAL E DASHBOARD
# ==============================================================================
@app.route('/')
def index():
    limpar_lixeira_automatica()
    u_id = session.get('usuario_id')

    conn = conectar_banco()
    cursor = conn.cursor()

    categoria_filtrada = request.args.get('categoria')
    prioridade_filtrada = request.args.get('prioridade')

    comando_sql = "SELECT * FROM notas WHERE status = 'Ativo' AND usuario_id = ?"
    parametros = [u_id]

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

    cursor.execute("SELECT * FROM notas WHERE status = 'Ativo' AND usuario_id = ?", (u_id,))
    todas_ativas = cursor.fetchall()
    total = len(todas_ativas)
    vencidas = 0
    alertas = 0
    hoje = date.today()

    for n in todas_ativas:
        if n['data_vencimento']:
            try:
                data_v = datetime.strptime(n['data_vencimento'], '%Y-%m-%d').date()
                diferenca = (data_v - hoje).days
                dias_aviso = int(n['dias_aviso']) if n['dias_aviso'] and str(n['dias_aviso']).isdigit() else 3
                if diferenca < 0:
                    vencidas += 1
                elif diferenca <= dias_aviso:
                    alertas += 1
            except ValueError:
                pass

    cursor.execute("SELECT COUNT(*) FROM notas WHERE status = 'Concluido' AND usuario_id = ?", (u_id,))
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
# SEÇÃO 6: ROTAS DE GESTÃO E EDIÇÃO DE NOTAS
# ==============================================================================
@app.route('/adicionar', methods=['POST'])
def adicionar():
    u_id = session.get('usuario_id')
    titulo = request.form.get('titulo')
    conteudo = request.form.get('conteudo')
    categoria = request.form.get('categoria')
    prioridade = request.form.get('prioridade')
    tipo = request.form.get('tipo') or 'texto'
    vencimento = request.form.get('data_vencimento') or None
    aviso = request.form.get('dias_aviso') or None
    recorrencia = request.form.get('recorrencia') or 'Nenhuma'

    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notas (titulo, conteudo, categoria, prioridade, tipo, data_vencimento, dias_aviso, recorrencia, usuario_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (titulo, conteudo, categoria, prioridade, tipo, vencimento, aviso, recorrencia, u_id))
        
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
    u_id = session.get('usuario_id')
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
        recorrencia = request.form.get('recorrencia') or 'Nenhuma'

        cursor.execute("""
            UPDATE notas 
            SET titulo = ?, conteudo = ?, categoria = ?, prioridade = ?, tipo = ?, data_vencimento = ?, dias_aviso = ?, recorrencia = ?
            WHERE id = ? AND usuario_id = ?
        """, (titulo, conteudo, categoria, prioridade, tipo, data_vencimento, dias_aviso, recorrencia, id, u_id))
        
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    cursor.execute("SELECT * FROM notas WHERE id = ? AND usuario_id = ?", (id, u_id))
    nota = cursor.fetchone()

    if not nota:
        conn.close()
        flash('Nota não encontrada.', 'danger')
        return redirect(url_for('index'))

    cursor.execute("SELECT id, nome, emoji FROM categorias")
    lista_categorias = cursor.fetchall()

    conn.close()
    return render_template('editar.html', nota=nota, categorias=lista_categorias)


@app.route('/concluir/<int:id>')
def concluir(id):
    u_id = session.get('usuario_id')
    with conectar_banco() as conn:
        cursor = conn.cursor()
        
        # 1. Busca as informações da nota atual
        cursor.execute("SELECT * FROM notas WHERE id = ? AND usuario_id = ?", (id, u_id))
        nota_row = cursor.fetchone()

        if nota_row:
            nota = dict(nota_row)
            recorrencia = nota.get('recorrencia', 'Nenhuma')
            data_venc = nota.get('data_vencimento')

            # 2. Se for uma nota recorrente com data de vencimento, gera a próxima automaticamente
            if recorrencia and recorrencia != 'Nenhuma' and data_venc:
                prox_vencimento = calcular_proximo_vencimento(data_venc, recorrencia)
                
                if prox_vencimento:
                    cursor.execute('''
                        INSERT INTO notas (titulo, conteudo, categoria, prioridade, tipo, data_vencimento, dias_aviso, recorrencia, usuario_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        nota['titulo'], nota['conteudo'], nota['categoria'], 
                        nota['prioridade'], nota['tipo'], prox_vencimento, 
                        nota['dias_aviso'], recorrencia, u_id
                    ))
                    nova_nota_id = cursor.lastrowid

                    # Caso a nota seja um checklist, duplica os itens marcando todos como desmarcados (0) para o novo mês
                    if nota['tipo'] == 'checklist':
                        cursor.execute("SELECT texto FROM itens_checklist WHERE nota_id = ?", (id,))
                        itens = cursor.fetchall()
                        for item in itens:
                            cursor.execute("INSERT INTO itens_checklist (nota_id, texto, concluido) VALUES (?, ?, 0)", (nova_nota_id, item['texto']))

            # 3. Finaliza a nota atual colocando o status como Concluido
            concluido = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("UPDATE notas SET status = 'Concluido', data_criacao = ? WHERE id = ? AND usuario_id = ?", (concluido, id, u_id))
            conn.commit()

    return redirect(url_for('index'))

@app.route('/restaurar/<int:id>')
def restaurar(id):
    u_id = session.get('usuario_id')
    with conectar_banco() as conn:
        cursor = conn.cursor()
        restaurado = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("UPDATE notas SET status = 'Ativo', data_criacao = ? WHERE id = ? AND usuario_id = ?", (restaurado, id, u_id))
        conn.commit()
    return redirect(url_for('concluidas'))

# ==============================================================================
# SEÇÃO 7: ROTAS DE GERENCIAMENTO DE CHECKLIST (AJAX E ITENS)
# ==============================================================================
@app.route('/adicionar_item_checklist/<int:nota_id>', methods=['POST'])
def adicionar_item_checklist(nota_id):
    u_id = session.get('usuario_id')
    texto = request.form.get('texto', '').strip()
    if texto:
        with conectar_banco() as conn:
            cursor = conn.cursor()
            # Garante que a nota pertence ao usuário
            cursor.execute("SELECT id FROM notas WHERE id = ? AND usuario_id = ?", (nota_id, u_id))
            if cursor.fetchone():
                cursor.execute("INSERT INTO itens_checklist (nota_id, texto) VALUES (?, ?)", (nota_id, texto))
                conn.commit()
    return redirect(request.referrer or url_for('index'))


@app.route('/toggle_item_checklist/<int:item_id>', methods=['POST'])
def toggle_item_checklist(item_id):
    u_id = session.get('usuario_id')
    with conectar_banco() as conn:
        cursor = conn.cursor()
        # Verifica se o item pertence a uma nota do usuário logado
        cursor.execute("""
            SELECT ic.id, ic.concluido, ic.nota_id 
            FROM itens_checklist ic
            JOIN notas n ON ic.nota_id = n.id
            WHERE ic.id = ? AND n.usuario_id = ?
        """, (item_id, u_id))
        item = cursor.fetchone()

        if not item:
            return jsonify({'success': False, 'error': 'Item não encontrado'}), 404

        cursor.execute("UPDATE itens_checklist SET concluido = NOT concluido WHERE id = ?", (item_id,))
        conn.commit()
        
        novo_status = not bool(item[1])
        nota_id = item[2]

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
    u_id = session.get('usuario_id')
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM itens_checklist 
            WHERE id = ? AND nota_id IN (SELECT id FROM notas WHERE usuario_id = ?)
        """, (item_id, u_id))
        conn.commit()
    return redirect(request.referrer or url_for('index'))

# ==============================================================================
# SEÇÃO 8: ROTAS DE CATEGORIAS
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
# SEÇÃO 9: HISTÓRICO, LIXEIRA E EXCLUSÃO PERMANENTE
# ==============================================================================
@app.route('/concluidas')
def concluidas():
    u_id = session.get('usuario_id')
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notas WHERE status = 'Concluido' AND usuario_id = ? ORDER BY data_criacao DESC", (u_id,))
    notas = cursor.fetchall()
    hoje = date.today()

    notas_processadas = [carregar_detalhes_nota(n, cursor, hoje) for n in notas]
    conn.close()

    return render_template('concluidas.html', notas=notas_processadas)


@app.route('/lixeira')
def lixeira():
    u_id = session.get('usuario_id')
    conn = conectar_banco()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notas WHERE status = 'lixeira' AND usuario_id = ? ORDER BY data_exclusao DESC", (u_id,))
    notas = cursor.fetchall()
    hoje = date.today()

    notas_processadas = []
    for n in notas:
        n_dict = carregar_detalhes_nota(n, cursor, hoje)
        if n_dict.get('data_exclusao'):
            try:
                data_ex = datetime.strptime(n_dict['data_exclusao'], '%Y-%m-%d').date()
                n_dict['data_exclusao_formatada'] = data_ex.strftime('%d/%m/%Y')
            except ValueError:
                pass
        notas_processadas.append(n_dict)

    conn.close()
    return render_template('lixeira.html', notas=notas_processadas)


@app.route('/deletar_lixeira/<int:id>')
def deletar_lixeira(id):
    u_id = session.get('usuario_id')
    with conectar_banco() as conn:
        cursor = conn.cursor()
        data_hoje = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("UPDATE notas SET status = 'lixeira', data_exclusao = ? WHERE id = ? AND usuario_id = ?", (data_hoje, id, u_id))
        conn.commit()
    return redirect(url_for('index'))


@app.route('/restaurar_lixeira/<int:id>')
def restaurar_lixeira(id):
    u_id = session.get('usuario_id')
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE notas SET status = 'Ativo', data_exclusao = NULL WHERE id = ? AND usuario_id = ?", (id, u_id))
        conn.commit()
    return redirect(url_for('lixeira'))


@app.route('/excluir_definitivo/<int:id>')
def excluir_definitivo(id):
    u_id = session.get('usuario_id')
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notas WHERE id = ? AND usuario_id = ?", (id, u_id))
        conn.commit()
    return redirect(url_for('lixeira'))


@app.route('/esvaziar_lixeira')
def esvaziar_lixeira():
    u_id = session.get('usuario_id')
    with conectar_banco() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM notas WHERE status = 'lixeira' AND usuario_id = ?", (u_id,))
        conn.commit()
    return redirect(url_for('lixeira'))

# ==============================================================================
# SEÇÃO 10: CALENDÁRIO E API REST
# ==============================================================================
@app.route('/calendario')
def calendario():
    return render_template('calendario.html')


@app.route('/api/eventos')
def api_eventos():
    u_id = session.get('usuario_id')
    conn = conectar_banco()
    
    # Busca notas
    notas_db = conn.execute('''
        SELECT id, titulo, data_vencimento, prioridade 
        FROM notas 
        WHERE status = 'Ativo'
          AND usuario_id = ?
          AND data_vencimento IS NOT NULL 
          AND data_vencimento != ''
    ''', (u_id,)).fetchall()
    conn.close()

    eventos = []
    for row in notas_db:
        nota = dict(row)
        
        # Define a cor no calendario baseado na prioridade
        cor = '#2563eb'
        if nota.get('prioridade') == 'Alta':
            cor = '#ef4444'
        elif nota.get('prioridade') == 'Média':
            cor = '#f59e0b'
        elif nota.get('prioridade') == 'Baixa':
            cor = '#10b981'

        eventos.append({
            'id': nota['id'],
            'title': nota['titulo'],
            'start': nota['data_vencimento'],
            'color': cor
        })

    return jsonify(eventos)

# ==============================================================================
# SEÇÃO 11: ROTAS PWA
# ==============================================================================
@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')

@app.route('/sw.js')
def service_worker():
    return app.send_static_file('sw.js')

# verificar_e_enviar_alertas() #teste de envio para email

# ==============================================================================
# EXECUÇÃO DO SERVIDOR
# ==============================================================================
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)