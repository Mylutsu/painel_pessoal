# 📋 Painel Pessoal de Notas e Tarefas

Um sistema de gerenciamento de notas inteligente desenvolvido com **Python** e **Flask**. O projeto vai além de um simples CRUD, incorporando lógica de negócios para cálculo de prazos, categorias e um dashboard de produtividade em tempo real.

## 🚀 Funcionalidades

- **Gerenciamento Completo (CRUD):** Criação, listagem e conclusão (exclusão) de notas.
- **Inteligência de Prazos:** - Cálculo automático de dias restantes para o vencimento.
  - **Alertas Visuais:** Sistema de cores e animações que destacam notas próximas ao vencimento (Amarelo) ou já vencidas (Vermelho).
- **Organização por Prioridade:** Ordenação automática que coloca tarefas de "Alta Prioridade" no topo.
- **Dashboard de Status:** Painel superior que exibe o total de notas, quantas estão vencidas e quantas estão em alerta.
- **Interface Responsiva:** Design limpo com feedback visual para o usuário.

## 🛠️ Tecnologias Utilizadas

- **Backend:** Python 3.x com framework Flask.
- **Banco de Dados:** SQLite (persistência de dados local).
- **Frontend:** HTML5, CSS3 (com animações de keyframes) e Jinja2 para renderização dinâmica.
- **Lógica de Datas:** Biblioteca `datetime` do Python.

## 📦 Como rodar o projeto

1. **Clone o repositório:**
   ```bash
   git clone [https://github.com/Mylutsu/painel_pessoal.git](https://github.com/Mylutsu/painel_pessoal.git)
   cd painel_pessoal

2. **Instale as dependencias:**
    pip install -r requirements.txt

3. **Execute a aplicação:**
    python app.py

4. **Acesse o navegador:**
    http://127.0.0.1:5000