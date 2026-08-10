# 📌 Painel Pessoal de Anotações e Lembretes
Uma aplicação web completa para gestão de tarefas, notas e compromissos financeiros, com suporte a **alertas automáticos por e-mail**, categorização personalizada, modo escuro e retenção temporária na lixeira.

---

## 🚀 Funcionalidades

- 📋 **Gestão de Notas e Tarefas:** Criação, edição, conclusão e exclusão de notas categorizadas por prioridade (*Alta, Média, Baixa*).
- 🏷️ **Categorias Personalizadas:** Adicione e remova categorias com emojis customizados.
- ⏰ **Alertas Inteligentes de Vencimento:** Cálculo automático de dias restantes para contas/tarefas a vencer.
- 📧 **Notificações por E-mail (HTML):** Agendador em segundo plano (`APScheduler`) que envia resumos diários às 08:00 com cards visuais formatados.
- 🗑️ **Lixeira Temporária:** Itens excluídos são mantidos por 30 dias com opção de restauração ou exclusão definitiva.
- 🌙 **Modo Escuro (Dark Mode):** Alternância fluida de temas armazenada nas preferências do navegador (`localStorage`).
- 🔍 **Busca em Tempo Real:** Filtragem instantânea via JavaScript no front-end.

---

## 🛠️ Tecnologias Utilizadas

- **Back-end:** Python, Flask, APScheduler
- **Banco de Dados:** SQLite3
- **Front-end:** HTML5, CSS3, JavaScript (Vanilla)
- **Outros:** SMTP (envio de e-mails via TLS), `python-dotenv`

---

## ⚙️ Como Executar o Projeto

### Pré-requisitos
- Python 3.10 ou superior instalado.

### Passo a Passo

1. **Clone o repositório:**
   ```bash
   git clone [https://github.com/Mylutsu/painel_pessoal.git](https://github.com/Mylutsu/painel_pessoal.git)
   cd painel_pessoal
   ```

2. **Crie e ative um ambiente virtual:**
   ```bash
   # Windows
   python -m venv venv
   venv\Scripts\activate

   # Linux/Mac
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure as Variáveis de Ambiente:**
   Crie um arquivo `.env` na raiz do projeto com base no arquivo `.env.example`:
   ```env
   EMAIL_USUARIO=seu_email@gmail.com
   EMAIL_SENHA=sua_senha_de_aplicativo
   ```

5. **Inicialize o Banco de Dados:**
   ```bash
   python init_db.py
   ```

6. **Execute a aplicação:**
   ```bash
   python app.py
   ```
   Acesse a aplicação no navegador em `http://127.0.0.1:5000`.
