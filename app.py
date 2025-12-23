from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3
import os
import csv
from datetime import datetime
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import urllib.parse

app = Flask(__name__)
app.secret_key = 'edutech-secret-key'
DB_NAME = "escola.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matricula TEXT NOT NULL,
            nome TEXT NOT NULL,
            telefone TEXT NOT NULL, 
            nota1 REAL NOT NULL,
            nota2 REAL NOT NULL,
            nota3 REAL NOT NULL,
            faltas INTEGER NOT NULL DEFAULT 0,
            media REAL NOT NULL,
            situacao TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def calcular_predicao(aluno):
    n1, n2, n3, faltas = aluno['nota1'], aluno['nota2'], aluno['nota3'], aluno['faltas']

    # Risco Crítico por Faltas
    if faltas >= 45:
        return {"status": "Risco Crítico", "cor": "danger", "msg": "Excesso de faltas"}

    # Alterado de 'Finalizado' para 'Aprovado' conforme solicitado
    if n1 > 0 and n2 > 0 and n3 > 0:
        return {"status": "Aprovado", "cor": "success", "msg": "Ciclo Encerrado"}

    notas_atuais = [n for n in [n1, n2] if n > 0]
    if len(notas_atuais) < 2:
        return {"status": "Aguardando", "cor": "info", "msg": "Coletando dados..."}

    precisa = 21.0 - (n1 + n2)
    alerta = " (Atenção às faltas!)" if faltas > 30 else ""

    if precisa <= 0:
        return {"status": "Aprovado", "cor": "success", "msg": "Já passou! 🚀" + alerta}
    elif precisa > 10:
        return {"status": "Crítico", "cor": "danger", "msg": f"Precisa {precisa:.1f} (Impossível)"}
    elif precisa >= 8:
        return {"status": "Alto Risco", "cor": "warning", "msg": f"Precisa {precisa:.1f}" + alerta}
    else:
        return {"status": "Estável", "cor": "primary", "msg": f"Precisa {precisa:.1f}" + alerta}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['usuario'] == "admin" and request.form['senha'] == "1234":
            session['logado'] = True
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if not session.get('logado'): return redirect(url_for('login'))
    conn = get_db_connection()
    alunos_db = conn.execute('SELECT * FROM alunos').fetchall()
    alunos_com_predicao = []
    apr, rep = 0, 0
    for aluno in alunos_db:
        a = dict(aluno)
        p = calcular_predicao(aluno)
        a['predicao'] = p
        alunos_com_predicao.append(a)
        if p['status'] == 'Aprovado': apr += 1
        elif 'Risco' in p['status'] or 'Crítico' in p['status']: rep += 1
    conn.close()
    return render_template('index.html', alunos=alunos_com_predicao, apr=apr, rep=rep)

@app.route('/add', methods=['POST'])
def add_student():
    if not session.get('logado'): return redirect(url_for('login'))
    try:
        n1 = float(request.form['nota1'].replace(',', '.') or 0)
        n2 = float(request.form['nota2'].replace(',', '.') or 0)
        n3 = float(request.form['nota3'].replace(',', '.') or 0)
        f = int(request.form['faltas'] or 0)
        m = (n1 + n2 + n3) / 3
        conn = get_db_connection()
        conn.execute('INSERT INTO alunos (matricula, nome, telefone, nota1, nota2, nota3, faltas, media, situacao) VALUES (?,?,?,?,?,?,?,?,?)',
                     (request.form['matricula'], request.form['nome'], request.form['telefone'], n1, n2, n3, f, m, "Ativo"))
        conn.commit()
        conn.close()
    except: pass
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_student(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM alunos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/whatsapp/<int:id>')
def enviar_whatsapp(id):
    conn = get_db_connection()
    aluno = conn.execute('SELECT * FROM alunos WHERE id = ?', (id,)).fetchone()
    conn.close()
    msg = f"Olá, aviso EduTech: O aluno {aluno['nome']} está com {aluno['faltas']} faltas e situação: {calcular_predicao(aluno)['status']}."
    return redirect(f"https://wa.me/55{aluno['telefone']}?text={urllib.parse.quote(msg)}")

init_db()
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
