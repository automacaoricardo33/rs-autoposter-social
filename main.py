# main.py (Versão Final Completa)
import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify
from werkzeug.utils import secure_filename
from database import criar_banco_de_dados

# Importamos as bibliotecas da automação
import feedparser
import requests
import io
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageOps
from datetime import datetime
from time import mktime
from google_drive import upload_para_google_drive

# --- CONFIGURAÇÃO INICIAL ---
criar_banco_de_dados()
app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- CÓDIGO DA AUTOMAÇÃO ---

ASSINATURA = "Desenvolvido por: Studio RS Ilhabela - +55 12 99627-3989"
IMG_WIDTH, IMG_HEIGHT = 1080, 1080

def get_db_connection():
    """Cria uma conexão com o banco de dados. Reusada por várias funções."""
    conn = sqlite3.connect('automacao.db')
    conn.row_factory = sqlite3.Row
    return conn

def marcar_como_publicado(conn, cliente_id, link_noticia):
    conn.execute('INSERT INTO posts_publicados (cliente_id, link_noticia) VALUES (?, ?)', (cliente_id, link_noticia))
    conn.commit()

def buscar_noticias_novas(conn, cliente):
    print(f"\nBuscando notícias para: {cliente['nome_cliente']}")
    feeds_db = conn.execute('SELECT url FROM rss_feeds WHERE cliente_id = ?', (cliente['id'],)).fetchall()
    urls_feeds = [feed['url'] for feed in feeds_db]
    posts_publicados_db = conn.execute('SELECT link_noticia FROM posts_publicados WHERE cliente_id = ?', (cliente['id'],)).fetchall()
    links_publicados = {post['link_noticia'] for post in posts_publicados_db}
    novas_noticias = []
    for url in urls_feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if entry.link not in links_publicados:
                    if hasattr(entry, 'published_parsed'):
                        entry.published_date = datetime.fromtimestamp(mktime(entry.published_parsed))
                    else:
                        entry.published_date = datetime.now()
                    novas_noticias.append(entry)
        except Exception as e:
            print(f"⚠️ Erro ao processar o feed {url}: {e}")
    novas_noticias.sort(key=lambda x: x.published_date, reverse=True)
    return novas_noticias

def gerar_legenda(noticia, cliente):
    titulo = noticia.title.upper()
    resumo = ""
    if hasattr(noticia, 'summary'):
        from bs4 import BeautifulSoup
        resumo_limpo = BeautifulSoup(noticia.summary, 'html.parser').get_text(strip=True)
        resumo = textwrap.shorten(resumo_limpo, width=200, placeholder="...")
    fonte = f"Fonte: {cliente['nome_cliente']}"
    hashtags = []
    nome_cliente_sem_espaco = "".join(cliente['nome_cliente'].split()).lower()
    hashtags.append(f"#{nome_cliente_sem_espaco}")
    if cliente['hashtags_fixas']:
        tags_fixas = cliente['hashtags_fixas'].split()
        hashtags.extend([f"#{tag.strip()}" for tag in tags_fixas])
    legenda = f"{titulo}\n\n{resumo}\n\nLeia a matéria completa em nosso site.\n\n{fonte}\n\n{' '.join(hashtags)}"
    return legenda

def publicar_no_instagram(url_imagem, legenda, cliente):
    print("📤 Publicando no Instagram...")
    token = cliente['meta_api_token']
    insta_id = cliente['instagram_id']
    if not all([token, insta_id]):
        print("⚠️ Credenciais do Instagram ausentes.")
        return False
    try:
        url_container = f"https://graph.facebook.com/v19.0/{insta_id}/media"
        params_container = {'image_url': url_imagem, 'caption': legenda, 'access_token': token}
        r_container = requests.post(url_container, params=params_container); r_container.raise_for_status()
        id_criacao = r_container.json()['id']
        url_publicacao = f"https://graph.facebook.com/v19.0/{insta_id}/media_publish"
        params_publicacao = {'creation_id': id_criacao, 'access_token': token}
        r_publish = requests.post(url_publicacao, params=params_publicacao); r_publish.raise_for_status()
        print("✅ Post publicado no Instagram!")
        return True
    except Exception as e:
        print(f"❌ Erro no Instagram: {e}")
        return False

def publicar_no_facebook(url_imagem, legenda, cliente):
    print("📤 Publicando no Facebook...")
    token = cliente['meta_api_token']
    page_id = cliente['facebook_page_id']
    if not all([token, page_id]):
        print("⚠️ Credenciais do Facebook ausentes.")
        return False
    try:
        url_post_foto = f"https://graph.facebook.com/v19.0/{page_id}/photos"
        params = {'url': url_imagem, 'message': legenda, 'access_token': token}
        r = requests.post(url_post_foto, params=params); r.raise_for_status()
        print("✅ Post publicado no Facebook!")
        return True
    except Exception as e:
        print(f"❌ Erro no Facebook: {e}")
        return False

def criar_imagem_post(noticia, cliente):
    print("🎨 Criando imagem do post...")
    titulo = noticia.title.upper()
    categoria = (noticia.tags[0].term if hasattr(noticia, 'tags') and noticia.tags else "").upper()
    url_imagem_noticia = None
    if 'links' in noticia:
        for link in noticia.links:
            if 'type' in link and link.type.startswith('image/'):
                url_imagem_noticia = link.href
                break
    if not url_imagem_noticia:
        print("⚠️ Nenhuma imagem encontrada no post RSS.")
        return None
    cor_fundo = cliente['cor_fundo_geral'] or '#051d40'
    fundo = Image.new('RGBA', (IMG_WIDTH, IMG_HEIGHT), cor_fundo)
    draw = ImageDraw.Draw(fundo)
    try:
        response_img = requests.get(url_imagem_noticia, stream=True); response_img.raise_for_status()
        imagem_noticia = Image.open(io.BytesIO(response_img.content)).convert("RGBA")
        if cliente['layout_imagem'] == 'fundo_completo':
            imagem_noticia = ImageOps.fit(imagem_noticia, (IMG_WIDTH, IMG_HEIGHT), Image.Resampling.LANCZOS)
            fundo.paste(imagem_noticia, (0, 0))
            overlay = Image.new('RGBA', (IMG_WIDTH, IMG_HEIGHT), (0,0,0,128))
            fundo = Image.alpha_composite(fundo, overlay)
            draw = ImageDraw.Draw(fundo)
        else:
            img_w, img_h = 980, 551
            imagem_noticia_resized = imagem_noticia.resize((img_w, img_h))
            pos_img_x = (IMG_WIDTH - img_w) // 2
            fundo.paste(imagem_noticia_resized, (pos_img_x, 50))
    except Exception as e:
        print(f"❌ Erro ao processar imagem da notícia: {e}")
        return None
    if cliente['logo_path']:
        try:
            logo = Image.open(cliente['logo_path']).convert("RGBA")
            logo.thumbnail((200, 100)); fundo.paste(logo, (70, 70), logo)
        except Exception as e: print(f"⚠️ Erro no logo: {e}")
    if categoria and cliente['fonte_categoria_path']:
        try:
            fonte_cat = ImageFont.truetype(cliente['fonte_categoria_path'], 40)
            pos_y_cat = 650
            if cliente['cor_faixa_categoria']: draw.rectangle([(50, pos_y_cat - 25), (IMG_WIDTH - 50, pos_y_cat + 25)], fill=cliente['cor_faixa_categoria'])
            draw.text((IMG_WIDTH / 2, pos_y_cat), categoria, font=fonte_cat, fill=cliente['cor_texto_categoria'] or '#FFD700', anchor="mm", align="center")
        except Exception as e: print(f"⚠️ Erro na categoria: {e}")
    try:
        fonte_titulo = ImageFont.truetype(cliente['fonte_titulo_path'], 70)
        linhas_texto = textwrap.wrap(titulo, width=28)
        texto_junto = "\n".join(linhas_texto)
        pos_y_titulo = 800
        if cliente['cor_caixa_titulo']: draw.rectangle([(50, pos_y_titulo - 100), (IMG_WIDTH - 50, pos_y_titulo + 100)], fill=cliente['cor_caixa_titulo'])
        draw.text((IMG_WIDTH / 2, pos_y_titulo), texto_junto, font=fonte_titulo, fill=cliente['cor_texto_titulo'] or '#FFFFFF', anchor="mm", align="center")
    except Exception as e:
        print(f"❌ Erro no título: {e}"); return None
    try:
        fonte_assinatura = ImageFont.truetype("Raleway-VariableFont_wght.ttf", 20)
        draw.text((IMG_WIDTH / 2, IMG_HEIGHT - 15), ASSINATURA, font=fonte_assinatura, fill=(200, 200, 200, 255), anchor="ms", align="center")
    except Exception: pass
    buffer_saida = io.BytesIO()
    fundo.convert("RGB").save(buffer_saida, format='JPEG', quality=90)
    print("✅ Imagem criada!"); return buffer_saida.getvalue()

def rodar_automacao_completa():
    log_execucao = []
    conn = get_db_connection()
    clientes_ativos = conn.execute('SELECT * FROM clientes WHERE ativo = 1').fetchall()
    if not clientes_ativos:
        log_execucao.append("Nenhum cliente ativo encontrado.")
        return log_execucao
    for cliente in clientes_ativos:
        novas_noticias = buscar_noticias_novas(conn, cliente)
        if not novas_noticias:
            log_execucao.append(f"Nenhuma notícia nova para {cliente['nome_cliente']}.")
            continue
        noticia_para_postar = novas_noticias[0]
        log_execucao.append(f"✅ Notícia encontrada para {cliente['nome_cliente']}: '{noticia_para_postar.title}'")
        imagem_bytes = criar_imagem_post(noticia_para_postar, cliente)
        if not imagem_bytes: continue
        nome_arquivo = f"post_{cliente['id']}_{int(datetime.now().timestamp())}.jpg"
        link_imagem_publica = upload_para_google_drive(imagem_bytes, nome_arquivo)
        if not link_imagem_publica: continue
        legenda = gerar_legenda(noticia_para_postar, cliente)
        publicar_no_instagram(link_imagem_publica, legenda, cliente)
        publicar_no_facebook(link_imagem_publica, legenda, cliente)
        marcar_como_publicado(conn, cliente['id'], noticia_para_postar.link)
        log_execucao.append(f"--- Processo para {cliente['nome_cliente']} concluído. ---")
    conn.close()
    return log_execucao

# --- ROTA SECRETA PARA AGENDADOR ---
@app.route('/rodar-automacao-agora')
def rota_automacao():
    print("🚀 Disparando automação via rota secreta...")
    logs = rodar_automacao_completa()
    print("🏁 Automação finalizada.")
    return jsonify(logs)

# --- ROTAS DO PAINEL DE CONTROLE (CRUD) ---
def get_cliente(cliente_id):
    conn = get_db_connection()
    cliente = conn.execute('SELECT * FROM clientes WHERE id = ?', (cliente_id,)).fetchone()
    conn.close()
    if cliente is None: abort(404)
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
        nome_cliente = request.form['nome_cliente']
        ativo = 1 if 'ativo' in request.form else 0
        layout_imagem = request.form['layout_imagem']
        hashtags_fixas = request.form['hashtags_fixas']
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
        cursor.execute('''INSERT INTO clientes (nome_cliente, ativo, layout_imagem, hashtags_fixas, logo_path, fonte_titulo_path, fonte_categoria_path, cor_fundo_geral, cor_caixa_titulo, cor_faixa_categoria, cor_texto_titulo, cor_texto_categoria, meta_api_token, instagram_id, facebook_page_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (nome_cliente, ativo, layout_imagem, hashtags_fixas, paths['logo'], paths['fonte_titulo'], paths['fonte_categoria'], cor_fundo_geral, cor_caixa_titulo, cor_faixa_categoria, cor_texto_titulo, cor_texto_categoria, meta_api_token, instagram_id, facebook_page_id))
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
        nome_cliente = request.form['nome_cliente']
        ativo = 1 if 'ativo' in request.form else 0
        layout_imagem = request.form['layout_imagem']
        hashtags_fixas = request.form['hashtags_fixas']
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
        conn.execute('''UPDATE clientes SET nome_cliente = ?, ativo = ?, layout_imagem = ?, hashtags_fixas = ?, logo_path = ?, fonte_titulo_path = ?, fonte_categoria_path = ?, cor_fundo_geral = ?, cor_caixa_titulo = ?, cor_faixa_categoria = ?, cor_texto_titulo = ?, cor_texto_categoria = ?, meta_api_token = ?, instagram_id = ?, facebook_page_id = ? WHERE id = ?''', (nome_cliente, ativo, layout_imagem, hashtags_fixas, paths['logo'], paths['fonte_titulo'], paths['fonte_categoria'], cor_fundo_geral, cor_caixa_titulo, cor_faixa_categoria, cor_texto_titulo, cor_texto_categoria, meta_api_token, instagram_id, facebook_page_id, id))
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
