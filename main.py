# main.py (Versão Final com Posicionamento Dinâmico do Logo)
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

# (Funções de automação como buscar_noticias_novas, etc. continuam as mesmas)
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
            if feed.bozo:
                print(f"⚠️ Aviso: O feed {url} pode estar mal formatado. Exceção: {feed.bozo_exception}")
            for entry in feed.entries:
                if entry.link not in links_publicados:
                    entry.published_date = datetime.fromtimestamp(mktime(entry.published_parsed)) if hasattr(entry, 'published_parsed') else datetime.now()
                    novas_noticias.append(entry)
        except Exception as e:
            print(f"⚠️ Erro ao processar o feed {url}: {e}")
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

def publicar_nas_redes(imagem_bytes, legenda, cliente):
    # (Esta função permanece como simulação por enquanto)
    print("✅ [SIMULAÇÃO] Publicando no Instagram e Facebook...")
    print(f"Legenda: {legenda[:100]}...")
    return True

# --- FUNÇÃO DE CRIAÇÃO DE IMAGEM (NOVA VERSÃO DINÂMICA) ---
def criar_imagem_post(noticia, cliente):
    print("🎨 Criando imagem com novo design...")
    titulo = noticia.title.upper()
    categoria = (noticia.tags[0].term if hasattr(noticia, 'tags') and noticia.tags else "").upper()
    url_imagem_noticia = None
    
    # Lógica de busca de imagem
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
    
    # --- Início do Novo Design ---
    cor_fundo = cliente['cor_fundo_geral'] or '#1a1a1a'
    fundo = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), cor_fundo)
    draw = ImageDraw.Draw(fundo)
    
    try:
        response_img = requests.get(url_imagem_noticia, stream=True, headers={'User-Agent': 'Mozilla/5.0'}); response_img.raise_for_status()
        imagem_noticia = Image.open(io.BytesIO(response_img.content))
        img_w, img_h = 1080, 680
        imagem_noticia = ImageOps.fit(imagem_noticia, (img_w, img_h), Image.Resampling.LANCZOS)
        fundo.paste(imagem_noticia, (0, 0))
    except Exception as e:
        return (False, f"Erro ao processar imagem da notícia: {e}")

    cor_rodape = cliente['cor_caixa_titulo'] or '#FFFFFF'
    draw.rectangle([(0, 680), (1080, 1080)], fill=cor_rodape)
    
    # --- LÓGICA DE POSICIONAMENTO DINÂMICO DO LOGO ---
    pos_y_logo_padrao = 710 # Posição dentro do rodapé
    pos_y_logo_topo = 40   # Posição no topo da imagem
    pos_y_logo_final = pos_y_logo_padrao # Assume a posição padrão

    tem_faixa_categoria = categoria and cliente['fonte_categoria_path'] and cliente['cor_faixa_categoria']

    if tem_faixa_categoria:
        # Se tem faixa, o logo sobe
        pos_y_logo_final = pos_y_logo_topo
        try:
            caminho_fonte_cat = os.path.join(UPLOADS_PATH, cliente['fonte_categoria_path'])
            fonte_cat = ImageFont.truetype(caminho_fonte_cat, 40)
            cor_texto_cat = cliente['cor_texto_categoria'] or '#000000'
            # Desenha a faixa e o texto
            draw.rectangle([(0, 680), (1080, 740)], fill=cliente['cor_faixa_categoria'])
            draw.text((540, 710), categoria, font=fonte_cat, fill=cor_texto_cat, anchor="mm", align="center")
        except Exception as e:
            print(f"⚠️ Erro ao renderizar categoria: {e}")

    # Coloca o logo na posição final decidida
    if cliente['logo_path']:
        try:
            caminho_logo = os.path.join(UPLOADS_PATH, cliente['logo_path'])
            logo = Image.open(caminho_logo).convert("RGBA")
            logo.thumbnail((220, 120))
            fundo.paste(logo, (50, pos_y_logo_final), logo)
        except Exception as e: print(f"⚠️ Erro no logo: {e}")

    # Título (posição ajustada se houver faixa)
    try:
        caminho_fonte_titulo = os.path.join(UPLOADS_PATH, cliente['fonte_titulo_path'])
        fonte_titulo = ImageFont.truetype(caminho_fonte_titulo, 65)
        cor_texto_titulo = cliente['cor_texto_titulo'] or '#000000'
        linhas_texto = textwrap.wrap(titulo, width=28)
        
        # Posição do título depende se a faixa de categoria existe
        pos_y_inicial_titulo = 820 if tem_faixa_categoria else 780
        
        pos_y_atual = pos_y_inicial_titulo
        for linha in linhas_texto:
            draw.text((540, pos_y_atual), linha, font=fonte_titulo, fill=cor_texto_titulo, anchor="ms", align="center")
            pos_y_atual += 70
    except Exception as e:
        return (False, f"Erro na fonte/texto do título: {e}")

    # Rodapé final com @handle
    if cliente['handle_social']:
        try:
            texto_cta = f"LEIA MAIS EM @{cliente['handle_social']}"
            fonte_cta = ImageFont.truetype("Anton-Regular.ttf", 40)
            draw.text((540, 1030), texto_cta, font=fonte_cta, fill="#555555", anchor="ms", align="center")
        except Exception as e: print(f"⚠️ Erro no handle social: {e}")
    
    try:
        fonte_assinatura = ImageFont.truetype("Raleway-VariableFont_wght.ttf", 20)
        draw.text((IMG_WIDTH / 2, IMG_HEIGHT - 15), ASSINATURA, font=fonte_assinatura, fill=(100, 100, 100, 255), anchor="ms", align="center")
    except Exception: pass
    
    buffer_saida = io.BytesIO()
    fundo.save(buffer_saida, format='JPEG', quality=90)
    print("✅ Imagem com novo design criada!"); return (True, buffer_saida.getvalue())

# --- O RESTANTE DO CÓDIGO (rodar_automacao_completa, rotas do painel, etc.)
# --- PERMANECE EXATAMENTE IGUAL À ÚLTIMA VERSÃO QUE ENVIEI ---
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

# ... (rotas /adicionar, /editar, /excluir completas e corretas aqui)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
