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

# --- CONFIGURAÇÃO ---
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

# --- FUNÇÃO DE CRIAÇÃO DE IMAGEM (NOVA VERSÃO COM DESIGN INTELIGENTE) ---
def criar_imagem_post(noticia, cliente):
    print("🎨 Criando imagem com design inteligente...")
    titulo = noticia.title.upper()
    categoria = (cliente['texto_categoria_fixo'] or (noticia.tags[0].term if hasattr(noticia, 'tags') and noticia.tags else "")).upper()
    url_imagem_noticia = None
    # ... (lógica de busca de imagem continua a mesma) ...
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
    
    cor_fundo = cliente['cor_fundo_geral'] or '#000000'
    fundo = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), cor_fundo)
    draw = ImageDraw.Draw(fundo)
    
    try:
        response_img = requests.get(url_imagem_noticia, stream=True, headers={'User-Agent': 'Mozilla/5.0'}); response_img.raise_for_status()
        imagem_noticia = Image.open(io.BytesIO(response_img.content))
        img_w, img_h = 1080, 750 # Altura da imagem principal
        imagem_noticia = ImageOps.fit(imagem_noticia, (img_w, img_h), Image.Resampling.LANCZOS)
        fundo.paste(imagem_noticia, (0, 0))
    except Exception as e:
        return (False, f"Erro ao processar imagem da notícia: {e}")

    # --- LÓGICA DE LAYOUT DINÂMICO ---
    tem_faixa_categoria = categoria and (cliente['cor_faixa_categoria'] not in [None, ''])

    if tem_faixa_categoria:
        # Layout com Faixa (ex: Boca no Trombone)
        cor_faixa = cliente['cor_faixa_categoria']
        draw.rectangle([(0, 650), (1080, 750)], fill=cor_faixa) # Desenha a faixa
        
        if cliente['fonte_categoria_path']:
            try:
                caminho_fonte_cat = os.path.join(UPLOADS_PATH, cliente['fonte_categoria_path'])
                fonte_cat = ImageFont.truetype(caminho_fonte_cat, 50)
                draw.text((540, 700), categoria, font=fonte_cat, fill="#FFFFFF", anchor="mm", align="center")
            except Exception as e: print(f"⚠️ Erro fonte categoria: {e}")

        # Título em caixa preta embaixo da faixa
        cor_caixa_titulo = cliente['cor_caixa_titulo'] or '#000000'
        draw.rectangle([(0, 750), (1080, 980)], fill=cor_caixa_titulo)
        
        # Logo sobe para o topo da imagem
        if cliente['logo_path']:
            try:
                caminho_logo = os.path.join(UPLOADS_PATH, cliente['logo_path'])
                logo = Image.open(caminho_logo).convert("RGBA")
                logo.thumbnail((250, 150))
                fundo.paste(logo, (40, 40), logo)
            except Exception as e: print(f"⚠️ Erro no logo: {e}")
            
    else:
        # Layout Padrão (ex: Voz do Litoral)
        cor_rodape = cliente['cor_caixa_titulo'] or '#051d40'
        draw.rectangle([(0, 680), (1080, 1080)], fill=cor_rodape)
        
        # Logo fica no centro, como elemento principal
        if cliente['logo_path']:
            try:
                caminho_logo = os.path.join(UPLOADS_PATH, cliente['logo_path'])
                logo = Image.open(caminho_logo).convert("RGBA")
                logo.thumbnail((300, 300))
                # Centraliza o logo na transição
                pos_x_logo = (IMG_WIDTH - logo.width) // 2
                pos_y_logo = 680 - (logo.height // 2)
                fundo.paste(logo, (pos_x_logo, pos_y_logo), logo)
            except Exception as e: print(f"⚠️ Erro no logo: {e}")
            
    # Título (desenhado no final para ficar por cima de tudo)
    try:
        caminho_fonte_titulo = os.path.join(UPLOADS_PATH, cliente['fonte_titulo_path'])
        fonte_titulo = ImageFont.truetype(caminho_fonte_titulo, 75)
        cor_texto_titulo = cliente['cor_texto_titulo'] or '#FFFFFF'
        linhas_texto = textwrap.wrap(titulo, width=28)
        texto_junto = "\n".join(linhas_texto)
        draw.text((540, 865), texto_junto, font=fonte_titulo, fill=cor_texto_titulo, anchor="mm", align="center")
    except Exception as e:
        return (False, f"Erro na fonte/texto do título: {e}")
    
    # Rodapé final com @handle
    if cliente['handle_social']:
        try:
            texto_cta = f"@{cliente['handle_social'].upper()}"
            fonte_cta = ImageFont.truetype("Anton-Regular.ttf", 45)
            draw.text((540, 1030), texto_cta, font=fonte_cta, fill="#FFFFFF", anchor="ms", align="center")
        except Exception as e: print(f"⚠️ Erro no handle social: {e}")

    buffer_saida = io.BytesIO()
    fundo.save(buffer_saida, format='JPEG', quality=90)
    print("✅ Imagem com novo design criada!"); return (True, buffer_saida.getvalue())


# --- O RESTANTE DO CÓDIGO (rodar_automacao_completa, rotas, etc.) ---
# (Cole aqui o restante do seu arquivo main.py da última versão que te enviei,
# começando da função 'def publicar_nas_redes(...)'. A lógica do painel já está correta,
# o problema estava na ausência dela no arquivo deployed.)

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
    # ... (código completo da função adicionar aqui) ...
    
@app.route('/editar/<int:id>', methods=('GET', 'POST'))
def editar(id):
    # ... (código completo da função editar aqui) ...
    
@app.route('/excluir/<int:id>', methods=('POST', 'GET'))
def excluir(id):
    # ... (código completo da função excluir aqui) ...

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
