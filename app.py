from flask import Flask, flash, render_template, redirect, url_for, request, session, flash, make_response, Response
from flask import render_template_string, jsonify, get_flashed_messages
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

        return redirect(url_for('inventario'))
    
    user_almox = int(session['user_id'])

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor()

    cur.execute(
        """ SELECT  t1.codigo,
                    t1.descricao, 
                    t1.familia, 
                    ROUND(COALESCE(SUM(t2.contagem)::numeric, 0), 2) AS total_contagem
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
    descricao = data['descricao']
    quantidade = data['quantidade']
    data_atual = datetime.now()
    familia = int(session['user_id'])
    origem = 'Fora da lista'

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor()

    if codigo:
        cur.execute("SELECT * FROM inventario.base_inventario_2023 WHERE codigo = %s AND familia = %s", (codigo, familia))
        data_verificar = cur.fetchall()
        
        if len(data_verificar) > 0:
            flash('Peça já existe na lista', 'error')

            return redirect(url_for('inventario'))
        
        else:
            # Inserir na base de cadastro de peça para aparecer da próxima vez
            cur.execute("INSERT INTO inventario.base_inventario_2023 (codigo, descricao, familia, origem) VALUES (%s, %s, %s, %s)", (codigo, descricao, familia, origem))

            # Inserir na base de registros
            cur.execute("INSERT INTO inventario.registros (codigo, descricao, familia, contagem, data_hora_atual) VALUES (%s, %s, %s, %s, %s)", (codigo, descricao, familia, quantidade, data_atual))

            # Fazer commit das alterações no banco de dados
            conn.commit()

            # Peça adicionada na lista com sucesso
            flash("Peça adicionada na lista com sucesso", 'sucess')
            
            return redirect(url_for('inventario'))

    else:
        # Inserir na base de cadastro de peça para aparecer da próxima vez
        cur.execute("INSERT INTO inventario.base_inventario_2023 (codigo, descricao, familia, origem) VALUES (%s, %s, %s, %s)", (codigo, descricao, familia, origem))

        # Inserir na base de registros
        cur.execute("INSERT INTO inventario.registros (codigo, descricao, familia, contagem, data_hora_atual) VALUES (%s, %s, %s, %s, %s)", (codigo, descricao, familia, quantidade, data_atual))

        # Fazer commit das alterações no banco de dados
        conn.commit()
        conn.close()

        # Peça adicionada na lista com sucesso
        flash("Peça adicionada na lista com sucesso", 'sucess')
        
        return redirect(url_for('inventario'))



@app.route('/pecas-fora-da-lista', methods=['GET'])
@login_required
def pecas_fora_da_lista():
    
    user_almox = int(session['user_id'])

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor()

    cur.execute(
        """ SELECT *
            FROM inventario.peca_fora_lista
            WHERE familia = {}
        """.format(user_almox))

    dados = cur.fetchall()

    return render_template('pecas-fora-da-lista.html', dados=dados)


if __name__ == '__main__':
    app.run()
