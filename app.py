from flask import Flask, render_template, request, redirect, url_for, session, send_file
import sqlite3
import os
import shutil
import csv
from datetime import datetime
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import urllib.parse

app = Flask(__name__)
app.secret_key = 'edutech-secret-key'
DB_NAME = "escola.db"
BACKUP_DIR = "backups"

# --- CONFIGURAÇÕES ---
USUARIO_ADMIN = "admin"
SENHA_ADMIN = "1234"

if not os.path.exists(BACKUP_DIR): 
    os.makedirs(BACKUP_DIR)

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    # Adicionado o campo 'faltas' na criação da tabela
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
    n1 = aluno['nota1']
    n2 = aluno['nota2']
    n3 = aluno['nota3']
    faltas = aluno['faltas']

    # LÓGICA DE FALTAS: Se tiver mais de 45 faltas, o risco é crítico independente da nota
    if faltas >= 45:
        return {"status": "Risco Crítico", "cor": "danger", "msg": "Excesso de faltas (Reprovação)"}

    if n1 > 0 and n2 > 0 and n3 > 0:
        return {"status": "Finalizado", "cor": "secondary", "msg": "Ciclo Encerrado"}

    notas_atuais = []
    if n1 > 0: notas_atuais.append(n1)
    if n2 > 0: notas_atuais.append(n2)

    if len(notas_atuais) < 2:
        return {"status": "Aguardando", "cor": "info", "msg": "Coletando notas..."}

    pontos_tem = n1 + n2
    precisa = 21.0 - pontos_tem

    # Alerta de atenção se as faltas estiverem subindo
    alerta_falta = " (Atenção às faltas!)" if faltas > 30 else ""

    if precisa <= 0:
        return {"status": "Aprovado", "cor": "success", "msg": "Já passou! 🚀" + alerta_falta}
    elif precisa > 10:
        return {"status": "Crítico", "cor": "danger", "msg": f"Nota impossível (Precisa {precisa:.1f})"}
    elif precisa >= 8:
        return {"status": "Alto Risco", "cor": "warning", "msg": f"Precisa {precisa:.1f} na 3ª Unid" + alerta_falta}
    else:
        return {"status": "Estável", "cor": "primary", "msg": f"Precisa {precisa:.1f} para passar" + alerta_falta}

# --- ROTAS (Mantidas e Atualizadas) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['usuario'] == USUARIO_ADMIN and request.form['senha'] == SENHA_ADMIN:
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
    try:
        alunos_db = conn.execute('SELECT * FROM alunos').fetchall()
        alunos_com_predicao = []
        aprovados = 0
        reprovados = 0
        for aluno in alunos_db:
            a = dict(aluno) 
            a['predicao'] = calcular_predicao(aluno)
            alunos_com_predicao.append(a)
            if aluno['situacao'] == 'Aprovado': aprovados += 1
            elif aluno['situacao'] == 'Reprovado': reprovados += 1
    except Exception as e:
        print(e)
        return "Erro ao carregar banco."
    conn.close()
    return render_template('index.html', alunos=alunos_com_predicao, apr=aprovados, rep=reprovados)

@app.route('/add', methods=['POST'])
def add_student():
    if not session.get('logado'): return redirect(url_for('login'))
    try:
        n1 = float(request.form['nota1'].replace(',', '.') or 0)
        n2 = float(request.form['nota2'].replace(',', '.') or 0)
        n3 = float(request.form['nota3'].replace(',', '.') or 0)
        faltas = int(request.form['faltas'] or 0) # Captura faltas
        
        media = (n1 + n2 + n3) / 3
        sit = "Aprovado" if media >= 6.0 and faltas < 45 else "Cursando"
        if faltas >= 45: sit = "Reprovado"

        conn = get_db_connection()
        conn.execute('INSERT INTO alunos (matricula, nome, telefone, nota1, nota2, nota3, faltas, media, situacao) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                     (request.form['matricula'], request.form['nome'], request.form['telefone'], n1, n2, n3, faltas, media, sit))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro: {e}")
    return redirect(url_for('index'))

# Outras rotas (boletim, delete, exportar) mantidas...
@app.route('/delete/<int:id>')
def delete_student(id):
    if not session.get('logado'): return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM alunos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/exportar')
def exportar_dados():
    if not session.get('logado'): return redirect(url_for('login'))
    conn = get_db_connection()
    alunos = conn.execute('SELECT * FROM alunos').fetchall()
    conn.close()
    arquivo_csv = "relatorio.csv"
    with open(arquivo_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['Nome', 'Faltas', 'Media', 'Predicao'])
        for a in alunos:
            p = calcular_predicao(a)
            w.writerow([a['nome'], a['faltas'], round(a['media'],1), p['msg']])
    return send_file(arquivo_csv, as_attachment=True)

@app.route('/whatsapp/<int:id>')
def enviar_whatsapp(id):
    conn = get_db_connection()
    aluno = conn.execute('SELECT * FROM alunos WHERE id = ?', (id,)).fetchone()
    conn.close()
    msg = f"Aviso EduTech: O aluno {aluno['nome']} possui {aluno['faltas']} faltas. {calcular_predicao(aluno)['msg']}"
    return redirect(f"https://wa.me/55{aluno['telefone']}?text={urllib.parse.quote(msg)}")

@app.route('/boletim/<int:id>')
def gerar_boletim(id):
    conn = get_db_connection()
    aluno = conn.execute('SELECT * FROM alunos WHERE id = ?', (id,)).fetchone()
    conn.close()
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.drawString(50, 800, f"RELATÓRIO ESCOLAR - {aluno['nome']}")
    p.drawString(50, 780, f"Faltas: {aluno['faltas']}")
    p.drawString(50, 760, f"Média: {round(aluno['media'],1)}")
    p.drawString(50, 740, f"Análise IA: {calcular_predicao(aluno)['msg']}")
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Boletim_{aluno['id']}.pdf")

init_db()
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
