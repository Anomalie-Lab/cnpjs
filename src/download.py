# -*- coding: utf-8 -*-
"""
Download CNPJ public data from Brazilian Federal Revenue

Lists files from the public data page and downloads them
https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/cadastros/consultas/dados-publicos-cnpj
https://dadosabertos.rfb.gov.br/CNPJ/
http://200.152.38.155/CNPJ/
https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/
"""

from bs4 import BeautifulSoup
import requests
import wget
import os
import sys
import time
import glob
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# URLs - try new format first, fallback to old format
url_dados_abertos = 'https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/'
url_old_format = 'http://200.152.38.155/CNPJ/'

# Get paths from environment or use defaults
# Garantir que os caminhos padrão fiquem dentro do diretório src/
base_dir = os.path.dirname(os.path.abspath(__file__))  # src/ (diretório onde está o script)
project_root = os.path.dirname(base_dir)  # Diretório raiz do projeto

# Obter caminhos do ambiente ou usar padrões dentro de src/
output_path = os.getenv('OUTPUT_FILES_PATH')
extracted_path = os.getenv('EXTRACTED_FILES_PATH')

# Resolver caminho para pasta_zip (sempre dentro de src/)
if not output_path:
    # Padrão: src/data/downloads
    pasta_zip = os.path.join(base_dir, 'data', 'downloads')
elif os.path.isabs(output_path):
    # Se for absoluto, usar como está
    pasta_zip = output_path
elif output_path.startswith('src/'):
    # Se começa com src/, resolver a partir da raiz do projeto
    pasta_zip = os.path.join(project_root, output_path)
else:
    # Caminho relativo, assumir que está dentro de src/
    pasta_zip = os.path.join(base_dir, output_path)

# Resolver caminho para pasta_cnpj (sempre dentro de src/)
if not extracted_path:
    # Padrão: src/data/extracted
    pasta_cnpj = os.path.join(base_dir, 'data', 'extracted')
elif os.path.isabs(extracted_path):
    # Se for absoluto, usar como está
    pasta_cnpj = extracted_path
elif extracted_path.startswith('src/'):
    # Se começa com src/, resolver a partir da raiz do projeto
    pasta_cnpj = os.path.join(project_root, extracted_path)
else:
    # Caminho relativo, assumir que está dentro de src/
    pasta_cnpj = os.path.join(base_dir, extracted_path)

# Converter para caminhos absolutos
pasta_zip = os.path.abspath(pasta_zip)
pasta_cnpj = os.path.abspath(pasta_cnpj)


def requisitos():
    """Create directories and check for existing files"""
    # Create directories if they don't exist
    if not os.path.isdir(pasta_cnpj):
        os.makedirs(pasta_cnpj)
    if not os.path.isdir(pasta_zip):
        os.makedirs(pasta_zip)
        
    arquivos_existentes = list(glob.glob(pasta_cnpj + '/*.*')) + list(glob.glob(pasta_zip + '/*.*'))
    if len(arquivos_existentes):
        print(f'\nArquivos encontrados nas pastas:')
        for arq in arquivos_existentes[:10]:  # Show first 10
            print(f'  - {arq}')
        if len(arquivos_existentes) > 10:
            print(f'  ... e mais {len(arquivos_existentes) - 10} arquivos')
        
        r = input(f'\nDeseja apagar os arquivos das pastas {pasta_cnpj} e {pasta_zip}? (y/n): ')
        if r and r.upper() == 'Y':
            for arq in arquivos_existentes:
                print(f'Apagando arquivo {arq}')
                os.remove(arq)
        else:
            print('Parando... Apague os arquivos manualmente e tente novamente')
            sys.exit(1)


def get_file_list(url):
    """Get list of ZIP files from URL"""
    try:
        print(f'Acessando: {url}')
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, features="lxml")
        
        lista = []
        print(f'\nRelação de arquivos em {url}:')
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and str(href).endswith('.zip'):
                if not href.startswith('http'):
                    full_url = url + href
                    print(f'  - {full_url}')
                    lista.append(full_url)
                else:
                    print(f'  - {href}')
                    lista.append(href)
        
        return lista
    except Exception as e:
        print(f'Erro ao acessar {url}: {e}')
        return []


def download_files(lista, pasta_destino):
    """Download files using wget"""
    # Ensure destination directory exists and is absolute
    pasta_destino = os.path.abspath(pasta_destino)
    if not os.path.exists(pasta_destino):
        os.makedirs(pasta_destino)
    
    def bar_progress(current, total, width=80):
        if total >= 2**20:
            tbytes = 'MB'
            unidade = 2**20
        else:
            tbytes = 'KB'
            unidade = 2**10
        progress_message = f"Baixando: %d%% [%d / %d] {tbytes}" % (
            current / total * 100, 
            current // unidade, 
            total // unidade
        )
        sys.stdout.write("\r" + progress_message)
        sys.stdout.flush()
    
    print(f'\nIniciando download de {len(lista)} arquivos...')
    print(f'Destino: {pasta_destino}')
    
    for k, url in enumerate(lista):
        filename = os.path.split(url)[1]
        file_path = os.path.join(pasta_destino, filename)
        
        # Skip if file already exists
        if os.path.exists(file_path):
            print(f'\n[{k+1}/{len(lista)}] Arquivo já existe: {filename}')
            continue
        
        print(f'\n[{k+1}/{len(lista)}] {time.asctime()} - Baixando: {filename}')
        print(f'  URL: {url}')
        print(f'  Destino: {file_path}')
        try:
            # Change to destination directory to ensure wget saves there
            original_cwd = os.getcwd()
            os.chdir(pasta_destino)
            wget.download(url, bar=bar_progress)
            os.chdir(original_cwd)
            print(f'\n✓ Download concluído: {filename}')
        except Exception as e:
            os.chdir(original_cwd)
            print(f'\n✗ Erro ao baixar {filename}: {e}')


if __name__ == '__main__':
    print(time.asctime(), f'Início de {sys.argv[0]}:')
    
    requisitos()
    
    # Try new format first (organized by date)
    print('\nTentando formato novo (organizado por data)...')
    try:
        soup_pagina_dados_abertos = BeautifulSoup(
            requests.get(url_dados_abertos, timeout=30).text, 
            features="lxml"
        )
        ultima_referencia = sorted([
            link.get('href') 
            for link in soup_pagina_dados_abertos.find_all('a') 
            if link.get('href') and link.get('href').startswith('20')
        ])[-1]
        
        url = url_dados_abertos + ultima_referencia
        print(f'Usando pasta mais recente: {url}')
        lista = get_file_list(url)
    except Exception as e:
        print(f'Formato novo não disponível: {e}')
        print('Tentando formato antigo...')
        lista = get_file_list(url_old_format)
    
    if not lista:
        print('Nenhum arquivo encontrado!')
        sys.exit(1)
    
    print(f'\nTotal de arquivos encontrados: {len(lista)}')
    resp = input(f'\nDeseja baixar os arquivos para a pasta {pasta_zip}? (y/n): ')
    if resp.lower() not in ['y', 's', 'yes', 'sim']:
        print('Download cancelado.')
        sys.exit()
    
    download_files(lista, pasta_zip)
    
    print(f'\n\n{time.asctime()} - Finalizou {sys.argv[0]}!!!')
    arquivos_baixados = len(glob.glob(os.path.join(pasta_zip, '*.zip')))
    print(f'Baixou {arquivos_baixados} arquivos.')

