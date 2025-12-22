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

if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)

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
            media REAL NOT NULL,
            situacao TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def realizar_backup():
    if os.path.exists(DB_NAME):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        shutil.copy2(DB_NAME, os.path.join(BACKUP_DIR, f"backup_{timestamp}.db"))

# --- LÓGICA DE PREDIÇÃO (IA SIMPLIFICADA) ---
def calcular_predicao(aluno):
    """Analisa as notas e define o risco e a necessidade."""
    n1 = aluno['nota1']
    n2 = aluno['nota2']
    n3 = aluno['nota3']
    
    # Se já tem as 3 notas, a situação já está definida
    if n1 > 0 and n2 > 0 and n3 > 0:
        return {"status": "Finalizado", "cor": "secondary", "msg": "Ciclo Encerrado"}

    # Se falta nota, vamos prever
    notas_atuais = []
    if n1 > 0: notas_atuais.append(n1)
    if n2 > 0: notas_atuais.append(n2)
    
    # Se não tem nota nenhuma ou só uma, é cedo para prever risco alto
    if len(notas_atuais) < 2:
        return {"status": "Aguardando", "cor": "info", "msg": "Coletando dados..."}

    # CÁLCULO MÁGICO: (Média 7.0 * 3) = 21 pontos totais necessários
    pontos_tem = n1 + n2
    precisa = 21.0 - pontos_tem
    
    if precisa <= 0:
        return {"status": "Aprovado", "cor": "success", "msg": "Já passou! 🚀"}
    elif precisa > 10:
        return {"status": "Crítico", "cor": "danger", "msg": f"Impossível matematicamente (Precisa de {precisa:.1f})"}
    elif precisa >= 8:
        return {"status": "Alto Risco", "cor": "warning", "msg": f"Precisa de {precisa:.1f} na 3ª Unid"}
    else:
        return {"status": "Estável", "cor": "primary", "msg": f"Precisa de {precisa:.1f} para passar"}

@app.route('/whatsapp/<int:id>')
def enviar_whatsapp(id):
    if not session.get('logado'): return redirect(url_for('login'))
    conn = get_db_connection()
    aluno = conn.execute('SELECT * FROM alunos WHERE id = ?', (id,)).fetchone()
    conn.close()
    if not aluno: return "Erro"
    
    telefone = aluno['telefone'].replace("(", "").replace(")", "").replace("-", "").replace(" ", "")
    
    # Mensagem inteligente baseada na predição
    predicao = calcular_predicao(aluno)
    
    if predicao['status'] == "Finalizado":
        msg = f"Olá! O aluno *{aluno['nome']}* finalizou o ano com média *{aluno['media']:.1f}*. Situação: *{aluno['situacao']}*."
    else:
        msg = f"Olá! O aluno *{aluno['nome']}* está com média parcial. {predicao['msg']}."

    texto_codificado = urllib.parse.quote(msg)
    return redirect(f"https://wa.me/55{telefone}?text={texto_codificado}")

@app.route('/boletim/<int:id>')
def gerar_boletim(id):
    if not session.get('logado'): return redirect(url_for('login'))
    conn = get_db_connection()
    aluno = conn.execute('SELECT * FROM alunos WHERE id = ?', (id,)).fetchone()
    conn.close()
    
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, 800, "EDUTECH.AI - RELATÓRIO DE INTELIGÊNCIA")
    p.setFont("Helvetica", 12)
    p.drawString(50, 780, "Análise de Desempenho e Predição")
    p.line(50, 770, 550, 770)
    
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, 730, f"ALUNO: {aluno['nome']}")
    p.drawString(50, 710, f"MATRÍCULA: {aluno['matricula']}")
    p.drawString(350, 710, f"CONTATO: {aluno['telefone']}")
    
    # Tabela Notas
    p.setFillColorRGB(0.9, 0.9, 0.9)
    p.rect(50, 630, 500, 30, fill=1) # Fundo cinza
    p.setFillColorRGB(0, 0, 0)
    
    p.setFont("Helvetica-Bold", 10)
    p.drawString(60, 640, "UNID 1")
    p.drawString(160, 640, "UNID 2")
    p.drawString(260, 640, "UNID 3")
    p.drawString(360, 640, "MÉDIA ATUAL")
    p.drawString(460, 640, "STATUS")
    
    p.setFont("Helvetica", 12)
    p.drawString(70, 600, str(aluno['nota1']))
    p.drawString(170, 600, str(aluno['nota2']))
    p.drawString(270, 600, str(aluno['nota3']))
    p.drawString(370, 600, "{:.1f}".format(aluno['media']))
    p.drawString(460, 600, aluno['situacao'])

    # ÁREA DE IA (Predição no PDF)
    predicao = calcular_predicao(aluno)
    p.setStrokeColorRGB(0, 0, 1) # Borda azul
    p.rect(50, 450, 500, 100)
    
    p.setFont("Helvetica-Bold", 14)
    p.drawString(70, 520, "ANÁLISE PREDITIVA DO SISTEMA:")
    p.setFont("Helvetica", 12)
    p.drawString(70, 490, f"Diagnóstico: {predicao['status']}")
    p.drawString(70, 470, f"Recomendação: {predicao['msg']}")

    p.showPage()
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"Relatorio_{aluno['nome']}.pdf", mimetype='application/pdf')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['usuario'] == USUARIO_ADMIN and request.form['senha'] == SENHA_ADMIN:
            session['logado'] = True
            realizar_backup()
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
        
        # Processa os alunos para adicionar a predição ANTES de mandar pro HTML
        alunos_com_predicao = []
        aprovados = 0
        reprovados = 0
        
        for aluno in alunos_db:
            # Converte para dicionário para poder adicionar campo novo
            a = dict(aluno) 
            a['predicao'] = calcular_predicao(aluno) # Adiciona a IA aqui
            alunos_com_predicao.append(a)
            
            if aluno['situacao'] == 'Aprovado': aprovados += 1
            elif aluno['situacao'] == 'Reprovado': reprovados += 1
            
    except Exception as e:
        print(e)
        return "Erro ao carregar banco."
    conn.close()
    return render_template('index.html', alunos=alunos_com_predicao, apr=aprovados, rep=reprovados)

@app.route('/exportar')
def exportar_dados():
    if not session.get('logado'): return redirect(url_for('login'))
    conn = get_db_connection()
    alunos = conn.execute('SELECT * FROM alunos').fetchall()
    conn.close()
    arquivo_csv = "relatorio_geral.csv"
    with open(arquivo_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['Matricula', 'Nome', 'Nota1', 'Nota2', 'Nota3', 'Media', 'Predicao'])
        for a in alunos: 
            pred = calcular_predicao(a)['msg']
            w.writerow([a['matricula'], a['nome'], a['nota1'], a['nota2'], a['nota3'], str(a['media']).replace('.',','), pred])
    return send_file(arquivo_csv, as_attachment=True)

@app.route('/add', methods=['POST'])
def add_student():
    if not session.get('logado'): return redirect(url_for('login'))
    try:
        n1 = float(request.form['nota1'].replace(',', '.') or 0)
        n2 = float(request.form['nota2'].replace(',', '.') or 0)
        n3 = float(request.form['nota3'].replace(',', '.') or 0)
        
        # Média simples. Se não tiver nota 3, ela entra como 0 na média atual
        media = (n1 + n2 + n3) / 3
        
        # Situação só define se fechou o ciclo? 
        # Vamos manter simples: >= 6 Aprovado, senão Reprovado (ou Cursando)
        if n1 > 0 and n2 > 0 and n3 > 0:
            sit = "Aprovado" if media >= 6.0 else "Reprovado"
        else:
            sit = "Cursando" # Status novo para quem ainda não terminou

        conn = get_db_connection()
        conn.execute('INSERT INTO alunos (matricula, nome, telefone, nota1, nota2, nota3, media, situacao) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                     (request.form['matricula'], request.form['nome'], request.form['telefone'], n1, n2, n3, media, sit))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro: {e}")
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_student(id):
    if not session.get('logado'): return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM alunos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
# Esse bloco garante que o banco de dados seja criado se não existir
with app.app_context():
    db.create_all()
    print("Banco de dados criado com sucesso!")

    init_db()
    app.run(debug=True, host='0.0.0.0')