# main.py (Versão FINAL com design dinâmico e CRUD completo)
import os
import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify
from dotenv import load_dotenv
from database import criar_banco_de_dados
import feedparser
import requests
import io
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageOps
from datetime import datetime
from time import mktime
from bs4 import BeautifulSoup
import time

load_dotenv()
app = Flask(__name__)
DATABASE_URL = os.getenv('DATABASE_URL')
UPLOADS_PATH = os.path.join('static', 'uploads')

if DATABASE_URL:
    criar_banco_de_dados()

ASSINATURA = "Desenvolvido por: Studio RS Ilhabela - +55 12 99627-3989"
IMG_WIDTH, IMG_HEIGHT = 1080, 1080
LIMITE_DE_POSTS_POR_CICLO = 1

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def marcar_como_publicado(conn, cliente_id, link_noticia):
    cur = conn.cursor()
    cur.execute('INSERT INTO posts_publicados (cliente_id, link_noticia) VALUES (%s, %s)', (cliente_id, link_noticia))
    conn.commit()
    cur.close()

def buscar_noticias_novas(conn, cliente):
    print(f"\nBuscando notícias para: {cliente['nome_cliente']}")
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT url FROM rss_feeds WHERE cliente_id = %s', (cliente['id'],))
    feeds_db = cur.fetchall()
    urls_feeds = [feed['url'] for feed in feeds_db]
    cur.execute('SELECT link_noticia FROM posts_publicados WHERE cliente_id = %s', (cliente['id'],))
    posts_publicados_db = cur.fetchall()
    links_publicados = {post['link_noticia'] for post in posts_publicados_db}
    cur.close()
    novas_noticias = []
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
    for url in urls_feeds:
        try:
            feed = feedparser.parse(url, agent=user_agent)
            if feed.bozo: print(f"⚠️ Aviso: O feed {url} pode estar mal formatado. Exceção: {feed.bozo_exception}")
            for entry in feed.entries:
                if entry.link not in links_publicados:
                    entry.published_date = datetime.fromtimestamp(mktime(entry.published_parsed)) if hasattr(entry, 'published_parsed') else datetime.now()
                    novas_noticias.append(entry)
        except Exception as e: print(f"⚠️ Erro ao processar o feed {url}: {e}")
    novas_noticias.sort(key=lambda x: x.published_date, reverse=True)
    return novas_noticias

def gerar_legenda(noticia, cliente):
    titulo = noticia.title.upper()
    resumo = ""
    if hasattr(noticia, 'summary'):
        resumo_limpo = BeautifulSoup(noticia.summary, 'html.parser').get_text(strip=True)
        resumo = textwrap.shorten(resumo_limpo, width=200, placeholder="...")
    fonte = f"Fonte: {cliente['nome_cliente']}"
    hashtags = []
    nome_cliente_sem_espaco = "".join(cliente['nome_cliente'].split()).lower()
    hashtags.append(f"#{nome_cliente_sem_espaco}")
    if cliente['hashtags_fixas']:
        tags_fixas = cliente['hashtags_fixas'].split()
        hashtags.extend([f"#{tag.strip()}" for tag in tags_fixas])
    return f"{titulo}\n\n{resumo}\n\nLeia a matéria completa em nosso site.\n\n{fonte}\n\n{' '.join(hashtags)}"

def criar_imagem_post(noticia, cliente):
    print("🎨 Criando imagem com design inteligente...")
    titulo = noticia.title.upper()
    categoria = (cliente['texto_categoria_fixo'] or (noticia.tags[0].term if hasattr(noticia, 'tags') and noticia.tags else "")).upper()
    url_imagem_noticia = None
    if hasattr(noticia, 'links'):
        for link in noticia.links:
            if link.get('type', '').startswith('image/'): url_imagem_noticia = link.href; break
    if not url_imagem_noticia and hasattr(noticia, 'media_content'):
        for media in noticia.media_content:
            if media.get('type', '').startswith('image/'): url_imagem_noticia = media.get('url'); break
    html_content = noticia.summary if hasattr(noticia, 'summary') else ""
    if not url_imagem_noticia and html_content:
        soup = BeautifulSoup(html_content, 'html.parser')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'): url_imagem_noticia = img_tag['src']
    if not url_imagem_noticia: return (False, "Nenhuma imagem encontrada no post RSS.")
    print(f"🖼️ Imagem encontrada: {url_imagem_noticia}")
    cor_fundo = cliente['cor_fundo_geral'] or '#000000'
    fundo = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), cor_fundo)
    draw = ImageDraw.Draw(fundo)
    try:
        response_img = requests.get(url_imagem_noticia, stream=True, headers={'User-Agent': 'Mozilla/5.0'}); response_img.raise_for_status()
        imagem_noticia = Image.open(io.BytesIO(response_img.content))
        img_w, img_h = 1080, 750
        imagem_noticia = ImageOps.fit(imagem_noticia, (img_w, img_h), Image.Resampling.LANCZOS)
        fundo.paste(imagem_noticia, (0, 0))
    except Exception as e:
        return (False, f"Erro ao processar imagem da notícia: {e}")
    tem_faixa_categoria = categoria and (cliente['cor_faixa_categoria'] not in [None, '', '#000000'])
    cor_rodape = cliente['cor_caixa_titulo'] or '#051d40'
    if tem_faixa_categoria:
        cor_faixa = cliente['cor_faixa_categoria']
        draw.rectangle([(0, 650), (1080, 750)], fill=cor_faixa)
        if cliente['fonte_categoria_path']:
            try:
                caminho_fonte_cat = os.path.join(UPLOADS_PATH, cliente['fonte_categoria_path'])
                fonte_cat = ImageFont.truetype(caminho_fonte_cat, 50)
                draw.text((540, 700), categoria, font=fonte_cat, fill=cliente['cor_texto_categoria'] or "#FFFFFF", anchor="mm", align="center")
            except Exception as e: print(f"⚠️ Erro fonte categoria: {e}")
        draw.rectangle([(0, 750), (1080, 980)], fill=cor_rodape)
        if cliente['logo_path']:
            try:
                caminho_logo = os.path.join(UPLOADS_PATH, cliente['logo_path'])
                logo = Image.open(caminho_logo).convert("RGBA")
                logo.thumbnail((250, 150)); fundo.paste(logo, (40, 40), logo)
            except Exception as e: print(f"⚠️ Erro no logo: {e}")
    else:
        draw.rectangle([(0, 680), (1080, 1080)], fill=cor_rodape)
        if cliente['logo_path']:
            try:
                caminho_logo = os.path.join(UPLOADS_PATH, cliente['logo_path'])
                logo = Image.open(caminho_logo).convert("RGBA")
                logo.thumbnail((300, 300))
                pos_x_logo = (IMG_WIDTH - logo.width) // 2
                pos_y_logo = 680 - (logo.height // 2)
                fundo.paste(logo, (pos_x_logo, pos_y_logo), logo)
            except Exception as e: print(f"⚠️ Erro no logo: {e}")
    try:
        caminho_fonte_titulo = os.path.join(UPLOADS_PATH, cliente['fonte_titulo_path'])
        fonte_titulo = ImageFont.truetype(caminho_fonte_titulo, 75)
        cor_texto_titulo = cliente['cor_texto_titulo'] or '#FFFFFF'
        linhas_texto = textwrap.wrap(titulo, width=28)
        texto_junto = "\n".join(linhas_texto)
        draw.text((540, 865), texto_junto, font=fonte_titulo, fill=cor_texto_titulo, anchor="mm", align="center")
    except Exception as e:
        return (False, f"Erro na fonte/texto do título: {e}")
    if cliente['handle_social']:
        try:
            texto_cta = f"@{cliente['handle_social'].upper()}"
            fonte_cta = ImageFont.truetype("Anton-Regular.ttf", 45)
            cor_cta = '#000000' if cor_rodape == '#FFFFFF' else '#FFFFFF'
            draw.text((540, 1030), texto_cta, font=fonte_cta, fill=cor_cta, anchor="ms", align="center")
        except Exception as e: print(f"⚠️ Erro no handle social: {e}")
    try:
        fonte_assinatura = ImageFont.truetype("Raleway-VariableFont_wght.ttf", 20)
        draw.text((IMG_WIDTH / 2, IMG_HEIGHT - 15), ASSINATURA, font=fonte_assinatura, fill=(100, 100, 100, 255), anchor="ms", align="center")
    except Exception: pass
    buffer_saida = io.BytesIO()
    fundo.save(buffer_saida, format='JPEG', quality=90)
    print("✅ Imagem com novo design criada!"); return (True, buffer_saida.getvalue())

def publicar_nas_redes(imagem_bytes, legenda, cliente):
    print("✅ [SIMULAÇÃO] Publicando no Instagram e Facebook...")
    print(f"Legenda: {legenda[:100]}...")
    return True

def rodar_automacao_completa():
    log_execucao = []
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM clientes WHERE ativo = 1')
    clientes_ativos = cur.fetchall()
    cur.close()
    if not clientes_ativos:
        log_execucao.append("Nenhum cliente ativo encontrado.")
        conn.close()
        return log_execucao
    for cliente in clientes_ativos:
        novas_noticias = buscar_noticias_novas(conn, cliente)
        if not novas_noticias:
            log_execucao.append(f"Nenhuma notícia nova para {cliente['nome_cliente']}.")
            continue
        log_execucao.append(f"Encontradas {len(novas_noticias)} notícias novas. Processando até {LIMITE_DE_POSTS_POR_CICLO}.")
        posts_neste_ciclo = 0
        for noticia_para_postar in novas_noticias:
            if posts_neste_ciclo >= LIMITE_DE_POSTS_POR_CICLO:
                log_execucao.append(f"Limite de {LIMITE_DE_POSTS_POR_CICLO} posts atingido.")
                break
            log_execucao.append(f"✅ Processando: '{noticia_para_postar.title}'")
            sucesso_img, resultado_img = criar_imagem_post(noticia_para_postar, cliente)
            if not sucesso_img:
                log_execucao.append(f"❌ Falha na imagem: {resultado_img}"); continue
            imagem_bytes = resultado_img
            legenda = gerar_legenda(noticia_para_postar, cliente)
            publicar_nas_redes(imagem_bytes, legenda, cliente)
            marcar_como_publicado(conn, cliente['id'], noticia_para_postar.link)
            log_execucao.append(f"--- Post para '{noticia_para_postar.title}' concluído (em modo simulação). ---")
            posts_neste_ciclo += 1
    conn.close()
    return log_execucao

@app.route('/rodar-automacao-agora')
def rota_automacao():
    print("🚀 Disparando automação via rota secreta...")
    logs = rodar_automacao_completa()
    print("🏁 Automação finalizada.")
    return jsonify({"status": "sucesso", "total_de_acoes": len(logs)})

def get_cliente(cliente_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM clientes WHERE id = %s', (cliente_id,))
    cliente = cur.fetchone()
    cur.close()
    conn.close()
    if cliente is None: abort(404)
    return cliente

def get_available_assets():
    imagens = []
    fontes = []
    if os.path.exists(UPLOADS_PATH):
        for f in os.listdir(UPLOADS_PATH):
            if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                imagens.append(f)
            elif f.lower().endswith(('.ttf', '.otf')):
                fontes.append(f)
    return sorted(imagens), sorted(fontes)

@app.route('/')
def index():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT * FROM clientes ORDER BY nome_cliente')
    clientes_db = cur.fetchall()
    clientes_com_feeds = []
    for cliente in clientes_db:
        cliente_dict = dict(cliente)
        cur.execute('SELECT url FROM rss_feeds WHERE cliente_id = %s', (cliente['id'],))
        feeds = cur.fetchall()
        cliente_dict['feeds'] = feeds
        clientes_com_feeds.append(cliente_dict)
    cur.close()
    conn.close()
    return render_template('index.html', clientes=clientes_com_feeds)

@app.route('/adicionar', methods=('GET', 'POST'))
def adicionar():
    if request.method == 'POST':
        nome_cliente = request.form['nome_cliente']
        ativo = 1 if 'ativo' in request.form else 0
        logo_path = request.form.get('logo_path')
        fonte_titulo_path = request.form.get('fonte_titulo_path')
        fonte_categoria_path = request.form.get('fonte_categoria_path')
        cor_fundo_geral = request.form['cor_fundo_geral']
        cor_faixa_categoria = request.form['cor_faixa_categoria']
        cor_caixa_titulo = request.form['cor_caixa_titulo']
        cor_texto_titulo = request.form['cor_texto_titulo']
        cor_texto_categoria = request.form['cor_texto_categoria']
        meta_api_token = request.form['meta_api_token']
        instagram_id = request.form['instagram_id']
        facebook_page_id = request.form['facebook_page_id']
        hashtags_fixas = request.form['hashtags_fixas']
        handle_social = request.form['handle_social']
        texto_categoria_fixo = request.form['texto_categoria_fixo']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO clientes (nome_cliente, ativo, logo_path, fonte_titulo_path, fonte_categoria_path, cor_fundo_geral, cor_faixa_categoria, cor_caixa_titulo, cor_texto_titulo, cor_texto_categoria, meta_api_token, instagram_id, facebook_page_id, hashtags_fixas, handle_social, texto_categoria_fixo) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        ''', (nome_cliente, ativo, logo_path, fonte_titulo_path, fonte_categoria_path, cor_fundo_geral, cor_faixa_categoria, cor_caixa_titulo, cor_texto_titulo, cor_texto_categoria, meta_api_token, instagram_id, facebook_page_id, hashtags_fixas, handle_social, texto_categoria_fixo))
        novo_cliente_id = cur.fetchone()[0]
        rss_urls_texto = request.form['rss_urls']
        urls = [url.strip() for url in rss_urls_texto.splitlines() if url.strip()]
        for url in urls:
            cur.execute('INSERT INTO rss_feeds (cliente_id, url) VALUES (%s, %s)', (novo_cliente_id, url))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    imagens, fontes = get_available_assets()
    return render_template('adicionar_cliente.html', imagens=imagens, fontes=fontes)

@app.route('/editar/<int:id>', methods=('GET', 'POST'))
def editar(id):
    cliente = get_cliente(id)
    if request.method == 'POST':
        nome_cliente = request.form['nome_cliente']
        ativo = 1 if 'ativo' in request.form else 0
        logo_path = request.form.get('logo_path')
        fonte_titulo_path = request.form.get('fonte_titulo_path')
        fonte_categoria_path = request.form.get('fonte_categoria_path')
        cor_fundo_geral = request.form['cor_fundo_geral']
        cor_faixa_categoria = request.form['cor_faixa_categoria']
        cor_caixa_titulo = request.form['cor_caixa_titulo']
        cor_texto_titulo = request.form['cor_texto_titulo']
        cor_texto_categoria = request.form['cor_texto_categoria']
        meta_api_token = request.form['meta_api_token']
        instagram_id = request.form['instagram_id']
        facebook_page_id = request.form['facebook_page_id']
        hashtags_fixas = request.form['hashtags_fixas']
        handle_social = request.form['handle_social']
        texto_categoria_fixo = request.form['texto_categoria_fixo']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            UPDATE clientes SET 
                nome_cliente = %s, ativo = %s, logo_path = %s, fonte_titulo_path = %s, fonte_categoria_path = %s,
                cor_fundo_geral = %s, cor_faixa_categoria = %s, cor_caixa_titulo = %s, cor_texto_titulo = %s,
                cor_texto_categoria = %s, meta_api_token = %s, instagram_id = %s, facebook_page_id = %s,
                hashtags_fixas = %s, handle_social = %s, texto_categoria_fixo = %s
            WHERE id = %s
        ''', (nome_cliente, ativo, logo_path, fonte_titulo_path, fonte_categoria_path, cor_fundo_geral, cor_faixa_categoria, cor_caixa_titulo, cor_texto_titulo, cor_texto_categoria, meta_api_token, instagram_id, facebook_page_id, hashtags_fixas, handle_social, texto_categoria_fixo, id))
        cur.execute('DELETE FROM rss_feeds WHERE cliente_id = %s', (id,))
        rss_urls_texto = request.form['rss_urls']
        urls = [url.strip() for url in rss_urls_texto.splitlines() if url.strip()]
        for url in urls:
            cur.execute('INSERT INTO rss_feeds (cliente_id, url) VALUES (%s, %s)', (id, url))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute('SELECT url FROM rss_feeds WHERE cliente_id = %s', (id,))
    feeds_db = cur.fetchall()
    cur.close()
    conn.close()
    rss_urls_texto = "\n".join([feed['url'] for feed in feeds_db])
    imagens, fontes = get_available_assets()
    return render_template('editar_cliente.html', cliente=cliente, rss_urls_texto=rss_urls_texto, imagens=imagens, fontes=fontes)

@app.route('/excluir/<int:id>', methods=('POST', 'GET'))
def excluir(id):
    get_cliente(id)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM clientes WHERE id = %s', (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
