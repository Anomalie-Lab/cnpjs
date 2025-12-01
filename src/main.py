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


print('='*60)
print('Iniciando processo ETL - Dados CNPJ Receita Federal')
print('='*60)

current_path = pathlib.Path().resolve()
dotenv_path = os.path.join(current_path, '.env')
if not os.path.isfile(dotenv_path):
    print('Arquivo .env não encontrado no diretório atual')
    print('Especifique o local do seu arquivo de configuração ".env". Por exemplo: C:\\...\\cnpj\\src')
    local_env = input()
    dotenv_path = os.path.join(local_env, '.env')
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

i_l = 0
for l in Files:
    try:
        i_l += 1
        print(f'[{i_l}/{len(Files)}] Descompactando: {l}')
        full_path = os.path.join(output_files, l)
        if not os.path.exists(full_path):
            print(f'  Arquivo não encontrado: {full_path}')
            continue
        with zipfile.ZipFile(full_path, 'r') as zip_ref:
            zip_ref.extractall(extracted_files)
        print(f'  ✓ Extração concluída: {l}')
    except Exception as e:
        print(f'  ✗ Erro ao extrair {l}: {e}')

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
    print('Verifique se o Docker está rodando: docker compose up -d')
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
            skip_next = False
            for line in lines:
                stripped = line.strip()
                # Pula CREATE DATABASE e \c (comandos CLI)
                if 'CREATE DATABASE' in stripped.upper() or stripped.startswith('\\c'):
                    continue
                # Remove comentários de linha única
                if stripped.startswith('--'):
                    continue
                cleaned_lines.append(line)
            
            schema_sql = '\n'.join(cleaned_lines)
            # Divide em comandos por ponto e vírgula
            commands = []
            current_command = []
            for line in schema_sql.split('\n'):
                stripped = line.strip()
                if stripped:
                    current_command.append(line)
                    if stripped.endswith(';'):
                        cmd = '\n'.join(current_command).strip()
                        if cmd and not cmd.startswith('--'):
                            commands.append(cmd.rstrip(';'))
                        current_command = []
            
            # Executa cada comando
            for command in commands:
                if command and command.strip():
                    try:
                        cur.execute(command)
                    except Exception as e:
                        error_msg = str(e).lower()
                        # Ignora erros de tabela/índice já existe
                        if 'already exists' not in error_msg:
                            print(f'Aviso ao executar comando: {str(e)[:150]}')
            conn.commit()
        print('✓ Schema criado com sucesso!')
    else:
        print('Arquivo schema.sql não encontrado. Criando tabelas dinamicamente...')

create_schema()

# #%%
# # Arquivos de empresa:
empresa_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DE EMPRESA')
print('='*60)

# Limpar dados antes do insert (tabela já existe pelo schema)
cur.execute('TRUNCATE TABLE "companies" CASCADE;')
conn.commit()

print(f'Total de arquivos de empresa para processar: {len(arquivos_empresa)}')
for e in range(0, len(arquivos_empresa)):
    print(f'[{e+1}/{len(arquivos_empresa)}] Processando arquivo: {arquivos_empresa[e]}')
    try:
        del empresa
    except:
        pass

    #empresa = pd.DataFrame(columns=[0, 1, 2, 3, 4, 5, 6])
    empresa_dtypes = {0: object, 1: object, 2: 'Int32', 3: 'Int32', 4: object, 5: 'Int32', 6: object}
    extracted_file_path = os.path.join(extracted_files, arquivos_empresa[e])

    empresa = pd.read_csv(filepath_or_buffer=extracted_file_path,
                          sep=';',
                          #nrows=100,
                          skiprows=0,
                          header=None,
                          dtype=empresa_dtypes,
                          encoding='latin-1',
    )

    # Tratamento do arquivo antes de inserir na base:
    empresa = empresa.reset_index()
    del empresa['index']

    # Renomear colunas
    empresa.columns = ['base_cnpj', 'company_name', 'legal_nature_code', 'responsible_qualification_code', 'capital', 'company_size_code', 'responsible_federative_entity']

    # Replace "," por "."
    empresa['capital'] = empresa['capital'].apply(lambda x: x.replace(',','.'))
    empresa['capital'] = empresa['capital'].astype(float)

    # Gravar dados no banco:
    # Empresa
    print(f'  Inserindo {len(empresa)} registros na tabela companies...')
    to_sql(empresa, name='companies', con=engine, if_exists='append', index=False)
    print(f'  ✓ Arquivo {arquivos_empresa[e]} inserido com sucesso!')

try:
    del empresa
except:
    pass
print('✓ Arquivos de empresa finalizados!')
empresa_insert_end = time.time()
empresa_Tempo_insert = round((empresa_insert_end - empresa_insert_start))
print(f'Tempo de execução do processo de empresa: {empresa_Tempo_insert} segundos ({empresa_Tempo_insert//60} minutos)')

#%%
# Arquivos de estabelecimento:
estabelecimento_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DE ESTABELECIMENTO')
print('='*60)

# Limpar dados antes do insert (tabela já existe pelo schema)
cur.execute('TRUNCATE TABLE "establishments" CASCADE;')
conn.commit()

print(f'Total de arquivos de estabelecimento para processar: {len(arquivos_estabelecimento)}')
for e in range(0, len(arquivos_estabelecimento)):
    print(f'[{e+1}/{len(arquivos_estabelecimento)}] Processando arquivo: {arquivos_estabelecimento[e]}')
    try:
        del estabelecimento
        gc.collect()
    except:
        pass

    # estabelecimento = pd.DataFrame(columns=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28])
    estabelecimento_dtypes = {0: object, 1: object, 2: object, 3: 'Int32', 4: object, 5: 'Int32', 6: 'Int32',
                              7: 'Int32', 8: object, 9: object, 10: 'Int32', 11: 'Int32', 12: object, 13: object,
                              14: object, 15: object, 16: object, 17: object, 18: object, 19: object,
                              20: 'Int32', 21: object, 22: object, 23: object, 24: object, 25: object,
                              26: object, 27: object, 28: object, 29: 'Int32'}
    extracted_file_path = os.path.join(extracted_files, arquivos_estabelecimento[e])

    NROWS = 2000000
    part = 0
    while True:
        estabelecimento = pd.read_csv(filepath_or_buffer=extracted_file_path,
                              sep=';',
                              nrows=NROWS,
                              skiprows=NROWS * part,
                              header=None,
                              dtype=estabelecimento_dtypes,
                              encoding='latin-1',
        )

        # Tratamento do arquivo antes de inserir na base:
        estabelecimento = estabelecimento.reset_index()
        del estabelecimento['index']
        gc.collect()

        # Renomear colunas
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

        # Gravar dados no banco:
        # estabelecimento
        print(f'  Inserindo {len(estabelecimento)} registros (parte {part}) na tabela establishments...')
        to_sql(estabelecimento, name='establishments', con=engine, if_exists='append', index=False)
        print(f'  ✓ Parte {part} do arquivo {arquivos_estabelecimento[e]} inserida com sucesso!')
        if len(estabelecimento) == NROWS:
            part += 1
        else:
            break

try:
    del estabelecimento
except:
    pass
print('✓ Arquivos de estabelecimento finalizados!')
estabelecimento_insert_end = time.time()
estabelecimento_Tempo_insert = round((estabelecimento_insert_end - estabelecimento_insert_start))
print(f'Tempo de execução do processo de estabelecimento: {estabelecimento_Tempo_insert} segundos ({estabelecimento_Tempo_insert//60} minutos)')

#%%
# Arquivos de socios:
socios_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DE SÓCIOS')
print('='*60)

# Limpar dados antes do insert (tabela já existe pelo schema)
cur.execute('TRUNCATE TABLE "partners" CASCADE;')
conn.commit()

for e in range(0, len(arquivos_socios)):
    print('Trabalhando no arquivo: '+arquivos_socios[e]+' [...]')
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
    socios = socios.reset_index()
    del socios['index']

    # Renomear colunas
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

    # Gravar dados no banco:
    # socios
    to_sql(socios, name='partners', con=engine, if_exists='append', index=False)
    print('Arquivo ' + arquivos_socios[e] + ' inserido com sucesso no banco de dados!')

try:
    del socios
except:
    pass
print('✓ Arquivos de sócios finalizados!')
socios_insert_end = time.time()
socios_Tempo_insert = round((socios_insert_end - socios_insert_start))
print(f'Tempo de execução do processo de sócios: {socios_Tempo_insert} segundos ({socios_Tempo_insert//60} minutos)')

#%%
# Arquivos de simples:
simples_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DO SIMPLES NACIONAL')
print('='*60)

# Limpar dados antes do insert (tabela já existe pelo schema)
cur.execute('TRUNCATE TABLE "simple_national" CASCADE;')
conn.commit()

for e in range(0, len(arquivos_simples)):
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
        simples = simples.reset_index()
        del simples['index']

        # Renomear colunas
        simples.columns = ['base_cnpj',
                           'opted_for_simple_national',
                           'simple_national_option_date',
                           'simple_national_exclusion_date',
                           'opted_for_mei',
                           'mei_option_date',
                           'mei_exclusion_date']

        skiprows = skiprows+nrows

        # Gravar dados no banco:
        # simples
        to_sql(simples, name='simple_national', con=engine, if_exists='append', index=False)
        print('Arquivo ' + arquivos_simples[e] + ' inserido com sucesso no banco de dados! - Parte '+ str(i+1))

        try:
            del simples
        except:
            pass

try:
    del simples
except:
    pass

print('✓ Arquivos do simples finalizados!')
simples_insert_end = time.time()
simples_Tempo_insert = round((simples_insert_end - simples_insert_start))
print(f'Tempo de execução do processo do Simples Nacional: {simples_Tempo_insert} segundos ({simples_Tempo_insert//60} minutos)')

#%%
# Arquivos de cnae:
cnae_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DE CNAE')
print('='*60)

# Limpar dados antes do insert (tabela já existe pelo schema)
cur.execute('TRUNCATE TABLE "cnae_codes" CASCADE;')
conn.commit()

for e in range(0, len(arquivos_cnae)):
    print('Trabalhando no arquivo: '+arquivos_cnae[e]+' [...]')
    try:
        del cnae
    except:
        pass

    extracted_file_path = os.path.join(extracted_files, arquivos_cnae[e])
    cnae = pd.DataFrame(columns=[1,2])
    cnae = pd.read_csv(filepath_or_buffer=extracted_file_path, sep=';', skiprows=0, header=None, dtype='object', encoding='latin-1')

    # Tratamento do arquivo antes de inserir na base:
    cnae = cnae.reset_index()
    del cnae['index']

    # Renomear colunas
    cnae.columns = ['code', 'description']

    # Gravar dados no banco:
    # cnae
    to_sql(cnae, name='cnae_codes', con=engine, if_exists='append', index=False)
    print('Arquivo ' + arquivos_cnae[e] + ' inserido com sucesso no banco de dados!')

try:
    del cnae
except:
    pass
print('✓ Arquivos de cnae finalizados!')
cnae_insert_end = time.time()
cnae_Tempo_insert = round((cnae_insert_end - cnae_insert_start))
print(f'Tempo de execução do processo de cnae: {cnae_Tempo_insert} segundos')

#%%
# Arquivos de moti:
moti_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DE MOTIVOS DA SITUAÇÃO CADASTRAL')
print('='*60)

# Limpar dados antes do insert (tabela já existe pelo schema)
cur.execute('TRUNCATE TABLE "registration_status_reasons" CASCADE;')
conn.commit()

for e in range(0, len(arquivos_moti)):
    print('Trabalhando no arquivo: '+arquivos_moti[e]+' [...]')
    try:
        del moti
    except:
        pass

    moti_dtypes = ({0: 'Int32', 1: object})
    extracted_file_path = os.path.join(extracted_files, arquivos_moti[e])
    moti = pd.read_csv(filepath_or_buffer=extracted_file_path, sep=';', skiprows=0, header=None, dtype=moti_dtypes, encoding='latin-1')

    # Tratamento do arquivo antes de inserir na base:
    moti = moti.reset_index()
    del moti['index']

    # Renomear colunas
    moti.columns = ['code', 'description']

    # Gravar dados no banco:
    # moti
    to_sql(moti, name='registration_status_reasons', con=engine, if_exists='append', index=False)
    print('Arquivo ' + arquivos_moti[e] + ' inserido com sucesso no banco de dados!')

try:
    del moti
except:
    pass
print('✓ Arquivos de motivos finalizados!')
moti_insert_end = time.time()
moti_Tempo_insert = round((moti_insert_end - moti_insert_start))
print(f'Tempo de execução do processo de motivos: {moti_Tempo_insert} segundos')

#%%
# Arquivos de munic:
munic_insert_start = time.time()
print('='*60)
print('PROCESSANDO ARQUIVOS DE MUNICÍPIOS')
print('='*60)

# Limpar dados antes do insert (tabela já existe pelo schema)
cur.execute('TRUNCATE TABLE "municipalities" CASCADE;')
conn.commit()

for e in range(0, len(arquivos_munic)):
    print('Trabalhando no arquivo: '+arquivos_munic[e]+' [...]')
    try:
        del munic
    except:
        pass

    munic_dtypes = ({0: 'Int32', 1: object})
    extracted_file_path = os.path.join(extracted_files, arquivos_munic[e])
    munic = pd.read_csv(filepath_or_buffer=extracted_file_path, sep=';', skiprows=0, header=None, dtype=munic_dtypes, encoding='latin-1')

    # Tratamento do arquivo antes de inserir na base:
    munic = munic.reset_index()
    del munic['index']

    # Renomear colunas
    munic.columns = ['code', 'description']

    # Gravar dados no banco:
    # munic
    to_sql(munic, name='municipalities', con=engine, if_exists='append', index=False)
    print('Arquivo ' + arquivos_munic[e] + ' inserido com sucesso no banco de dados!')

try:
    del munic
except:
    pass
print('✓ Arquivos de municípios finalizados!')
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

# Limpar dados antes do insert (tabela já existe pelo schema)
cur.execute('TRUNCATE TABLE "legal_natures" CASCADE;')
conn.commit()

for e in range(0, len(arquivos_natju)):
    print('Trabalhando no arquivo: '+arquivos_natju[e]+' [...]')
    try:
        del natju
    except:
        pass

    natju_dtypes = ({0: 'Int32', 1: object})
    extracted_file_path = os.path.join(extracted_files, arquivos_natju[e])
    natju = pd.read_csv(filepath_or_buffer=extracted_file_path, sep=';', skiprows=0, header=None, dtype=natju_dtypes, encoding='latin-1')

    # Tratamento do arquivo antes de inserir na base:
    natju = natju.reset_index()
    del natju['index']

    # Renomear colunas
    natju.columns = ['code', 'description']

    # Gravar dados no banco:
    # natju
    to_sql(natju, name='legal_natures', con=engine, if_exists='append', index=False)
    print('Arquivo ' + arquivos_natju[e] + ' inserido com sucesso no banco de dados!')

try:
    del natju
except:
    pass
print('Arquivos de natju finalizados!')
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

# Limpar dados antes do insert (tabela já existe pelo schema)
cur.execute('TRUNCATE TABLE "countries" CASCADE;')
conn.commit()

for e in range(0, len(arquivos_pais)):
    print('Trabalhando no arquivo: '+arquivos_pais[e]+' [...]')
    try:
        del pais
    except:
        pass

    pais_dtypes = ({0: 'Int32', 1: object})
    extracted_file_path = os.path.join(extracted_files, arquivos_pais[e])
    pais = pd.read_csv(filepath_or_buffer=extracted_file_path, sep=';', skiprows=0, header=None, dtype=pais_dtypes, encoding='latin-1')

    # Tratamento do arquivo antes de inserir na base:
    pais = pais.reset_index()
    del pais['index']

    # Renomear colunas
    pais.columns = ['code', 'description']

    # Gravar dados no banco:
    # pais
    to_sql(pais, name='countries', con=engine, if_exists='append', index=False)
    print('Arquivo ' + arquivos_pais[e] + ' inserido com sucesso no banco de dados!')

try:
    del pais
except:
    pass
print('Arquivos de pais finalizados!')
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

# Limpar dados antes do insert (tabela já existe pelo schema)
cur.execute('TRUNCATE TABLE "qualifications" CASCADE;')
conn.commit()

for e in range(0, len(arquivos_quals)):
    print('Trabalhando no arquivo: '+arquivos_quals[e]+' [...]')
    try:
        del quals
    except:
        pass

    quals_dtypes = ({0: 'Int32', 1: object})
    extracted_file_path = os.path.join(extracted_files, arquivos_quals[e])
    quals = pd.read_csv(filepath_or_buffer=extracted_file_path, sep=';', skiprows=0, header=None, dtype=quals_dtypes, encoding='latin-1')

    # Tratamento do arquivo antes de inserir na base:
    quals = quals.reset_index()
    del quals['index']

    # Renomear colunas
    quals.columns = ['code', 'description']

    # Gravar dados no banco:
    # quals
    to_sql(quals, name='qualifications', con=engine, if_exists='append', index=False)
    print('Arquivo ' + arquivos_quals[e] + ' inserido com sucesso no banco de dados!')

try:
    del quals
except:
    pass
print('Arquivos de quals finalizados!')
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