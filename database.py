# database.py (Versão final sem IA)
import sqlite3

def criar_banco_de_dados():
    conn = sqlite3.connect('automacao.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_cliente TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1,
            logo_path TEXT,
            fonte_titulo_path TEXT,
            fonte_categoria_path TEXT,
            layout_imagem TEXT DEFAULT 'padrão',
            cor_fundo_geral TEXT,
            cor_faixa_categoria TEXT,
            cor_caixa_titulo TEXT,
            cor_texto_titulo TEXT,
            cor_texto_categoria TEXT,
            meta_api_token TEXT,
            instagram_id TEXT,
            facebook_page_id TEXT,
            hashtags_fixas TEXT -- Campo para hashtags manuais
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rss_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts_publicados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            link_noticia TEXT NOT NULL,
            data_publicacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes (id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ Banco de dados 'automacao.db' (sem IA, com hashtags manuais) verificado e pronto.")