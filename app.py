from flask import Flask, render_template, redirect, url_for, request, session, flash, make_response, Response
from flask import render_template_string, jsonify
import functools

import datetime
from datetime import datetime

import psycopg2  # pip install psycopg2
import psycopg2.extras

# DB_HOST = "localhost"
DB_HOST = "database-2.cdcogkfzajf0.us-east-1.rds.amazonaws.com"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "15512332"

app = Flask(__name__)
app.secret_key = 'app_inventario'  # Configure uma chave secreta adequada


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        return view(**kwargs)

    return wrapped_view


@app.route('/')
def index():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur.execute(
            "SELECT * FROM inventario.usuario WHERE usuario = %s AND password = %s", (username, password))
        user = cur.fetchone()

        print(user)

        if user is not None:
            session['user_id'] = user['usuario']
            flash('Bem vindo', category='error')
            return redirect(url_for('inventario'))
        else:
            flash('Usuário ou Senha inválida', category='error')

    return render_template('login.html')


@app.route('/inventario', methods=['POST','GET'])
@login_required
def inventario():
    
    if request.method == 'POST':

        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
        cur = conn.cursor()

        # Obtenha os dados enviados no corpo da solicitação POST
        dados = request.get_json()

        # Agora você pode acessar os dados individualmente, por exemplo:
        codigo = dados.get('codigo')
        descricao = dados.get('descricao')
        contagem = dados.get('contagem')
        familia = int(session['user_id'])
        data_atual = datetime.now()
        # Salvar dados na tabela registro

        cur.execute("INSERT INTO inventario.registros (codigo,descricao,familia,contagem, data_hora_atual) VALUES ('{}','{}',{}, {}, '{}')".format(codigo,descricao,familia,contagem,data_atual))

        conn.commit()
        
        cur.close()
        conn.close()

        return jsonify({"message": "Dados recebidos com sucesso"})

    user_almox = int(session['user_id'])

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor()

    cur.execute(
        """ SELECT  t1.codigo,
                    t1.descricao, 
                    t1.familia, 
                    COALESCE(SUM(t2.contagem), 0) AS total_contagem
            FROM inventario.base_inventario_2023 AS t1
            LEFT JOIN inventario.registros AS t2 ON t2.codigo = t1.codigo 
            WHERE t1.familia = {}
            GROUP BY t1.codigo, t1.descricao, t1.familia;
        """.format(user_almox))

    dados = cur.fetchall()

    return render_template('inventario.html', dados=dados)


@app.route('/logout')
@login_required
def logout():
    
    session.clear() 
    
    return redirect(url_for('login'))


@app.route('/modal', methods=['POST'])
@login_required
def modal():

    data = request.get_json()

    codigo = data['codigo']
    quantidade = data['quantidade']

    print(codigo, quantidade)

    return 'salvo com sucesso'


if __name__ == '__main__':
    app.run()
