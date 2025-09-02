# main.py (Versão Final com Cloudinary para assets)
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
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.pagepost import PagePost
from cloudinary_handler import upload_asset_to_cloudinary # NOSSA NOVA IMPORTAÇÃO

load_dotenv()
app = Flask(__name__)
DATABASE_URL = os.getenv('DATABASE_URL')
UPLOADS_PATH = os.path.join('static', 'uploads')

if DATABASE_URL:
    criar_banco_de_dados()

ASSINATURA = "Desenvolvido por: Studio RS Ilhabela - +55 12 99627-3989"
IMG_WIDTH, IMG_HEIGHT = 1080, 1080
LIMITE_DE_POSTS_POR_CICLO = 2

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def criar_imagem_post(noticia, cliente):
    # (A lógica de busca de imagem da notícia continua a mesma)
    # ...
    # LÓGICA DE ABERTURA DE ARQUIVO ATUALIZADA PARA USAR URLS DO CLOUDINARY
    if cliente['logo_path']:
        try:
            # Baixa o logo da URL do Cloudinary
            response = requests.get(cliente['logo_path'], stream=True)
            response.raise_for_status()
            logo = Image.open(io.BytesIO(response.content)).convert("RGBA")
            logo.thumbnail((200, 100)); fundo.paste(logo, (70, 70), logo)
        except Exception as e: return (False, f"Erro ao carregar logo do Cloudinary: {e}")
    if categoria and cliente['fonte_categoria_path']:
        try:
            # Baixa a fonte da URL do Cloudinary
            response = requests.get(cliente['fonte_categoria_path'])
            response.raise_for_status()
            fonte_cat = ImageFont.truetype(io.BytesIO(response.content), 40)
            # ... (resto da lógica de desenhar categoria)
        except Exception as e: return (False, f"Erro na fonte/texto da categoria: {e}")
    try:
        # Baixa a fonte da URL do Cloudinary
        response = requests.get(cliente['fonte_titulo_path'])
        response.raise_for_status()
        fonte_titulo = ImageFont.truetype(io.BytesIO(response.content), 70)
        # ... (resto da lógica de desenhar título)
    except Exception as e: return (False, f"Erro na fonte/texto do título: {e}")
    # ... (resto da função criar_imagem_post)
    return (True, buffer_saida.getvalue())

def rodar_automacao_completa():
    # ... (lógica de buscar clientes e notícias)
    for noticia_para_postar in novas_noticias:
        # ...
        sucesso_img, resultado_img = criar_imagem_post(noticia_para_postar, cliente)
        if not sucesso_img:
            log_execucao.append(f"❌ Falha na imagem: {resultado_img}"); continue
        imagem_bytes = resultado_img
        
        legenda = gerar_legenda(noticia_para_postar, cliente)
        
        # REMOVEMOS O GOOGLE DRIVE, PUBLICAMOS OS BYTES DIRETAMENTE
        publicar_no_instagram_direto(imagem_bytes, legenda, cliente)
        publicar_no_facebook_direto(imagem_bytes, legenda, cliente)
        
        marcar_como_publicado(conn, cliente['id'], noticia_para_postar.link)
        # ...
    # ...
    
# --- ROTAS DO PAINEL ---
@app.route('/adicionar', methods=('GET', 'POST'))
def adicionar():
    if request.method == 'POST':
        paths = {'logo': None, 'fonte_titulo': None, 'fonte_categoria': None}
        for tipo in ['logo', 'fonte_titulo', 'fonte_categoria']:
            if tipo in request.files and request.files[tipo].filename != '':
                arquivo = request.files[tipo]
                # FAZ O UPLOAD PARA O CLOUDINARY E SALVA A URL
                url_segura = upload_asset_to_cloudinary(arquivo.stream, arquivo.filename)
                paths[tipo] = url_segura
        
        # ... (Pega os outros dados do formulário e insere no banco, salvando as URLs nos campos _path)
        # ...
        return redirect(url_for('index'))
    return render_template('adicionar_cliente.html')

@app.route('/editar/<int:id>', methods=('GET', 'POST'))
def editar(id):
    cliente = get_cliente(id)
    if request.method == 'POST':
        paths = {'logo': cliente['logo_path'], 'fonte_titulo': cliente['fonte_titulo_path'], 'fonte_categoria': cliente['fonte_categoria_path']}
        for tipo in ['logo', 'fonte_titulo', 'fonte_categoria']:
            if tipo in request.files and request.files[tipo].filename != '':
                arquivo = request.files[tipo]
                # FAZ O UPLOAD PARA O CLOUDINARY E ATUALIZA A URL
                url_segura = upload_asset_to_cloudinary(arquivo.stream, arquivo.filename)
                paths[tipo] = url_segura
        
        # ... (Pega os outros dados do formulário e faz o UPDATE no banco com as novas URLs)
        # ...
        return redirect(url_for('index'))
    return render_template('editar_cliente.html', cliente=cliente, rss_urls_texto=rss_urls_texto)

# (O resto do código, como as rotas de GET, index, excluir, etc., não precisa de grandes mudanças)
