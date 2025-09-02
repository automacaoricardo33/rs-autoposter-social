# main.py (Versão Final sem Google Drive, com upload direto)
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

load_dotenv()
app = Flask(__name__)
DATABASE_URL = os.getenv('DATABASE_URL')
UPLOADS_PATH = os.path.join('static', 'uploads')

if DATABASE_URL:
    criar_banco_de_dados()

ASSINATURA = "Desenvolvido por: Studio RS Ilhabela - +55 12 99627-3989"
IMG_WIDTH, IMG_HEIGHT = 1080, 1080
LIMITE_DE_POSTS_POR_CICLO = 2 # Reduzido para ser mais leve para o Render

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# (Funções buscar_noticias_novas, gerar_legenda, criar_imagem_post permanecem as mesmas)
def buscar_noticias_novas(conn, cliente):
    #... (código idêntico ao anterior)
def gerar_legenda(noticia, cliente):
    #... (código idêntico ao anterior)
def criar_imagem_post(noticia, cliente):
    #... (código idêntico ao anterior)

# --- FUNÇÕES DE PUBLICAÇÃO ATUALIZADAS ---
def publicar_no_facebook_direto(imagem_bytes, legenda, cliente):
    print("📤 Publicando no Facebook (método direto)...")
    token = cliente['meta_api_token']
    page_id = cliente['facebook_page_id']
    if not all([token, page_id]): return False
    
    try:
        FacebookAdsApi.init(access_token=token)
        PagePost.api_create(
            page_id=page_id,
            message=legenda,
            source=io.BytesIO(imagem_bytes), # Envia os bytes da imagem
        )
        print("✅ Post publicado no Facebook!")
        return True
    except Exception as e:
        print(f"❌ Erro ao publicar no Facebook: {e}")
        return False

def publicar_no_instagram_direto(imagem_bytes, legenda, cliente):
    print("📤 Publicando no Instagram (método direto)...")
    token = cliente['meta_api_token']
    insta_id = cliente['instagram_id']
    if not all([token, insta_id]): return False

    # Infelizmente, a API do Instagram exige um link público. Usaremos um truque:
    # Faremos o upload da foto para a página do Facebook primeiro, sem publicá-la,
    # apenas para obter um link temporário que o Instagram possa usar.
    
    page_id = cliente['facebook_page_id']
    if not page_id:
        print("❌ Para postar no Instagram, o ID da Página do Facebook também é necessário.")
        return False

    try:
        # 1. Upload temporário para o Facebook para gerar uma URL
        upload_url = f"https://graph.facebook.com/{page_id}/photos"
        files = {'source': ('post.jpg', io.BytesIO(imagem_bytes), 'image/jpeg')}
        params = {'published': 'false', 'access_token': token}
        r_upload = requests.post(upload_url, files=files, params=params)
        r_upload.raise_for_status()
        photo_id = r_upload.json()['id']
        
        # 2. Pega a URL da imagem recém-criada
        photo_info_url = f"https://graph.facebook.com/{photo_id}?fields=images&access_token={token}"
        r_photo_info = requests.get(photo_info_url); r_photo_info.raise_for_status()
        image_url = r_photo_info.json()['images'][0]['source']

        # 3. Publica no Instagram usando a URL gerada
        url_container = f"https://graph.facebook.com/v19.0/{insta_id}/media"
        params_container = {'image_url': image_url, 'caption': legenda, 'access_token': token}
        r_container = requests.post(url_container, params=params_container); r_container.raise_for_status()
        id_criacao = r_container.json()['id']

        # 4. Finaliza a publicação no Instagram
        url_publicacao = f"https://graph.facebook.com/v19.0/{insta_id}/media_publish"
        params_publicacao = {'creation_id': id_criacao, 'access_token': token}
        r_publish = requests.post(url_publicacao, params=params_publicacao); r_publish.raise_for_status()
        
        print("✅ Post publicado no Instagram!")
        return True
    except Exception as e:
        print(f"❌ Erro ao publicar no Instagram: {e}")
        return False

def rodar_automacao_completa():
    log_execucao = []
    conn = get_db_connection()
    # ... (lógica de buscar clientes, igual à anterior)

    for cliente in clientes_ativos:
        novas_noticias = buscar_noticias_novas(conn, cliente)
        if not novas_noticias:
            log_execucao.append(f"Nenhuma notícia nova para {cliente['nome_cliente']}.")
            continue
        
        log_execucao.append(f"Encontradas {len(novas_noticias)} notícias. Processando até {LIMITE_DE_POSTS_POR_CICLO}.")
        posts_neste_ciclo = 0
        for noticia_para_postar in novas_noticias:
            if posts_neste_ciclo >= LIMITE_DE_POSTS_POR_CICLO:
                log_execucao.append("Limite de posts atingido.")
                break

            log_execucao.append(f"✅ Processando: '{noticia_para_postar.title}'")
            
            sucesso_img, resultado_img = criar_imagem_post(noticia_para_postar, cliente)
            if not sucesso_img:
                log_execucao.append(f"❌ Falha na imagem: {resultado_img}"); continue
            imagem_bytes = resultado_img
            
            legenda = gerar_legenda(noticia_para_postar, cliente)
            
            # CHAMA AS NOVAS FUNÇÕES DE PUBLICAÇÃO DIRETA
            publicar_no_instagram_direto(imagem_bytes, legenda, cliente)
            publicar_no_facebook_direto(imagem_bytes, legenda, cliente)
            
            marcar_como_publicado(conn, cliente['id'], noticia_para_postar.link)
            log_execucao.append(f"--- Post para '{noticia_para_postar.title}' concluído. ---")
            posts_neste_ciclo += 1
    conn.close()
    return log_execucao

# ... (TODAS as rotas do painel CRUD e outras funções continuam aqui, sem alteração)
