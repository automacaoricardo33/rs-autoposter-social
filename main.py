# main.py (Final com CRUD, Múltiplos RSS e Hashtags Manuais)
import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, abort
from werkzeug.utils import secure_filename
from database import criar_banco_de_dados

# --- CONFIGURAÇÃO INICIAL ---
criar_banco_de_dados()
app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def get_db_connection():
    conn = sqlite3.connect('automacao.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_cliente(cliente_id):
    conn = get_db_connection()
    cliente = conn.execute('SELECT * FROM clientes WHERE id = ?', (cliente_id,)).fetchone()
    conn.close()
    if cliente is None:
        abort(404)
    return cliente

@app.route('/')
def index():
    conn = get_db_connection()
    clientes_db = conn.execute('SELECT * FROM clientes ORDER BY nome_cliente').fetchall()
    clientes_com_feeds = []
    for cliente in clientes_db:
        cliente_dict = dict(cliente)
        feeds = conn.execute('SELECT url FROM rss_feeds WHERE cliente_id = ?', (cliente['id'],)).fetchall()
        cliente_dict['feeds'] = feeds
        clientes_com_feeds.append(cliente_dict)
    conn.close()
    return render_template('index.html', clientes=clientes_com_feeds)

@app.route('/adicionar', methods=('GET', 'POST'))
def adicionar():
    if request.method == 'POST':
        # Coleta todos os dados, incluindo o novo campo de hashtags
        nome_cliente = request.form['nome_cliente']
        ativo = 1 if 'ativo' in request.form else 0
        layout_imagem = request.form['layout_imagem']
        hashtags_fixas = request.form['hashtags_fixas']
        # ... (coleta de todos os outros campos)
        cor_fundo_geral = request.form['cor_fundo_geral']
        cor_caixa_titulo = request.form['cor_caixa_titulo']
        cor_faixa_categoria = request.form['cor_faixa_categoria']
        cor_texto_titulo = request.form['cor_texto_titulo']
        cor_texto_categoria = request.form['cor_texto_categoria']
        meta_api_token = request.form['meta_api_token']
        instagram_id = request.form['instagram_id']
        facebook_page_id = request.form['facebook_page_id']
        
        paths = {'logo': None, 'fonte_titulo': None, 'fonte_categoria': None}
        for tipo in ['logo', 'fonte_titulo', 'fonte_categoria']:
            if tipo in request.files and request.files[tipo].filename != '':
                arquivo = request.files[tipo]
                nome_seguro = secure_filename(arquivo.filename)
                caminho_salvar = os.path.join(app.config['UPLOAD_FOLDER'], nome_seguro)
                arquivo.save(caminho_salvar)
                paths[tipo] = caminho_salvar
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO clientes (nome_cliente, ativo, layout_imagem, hashtags_fixas, logo_path, fonte_titulo_path, 
                                  fonte_categoria_path, cor_fundo_geral, cor_caixa_titulo, cor_faixa_categoria, 
                                  cor_texto_titulo, cor_texto_categoria, meta_api_token, instagram_id, facebook_page_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nome_cliente, ativo, layout_imagem, hashtags_fixas, paths['logo'], paths['fonte_titulo'], 
              paths['fonte_categoria'], cor_fundo_geral, cor_caixa_titulo, cor_faixa_categoria, 
              cor_texto_titulo, cor_texto_categoria, meta_api_token, instagram_id, facebook_page_id))
        
        novo_cliente_id = cursor.lastrowid

        rss_urls_texto = request.form['rss_urls']
        urls = [url.strip() for url in rss_urls_texto.splitlines() if url.strip()]
        for url in urls:
            conn.execute('INSERT INTO rss_feeds (cliente_id, url) VALUES (?, ?)', (novo_cliente_id, url))

        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    return render_template('adicionar_cliente.html')

@app.route('/editar/<int:id>', methods=('GET', 'POST'))
def editar(id):
    cliente = get_cliente(id)
    conn = get_db_connection()
    if request.method == 'POST':
        # Lógica de update com o campo de hashtags
        nome_cliente = request.form['nome_cliente']
        ativo = 1 if 'ativo' in request.form else 0
        layout_imagem = request.form['layout_imagem']
        hashtags_fixas = request.form['hashtags_fixas']
        # ... (coleta dos outros campos)
        cor_fundo_geral = request.form['cor_fundo_geral']
        cor_caixa_titulo = request.form['cor_caixa_titulo']
        cor_faixa_categoria = request.form['cor_faixa_categoria']
        cor_texto_titulo = request.form['cor_texto_titulo']
        cor_texto_categoria = request.form['cor_texto_categoria']
        meta_api_token = request.form['meta_api_token']
        instagram_id = request.form['instagram_id']
        facebook_page_id = request.form['facebook_page_id']

        paths = {'logo': cliente['logo_path'], 'fonte_titulo': cliente['fonte_titulo_path'], 'fonte_categoria': cliente['fonte_categoria_path']}
        for tipo in ['logo', 'fonte_titulo', 'fonte_categoria']:
            if tipo in request.files and request.files[tipo].filename != '':
                arquivo = request.files[tipo]
                nome_seguro = secure_filename(arquivo.filename)
                caminho_salvar = os.path.join(app.config['UPLOAD_FOLDER'], nome_seguro)
                arquivo.save(caminho_salvar)
                paths[tipo] = caminho_salvar

        conn.execute('''
            UPDATE clientes SET
                nome_cliente = ?, ativo = ?, layout_imagem = ?, hashtags_fixas = ?, logo_path = ?, 
                fonte_titulo_path = ?, fonte_categoria_path = ?, cor_fundo_geral = ?, cor_caixa_titulo = ?, 
                cor_faixa_categoria = ?, cor_texto_titulo = ?, cor_texto_categoria = ?, meta_api_token = ?, 
                instagram_id = ?, facebook_page_id = ?
            WHERE id = ?
        ''', (nome_cliente, ativo, layout_imagem, hashtags_fixas, paths['logo'], paths['fonte_titulo'],
              paths['fonte_categoria'], cor_fundo_geral, cor_caixa_titulo, cor_faixa_categoria,
              cor_texto_titulo, cor_texto_categoria, meta_api_token, instagram_id,
              facebook_page_id, id))

        conn.execute('DELETE FROM rss_feeds WHERE cliente_id = ?', (id,))
        rss_urls_texto = request.form['rss_urls']
        urls = [url.strip() for url in rss_urls_texto.splitlines() if url.strip()]
        for url in urls:
            conn.execute('INSERT INTO rss_feeds (cliente_id, url) VALUES (?, ?)', (id, url))

        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    feeds_db = conn.execute('SELECT url FROM rss_feeds WHERE cliente_id = ?', (id,)).fetchall()
    conn.close()
    rss_urls_texto = "\n".join([feed['url'] for feed in feeds_db])
    
    return render_template('editar_cliente.html', cliente=cliente, rss_urls_texto=rss_urls_texto)

@app.route('/excluir/<int:id>', methods=('POST', 'GET'))
def excluir(id):
    get_cliente(id)
    conn = get_db_connection()
    conn.execute('DELETE FROM clientes WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)