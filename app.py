from flask import Flask, flash, render_template, redirect, url_for, request, session, flash, make_response, Response
from flask import render_template_string, jsonify, get_flashed_messages
import functools

import datetime
from datetime import datetime

import psycopg2  # pip install psycopg2
import psycopg2.extras

import cachetools
from cachetools import Cache

import gspread

import pandas as pd

# flask run -h localhost -p 3000

filename = "service_account.json"

# DB_HOST = "localhost"
DB_HOST = "database-2.cdcogkfzajf0.us-east-1.rds.amazonaws.com"
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "15512332"

app = Flask(__name__)
app.secret_key = 'app_inventario'  # Configure uma chave secreta adequada

cache_recontagem = cachetools.LRUCache(maxsize=128)

def resetar_cache(cache):

    """
    Função para limpar caches
    """

    cache.clear()



def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        return view(**kwargs)

    return wrapped_view


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


@app.route('/', methods=['POST','GET'])
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
        print(contagem)
        print(descricao)
        descricao = descricao.replace("'"," ")
        cur.execute("INSERT INTO inventario.registros (codigo,descricao,familia,contagem, data_hora_atual) VALUES ('{}','{}',{}, {}, '{}')".format(codigo,descricao,familia,contagem,data_atual))

        cur.execute("SELECT sum(contagem) FROM inventario.registros WHERE codigo = '{}' AND familia = '{}' GROUP BY codigo,familia".format(codigo,familia))
        contagem = cur.fetchall()

        contagem = contagem[0][0]

        try:

            cur.execute("SELECT saldo,curva_abc FROM inventario.base_inventario_2023 WHERE codigo = '{}' AND familia = {} AND origem = 'Innovaro'".format(codigo,familia))
                        
            saldo = cur.fetchall()

            saldo_value = saldo[0][0]
            curva_abc = saldo[0][1]

        except:
            saldo = []

        conn.commit()
        
        cur.close()
        conn.close()

        print(saldo)

        if len(saldo) > 0:

            if curva_abc == 'A' and contagem != saldo_value:
                return jsonify(codigo)
            elif curva_abc == 'B' and contagem != saldo_value and (contagem > (saldo_value - (0.1 * saldo_value)) or contagem < (saldo_value + (0.1 * saldo_value))):
                return jsonify(codigo)
            elif curva_abc == 'C' and contagem != saldo_value and (contagem > (saldo_value - (0.2 * saldo_value)) or contagem < (saldo_value + (0.2 * saldo_value))):
                return jsonify(codigo)
            else: 
                print("Não precisa de recontagem")

        else: 
            print("Não precisa de recontagem")

        return redirect(url_for('inventario'))
    
    user_almox = int(session['user_id'])

    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                            password=DB_PASS, host=DB_HOST)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute(
        """ SELECT
                t1.codigo,
                t1.descricao,
                t1.familia,
                CASE 
                    WHEN COALESCE(SUM(t2.recontagem), 0) > 0 THEN ROUND(COALESCE(SUM(t2.recontagem)::numeric, 0), 2)
                    ELSE ROUND(COALESCE(SUM(t2.contagem)::numeric, 0), 2)
                END AS total_contagem
            FROM inventario.base_inventario_2023 AS t1
            LEFT JOIN inventario.registros AS t2 ON t2.codigo = t1.codigo and t2.familia = t1.familia 
            WHERE t1.familia = {}
            GROUP BY t1.codigo, t1.descricao, t1.familia;
        """.format(user_almox))

    dados = cur.fetchall()

    cur.execute(
            """
                SELECT
                    T5.*,
                    T6.data_mais_antiga,
                    CASE
                        WHEN T5.contagem_agrupada != T5.saldo AND T5.recontagem_agrupada IS NULL THEN 'Recontar'
                        ELSE ''
                    END AS necessidade_recontagem
                FROM (
                    SELECT DISTINCT T3.*, T4.nome_almoxarifado
                    FROM (
                        SELECT
                            T1.familia,
                            T1.codigo,
                            T1.descricao,
                            T2.etapa,
                            T2.origem,
                            T2.curva_abc,
                            T2.saldo,
                            T2.custo,
                            T2.custo_medio,
                            ROUND(SUM(T1.contagem)) AS contagem_agrupada,
                            ROUND(SUM(T1.recontagem)) AS recontagem_agrupada,
                            SUM(saldo) as saldo_somado
                        FROM inventario.registros AS T1
                        LEFT JOIN inventario.base_inventario_2023 AS T2
                            ON T1.codigo = T2.codigo AND T1.familia = T2.familia
                        WHERE T1.familia = {}
                        GROUP BY
                            T1.familia,
                            T1.codigo,
                            T1.descricao,
                            T2.etapa,
                            T2.origem,
                            T2.curva_abc,
                            T2.saldo,
                            T2.custo,
                            T2.custo_medio
                    ) AS T3
                    LEFT JOIN inventario.familias AS T4
                        ON T3.familia = T4.id_lista
                ) AS T5
                LEFT JOIN (
                    SELECT codigo, familia, MIN(data_hora_atual) AS data_mais_antiga
                    FROM inventario.registros
                    GROUP BY codigo, familia
                ) AS T6 ON T5.codigo = T6.codigo AND T5.familia = T6.familia
                ORDER BY T6.data_mais_antiga;
                """.format(user_almox))
    
    necessidade_recontagem = cur.fetchall()

    df_dados = pd.DataFrame(dados)
    df_necessidade_recontagem = pd.DataFrame(necessidade_recontagem)

    if len(df_necessidade_recontagem) > 0:
        df_merge = df_dados.merge(df_necessidade_recontagem[['codigo','familia','necessidade_recontagem']], how='left', on=['codigo', 'familia'])
    
        dados = df_merge.values.tolist()
    else:
        dados = df_dados.values.tolist()

    return render_template('inventario.html', dados=dados)

@app.route('/modal_recontagem', methods=['POST'])
@login_required
def modal_recontagem():
        
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER,
                        password=DB_PASS, host=DB_HOST)
    cur = conn.cursor()

    # Obtenha os dados enviados no corpo da solicitação POST
    dados_recebidos = request.get_json()
    print(dados_recebidos)
    
    # Faça o processamento necessário com os dados recebidos
    codigo_recontagem = dados_recebidos.get('codigoRecontagem')
    recontagem = dados_recebidos.get('recontagem')
    familia = int(session['user_id'])
    # Salvar dados na tabela registro

    codigo_recontagem = codigo_recontagem.split()[0]

    cur.execute("SELECT COUNT(*) FROM inventario.registros WHERE codigo = '{}' AND familia = {}".format(codigo_recontagem,familia))

    count_linhas = cur.fetchall()
    print(count_linhas)

    count_linhas = count_linhas[0][0]

    print(count_linhas)

    recontagem = float(recontagem) / count_linhas

    print(recontagem)

    cur.execute("UPDATE inventario.registros SET recontagem = {} WHERE codigo = '{}' AND familia = {}".format(recontagem,codigo_recontagem,familia))

    conn.commit()
    
    cur.close()
    conn.close()

    return redirect(url_for('inventario'))

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
    
    descricao = descricao.replace("'"," ")

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


@cachetools.cached(cache_recontagem)
def tabela_recontagem():

    """
    Função para acessar google sheets via api e
    buscar dados da base de recontagem.
    """

    sheet_id = '1P_9mmPVTVYlQh0EBYBgzadkfNOvWvCUGX536EraZ4HE'
    worksheet1 = 'Base recontagem'

    sa = gspread.service_account(filename)
    sh = sa.open_by_key(sheet_id)

    wks1 = sh.worksheet(worksheet1)

    headers = wks1.row_values(1)

    base = wks1.get()
    base = pd.DataFrame(base)
    # base = base.iloc[:,:23]
    base_carretas = base.set_axis(headers, axis=1)[1:]
    base_carretas['PED_PREVISAOEMISSAODOC'] = pd.to_datetime(base_carretas['PED_PREVISAOEMISSAODOC'], format="%d/%M/%Y", errors='ignore')

    return base_carretas


@app.route("/recontagem")
def recontagem():

    """
    Rota para recontagem de itens
    """

    

    return 'sucess'


if __name__ == '__main__':
    app.run()