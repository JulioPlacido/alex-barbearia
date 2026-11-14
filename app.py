from datetime import datetime
import os
import sqlite3
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

app = Flask(__name__)
app.secret_key = "chave_secreta_super_segura_alex"


def init_db():
  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS agendamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_nome TEXT NOT NULL,
            servico TEXT NOT NULL,
            valor REAL NOT NULL,
            barbeiro TEXT NOT NULL,
            data TEXT NOT NULL,
            horario TEXT NOT NULL
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            papel TEXT NOT NULL
        )
    """)
  
  try:
    cursor.execute("ALTER TABLE usuarios ADD COLUMN whatsapp TEXT DEFAULT '35988596966'")
  except:
    pass
  try:
    cursor.execute("ALTER TABLE usuarios ADD COLUMN foto TEXT DEFAULT 'alex.png'")
  except:
    pass

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS horarios_bloqueados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barbeiro TEXT NOT NULL,
            data TEXT NOT NULL,
            horario TEXT NOT NULL,
            motivo TEXT NOT NULL
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT,
            preco REAL NOT NULL,
            quantidade INTEGER NOT NULL
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS fidelidade (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_nome TEXT UNIQUE NOT NULL,
            cortes_realizados INTEGER DEFAULT 1
        )
    """)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS ajustes_desempenho (
            barbeiro TEXT PRIMARY KEY,
            atendimentos_extra INTEGER DEFAULT 0,
            faturamento_extra REAL DEFAULT 0.0
        )
    """)
  
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            imagem TEXT
        )
    """)
  conn.commit()

  cursor.execute("SELECT COUNT(*) FROM usuarios")
  if cursor.fetchone()[0] == 0:
    cursor.execute(
        "INSERT INTO usuarios (nome, senha, papel, whatsapp, foto) VALUES (?, ?, ?, ?, ?)",
        ("Alex", "1234", "admin", "35988596966", "alex.png"),
    )
    cursor.execute(
        "INSERT INTO usuarios (nome, senha, papel, whatsapp, foto) VALUES (?, ?, ?, ?, ?)",
        ("Guilherme", "1234", "barbeiro", "35991191688", "guilherme.png"),
    )
    conn.commit()
  else:
    cursor.execute("UPDATE usuarios SET whatsapp = '35988596966' WHERE nome = 'Alex'")
    cursor.execute("UPDATE usuarios SET whatsapp = '35991191688' WHERE nome = 'Guilherme'")
    conn.commit()

  cursor.execute("SELECT COUNT(*) FROM servicos")
  if cursor.fetchone()[0] == 0:
    servicos_iniciais = [
        ("Corte de Cabelo", 35.0, "corte.png"),
        ("Barba", 25.0, "barba.png"),
        ("Alisamento", 50.0, "alisamento.png"),
        ("Sobrancelha", 15.0, "sobrancelha.png"),
        ("Corte e Barba", 55.0, "corte_barba.png"),
        ("Corte e Sobrancelha", 40.0, "corte_sobrancelha.png"),
    ]
    cursor.executemany(
        "INSERT INTO servicos (nome, preco, imagem) VALUES (?, ?, ?)",
        servicos_iniciais,
    )
    conn.commit()

  conn.close()


with app.app_context():
  init_db()


def formatar_data(data_str):
  if not data_str or len(data_str) != 10:
    return data_str
  try:
    partes = data_str.split("-")
    if len(partes) == 3:
      return f"{partes[2]}/{partes[1]}/{partes[0]}"
  except:
    pass
  return data_str


@app.route("/")
def index():
  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  
  cursor.execute("SELECT nome, whatsapp, foto FROM usuarios WHERE papel IN ('barbeiro', 'admin')")
  barbeiros_db = cursor.fetchall()
  barbeiros = [
      {
          "nome": b[0], 
          "whatsapp": b[1] if b[1] else "35988596966", 
          "foto": b[2] if b[2] and b[2].strip() else "alex.png"
      }
      for b in barbeiros_db
  ]

  cursor.execute("SELECT id, nome, preco, imagem FROM servicos")
  servicos_db = cursor.fetchall()
  servicos = [
      {"id": s[0], "nome": s[1], "preco": s[2], "imagem": s[3]}
      for s in servicos_db
  ]

  cursor.execute("SELECT barbeiro, data, horario FROM agendamentos")
  ocupados = cursor.fetchall()
  cursor.execute("SELECT barbeiro, data, horario, motivo FROM horarios_bloqueados")
  bloqueados = cursor.fetchall()
  cursor.execute("SELECT id, nome, descricao, preco, quantidade FROM produtos")
  produtos = cursor.fetchall()
  conn.close()

  return render_template(
      "index.html",
      servicos=servicos,
      barbeiros=barbeiros,
      ocupados=ocupados,
      bloqueados=bloqueados,
      produtos=produtos,
      hoje=datetime.now().strftime("%Y-%m-%d"),
  )


@app.route("/agendar", methods=["POST"])
def agendar():
  cliente_nome = request.form["cliente_nome"].strip()

  if len(cliente_nome) <= 9:
    return (
        "<h1>Erro: Informe seu nome e sobrenome completo (mais de 9"
        " caracteres) para garantir a fidelidade.</h1><a"
        " href='/'>Voltar</a>"
    )

  servico_info = request.form["servico"].split("|")
  servico_nome = servico_info[0]
  servico_valor = float(servico_info[1])

  produto_id = request.form.get("produto_id")
  produto_texto = ""
  produto_valor = 0.0

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()

  if produto_id:
    cursor.execute(
        "SELECT id, nome, preco, quantidade FROM produtos WHERE id = ?",
        (produto_id,),
    )
    prod = cursor.fetchone()
    if prod and prod[3] > 0:
      produto_texto = prod[1]
      produto_valor = prod[2]
      servico_valor += produto_valor
      servico_nome += f" + {produto_texto}"

  barbeiro = request.form["barbeiro"]
  data = request.form["data"]
  horario = request.form["horario"]

  cursor.execute(
      "SELECT motivo FROM horarios_bloqueados WHERE barbeiro = ? AND data = ? AND"
      " horario = ?",
      (barbeiro, data, horario),
  )
  bloqueio = cursor.fetchone()
  if bloqueio:
    conn.close()
    return (
        f"<h1>Erro: Este horário está indisponível ({bloqueio[0]}). Escolha"
        " outro.</h1><a href='/'>Voltar</a>"
    )

  cursor.execute(
      "SELECT * FROM agendamentos WHERE barbeiro = ? AND data = ? AND horario ="
      " ?",
      (barbeiro, data, horario),
  )
  if cursor.fetchone():
    conn.close()
    return (
        "<h1>Erro: Este horário já foi reservado!</h1><a href='/'>Voltar</a>"
    )

  cursor.execute(
      """
        INSERT INTO agendamentos (cliente_nome, servico, valor, barbeiro, data, horario)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
      (cliente_nome, servico_nome, servico_valor, barbeiro, data, horario),
  )

  cursor.execute(
      "SELECT cortes_realizados FROM fidelidade WHERE cliente_nome = ?",
      (cliente_nome,),
  )
  fid = cursor.fetchone()
  if fid:
    cursor.execute(
        "UPDATE fidelidade SET cortes_realizados = cortes_realizados + 1 WHERE"
        " cliente_nome = ?",
        (cliente_nome,),
    )
    cortes_totais = fid[0] + 1
  else:
    cursor.execute(
        "INSERT INTO fidelidade (cliente_nome, cortes_realizados) VALUES (?,"
        " 1)",
        (cliente_nome,),
    )
    cortes_totais = 1

  conn.commit()

  cursor.execute("SELECT whatsapp FROM usuarios WHERE nome = ?", (barbeiro,))
  u_tel = cursor.fetchone()
  tel = u_tel[0] if u_tel and u_tel[0] else "35988596966"
  conn.close()

  data_formatada = formatar_data(data)

  msg = (
      f"💈 *NOVO AGENDAMENTO CONFIRMADO* 💈%0A"
      f"────────────────────────%0A"
      f"👤 *Profissional:* {barbeiro}%0A"
      f"*Cliente:* {cliente_nome}%0A"
      f"✂️ *Serviço:* {servico_nome}%0A"
      f"💰 *Valor:* R$ {servico_valor:.2f}%0A"
      f"📅 *Data:* {data_formatada}%0A"
      f"⏰ *Horário:* {horario}%0A"
      f"────────────────────────%0A"
      f"✨ *Alex Barbearia* - Estilo e Tradição!"
  )
  
  whatsapp_url = f"https://api.whatsapp.com/send?phone=55{tel}&text={msg}"

  return render_template(
      "sucesso.html",
      cliente=cliente_nome,
      barbeiro=barbeiro,
      servico=servico_nome,
      valor=servico_valor,
      data=data_formatada,
      horario=horario,
      cortes_totais=cortes_totais,
      whatsapp_url=whatsapp_url,
  )


@app.route("/login", methods=["GET", "POST"])
def login():
  if request.method == "POST":
    nome = request.form["nome"]
    senha = request.form["senha"]
    conn = sqlite3.connect("barbearia.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM usuarios WHERE nome = ? AND senha = ?", (nome, senha)
    )
    user = cursor.fetchone()
    conn.close()

    if user:
      session["user_nome"] = user[1]
      session["user_papel"] = user[3]
      return redirect(url_for("painel"))
    else:
      return render_template(
          "login.html", erro="Nome ou senha incorretos!"
      )
  return render_template("login.html")


@app.route("/logout")
def logout():
  session.clear()
  return redirect(url_for("login"))


@app.route("/painel")
def painel():
  if "user_nome" not in session:
    return redirect(url_for("login"))

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()

  user = session["user_nome"]
  papel = session["user_papel"]

  cursor.execute(
      "SELECT id, cliente_nome, servico, valor, barbeiro, data, horario FROM"
      " agendamentos WHERE barbeiro = ? ORDER BY data DESC, horario DESC",
      (user,),
  )
  agendamentos_raw = cursor.fetchall()
  agendamentos = [
      (a[0], a[1], a[2], a[3], a[4], formatar_data(a[5]), a[6])
      for a in agendamentos_raw
  ]

  cursor.execute(
      "SELECT id, data, horario, motivo FROM horarios_bloqueados WHERE barbeiro"
      " = ? ORDER BY data, horario",
      (user,),
  )
  bloqueios_raw = cursor.fetchall()
  meus_bloqueios = [
      (b[0], formatar_data(b[1]), b[2], b[3])
      for b in bloqueios_raw
  ]

  stats_barbeiros = []
  usuarios_lista = []
  servicos_lista = []
  
  if papel == "admin":
    cursor.execute(
        "SELECT nome FROM usuarios WHERE papel IN ('barbeiro', 'admin')"
    )
    todos_barbs = [r[0] for r in cursor.fetchall()]

    for b in todos_barbs:
      cursor.execute(
          "SELECT COUNT(*), SUM(valor) FROM agendamentos WHERE barbeiro = ?",
          (b,),
      )
      res = cursor.fetchone()
      qtd_real = res[0] or 0
      total_real = res[1] or 0.0

      cursor.execute(
          "SELECT atendimentos_extra, faturamento_extra FROM"
          " ajustes_desempenho WHERE barbeiro = ?",
          (b,),
      )
      adj = cursor.fetchone()
      atend_extra = adj[0] if adj else 0
      fat_extra = adj[1] if adj else 0.0

      qtd = max(0, qtd_real + atend_extra)
      total = max(0.0, total_real + fat_extra)

      comissao_casa = total * 0.40
      comissao_barbeiro = total * 0.60
      stats_barbeiros.append({
          "nome": b,
          "qtd": qtd,
          "faturamento": total,
          "casa": comissao_casa,
          "barbeiro": comissao_barbeiro,
      })

    cursor.execute("SELECT id, nome, senha, papel, whatsapp FROM usuarios")
    usuarios_lista = cursor.fetchall()

  cursor.execute("SELECT id, nome, preco FROM servicos")
  servicos_lista = cursor.fetchall()

  filtro_fat = request.args.get("filtro", "mes")
  hoje_str = datetime.now().strftime("%Y-%m-%d")
  ano_atual = datetime.now().strftime("%Y")
  mes_atual = datetime.now().strftime("%Y-%m")

  query_fat_base = (
      "SELECT id, cliente_nome, servico, valor, barbeiro, data, horario FROM"
      " agendamentos"
  )
  params_fat = []

  if papel != "admin":
    query_fat_base += " WHERE barbeiro = ?"
    params_fat.append(user)

  cursor.execute(query_fat_base + " ORDER BY data DESC, horario DESC", params_fat)
  todos_para_fat = cursor.fetchall()

  fat_filtrado = []
  total_fat = 0.0

  for row in todos_para_fat:
    data_item = row[5]
    valor_item = row[3]

    incluir = False
    if filtro_fat == "dia" and data_item == hoje_str:
      incluir = True
    elif filtro_fat == "mes" and data_item.startswith(mes_atual):
      incluir = True
    elif filtro_fat == "ano" and data_item.startswith(ano_atual):
      incluir = True
    elif filtro_fat == "todos":
      incluir = True

    if incluir:
      fat_filtrado.append((row[0], row[1], row[2], row[3], row[4], formatar_data(row[5]), row[6]))
      total_fat += valor_item

  cursor.execute("SELECT id, nome, descricao, preco, quantidade FROM produtos")
  produtos = cursor.fetchall()

  cursor.execute(
      "SELECT id, cliente_nome, cortes_realizados FROM fidelidade ORDER BY"
      " cortes_realizados DESC"
  )
  fidelidade_clientes = cursor.fetchall()

  conn.close()

  return render_template(
      "painel.html",
      agendamentos=agendamentos,
      usuario=user,
      papel=papel,
      meus_bloqueios=meus_bloqueios,
      fat_filtrado=fat_filtrado,
      total_fat=total_fat,
      filtro_fat=filtro_fat,
      hoje=formatar_data(hoje_str),
      stats_barbeiros=stats_barbeiros,
      produtos=produtos,
      fidelidade_clientes=fidelidade_clientes,
      usuarios_lista=usuarios_lista,
      servicos_lista=servicos_lista,
  )


@app.route("/atualizar_servico/<int:id>", methods=["POST"])
def atualizar_servico(id):
  if "user_nome" not in session or session.get("user_papel") != "admin":
    return redirect(url_for("login"))

  novo_nome = request.form["nome"]
  novo_preco = float(request.form["preco"])

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE servicos SET nome = ?, preco = ? WHERE id = ?",
      (novo_nome, novo_preco, id),
  )
  conn.commit()
  conn.close()
  return redirect(url_for("painel"))


@app.route("/bloquear_horario", methods=["POST"])
def bloquear_horario():
  if "user_nome" not in session:
    return redirect(url_for("login"))

  barbeiro = session["user_nome"]
  data_form = request.form["data_bloqueio"]
  horario = request.form["horario_bloqueio"]
  motivo = request.form["motivo"]

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  try:
    cursor.execute(
        "INSERT INTO horarios_bloqueados (barbeiro, data, horario, motivo)"
        " VALUES (?, ?, ?, ?)",
        (barbeiro, data_form, horario, motivo),
    )
    conn.commit()
  except:
    pass
  conn.close()
  return redirect(url_for("painel"))


@app.route("/desbloquear_horario/<int:id>")
def desbloquear_horario(id):
  if "user_nome" not in session:
    return redirect(url_for("login"))

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute("DELETE FROM horarios_bloqueados WHERE id = ?", (id,))
  conn.commit()
  conn.close()
  return redirect(url_for("painel"))


@app.route("/cancelar/<int:id>")
def cancelar(id):
  if "user_nome" not in session:
    return redirect(url_for("login"))

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute("DELETE FROM agendamentos WHERE id = ?", (id,))
  conn.commit()
  conn.close()
  return redirect(url_for("painel"))


@app.route("/adicionar_produto", methods=["POST"])
def adicionar_produto():
  if "user_nome" not in session:
    return redirect(url_for("login"))

  nome = request.form["nome"]
  descricao = request.form["descricao"]
  preco = float(request.form["preco"])
  quantidade = int(request.form["quantidade"])

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute(
      """
        INSERT INTO produtos (nome, descricao, preco, quantidade) 
        VALUES (?, ?, ?, ?)
    """,
      (nome, descricao, preco, quantidade),
  )
  conn.commit()
  conn.close()
  return redirect(url_for("painel"))


@app.route("/remover_produto/<int:id>")
def remover_produto(id):
  if "user_nome" not in session:
    return redirect(url_for("login"))

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute("DELETE FROM produtos WHERE id = ?", (id,))
  conn.commit()
  conn.close()
  return redirect(url_for("painel"))


@app.route("/dar_baixa_produto/<int:id>", methods=["POST"])
def dar_baixa_produto(id):
  if "user_nome" not in session:
    return redirect(url_for("login"))

  qtd_baixa = int(request.form.get("quantidade_baixa", 1))

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute("SELECT quantidade FROM produtos WHERE id = ?", (id,))
  prod = cursor.fetchone()
  if prod:
    nova_qtd = max(0, prod[0] - qtd_baixa)
    cursor.execute(
        "UPDATE produtos SET quantidade = ? WHERE id = ?", (nova_qtd, id)
    )
    conn.commit()
  conn.close()
  return redirect(url_for("painel"))


@app.route("/zerar_fidelidade/<int:id>")
def zerar_fidelidade(id):
  if "user_nome" not in session:
    return redirect(url_for("login"))

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE fidelidade SET cortes_realizados = 0 WHERE id = ?", (id,)
  )
  conn.commit()
  conn.close()
  return redirect(url_for("painel"))


@app.route("/remover_fidelidade/<int:id>")
def remover_fidelidade(id):
  if "user_nome" not in session:
    return redirect(url_for("login"))

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute("DELETE FROM fidelidade WHERE id = ?", (id,))
  conn.commit()
  conn.close()
  return redirect(url_for("painel"))


@app.route("/zerar_tudo_faturamento")
def zerar_tudo_faturamento():
  if "user_nome" not in session or session.get("user_papel") != "admin":
    return redirect(url_for("login"))

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute("DELETE FROM agendamentos")
  cursor.execute("DELETE FROM ajustes_desempenho")
  conn.commit()
  conn.close()
  return redirect(url_for("painel"))


@app.route("/atualizar_usuario/<int:id>", methods=["POST"])
def atualizar_usuario(id):
  if "user_nome" not in session or session.get("user_papel") != "admin":
    return redirect(url_for("login"))

  novo_nome = request.form["nome"]
  nova_senha = request.form["senha"]
  novo_whatsapp = request.form["whatsapp"]
  foto_nome = novo_nome.lower().replace(" ", "_") + ".png"

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE usuarios SET nome = ?, senha = ?, whatsapp = ?, foto = ? WHERE id = ?",
      (novo_nome, nova_senha, novo_whatsapp, foto_nome, id),
  )
  conn.commit()
  conn.close()
  return redirect(url_for("painel"))


@app.route("/criar_usuario", methods=["POST"])
def criar_usuario():
  if "user_nome" not in session or session.get("user_papel") != "admin":
    return redirect(url_for("login"))

  nome = request.form["nome"]
  senha = request.form["senha"]
  papel = request.form["papel"]
  whatsapp = request.form["whatsapp"]
  foto_nome = nome.lower().replace(" ", "_") + ".png"

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  try:
    cursor.execute(
        "INSERT INTO usuarios (nome, senha, papel, whatsapp, foto) VALUES (?, ?, ?, ?, ?)",
        (nome, senha, papel, whatsapp, foto_nome),
    )
    conn.commit()
  except:
    pass
  conn.close()
  return redirect(url_for("painel"))


@app.route("/remover_usuario/<int:id>")
def remover_usuario(id):
  if "user_nome" not in session or session.get("user_papel") != "admin":
    return redirect(url_for("login"))

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute("SELECT nome FROM usuarios WHERE id = ?", (id,))
  user_alvo = cursor.fetchone()
  
  if user_alvo and user_alvo[0] != "Alex":
    cursor.execute("DELETE FROM usuarios WHERE id = ?", (id,))
    conn.commit()
    
  conn.close()
  return redirect(url_for("painel"))


@app.route("/ajustar_atendimentos", methods=["POST"])
def ajustar_atendimentos():
  if "user_nome" not in session or session.get("user_papel") != "admin":
    return redirect(url_for("login"))

  barbeiro = request.form["barbeiro"]
  delta = int(request.form["delta"])

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute(
      "SELECT atendimentos_extra, faturamento_extra FROM ajustes_desempenho"
      " WHERE barbeiro = ?",
      (barbeiro,),
  )
  row = cursor.fetchone()
  if row:
    novo_val = row[0] + delta
    cursor.execute(
        "UPDATE ajustes_desempenho SET atendimentos_extra = ? WHERE barbeiro ="
        " ?",
        (novo_val, barbeiro),
    )
  else:
    cursor.execute(
        "INSERT INTO ajustes_desempenho (barbeiro, atendimentos_extra,"
        " faturamento_extra) VALUES (?, ?, 0.0)",
        (barbeiro, delta),
    )
  conn.commit()
  conn.close()
  return redirect(url_for("painel"))


@app.route("/ajustar_faturamento", methods=["POST"])
def ajustar_faturamento():
  if "user_nome" not in session or session.get("user_papel") != "admin":
    return redirect(url_for("login"))

  barbeiro = request.form["barbeiro"]
  delta = float(request.form["delta"])

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute(
      "SELECT atendimentos_extra, faturamento_extra FROM ajustes_desempenho"
      " WHERE barbeiro = ?",
      (barbeiro,),
  )
  row = cursor.fetchone()
  if row:
    novo_val = row[1] + delta
    cursor.execute(
        "UPDATE ajustes_desempenho SET faturamento_extra = ? WHERE barbeiro ="
        " ?",
        (novo_val, barbeiro),
    )
  else:
    cursor.execute(
        "INSERT INTO ajustes_desempenho (barbeiro, atendimentos_extra,"
        " faturamento_extra) VALUES (?, 0, ?)",
        (barbeiro, delta),
    )
  conn.commit()
  conn.close()
  return redirect(url_for("painel"))


@app.route("/zerar_desempenho_barbeiro/<barbeiro>")
def zerar_desempenho_barbeiro(barbeiro):
  if "user_nome" not in session or session.get("user_papel") != "admin":
    return redirect(url_for("login"))

  conn = sqlite3.connect("barbearia.db")
  cursor = conn.cursor()
  cursor.execute("DELETE FROM agendamentos WHERE barbeiro = ?", (barbeiro,))
  cursor.execute("DELETE FROM ajustes_desempenho WHERE barbeiro = ?", (barbeiro,))
  conn.commit()
  conn.close()
  return redirect(url_for("painel"))


if __name__ == "__main__":
  app.run(debug=True)