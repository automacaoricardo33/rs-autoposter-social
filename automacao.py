# automacao.py
import sqlite3
import feedparser
import requests
import io
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageOps
from datetime import datetime
from time import mktime
from google_drive import upload_para_google_drive

# --- CONSTANTES E CONFIGS ---
ASSINATURA = "Desenvolvido por: Studio RS Ilhabela - +55 12 99627-3989"
IMG_WIDTH, IMG_HEIGHT = 1080, 1080

# --- FUNÇÕES DE BANCO DE DADOS ---
def get_db_connection():
    conn = sqlite3.connect('automacao.db')
    conn.row_factory = sqlite3.Row
    return conn

def marcar_como_publicado(conn, cliente_id, link_noticia):
    conn.execute('INSERT INTO posts_publicados (cliente_id, link_noticia) VALUES (?, ?)', (cliente_id, link_noticia))
    conn.commit()

# --- FUNÇÕES DE CONTEÚDO ---
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
                    # Adiciona data de publicação para ordenação
                    if hasattr(entry, 'published_parsed'):
                        entry.published_date = datetime.fromtimestamp(mktime(entry.published_parsed))
                    else:
                        entry.published_date = datetime.now() # Fallback
                    novas_noticias.append(entry)
        except Exception as e:
            print(f"⚠️ Erro ao processar o feed {url}: {e}")
    
    # Ordena por data (mais recente primeiro)
    novas_noticias.sort(key=lambda x: x.published_date, reverse=True)
    return novas_noticias

def gerar_legenda(noticia, cliente):
    titulo = noticia.title
    resumo = ""
    if hasattr(noticia, 'summary'):
        # Limpa e limita o resumo
        from bs4 import BeautifulSoup
        resumo_limpo = BeautifulSoup(noticia.summary, 'html.parser').get_text(strip=True)
        resumo = textwrap.shorten(resumo_limpo, width=200, placeholder="...")

    fonte = f"Fonte: {cliente['nome_cliente']}"

    # Monta as hashtags
    hashtags = []
    # 1. Hashtag automática do nome do cliente
    nome_cliente_sem_espaco = "".join(cliente['nome_cliente'].split()).lower()
    hashtags.append(f"#{nome_cliente_sem_espaco}")
    # 2. Hashtags fixas do painel
    if cliente['hashtags_fixas']:
        tags_fixas = cliente['hashtags_fixas'].split()
        hashtags.extend([f"#{tag.strip()}" for tag in tags_fixas])

    legenda = f"{titulo}\n\n{resumo}\n\nLeia a matéria completa em nosso site.\n\n{fonte}\n\n{' '.join(hashtags)}"
    return legenda

# --- FUNÇÕES DE PUBLICAÇÃO ---
def publicar_no_instagram(url_imagem, legenda, cliente):
    print("📤 Publicando no Instagram...")
    token = cliente['meta_api_token']
    insta_id = cliente['instagram_id']
    if not all([token, insta_id]):
        print("⚠️ Credenciais do Instagram ausentes. Pulando publicação.")
        return False
    try:
        url_container = f"https://graph.facebook.com/v19.0/{insta_id}/media"
        params_container = {'image_url': url_imagem, 'caption': legenda, 'access_token': token}
        r_container = requests.post(url_container, params=params_container); r_container.raise_for_status()
        id_criacao = r_container.json()['id']
        url_publicacao = f"https://graph.facebook.com/v19.0/{insta_id}/media_publish"
        params_publicacao = {'creation_id': id_criacao, 'access_token': token}
        r_publish = requests.post(url_publicacao, params=params_publicacao); r_publish.raise_for_status()
        print("✅ Post publicado no Instagram com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao publicar no Instagram: {e.text}")
        return False

def publicar_no_facebook(url_imagem, legenda, cliente):
    print("📤 Publicando no Facebook...")
    token = cliente['meta_api_token']
    page_id = cliente['facebook_page_id']
    if not all([token, page_id]):
        print("⚠️ Credenciais do Facebook ausentes. Pulando publicação.")
        return False
    try:
        url_post_foto = f"https://graph.facebook.com/v19.0/{page_id}/photos"
        params = {'url': url_imagem, 'message': legenda, 'access_token': token}
        r = requests.post(url_post_foto, params=params); r.raise_for_status()
        print("✅ Post publicado na Página do Facebook com sucesso!")
        return True
    except Exception as e:
        print(f"❌ Erro ao publicar no Facebook: {e.text}")
        return False

# --- FUNÇÃO DE CRIAÇÃO DE IMAGEM ---
def criar_imagem_post(noticia, cliente):
    print("🎨 Criando imagem do post...")
    
    # --- Carrega dados ---
    titulo = noticia.title
    categoria = noticia.tags[0].term if hasattr(noticia, 'tags') and noticia.tags else ""
    url_imagem_noticia = noticia.links[1].href if hasattr(noticia, 'links') and len(noticia.links) > 1 and noticia.links[1].type.startswith('image/') else None

    if not url_imagem_noticia:
        print("⚠️ Nenhuma imagem encontrada no post RSS.")
        return None

    # --- Prepara o canvas ---
    cor_fundo = cliente['cor_fundo_geral'] or '#051d40'
    fundo = Image.new('RGBA', (IMG_WIDTH, IMG_HEIGHT), cor_fundo)
    draw = ImageDraw.Draw(fundo)

    # --- Insere a imagem da notícia ---
    try:
        response_img = requests.get(url_imagem_noticia, stream=True); response_img.raise_for_status()
        imagem_noticia = Image.open(io.BytesIO(response_img.content)).convert("RGBA")

        if cliente['layout_imagem'] == 'fundo_completo':
            # Recorte inteligente para preencher o fundo sem distorcer
            imagem_noticia = ImageOps.fit(imagem_noticia, (IMG_WIDTH, IMG_HEIGHT), Image.Resampling.LANCZOS)
            fundo.paste(imagem_noticia, (0, 0))
            # Adiciona uma sobreposição escura para legibilidade
            overlay = Image.new('RGBA', (IMG_WIDTH, IMG_HEIGHT), (0,0,0,128))
            fundo = Image.alpha_composite(fundo, overlay)
            draw = ImageDraw.Draw(fundo) # Redesenha sobre a nova imagem
        else: # Layout Padrão
            img_w, img_h = 980, 551
            imagem_noticia_resized = imagem_noticia.resize((img_w, img_h))
            pos_img_x = (IMG_WIDTH - img_w) // 2
            fundo.paste(imagem_noticia_resized, (pos_img_x, 50))

    except Exception as e:
        print(f"❌ Erro ao baixar ou processar a imagem da notícia: {e}")
        return None

    # --- Insere Logo ---
    if cliente['logo_path']:
        try:
            logo = Image.open(cliente['logo_path']).convert("RGBA")
            logo.thumbnail((200, 100))
            fundo.paste(logo, (70, 70), logo)
        except Exception as e:
            print(f"⚠️ Erro ao carregar logo: {e}")

    # --- Desenha faixas e textos ---
    # Categoria
    if categoria and cliente['fonte_categoria_path']:
        try:
            fonte_cat = ImageFont.truetype(cliente['fonte_categoria_path'], 40)
            # Converte para CAIXA ALTA
            categoria_texto = categoria.upper()
            pos_y_cat = 650
            if cliente['cor_faixa_categoria']:
                draw.rectangle([(50, pos_y_cat - 25), (IMG_WIDTH - 50, pos_y_cat + 25)], fill=cliente['cor_faixa_categoria'])
            draw.text((IMG_WIDTH / 2, pos_y_cat), categoria_texto, font=fonte_cat, fill=cliente['cor_texto_categoria'] or '#FFD700', anchor="mm", align="center")
        except Exception as e:
            print(f"⚠️ Erro ao renderizar categoria: {e}")

    # Título
    try:
        fonte_titulo = ImageFont.truetype(cliente['fonte_titulo_path'], 70)
        # Converte para CAIXA ALTA
        titulo_texto = titulo.upper()
        linhas_texto = textwrap.wrap(titulo_texto, width=28)
        texto_junto = "\n".join(linhas_texto)
        pos_y_titulo = 800
        if cliente['cor_caixa_titulo']:
            draw.rectangle([(50, pos_y_titulo - 100), (IMG_WIDTH - 50, pos_y_titulo + 100)], fill=cliente['cor_caixa_titulo'])
        draw.text((IMG_WIDTH / 2, pos_y_titulo), texto_junto, font=fonte_titulo, fill=cliente['cor_texto_titulo'] or '#FFFFFF', anchor="mm", align="center")
    except Exception as e:
        print(f"❌ Erro ao renderizar título: {e}")
        return None
    
    # Assinatura
    try:
        fonte_assinatura = ImageFont.truetype("Raleway-VariableFont_wght.ttf", 20)
        draw.text((IMG_WIDTH / 2, IMG_HEIGHT - 15), ASSINATURA, font=fonte_assinatura, fill=(200, 200, 200, 255), anchor="ms", align="center")
    except Exception: pass # Assinatura é opcional

    buffer_saida = io.BytesIO()
    fundo.convert("RGB").save(buffer_saida, format='JPEG', quality=90)
    print("✅ Imagem criada com sucesso!")
    return buffer_saida.getvalue()


# --- FUNÇÃO PRINCIPAL DA AUTOMAÇÃO ---
def rodar_automacao():
    conn = get_db_connection()
    clientes_ativos = conn.execute('SELECT * FROM clientes WHERE ativo = 1').fetchall()
    
    if not clientes_ativos:
        print("Nenhum cliente ativo encontrado. Encerrando.")
        return

    for cliente in clientes_ativos:
        novas_noticias = buscar_noticias_novas(conn, cliente)
        
        if not novas_noticias:
            print(f"Nenhuma notícia nova para {cliente['nome_cliente']}.")
            continue
            
        # Pega apenas a notícia mais recente
        noticia_para_postar = novas_noticias[0]
        print(f"✅ Notícia mais recente encontrada: '{noticia_para_postar.title}'")

        # 1. Cria a imagem
        imagem_bytes = criar_imagem_post(noticia_para_postar, cliente)
        if not imagem_bytes: continue

        # 2. Faz o upload para o Google Drive
        nome_arquivo = f"post_{cliente['id']}_{int(datetime.now().timestamp())}.jpg"
        link_imagem_publica = upload_para_google_drive(imagem_bytes, nome_arquivo)
        if not link_imagem_publica: continue

        # 3. Gera a legenda
        legenda = gerar_legenda(noticia_para_postar, cliente)

        # 4. Publica
        publicar_no_instagram(link_imagem_publica, legenda, cliente)
        publicar_no_facebook(link_imagem_publica, legenda, cliente)

        # 5. Marca como publicado para não repetir
        marcar_como_publicado(conn, cliente['id'], noticia_para_postar.link)
        print(f"--- Processo para {cliente['nome_cliente']} concluído. ---")

    conn.close()

if __name__ == '__main__':
    print("🚀 Iniciando a rotina de automação...")
    rodar_automacao()
    print("🏁 Rotina de automação finalizada.")