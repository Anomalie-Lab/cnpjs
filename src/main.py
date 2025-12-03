import datetime
import gc
import pathlib
from dotenv import load_dotenv
from sqlalchemy import create_engine
import os
import pandas as pd
import psycopg2
import sys
import time
import gc
import zipfile


#%%
def makedirs(path):
    '''
    cria path caso seja necessario
    '''
    if not os.path.exists(path):
        os.makedirs(path)

#%%
def to_sql(dataframe, **kwargs):
    '''
    Quebra em pedacos a tarefa de inserir registros no banco
    '''
    size = 4096  #TODO param
    total = len(dataframe)
    name = kwargs.get('name')

    def chunker(df):
        return (df[i:i + size] for i in range(0, len(df), size))

    for i, df in enumerate(chunker(dataframe)):
        df.to_sql(**kwargs)
        index = i * size
        percent = (index * 100) / total
        progress = f'{name} {percent:.2f}% {index:0{len(str(total))}}/{total}'
        sys.stdout.write(f'\r{progress}')
    sys.stdout.write('\n')

#%%
# Ler arquivo de configuração de ambiente
def getEnv(env):
    return os.getenv(env)

#%%
# Função auxiliar para converter datas de formato inteiro (YYYYMMDD) para DATE
def convert_date_int_to_date(date_int):
    '''
    Converte data de formato inteiro YYYYMMDD para objeto date do Python
    '''
    if pd.isna(date_int) or date_int is None or date_int == 0:
        return None
    try:
        date_str = str(int(date_int))
        if len(date_str) == 8:
            return pd.to_datetime(date_str, format='%Y%m%d').date()
        return None
    except:
        return None


print('='*60)
print('Iniciando processo ETL - Dados CNPJ Receita Federal')
print('='*60)

current_path = pathlib.Path().resolve()
dotenv_path = os.path.join(current_path, '.env')

# Se não encontrar no diretório atual, procurar no diretório pai
if not os.path.isfile(dotenv_path):
    parent_path = current_path.parent
    dotenv_path = os.path.join(parent_path, '.env')
    
# Se ainda não encontrar, procurar em src/.env
if not os.path.isfile(dotenv_path):
    src_env_path = os.path.join(current_path, 'src', '.env')
    if os.path.isfile(src_env_path):
        dotenv_path = src_env_path

if not os.path.isfile(dotenv_path):
    print('Arquivo .env não encontrado!')
    print('Procurando em:')
    print(f'  - {current_path}/.env')
    print(f'  - {current_path.parent}/.env')
    print(f'  - {current_path}/src/.env')
    print('\nCrie um arquivo .env com as configurações necessárias ou execute o script run.sh')
    sys.exit(1)

print(f'Carregando variáveis de ambiente de: {dotenv_path}')
load_dotenv(dotenv_path=dotenv_path)

# Read details from ".env" file:
output_files = None
extracted_files = None
try:
    output_files = getEnv('OUTPUT_FILES_PATH')
    makedirs(output_files)

    extracted_files = getEnv('EXTRACTED_FILES_PATH')
    makedirs(extracted_files)

    print('Diretórios definidos:')
    print(f'output_files: {output_files}')
    print(f'extracted_files: {extracted_files}')
except Exception as e:
    print(f'Erro na definição dos diretórios: {e}')
    print('Verifique o arquivo ".env" ou o local informado do seu arquivo de configuração.')
    sys.exit(1)

#%%
# Extracting files:
print('='*60)
print('INICIANDO EXTRAÇÃO DOS ARQUIVOS')
print('='*60)

# Get list of ZIP files from download directory
Files = [f for f in os.listdir(output_files) if f.endswith('.zip')]

if not Files:
    print(f'Nenhum arquivo ZIP encontrado em {output_files}')
    print('Execute primeiro o script download.py para baixar os arquivos')
    sys.exit(1)

print(f'Total de arquivos ZIP encontrados: {len(Files)}')

# Verificar quais arquivos já foram extraídos
extracted_items = set(os.listdir(extracted_files)) if os.path.exists(extracted_files) else set()

i_l = 0
extracted_count = 0
skipped_count = 0
for l in Files:
    try:
        i_l += 1
        full_path = os.path.join(output_files, l)
        if not os.path.exists(full_path):
            print(f'[{i_l}/{len(Files)}] Arquivo não encontrado: {l}')
            continue
        
        # Verificar se o arquivo ZIP já foi extraído
        # Obtém a lista de arquivos dentro do ZIP
        with zipfile.ZipFile(full_path, 'r') as zip_ref:
            zip_contents = set(zip_ref.namelist())
        
        # Verifica se todos os arquivos do ZIP já existem no diretório de extração
        already_extracted = zip_contents.issubset(extracted_items)
        
        if already_extracted:
            print(f'[{i_l}/{len(Files)}] Arquivo já descompactado: {l}')
            skipped_count += 1
            continue
        
        print(f'[{i_l}/{len(Files)}] Descompactando: {l}')
        with zipfile.ZipFile(full_path, 'r') as zip_ref:
            zip_ref.extractall(extracted_files)
            # Atualiza a lista de arquivos extraídos
            extracted_items.update(zip_ref.namelist())
        print(f'  ✓ Extração concluída: {l}')
        extracted_count += 1
    except Exception as e:
        print(f'  ✗ Erro ao extrair {l}: {e}')

print('='*60)
print(f'Resumo da extração:')
print(f'  - Arquivos extraídos: {extracted_count}')
print(f'  - Arquivos já descompactados (pulados): {skipped_count}')
print(f'  - Total processado: {extracted_count + skipped_count}/{len(Files)}')
print('='*60)

#%%
########################################################################################################################
## LER E INSERIR DADOS #################################################################################################
########################################################################################################################
print('='*60)
print('INICIANDO PROCESSAMENTO E INSERÇÃO DOS DADOS')
print('='*60)
insert_start = time.time()

# Files:
Items = [name for name in os.listdir(extracted_files) if name.endswith('')]

# Separar arquivos:
arquivos_empresa = []
arquivos_estabelecimento = []
arquivos_socios = []
arquivos_simples = []
arquivos_cnae = []
arquivos_moti = []
arquivos_munic = []
arquivos_natju = []
arquivos_pais = []
arquivos_quals = []
for i in range(len(Items)):
    if Items[i].find('EMPRE') > -1:
        arquivos_empresa.append(Items[i])
    elif Items[i].find('ESTABELE') > -1:
        arquivos_estabelecimento.append(Items[i])
    elif Items[i].find('SOCIO') > -1:
        arquivos_socios.append(Items[i])
    elif Items[i].find('SIMPLES') > -1:
        arquivos_simples.append(Items[i])
    elif Items[i].find('CNAE') > -1:
        arquivos_cnae.append(Items[i])
    elif Items[i].find('MOTI') > -1:
        arquivos_moti.append(Items[i])
    elif Items[i].find('MUNIC') > -1:
        arquivos_munic.append(Items[i])
    elif Items[i].find('NATJU') > -1:
        arquivos_natju.append(Items[i])
    elif Items[i].find('PAIS') > -1:
        arquivos_pais.append(Items[i])
    elif Items[i].find('QUALS') > -1:
        arquivos_quals.append(Items[i])
    else:
        pass

print(f'Arquivos organizados:')
print(f'  - Empresa: {len(arquivos_empresa)}')
print(f'  - Estabelecimento: {len(arquivos_estabelecimento)}')
print(f'  - Sócios: {len(arquivos_socios)}')
print(f'  - Simples: {len(arquivos_simples)}')
print(f'  - CNAE: {len(arquivos_cnae)}')
print(f'  - Motivos: {len(arquivos_moti)}')
print(f'  - Municípios: {len(arquivos_munic)}')
print(f'  - Natureza Jurídica: {len(arquivos_natju)}')
print(f'  - Países: {len(arquivos_pais)}')
print(f'  - Qualificações: {len(arquivos_quals)}')

#%%
# Conectar no banco de dados:
# Dados da conexão com o BD
user=getEnv('DB_USER')
passw=getEnv('DB_PASSWORD')
host=getEnv('DB_HOST')
port=getEnv('DB_PORT')
database=getEnv('DB_NAME')

# Conectar:
print('='*60)
print('CONECTANDO AO BANCO DE DADOS')
print('='*60)
print(f'Host: {host}:{port}')
print(f'Database: {database}')
print(f'User: {user}')
try:
    engine = create_engine('postgresql://'+user+':'+passw+'@'+host+':'+port+'/'+database)
    conn = psycopg2.connect('dbname='+database+' '+'user='+user+' '+'host='+host+' '+'port='+port+' '+'password='+passw)
    cur = conn.cursor()
    print('✓ Conexão estabelecida com sucesso!')
except Exception as e:
    print(f'✗ Erro ao conectar ao banco de dados: {e}')
    print('Verifique se o PostgreSQL está rodando e as configurações no arquivo .env')
    sys.exit(1)

#%%
# Criar schema do banco de dados
def create_schema():
    '''
    Cria as tabelas do banco de dados conforme o schema.sql
    '''
    schema_path = os.path.join(current_path, 'schema.sql')
    if os.path.isfile(schema_path):
        print('Criando schema do banco de dados...')
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            
            # Remove linhas de comentário e comandos específicos do CLI
            lines = schema_sql.split('\n')
            cleaned_lines = []
            for line in lines:
                stripped = line.strip()
                # Pula CREATE DATABASE e \c (comandos CLI)
                if 'CREATE DATABASE' in stripped.upper() or stripped.startswith('\\c'):
                    continue
                # Remove apenas comentários de linha única que não são COMMENT ON
                if stripped.startswith('--') and 'COMMENT' not in stripped.upper():
                    continue
                cleaned_lines.append(line)
            
            schema_sql = '\n'.join(cleaned_lines)
            
            # Divide o SQL em comandos individuais
            # Remove espaços em branco extras
            schema_sql = schema_sql.strip()
            
            # Divide por ponto e vírgula seguido de nova linha ou fim de string
            # Usa uma abordagem simples: divide por ';\n' ou ';' no final
            import re
            # Divide por ponto e vírgula seguido de espaços em branco e nova linha
            # Mas preserva o ponto e vírgula no comando
            parts = re.split(r';\s*\n', schema_sql)
            
            # Limpa e executa cada comando
            executed = 0
            errors = 0
            for i, part in enumerate(parts):
                cmd = part.strip()
                if not cmd or cmd.startswith('--'):
                    continue
                
                # Remove linhas vazias e comentários no início
                lines = [l for l in cmd.split('\n') if l.strip() and not l.strip().startswith('--')]
                cmd = '\n'.join(lines).strip()
                
                if not cmd:
                    continue
                
                # Adiciona ponto e vírgula se não tiver
                if not cmd.rstrip().endswith(';'):
                    cmd += ';'
                
                try:
                    cur.execute(cmd)
                    executed += 1
                except Exception as e:
                    error_msg = str(e).lower()
                    # Se a transação foi abortada, faz rollback
                    if 'aborted' in error_msg or 'transaction' in error_msg:
                        conn.rollback()
                        # Tenta executar novamente após rollback
                        try:
                            cur.execute(cmd)
                            executed += 1
                        except Exception as e2:
                            error_msg2 = str(e2).lower()
                            if 'already exists' not in error_msg2 and 'duplicate' not in error_msg2:
                                errors += 1
                                if errors <= 3:
                                    print(f'  Aviso ao executar comando {i+1} (após rollback): {str(e2)[:100]}')
                    # Ignora erros de tabela/índice já existe
                    elif 'already exists' not in error_msg and 'duplicate' not in error_msg:
                        errors += 1
                        # Mostra apenas alguns erros para não poluir a saída
                        if errors <= 3:
                            print(f'  Aviso ao executar comando {i+1}: {str(e)[:100]}')
            
            conn.commit()
            if executed > 0:
                print(f'  Executados {executed} comandos SQL com sucesso')
            if errors > 0:
                print(f'  {errors} comandos tiveram avisos (geralmente tabelas/índices já existentes)')
        print('✓ Schema criado com sucesso!')
    else:
        print('Arquivo schema.sql não encontrado. Criando tabelas dinamicamente...')

create_schema()

#%%
# Criar tabela de controle de arquivos processados
def create_processed_files_table():
    '''
    Cria tabela para rastrear arquivos já processados
    '''
    try:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS processed_files (
                filename VARCHAR(255) NOT NULL,
                table_name VARCHAR(100) NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_size BIGINT,
                records_count INTEGER,
                PRIMARY KEY (filename, table_name)
            );
        ''')
        conn.commit()
    except Exception as e:
        print(f'Aviso ao criar tabela processed_files: {e}')
        conn.rollback()

def is_file_processed(filename, table_name):
    '''
    Verifica se um arquivo já foi processado
    '''
    try:
        cur.execute('''
            SELECT COUNT(*) FROM processed_files 
            WHERE filename = %s AND table_name = %s
        ''', (filename, table_name))
        return cur.fetchone()[0] > 0
    except Exception as e:
        # Se a tabela não existir, retorna False
        return False

def mark_file_as_processed(filename, table_name, file_size=None, records_count=None):
    '''
    Marca um arquivo como processado
    '''
    try:
        cur.execute('''
            INSERT INTO processed_files (filename, table_name, file_size, records_count)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (filename, table_name) 
            DO UPDATE SET processed_at = CURRENT_TIMESTAMP, 
                         file_size = EXCLUDED.file_size,
                         records_count = EXCLUDED.records_count
        ''', (filename, table_name, file_size, records_count))
        conn.commit()
    except Exception as e:
        print(f'Aviso ao marcar arquivo como processado: {e}')
        conn.rollback()

def table_exists(table_name):
    '''
    Verifica se uma tabela existe no banco de dados
    '''
    try:
        cur.execute('''
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = %s
            );
        ''', (table_name,))
        return cur.fetchone()[0]
    except Exception:
        return False

def safe_truncate_table(table_name):
    '''
    Executa TRUNCATE com tratamento de erros
    '''
    # Verificar se a tabela existe primeiro
    if not table_exists(table_name):
        print(f'⚠ Tabela {table_name} não existe. Criando schema...')
        # Garantir que não há transação abortada
        try:
            conn.rollback()
        except:
            pass
        create_schema()
        # Verificar novamente após criar schema
        if not table_exists(table_name):
            print(f'⚠ Tabela {table_name} ainda não existe após criar schema. Pulando TRUNCATE.')
            return False
    
    try:
        # Garantir que não há transação abortada
        try:
            conn.rollback()
        except:
            pass
        
        cur.execute(f'TRUNCATE TABLE "{table_name}" CASCADE;')
        conn.commit()
        return True
    except psycopg2.errors.UndefinedTable:
        print(f'⚠ Tabela {table_name} não existe. Criando schema novamente...')
        try:
            conn.rollback()
        except:
            pass
        create_schema()
        if not table_exists(table_name):
            print(f'⚠ Tabela {table_name} ainda não existe após criar schema.')
            return False
        try:
            cur.execute(f'TRUNCATE TABLE "{table_name}" CASCADE;')
            conn.commit()
            return True
        except Exception as e2:
            print(f'⚠ Erro ao limpar tabela {table_name} após criar schema: {e2}')
            conn.rollback()
            return False
    except Exception as e:
        error_msg = str(e).lower()
        if 'aborted' in error_msg or 'transaction' in error_msg:
            conn.rollback()
            try:
                cur.execute(f'TRUNCATE TABLE "{table_name}" CASCADE;')
                conn.commit()
                return True
            except Exception as e2:
                print(f'⚠ Erro ao limpar tabela {table_name} (após rollback): {e2}')
                conn.rollback()
                return False
        else:
            print(f'⚠ Erro ao limpar tabela {table_name}: {e}')
            conn.rollback()
            return False

create_processed_files_table()

#%%
# Arquivos de empresa:
empresa_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DE EMPRESA')
print('='*60)

# Verificar se precisa limpar tabela (apenas se não houver arquivos processados)
arquivos_nao_processados = [f for f in arquivos_empresa if not is_file_processed(f, 'companies')]
if len(arquivos_nao_processados) < len(arquivos_empresa):
    print(f'Arquivos já processados: {len(arquivos_empresa) - len(arquivos_nao_processados)}/{len(arquivos_empresa)}')
    # Se todos já foram processados, não precisa limpar
    if len(arquivos_nao_processados) == 0:
        print('Todos os arquivos de empresa já foram processados. Pulando...')
    else:
        # Limpa apenas se houver arquivos novos para processar
        safe_truncate_table('companies')
else:
    # Primeira execução, limpa a tabela
    safe_truncate_table('companies')

print(f'Total de arquivos de empresa para processar: {len(arquivos_empresa)}')
processed_count = 0
skipped_count = 0
try:
    for e in range(0, len(arquivos_empresa)):
        filename = arquivos_empresa[e]
        
        # Verificar se arquivo já foi processado
        if is_file_processed(filename, 'companies'):
            print(f'[{e+1}/{len(arquivos_empresa)}] Arquivo já processado (pulando): {filename}')
            skipped_count += 1
            continue
        
        print(f'[{e+1}/{len(arquivos_empresa)}] Processando arquivo: {filename}')
        try:
            del empresa
        except:
            pass

        #empresa = pd.DataFrame(columns=[0, 1, 2, 3, 4, 5, 6])
        empresa_dtypes = {0: object, 1: object, 2: 'Int32', 3: 'Int32', 4: object, 5: 'Int32', 6: object}
        extracted_file_path = os.path.join(extracted_files, filename)
        
        # Verificar tamanho do arquivo
        file_size = os.path.getsize(extracted_file_path) if os.path.exists(extracted_file_path) else None
        if file_size:
            file_size_mb = file_size / (1024 * 1024)
            print(f'  Tamanho do arquivo: {file_size_mb:.2f} MB')
        
        print(f'  Lendo arquivo CSV... (isso pode levar alguns minutos para arquivos grandes)')
        try:
            empresa = pd.read_csv(filepath_or_buffer=extracted_file_path,
                              sep=';',
                              #nrows=100,
                              skiprows=0,
                              header=None,
                              dtype=empresa_dtypes,
                              encoding='latin-1',
            )
            print(f'  ✓ Arquivo lido: {len(empresa)} registros encontrados')
        except KeyboardInterrupt:
            print(f'\n\n⚠ Processo interrompido pelo usuário durante leitura do arquivo: {filename}')
            print('O arquivo não foi marcado como processado e será reprocessado na próxima execução.')
            print('Progresso salvo até agora:')
            print(f'  - Arquivos processados: {processed_count}')
            print(f'  - Arquivos pulados: {skipped_count}')
            raise

        # Tratamento do arquivo antes de inserir na base:
        # Não precisa reset_index, vamos renomear diretamente
        # empresa = empresa.reset_index()
        # del empresa['index']

        # Renomear colunas diretamente
        empresa.columns = ['base_cnpj', 'company_name', 'legal_nature_code', 'responsible_qualification_code', 'capital', 'company_size_code', 'responsible_federative_entity']

        # Extrair CPF do campo company_name (CPF está concatenado no final do nome)
        import re
        def extract_cpf_from_name(name_str):
            '''Extrai CPF (11 dígitos) ou CNPJ (14 dígitos) do final do nome'''
            if pd.isna(name_str) or name_str == '':
                return None
            name_str = str(name_str).strip()
            # Procurar por CPF (11 dígitos) no final
            match_cpf = re.search(r'(\d{11})$', name_str)
            if match_cpf:
                return match_cpf.group(1)
            # Procurar por CNPJ (14 dígitos) no final
            match_cnpj = re.search(r'(\d{14})$', name_str)
            if match_cnpj:
                return match_cnpj.group(1)
            return None
        
        def clean_company_name(name_str):
            '''Remove CPF/CNPJ do final do nome da empresa'''
            if pd.isna(name_str) or name_str == '':
                return name_str
            name_str = str(name_str).strip()
            # Remover CPF (11 dígitos) do final
            name_str = re.sub(r'\s+\d{11}$', '', name_str)
            # Remover CNPJ (14 dígitos) do final
            name_str = re.sub(r'\s+\d{14}$', '', name_str)
            return name_str.strip()
        
        # Extrair CPF e limpar nome
        empresa['responsible_cpf'] = empresa['company_name'].apply(extract_cpf_from_name)
        empresa['company_name'] = empresa['company_name'].apply(clean_company_name)

        # Replace "," por "."
        empresa['capital'] = empresa['capital'].apply(lambda x: x.replace(',','.'))
        empresa['capital'] = empresa['capital'].astype(float)

        # Gravar dados no banco:
        # Empresa
        print(f'  Inserindo {len(empresa)} registros na tabela companies...')
        try:
            to_sql(empresa, name='companies', con=engine, if_exists='append', index=False)
        except KeyboardInterrupt:
            print(f'\n\n⚠ Processo interrompido pelo usuário durante inserção do arquivo: {filename}')
            print('O arquivo não foi marcado como processado e será reprocessado na próxima execução.')
            print('Progresso salvo até agora:')
            print(f'  - Arquivos processados: {processed_count}')
            print(f'  - Arquivos pulados: {skipped_count}')
            raise
        
        # Marcar como processado
        mark_file_as_processed(filename, 'companies', file_size, len(empresa))
        processed_count += 1
        print(f'  ✓ Arquivo {filename} inserido com sucesso!')
except KeyboardInterrupt:
    print('\n\n' + '='*60)
    print('PROCESSO INTERROMPIDO PELO USUÁRIO')
    print('='*60)
    print('Progresso salvo:')
    print(f'  - Arquivos de empresa processados: {processed_count}')
    print(f'  - Arquivos de empresa pulados: {skipped_count}')
    print('\nVocê pode executar o script novamente e ele continuará de onde parou.')
    print('Arquivos já processados serão pulados automaticamente.')
    print('='*60)
    sys.exit(0)

try:
    del empresa
except:
    pass
print('✓ Arquivos de empresa finalizados!')
print(f'  - Processados: {processed_count}')
print(f'  - Já processados (pulados): {skipped_count}')
empresa_insert_end = time.time()
empresa_Tempo_insert = round((empresa_insert_end - empresa_insert_start))
print(f'Tempo de execução do processo de empresa: {empresa_Tempo_insert} segundos ({empresa_Tempo_insert//60} minutos)')

#%%
# Arquivos de estabelecimento:
estabelecimento_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DE ESTABELECIMENTO')
print('='*60)

# Verificar se precisa limpar tabela
arquivos_nao_processados_est = [f for f in arquivos_estabelecimento if not is_file_processed(f, 'establishments')]
if len(arquivos_nao_processados_est) < len(arquivos_estabelecimento):
    print(f'Arquivos já processados: {len(arquivos_estabelecimento) - len(arquivos_nao_processados_est)}/{len(arquivos_estabelecimento)}')
    if len(arquivos_nao_processados_est) == 0:
        print('Todos os arquivos de estabelecimento já foram processados. Pulando...')
    else:
        safe_truncate_table('establishments')
else:
    safe_truncate_table('establishments')

print(f'Total de arquivos de estabelecimento para processar: {len(arquivos_estabelecimento)}')
processed_count_est = 0
skipped_count_est = 0
for e in range(0, len(arquivos_estabelecimento)):
    filename = arquivos_estabelecimento[e]
    
    # Verificar se arquivo já foi processado
    if is_file_processed(filename, 'establishments'):
        print(f'[{e+1}/{len(arquivos_estabelecimento)}] Arquivo já processado (pulando): {filename}')
        skipped_count_est += 1
        continue
    
    print(f'[{e+1}/{len(arquivos_estabelecimento)}] Processando arquivo: {filename}')
    try:
        del estabelecimento
        gc.collect()
    except:
        pass

    # estabelecimento = pd.DataFrame(columns=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28])
    estabelecimento_dtypes = {0: object, 1: object, 2: object, 3: 'Int32', 4: object, 5: 'Int32', 6: 'Int32',
                              7: 'Int32', 8: object, 9: object, 10: 'Int32', 11: object, 12: object, 13: object,
                              14: object, 15: object, 16: object, 17: object, 18: object, 19: object,
                              20: 'Int32', 21: object, 22: object, 23: object, 24: object, 25: object,
                              26: object, 27: object, 28: object, 29: 'Int32'}
    extracted_file_path = os.path.join(extracted_files, arquivos_estabelecimento[e])

    NROWS = 2000000
    part = 0
    
    # Mostrar tamanho do arquivo
    file_size = os.path.getsize(extracted_file_path) if os.path.exists(extracted_file_path) else None
    if file_size:
        file_size_mb = file_size / (1024 * 1024)
        print(f'  Tamanho do arquivo: {file_size_mb:.2f} MB')
    
    while True:
        if part > 0:
            print(f'  Lendo parte {part + 1} do arquivo (pulando {NROWS * part:,} linhas)...')
        else:
            print(f'  Lendo primeira parte do arquivo...')
        
        try:
            estabelecimento = pd.read_csv(filepath_or_buffer=extracted_file_path,
                                  sep=';',
                                  nrows=NROWS,
                                  skiprows=NROWS * part,
                                  header=None,
                                  dtype=estabelecimento_dtypes,
                                  encoding='latin-1',
            )
            print(f'  ✓ Arquivo lido: {len(estabelecimento):,} registros carregados')
        except KeyboardInterrupt:
            print(f'\n\n⚠ Processo interrompido pelo usuário durante leitura do arquivo: {filename}')
            print('O arquivo não foi marcado como processado e será reprocessado na próxima execução.')
            raise
        except Exception as e:
            print(f'  ⚠ Erro ao ler arquivo: {e}')
            raise

        # Tratamento do arquivo antes de inserir na base:
        print(f'  Processando dados (renomear colunas)...')
        # Não precisa reset_index, vamos renomear diretamente
        # estabelecimento = estabelecimento.reset_index()
        # del estabelecimento['index']
        gc.collect()

        # Renomear colunas diretamente
        print(f'  Renomeando colunas...')
        estabelecimento.columns = ['base_cnpj',
                                   'cnpj_order',
                                   'cnpj_check_digit',
                                   'matrix_branch_identifier',
                                   'trade_name',
                                   'registration_status',
                                   'registration_status_date',
                                   'registration_status_reason_code',
                                   'foreign_city_name',
                                   'country_code',
                                   'activity_start_date',
                                   'main_cnae_code',
                                   'secondary_cnae_codes',
                                   'street_type',
                                   'street_name',
                                   'number',
                                   'complement',
                                   'neighborhood',
                                   'zip_code',
                                   'state_code',
                                   'city_code',
                                   'area_code_1',
                                   'phone_1',
                                   'area_code_2',
                                   'phone_2',
                                   'fax_area_code',
                                   'fax_number',
                                   'email',
                                   'special_situation',
                                   'special_situation_date']
        
        # Corrigir tipos de dados para preservar zeros à esquerda e garantir que email seja string
        # area_code_1 precisa ser string e limitado a 2 caracteres (VARCHAR(2) no banco)
        def format_area_code(x):
            if pd.isna(x) or str(x).lower() == 'nan' or str(x).strip() == '':
                return None
            x_str = str(x).strip()
            # Se for número, pegar apenas os últimos 2 dígitos e preencher com zero à esquerda se necessário
            if x_str.isdigit():
                # Pegar últimos 2 dígitos e garantir 2 caracteres com zero à esquerda
                x_str = x_str[-2:].zfill(2)
            # Limitar a 2 caracteres (truncar se necessário)
            return x_str[:2] if len(x_str) > 0 else None
        
        estabelecimento['area_code_1'] = estabelecimento['area_code_1'].apply(format_area_code)
        estabelecimento['area_code_2'] = estabelecimento['area_code_2'].apply(format_area_code)
        estabelecimento['fax_area_code'] = estabelecimento['fax_area_code'].apply(format_area_code)
        
        # Garantir que email seja string e não seja convertido para número
        estabelecimento['email'] = estabelecimento['email'].astype(str)
        estabelecimento['email'] = estabelecimento['email'].replace('nan', None)
        estabelecimento['email'] = estabelecimento['email'].apply(lambda x: None if pd.isna(x) or str(x).lower() == 'nan' or str(x).strip() == '' else str(x).strip())

        # Converter colunas de data de formato inteiro (YYYYMMDD) para DATE
        print(f'  Convertendo datas...')
        estabelecimento['registration_status_date'] = estabelecimento['registration_status_date'].apply(convert_date_int_to_date)
        estabelecimento['activity_start_date'] = estabelecimento['activity_start_date'].apply(convert_date_int_to_date)
        estabelecimento['special_situation_date'] = estabelecimento['special_situation_date'].apply(convert_date_int_to_date)
        print(f'  ✓ Datas convertidas')

        # Gravar dados no banco:
        # estabelecimento
        # Calcular porcentagem aproximada (assumindo que cada parte tem NROWS registros)
        # Para a última parte, não sabemos o total exato, então não mostramos porcentagem
        if len(estabelecimento) == NROWS:
            # Estimar total de partes baseado no tamanho do arquivo
            file_size = os.path.getsize(extracted_file_path) if os.path.exists(extracted_file_path) else None
            if file_size:
                # Estimativa grosseira: assumir ~200 bytes por registro
                estimated_total_parts = max(1, int((file_size / (200 * NROWS)) + 1))
                percentage = min(100, int(((part + 1) / estimated_total_parts) * 100))
                print(f'  Inserindo {len(estabelecimento)} registros (parte {part + 1}, ~{percentage}%) na tabela establishments...')
            else:
                print(f'  Inserindo {len(estabelecimento)} registros (parte {part + 1}) na tabela establishments...')
        else:
            print(f'  Inserindo {len(estabelecimento)} registros (parte final) na tabela establishments...')
        to_sql(estabelecimento, name='establishments', con=engine, if_exists='append', index=False)
        print(f'  ✓ Parte {part + 1} do arquivo {filename} inserida com sucesso!')
        if len(estabelecimento) == NROWS:
            part += 1
        else:
            # Última parte, marcar como processado
            file_size = os.path.getsize(extracted_file_path) if os.path.exists(extracted_file_path) else None
            # Contar registros totais seria custoso, então não contamos
            mark_file_as_processed(filename, 'establishments', file_size, None)
            processed_count_est += 1
            break

try:
    del estabelecimento
except:
    pass
print('✓ Arquivos de estabelecimento finalizados!')
print(f'  - Processados: {processed_count_est}')
print(f'  - Já processados (pulados): {skipped_count_est}')
estabelecimento_insert_end = time.time()
estabelecimento_Tempo_insert = round((estabelecimento_insert_end - estabelecimento_insert_start))
print(f'Tempo de execução do processo de estabelecimento: {estabelecimento_Tempo_insert} segundos ({estabelecimento_Tempo_insert//60} minutos)')

# Atualizar tabela companies com dados de situação cadastral e data de abertura do estabelecimento matriz
print('='*60)
print('ATUALIZANDO TABELA COMPANIES COM DADOS DO ESTABELECIMENTO MATRIZ')
print('='*60)
print('Atualizando situação cadastral e data de abertura...')
try:
    cur.execute('''
        UPDATE companies c
        SET 
            registration_status = e.registration_status,
            registration_status_date = e.registration_status_date,
            activity_start_date = e.activity_start_date
        FROM establishments e
        WHERE c.base_cnpj = e.base_cnpj
        AND e.matrix_branch_identifier = 1
        AND (c.registration_status IS NULL OR c.registration_status_date IS NULL OR c.activity_start_date IS NULL);
    ''')
    updated_rows = cur.rowcount
    conn.commit()
    print(f'✓ {updated_rows:,} empresas atualizadas com situação cadastral e data de abertura')
except Exception as e:
    print(f'⚠ Erro ao atualizar companies: {e}')
    conn.rollback()

#%%
# Arquivos de socios:
socios_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DE SÓCIOS')
print('='*60)

# Verificar se precisa limpar tabela
arquivos_nao_processados_soc = [f for f in arquivos_socios if not is_file_processed(f, 'partners')]
if len(arquivos_nao_processados_soc) < len(arquivos_socios):
    print(f'Arquivos já processados: {len(arquivos_socios) - len(arquivos_nao_processados_soc)}/{len(arquivos_socios)}')
    if len(arquivos_nao_processados_soc) == 0:
        print('Todos os arquivos de sócios já foram processados. Pulando...')
    else:
        safe_truncate_table('partners')
else:
    safe_truncate_table('partners')

processed_count_soc = 0
skipped_count_soc = 0
for e in range(0, len(arquivos_socios)):
    filename = arquivos_socios[e]
    
    # Verificar se arquivo já foi processado
    if is_file_processed(filename, 'partners'):
        print(f'Arquivo já processado (pulando): {filename}')
        skipped_count_soc += 1
        continue
    
    print('Trabalhando no arquivo: '+filename+' [...]')
    try:
        del socios
    except:
        pass

    socios_dtypes = {0: object, 1: 'Int32', 2: object, 3: object, 4: 'Int32', 5: 'Int32', 6: 'Int32',
                     7: object, 8: object, 9: 'Int32', 10: 'Int32'}
    extracted_file_path = os.path.join(extracted_files, arquivos_socios[e])
    socios = pd.read_csv(filepath_or_buffer=extracted_file_path,
                          sep=';',
                          #nrows=100,
                          skiprows=0,
                          header=None,
                          dtype=socios_dtypes,
                          encoding='latin-1',
    )

    # Tratamento do arquivo antes de inserir na base:
    # Não precisa reset_index, vamos renomear diretamente
    # socios = socios.reset_index()
    # del socios['index']

    # Renomear colunas diretamente
    socios.columns = ['base_cnpj',
                      'partner_identifier',
                      'partner_name_or_company_name',
                      'partner_cpf_cnpj',
                      'partner_qualification_code',
                      'partnership_start_date',
                      'country_code',
                      'legal_representative_cpf',
                      'representative_name',
                      'legal_representative_qualification_code',
                      'age_range_code']

    # Converter colunas de data de formato inteiro (YYYYMMDD) para DATE
    socios['partnership_start_date'] = socios['partnership_start_date'].apply(convert_date_int_to_date)

    # Gravar dados no banco:
    # socios
    file_size = os.path.getsize(extracted_file_path) if os.path.exists(extracted_file_path) else None
    to_sql(socios, name='partners', con=engine, if_exists='append', index=False)
    mark_file_as_processed(filename, 'partners', file_size, len(socios))
    processed_count_soc += 1
    print('Arquivo ' + filename + ' inserido com sucesso no banco de dados!')

try:
    del socios
except:
    pass
print('✓ Arquivos de sócios finalizados!')
print(f'  - Processados: {processed_count_soc}')
print(f'  - Já processados (pulados): {skipped_count_soc}')
socios_insert_end = time.time()
socios_Tempo_insert = round((socios_insert_end - socios_insert_start))
print(f'Tempo de execução do processo de sócios: {socios_Tempo_insert} segundos ({socios_Tempo_insert//60} minutos)')

#%%
# Arquivos de simples:
simples_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DO SIMPLES NACIONAL')
print('='*60)

# Verificar se precisa limpar tabela
arquivos_nao_processados_sim = [f for f in arquivos_simples if not is_file_processed(f, 'simple_national')]
if len(arquivos_nao_processados_sim) < len(arquivos_simples):
    print(f'Arquivos já processados: {len(arquivos_simples) - len(arquivos_nao_processados_sim)}/{len(arquivos_simples)}')
    if len(arquivos_nao_processados_sim) == 0:
        print('Todos os arquivos do Simples já foram processados. Pulando...')
    else:
        safe_truncate_table('simple_national')
else:
    safe_truncate_table('simple_national')

processed_count_sim = 0
skipped_count_sim = 0
for e in range(0, len(arquivos_simples)):
    filename = arquivos_simples[e]
    
    # Verificar se arquivo já foi processado
    if is_file_processed(filename, 'simple_national'):
        print(f'Arquivo já processado (pulando): {filename}')
        skipped_count_sim += 1
        continue
    print('Trabalhando no arquivo: '+arquivos_simples[e]+' [...]')
    try:
        del simples
    except:
        pass

    # Verificar tamanho do arquivo:
    print('Lendo o arquivo ' + arquivos_simples[e]+' [...]')
    simples_dtypes = ({0: object, 1: object, 2: 'Int32', 3: 'Int32', 4: object, 5: 'Int32', 6: 'Int32'})
    extracted_file_path = os.path.join(extracted_files, arquivos_simples[e])

    simples_lenght = sum(1 for line in open(extracted_file_path, "r"))
    print('Linhas no arquivo do Simples '+ arquivos_simples[e] +': '+str(simples_lenght))

    tamanho_das_partes = 1000000 # Registros por carga
    partes = round(simples_lenght / tamanho_das_partes)
    nrows = tamanho_das_partes
    skiprows = 0

    print('Este arquivo será dividido em ' + str(partes) + ' partes para inserção no banco de dados')

    for i in range(0, partes):
        print('Iniciando a parte ' + str(i+1) + ' [...]')
        simples = pd.DataFrame(columns=[1,2,3,4,5,6])

        simples = pd.read_csv(filepath_or_buffer=extracted_file_path,
                              sep=';',
                              nrows=nrows,
                              skiprows=skiprows,
                              header=None,
                              dtype=simples_dtypes,
                              encoding='latin-1',
        )

        # Tratamento do arquivo antes de inserir na base:
        # Não precisa reset_index, vamos renomear diretamente
        # simples = simples.reset_index()
        # del simples['index']

        # Renomear colunas diretamente
        simples.columns = ['base_cnpj',
                           'opted_for_simple_national',
                           'simple_national_option_date',
                           'simple_national_exclusion_date',
                           'opted_for_mei',
                           'mei_option_date',
                           'mei_exclusion_date']

        # Converter colunas de data de formato inteiro (YYYYMMDD) para DATE
        simples['simple_national_option_date'] = simples['simple_national_option_date'].apply(convert_date_int_to_date)
        simples['simple_national_exclusion_date'] = simples['simple_national_exclusion_date'].apply(convert_date_int_to_date)
        simples['mei_option_date'] = simples['mei_option_date'].apply(convert_date_int_to_date)
        simples['mei_exclusion_date'] = simples['mei_exclusion_date'].apply(convert_date_int_to_date)

        skiprows = skiprows+nrows

        # Gravar dados no banco:
        # simples
        to_sql(simples, name='simple_national', con=engine, if_exists='append', index=False)
        print('Arquivo ' + filename + ' inserido com sucesso no banco de dados! - Parte '+ str(i+1))

        try:
            del simples
        except:
            pass
    
    # Marcar como processado após todas as partes
    file_size = os.path.getsize(extracted_file_path) if os.path.exists(extracted_file_path) else None
    mark_file_as_processed(filename, 'simple_national', file_size, simples_lenght)
    processed_count_sim += 1

try:
    del simples
except:
    pass

print('✓ Arquivos do simples finalizados!')
print(f'  - Processados: {processed_count_sim}')
print(f'  - Já processados (pulados): {skipped_count_sim}')
simples_insert_end = time.time()
simples_Tempo_insert = round((simples_insert_end - simples_insert_start))
print(f'Tempo de execução do processo do Simples Nacional: {simples_Tempo_insert} segundos ({simples_Tempo_insert//60} minutos)')

#%%
# Arquivos de cnae:
cnae_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DE CNAE')
print('='*60)

# Verificar se precisa limpar tabela
arquivos_nao_processados_cnae = [f for f in arquivos_cnae if not is_file_processed(f, 'cnae_codes')]
if len(arquivos_nao_processados_cnae) < len(arquivos_cnae):
    if len(arquivos_nao_processados_cnae) == 0:
        print('Todos os arquivos de CNAE já foram processados. Pulando...')
    else:
        safe_truncate_table('cnae_codes')
else:
    safe_truncate_table('cnae_codes')
processed_count_cnae = 0
skipped_count_cnae = 0

for e in range(0, len(arquivos_cnae)):
    filename = arquivos_cnae[e]
    if is_file_processed(filename, 'cnae_codes'):
        print(f'Arquivo já processado (pulando): {filename}')
        skipped_count_cnae += 1
        continue
    
    print('Trabalhando no arquivo: '+filename+' [...]')
    try:
        del cnae
    except:
        pass

    extracted_file_path = os.path.join(extracted_files, filename)
    cnae = pd.DataFrame(columns=[1,2])
    cnae = pd.read_csv(filepath_or_buffer=extracted_file_path, sep=';', skiprows=0, header=None, dtype='object', encoding='latin-1')

    # Tratamento do arquivo antes de inserir na base:
    # Não precisa reset_index, vamos renomear diretamente
    # cnae = cnae.reset_index()
    # del cnae['index']

    # Renomear colunas diretamente
    cnae.columns = ['code', 'description']

    # Gravar dados no banco:
    # cnae
    file_size = os.path.getsize(extracted_file_path) if os.path.exists(extracted_file_path) else None
    to_sql(cnae, name='cnae_codes', con=engine, if_exists='append', index=False)
    mark_file_as_processed(filename, 'cnae_codes', file_size, len(cnae))
    processed_count_cnae += 1
    print('Arquivo ' + filename + ' inserido com sucesso no banco de dados!')

try:
    del cnae
except:
    pass
print('✓ Arquivos de cnae finalizados!')
print(f'  - Processados: {processed_count_cnae}')
print(f'  - Já processados (pulados): {skipped_count_cnae}')
cnae_insert_end = time.time()
cnae_Tempo_insert = round((cnae_insert_end - cnae_insert_start))
print(f'Tempo de execução do processo de cnae: {cnae_Tempo_insert} segundos')

#%%
# Arquivos de moti:
moti_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DE MOTIVOS DA SITUAÇÃO CADASTRAL')
print('='*60)

# Verificar se precisa limpar tabela
arquivos_nao_processados_moti = [f for f in arquivos_moti if not is_file_processed(f, 'registration_status_reasons')]
if len(arquivos_nao_processados_moti) < len(arquivos_moti):
    if len(arquivos_nao_processados_moti) == 0:
        print('Todos os arquivos de motivos já foram processados. Pulando...')
    else:
        safe_truncate_table('registration_status_reasons')
else:
    safe_truncate_table('registration_status_reasons')
processed_count_moti = 0
skipped_count_moti = 0

for e in range(0, len(arquivos_moti)):
    filename = arquivos_moti[e]
    if is_file_processed(filename, 'registration_status_reasons'):
        print(f'Arquivo já processado (pulando): {filename}')
        skipped_count_moti += 1
        continue
    
    print('Trabalhando no arquivo: '+filename+' [...]')
    try:
        del moti
    except:
        pass

    moti_dtypes = ({0: 'Int32', 1: object})
    extracted_file_path = os.path.join(extracted_files, filename)
    moti = pd.read_csv(filepath_or_buffer=extracted_file_path, sep=';', skiprows=0, header=None, dtype=moti_dtypes, encoding='latin-1')

    # Tratamento do arquivo antes de inserir na base:
    # Não precisa reset_index, vamos renomear diretamente
    # moti = moti.reset_index()
    # del moti['index']

    # Renomear colunas diretamente
    moti.columns = ['code', 'description']

    # Gravar dados no banco:
    # moti
    file_size = os.path.getsize(extracted_file_path) if os.path.exists(extracted_file_path) else None
    to_sql(moti, name='registration_status_reasons', con=engine, if_exists='append', index=False)
    mark_file_as_processed(filename, 'registration_status_reasons', file_size, len(moti))
    processed_count_moti += 1
    print('Arquivo ' + filename + ' inserido com sucesso no banco de dados!')

try:
    del moti
except:
    pass
print('✓ Arquivos de motivos finalizados!')
print(f'  - Processados: {processed_count_moti}')
print(f'  - Já processados (pulados): {skipped_count_moti}')
moti_insert_end = time.time()
moti_Tempo_insert = round((moti_insert_end - moti_insert_start))
print(f'Tempo de execução do processo de motivos: {moti_Tempo_insert} segundos')

#%%
# Arquivos de munic:
munic_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DE MUNICÍPIOS')
print('='*60)

# Verificar se precisa limpar tabela
arquivos_nao_processados_munic = [f for f in arquivos_munic if not is_file_processed(f, 'municipalities')]
if len(arquivos_nao_processados_munic) < len(arquivos_munic):
    if len(arquivos_nao_processados_munic) == 0:
        print('Todos os arquivos de municípios já foram processados. Pulando...')
    else:
        safe_truncate_table('municipalities')
else:
    safe_truncate_table('municipalities')
processed_count_munic = 0
skipped_count_munic = 0

for e in range(0, len(arquivos_munic)):
    filename = arquivos_munic[e]
    if is_file_processed(filename, 'municipalities'):
        print(f'Arquivo já processado (pulando): {filename}')
        skipped_count_munic += 1
        continue
    
    print('Trabalhando no arquivo: '+filename+' [...]')
    try:
        del munic
    except:
        pass

    munic_dtypes = ({0: 'Int32', 1: object})
    extracted_file_path = os.path.join(extracted_files, filename)
    munic = pd.read_csv(filepath_or_buffer=extracted_file_path, sep=';', skiprows=0, header=None, dtype=munic_dtypes, encoding='latin-1')

    # Tratamento do arquivo antes de inserir na base:
    # Não precisa reset_index, vamos renomear diretamente
    # munic = munic.reset_index()
    # del munic['index']

    # Renomear colunas diretamente
    munic.columns = ['code', 'description']

    # Gravar dados no banco:
    # munic
    file_size = os.path.getsize(extracted_file_path) if os.path.exists(extracted_file_path) else None
    to_sql(munic, name='municipalities', con=engine, if_exists='append', index=False)
    mark_file_as_processed(filename, 'municipalities', file_size, len(munic))
    processed_count_munic += 1
    print('Arquivo ' + filename + ' inserido com sucesso no banco de dados!')

try:
    del munic
except:
    pass
print('✓ Arquivos de municípios finalizados!')
print(f'  - Processados: {processed_count_munic}')
print(f'  - Já processados (pulados): {skipped_count_munic}')
munic_insert_end = time.time()
munic_Tempo_insert = round((munic_insert_end - munic_insert_start))
print(f'Tempo de execução do processo de municípios: {munic_Tempo_insert} segundos')

#%%
# Arquivos de natju:
natju_insert_start = time.time()
print("""
#################################
## Arquivos de natureza jurídica:
#################################
""")

# Verificar se precisa limpar tabela
arquivos_nao_processados_natju = [f for f in arquivos_natju if not is_file_processed(f, 'legal_natures')]
if len(arquivos_nao_processados_natju) < len(arquivos_natju):
    if len(arquivos_nao_processados_natju) == 0:
        print('Todos os arquivos de natureza jurídica já foram processados. Pulando...')
    else:
        safe_truncate_table('legal_natures')
else:
    safe_truncate_table('legal_natures')
processed_count_natju = 0
skipped_count_natju = 0

for e in range(0, len(arquivos_natju)):
    filename = arquivos_natju[e]
    if is_file_processed(filename, 'legal_natures'):
        print(f'Arquivo já processado (pulando): {filename}')
        skipped_count_natju += 1
        continue
    
    print('Trabalhando no arquivo: '+filename+' [...]')
    try:
        del natju
    except:
        pass

    natju_dtypes = ({0: 'Int32', 1: object})
    extracted_file_path = os.path.join(extracted_files, filename)
    natju = pd.read_csv(filepath_or_buffer=extracted_file_path, sep=';', skiprows=0, header=None, dtype=natju_dtypes, encoding='latin-1')

    # Tratamento do arquivo antes de inserir na base:
    # Não precisa reset_index, vamos renomear diretamente
    # natju = natju.reset_index()
    # del natju['index']

    # Renomear colunas diretamente
    natju.columns = ['code', 'description']

    # Gravar dados no banco:
    # natju
    file_size = os.path.getsize(extracted_file_path) if os.path.exists(extracted_file_path) else None
    to_sql(natju, name='legal_natures', con=engine, if_exists='append', index=False)
    mark_file_as_processed(filename, 'legal_natures', file_size, len(natju))
    processed_count_natju += 1
    print('Arquivo ' + filename + ' inserido com sucesso no banco de dados!')

try:
    del natju
except:
    pass
print('Arquivos de natju finalizados!')
print(f'  - Processados: {processed_count_natju}')
print(f'  - Já processados (pulados): {skipped_count_natju}')
natju_insert_end = time.time()
natju_Tempo_insert = round((natju_insert_end - natju_insert_start))
print('Tempo de execução do processo de natureza jurídica (em segundos): ' + str(natju_Tempo_insert))

#%%
# Arquivos de pais:
pais_insert_start = time.time()
print("""
######################
## Arquivos de país:
######################
""")

# Verificar se precisa limpar tabela
arquivos_nao_processados_pais = [f for f in arquivos_pais if not is_file_processed(f, 'countries')]
if len(arquivos_nao_processados_pais) < len(arquivos_pais):
    if len(arquivos_nao_processados_pais) == 0:
        print('Todos os arquivos de países já foram processados. Pulando...')
    else:
        safe_truncate_table('countries')
else:
    safe_truncate_table('countries')
processed_count_pais = 0
skipped_count_pais = 0

for e in range(0, len(arquivos_pais)):
    filename = arquivos_pais[e]
    if is_file_processed(filename, 'countries'):
        print(f'Arquivo já processado (pulando): {filename}')
        skipped_count_pais += 1
        continue
    
    print('Trabalhando no arquivo: '+filename+' [...]')
    try:
        del pais
    except:
        pass

    pais_dtypes = ({0: 'Int32', 1: object})
    extracted_file_path = os.path.join(extracted_files, filename)
    pais = pd.read_csv(filepath_or_buffer=extracted_file_path, sep=';', skiprows=0, header=None, dtype=pais_dtypes, encoding='latin-1')

    # Tratamento do arquivo antes de inserir na base:
    # Não precisa reset_index, vamos renomear diretamente
    # pais = pais.reset_index()
    # del pais['index']

    # Renomear colunas diretamente
    pais.columns = ['code', 'description']

    # Gravar dados no banco:
    # pais
    file_size = os.path.getsize(extracted_file_path) if os.path.exists(extracted_file_path) else None
    to_sql(pais, name='countries', con=engine, if_exists='append', index=False)
    mark_file_as_processed(filename, 'countries', file_size, len(pais))
    processed_count_pais += 1
    print('Arquivo ' + filename + ' inserido com sucesso no banco de dados!')

try:
    del pais
except:
    pass
print('Arquivos de pais finalizados!')
print(f'  - Processados: {processed_count_pais}')
print(f'  - Já processados (pulados): {skipped_count_pais}')
pais_insert_end = time.time()
pais_Tempo_insert = round((pais_insert_end - pais_insert_start))
print('Tempo de execução do processo de país (em segundos): ' + str(pais_Tempo_insert))

#%%
# Arquivos de qualificação de sócios:
quals_insert_start = time.time()
print("""
######################################
## Arquivos de qualificação de sócios:
######################################
""")

# Verificar se precisa limpar tabela
arquivos_nao_processados_quals = [f for f in arquivos_quals if not is_file_processed(f, 'qualifications')]
if len(arquivos_nao_processados_quals) < len(arquivos_quals):
    if len(arquivos_nao_processados_quals) == 0:
        print('Todos os arquivos de qualificações já foram processados. Pulando...')
    else:
        safe_truncate_table('qualifications')
else:
    safe_truncate_table('qualifications')
processed_count_quals = 0
skipped_count_quals = 0

for e in range(0, len(arquivos_quals)):
    filename = arquivos_quals[e]
    if is_file_processed(filename, 'qualifications'):
        print(f'Arquivo já processado (pulando): {filename}')
        skipped_count_quals += 1
        continue
    
    print('Trabalhando no arquivo: '+filename+' [...]')
    try:
        del quals
    except:
        pass

    quals_dtypes = ({0: 'Int32', 1: object})
    extracted_file_path = os.path.join(extracted_files, filename)
    quals = pd.read_csv(filepath_or_buffer=extracted_file_path, sep=';', skiprows=0, header=None, dtype=quals_dtypes, encoding='latin-1')

    # Tratamento do arquivo antes de inserir na base:
    # Não precisa reset_index, vamos renomear diretamente
    # quals = quals.reset_index()
    # del quals['index']

    # Renomear colunas diretamente
    quals.columns = ['code', 'description']

    # Gravar dados no banco:
    # quals
    file_size = os.path.getsize(extracted_file_path) if os.path.exists(extracted_file_path) else None
    to_sql(quals, name='qualifications', con=engine, if_exists='append', index=False)
    mark_file_as_processed(filename, 'qualifications', file_size, len(quals))
    processed_count_quals += 1
    print('Arquivo ' + filename + ' inserido com sucesso no banco de dados!')

try:
    del quals
except:
    pass
print('Arquivos de quals finalizados!')
print(f'  - Processados: {processed_count_quals}')
print(f'  - Já processados (pulados): {skipped_count_quals}')
quals_insert_end = time.time()
quals_Tempo_insert = round((quals_insert_end - quals_insert_start))
print('Tempo de execução do processo de qualificação de sócios (em segundos): ' + str(quals_Tempo_insert))

#%%
insert_end = time.time()
Tempo_insert = round((insert_end - insert_start))

print('='*60)
print('PROCESSO DE CARGA DOS ARQUIVOS FINALIZADO!')
print('='*60)
print(f'Tempo total de execução: {Tempo_insert} segundos ({Tempo_insert//60} minutos, {Tempo_insert//3600} horas)')

# ###############################
# Tamanho dos arquivos:
# empresa = 45.811.638
# estabelecimento = 48.421.619
# socios = 20.426.417
# simples = 27.893.923
# ###############################

#%%
# Criar índices na base de dados:
index_start = time.time()
print('='*60)
print('CRIANDO/VERIFICANDO ÍNDICES NA BASE DE DADOS')
print('='*60)
# Índices já foram criados pelo schema.sql, apenas verifica se existem
cur.execute("""
CREATE INDEX IF NOT EXISTS idx_companies_base_cnpj ON companies(base_cnpj);
CREATE INDEX IF NOT EXISTS idx_establishments_base_cnpj ON establishments(base_cnpj);
CREATE INDEX IF NOT EXISTS idx_partners_base_cnpj ON partners(base_cnpj);
CREATE INDEX IF NOT EXISTS idx_simple_national_base_cnpj ON simple_national(base_cnpj);
""")
conn.commit()
print('✓ Índices criados/verificados nas tabelas para a coluna `base_cnpj`:')
print('  - companies')
print('  - establishments')
print('  - partners')
print('  - simple_national')
index_end = time.time()
index_time = round(index_end - index_start)
print(f'Tempo para criar os índices: {index_time} segundos')

#%%
print('='*60)
print('PROCESSO 100% FINALIZADO!')
print('='*60)
print('Você já pode usar seus dados no banco de dados!')
print('='*60)