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

# --- CONFIGURAÇÃO ---
load_dotenv()
app = Flask(__name__)
DATABASE_URL = os.getenv('DATABASE_URL')
UPLOADS_PATH = os.path.join('static', 'uploads')

if DATABASE_URL:
    criar_banco_de_dados()

ASSINATURA = "Desenvolvido por: Studio RS Ilhabela - +55 12 99627-3989"
IMG_WIDTH, IMG_HEIGHT = 1080, 1080
LIMITE_DE_POSTS_POR_CICLO = 5

# --- FUNÇÕES AUXILIARES ---
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

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
    print("🎨 Criando imagem com design final...")
    titulo = noticia.title.upper()
    categoria = (cliente['texto_categoria_fixo'] or (noticia.tags[0].term if hasattr(noticia, 'tags') and noticia.tags else "")).upper()
    url_imagem_noticia = None
    if hasattr(noticia, 'links'):
        for link in noticia.links:
            if link.get('type','').startswith('image/'): url_imagem_noticia = link.href; break
    if not url_imagem_noticia and hasattr(noticia, 'media_content'):
        for media in noticia.media_content:
            if media.get('type','').startswith('image/'): url_imagem_noticia = media.get('url'); break
    html_content = noticia.summary if hasattr(noticia, 'summary') else ""
    if not url_imagem_noticia and html_content:
        soup = BeautifulSoup(html_content, 'html.parser')
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'): url_imagem_noticia = img_tag['src']
    if not url_imagem_noticia: return (False, "Nenhuma imagem encontrada.")
    print(f"🖼️ Imagem encontrada: {url_imagem_noticia}")
    cor_fundo = cliente['cor_fundo_geral'] or '#FFFFFF'
    fundo = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), cor_fundo)
    draw = ImageDraw.Draw(fundo, 'RGBA')
    try:
        response_img = requests.get(url_imagem_noticia, stream=True, headers={'User-Agent': 'Mozilla/5.0'}); response_img.raise_for_status()
        imagem_noticia = Image.open(io.BytesIO(response_img.content))
        img_w, img_h = 1080, 750
        imagem_noticia = ImageOps.fit(imagem_noticia, (img_w, img_h), Image.Resampling.LANCZOS)
        fundo.paste(imagem_noticia, (0, 0))
    except Exception as e: return (False, f"Erro ao processar imagem: {e}")
    tem_faixa_categoria = categoria and (cliente['cor_faixa_categoria'] not in [None, '', '#000000'])
    cor_caixa_titulo = cliente['cor_caixa_titulo'] or '#051d40'
    cor_borda = cliente['cor_borda_caixa'] or None
    raio = cliente['raio_borda_caixa'] or 0
    box_coords = [40, 780, 1040, 1000]
    if cor_borda:
        draw.rounded_rectangle(box_coords, radius=raio, fill=cor_borda)
        draw.rounded_rectangle([box_coords[0]+5, box_coords[1]+5, box_coords[2]-5, box_coords[3]-5], radius=raio, fill=cor_caixa_titulo)
    else:
        draw.rounded_rectangle(box_coords, radius=raio, fill=cor_caixa_titulo)
    if cliente['logo_path']:
        try:
            caminho_logo = os.path.join(UPLOADS_PATH, cliente['logo_path'])
            logo = Image.open(caminho_logo).convert("RGBA")
            logo_w, logo_h = logo.size
            logo.thumbnail((int(logo_w * 0.85), int(logo_h * 0.85)))
            if tem_faixa_categoria:
                fundo.paste(logo, (40, 40), logo)
            else:
                pos_x = (IMG_WIDTH - logo.width) // 2
                pos_y = 680 - (logo.height // 2)
                fundo.paste(logo, (pos_x, pos_y), logo)
        except Exception as e: print(f"⚠️ Erro no logo: {e}")
    if tem_faixa_categoria:
        draw.rectangle([(0, 680), (1080, 750)], fill=cliente['cor_faixa_categoria'])
        if cliente['fonte_categoria_path']:
            try:
                caminho_fonte = os.path.join(UPLOADS_PATH, cliente['fonte_categoria_path'])
                fonte = ImageFont.truetype(caminho_fonte, 60)
                draw.text((540, 715), categoria, font=fonte, fill=cliente['cor_texto_categoria'] or "#FFFFFF", anchor="mm")
            except Exception as e: print(f"⚠️ Erro na fonte da categoria: {e}")
    try:
        caminho_fonte_titulo = os.path.join(UPLOADS_PATH, cliente['fonte_titulo_path'])
        fonte_titulo = ImageFont.truetype(caminho_fonte_titulo, 50)
        cor_texto_titulo = cliente['cor_texto_titulo'] or '#FFFFFF'
        linhas = textwrap.wrap(titulo, width=30)
        texto_renderizado = "\n".join(linhas)
        draw.text((540, 890), texto_renderizado, font=fonte_titulo, fill=cor_texto_titulo, anchor="mm", align="center")
    except Exception as e: return (False, f"Erro na fonte do título: {e}")
    if cliente['handle_social']:
        try:
            fonte_handle = ImageFont.truetype("Anton-Regular.ttf", 45)
            draw.text((540, 1040), f"@{cliente['handle_social'].upper()}", font=fonte_handle, fill="#333333", anchor="ms")
        except Exception as e: print(f"⚠️ Erro no handle: {e}")
    try:
        fonte_assinatura = ImageFont.truetype("Raleway-VariableFont_wght.ttf", 20)
        draw.text((IMG_WIDTH / 2, IMG_HEIGHT - 15), ASSINATURA, font=fonte_assinatura, fill=(100, 100, 100, 255), anchor="ms", align="center")
    except Exception: pass
    buffer_saida = io.BytesIO()
    fundo.save(buffer_saida, format='JPEG', quality=95)
    print("✅ Imagem final criada!"); return (True, buffer_saida.getvalue())

def publicar_nas_redes(imagem_bytes, legenda, cliente):
    # ... (código inalterado)

def rodar_automacao_completa():
    # ... (código inalterado)

@app.route('/rodar-automacao-agora')
def rota_automacao():
    print("🚀 Disparando automação via rota secreta...")
    rodar_automacao_completa()
    print("🏁 Automação finalizada.")
    return jsonify({"status": "execucao_concluida"})

# ... (O restante do arquivo, com as rotas do painel CRUD, continua aqui)
