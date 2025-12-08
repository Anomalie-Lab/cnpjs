#!/usr/bin/env python3
"""
Script de busca interativa no banco de dados CNPJ
Busca empresas ativas e relaciona dados importantes (empresa, estabelecimentos, sócios, simples nacional)
Exporta resultados para CSV
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import csv
import pandas as pd
from datetime import datetime

# Carregar variáveis de ambiente
load_dotenv()

def get_db_connection():
    """Conecta ao banco de dados"""
    user = os.getenv('DB_USER')
    passw = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT', '5432')
    database = os.getenv('DB_NAME')
    
    if not all([user, passw, host, database]):
        print("❌ Erro: Variáveis de ambiente do banco de dados não configuradas!")
        print("   Verifique o arquivo .env")
        sys.exit(1)
    
    try:
        conn = psycopg2.connect(
            dbname=database,
            user=user,
            host=host,
            port=port,
            password=passw
        )
        return conn
    except Exception as e:
        print(f"❌ Erro ao conectar ao banco de dados: {e}")
        sys.exit(1)

def ask_question(question, default=None, required=False):
    """Faz uma pergunta ao usuário e retorna a resposta"""
    if default:
        prompt = f"{question} [{default}]: "
    else:
        prompt = f"{question}: "
    
    while True:
        answer = input(prompt).strip()
        
        if not answer:
            if default:
                return default
            elif required:
                print("⚠️  Este campo é obrigatório!")
                continue
            else:
                return None
        
        return answer

def ask_yes_no(question, default=True):
    """Faz uma pergunta sim/não"""
    default_text = "S/n" if default else "s/N"
    answer = input(f"{question} [{default_text}]: ").strip().lower()
    
    if not answer:
        return default
    
    return answer in ['s', 'sim', 'y', 'yes']

def search_companies_batch(filters, offset=0, limit=1000):
    """
    Busca empresas ativas com filtros (em lotes)
    """
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT 
            c.base_cnpj,
            c.company_name as razao_social,
            c.legal_nature_code,
            ln.description as natureza_juridica,
            c.registration_status,
            c.registration_status_date as data_situacao_cadastral,
            c.activity_start_date as data_abertura,
            c.capital,
            c.company_size_code as porte,
            c.responsible_federative_entity as uf_responsavel
        FROM companies c
        LEFT JOIN legal_natures ln ON c.legal_nature_code = ln.code
        WHERE c.registration_status = 2
    """
    
    params = []
    
    # Filtro por CNPJ (base)
    if filters.get('cnpj'):
        cnpj = filters['cnpj'].replace('.', '').replace('/', '').replace('-', '')
        if len(cnpj) == 14:
            cnpj = cnpj[:8]
        elif len(cnpj) != 8:
            print(f"⚠️  CNPJ inválido: {filters['cnpj']}")
            return []
        
        query += " AND c.base_cnpj = %s"
        params.append(cnpj)
    
    # Filtro por nome da empresa
    if filters.get('nome'):
        query += " AND c.company_name ILIKE %s"
        params.append(f"%{filters['nome']}%")
    
    # Filtro por data de abertura inicial
    if filters.get('data_inicio'):
        query += " AND c.activity_start_date >= %s"
        params.append(filters['data_inicio'])
    
    # Filtro por data de abertura final
    if filters.get('data_fim'):
        query += " AND c.activity_start_date <= %s"
        params.append(filters['data_fim'])
    
    # Filtro por capital mínimo
    if filters.get('capital_min'):
        query += " AND c.capital >= %s"
        params.append(float(filters['capital_min']))
    
    # Filtro por capital máximo
    if filters.get('capital_max'):
        query += " AND c.capital <= %s"
        params.append(float(filters['capital_max']))
    
    # Filtro por natureza jurídica
    if filters.get('natureza_juridica'):
        query += " AND c.legal_nature_code = %s"
        params.append(int(filters['natureza_juridica']))
    
    # Filtro por porte
    if filters.get('porte'):
        query += " AND c.company_size_code = %s"
        params.append(int(filters['porte']))
    
    # Filtro por estado
    if filters.get('estado'):
        query += " AND c.responsible_federative_entity = %s"
        params.append(filters['estado'].upper())
    
    query += " ORDER BY c.company_name LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    try:
        cur.execute(query, params)
        results = cur.fetchall()
        return results
    except Exception as e:
        print(f"❌ Erro ao executar busca: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_establishments_for_company(base_cnpj):
    """Busca estabelecimentos de uma empresa"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT 
            CONCAT(e.base_cnpj, e.cnpj_order, e.cnpj_check_digit) as cnpj_completo,
            e.trade_name as nome_fantasia,
            CASE WHEN e.matrix_branch_identifier = 1 THEN 'Matriz' ELSE 'Filial' END as tipo,
            e.main_cnae_code as cnae_principal,
            cnae.description as descricao_cnae_principal,
            e.secondary_cnae_codes as cnaes_secundarios,
            e.street_type as tipo_logradouro,
            e.street_name as logradouro,
            e.number as numero,
            e.complement as complemento,
            e.neighborhood as bairro,
            e.zip_code as cep,
            e.state_code as uf,
            e.city_code as codigo_municipio,
            m.description as municipio,
            e.area_code_1 as ddd_1,
            e.phone_1 as telefone_1,
            e.area_code_2 as ddd_2,
            e.phone_2 as telefone_2,
            e.email,
            e.registration_status as situacao_cadastral,
            e.registration_status_date as data_situacao_cadastral,
            e.activity_start_date as data_inicio_atividade
        FROM establishments e
        LEFT JOIN cnae_codes cnae ON e.main_cnae_code = cnae.code
        LEFT JOIN municipalities m ON e.city_code = m.code
        WHERE e.base_cnpj = %s
        ORDER BY e.matrix_branch_identifier, e.trade_name
    """
    
    try:
        cur.execute(query, (base_cnpj,))
        results = cur.fetchall()
        return results
    except Exception as e:
        print(f"  ⚠️  Erro ao buscar estabelecimentos: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_partners_for_company(base_cnpj):
    """Busca sócios de uma empresa"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT 
            CASE WHEN p.partner_identifier = 1 THEN 'Pessoa Física' ELSE 'Pessoa Jurídica' END as tipo_socio,
            p.partner_name_or_company_name as nome_socio,
            p.partner_cpf_cnpj as cpf_cnpj_socio,
            p.partner_qualification_code as codigo_qualificacao,
            q.description as qualificacao,
            p.partnership_start_date as data_entrada_sociedade,
            p.country_code as codigo_pais,
            co.description as pais
        FROM partners p
        LEFT JOIN qualifications q ON p.partner_qualification_code = q.code
        LEFT JOIN countries co ON p.country_code = co.code
        WHERE p.base_cnpj = %s
        ORDER BY p.partner_name_or_company_name
    """
    
    try:
        cur.execute(query, (base_cnpj,))
        results = cur.fetchall()
        return results
    except Exception as e:
        print(f"  ⚠️  Erro ao buscar sócios: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_simple_national_for_company(base_cnpj):
    """Busca dados do Simples Nacional de uma empresa"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT 
            CASE WHEN sn.opted_for_simple_national = 'S' THEN 'Sim' ELSE 'Não' END as optou_simples,
            sn.simple_national_option_date as data_opcao_simples,
            sn.simple_national_exclusion_date as data_exclusao_simples,
            CASE WHEN sn.opted_for_mei = 'S' THEN 'Sim' ELSE 'Não' END as optou_mei,
            sn.mei_option_date as data_opcao_mei,
            sn.mei_exclusion_date as data_exclusao_mei
        FROM simple_national sn
        WHERE sn.base_cnpj = %s
        LIMIT 1
    """
    
    try:
        cur.execute(query, (base_cnpj,))
        result = cur.fetchone()
        return result if result else {}
    except Exception as e:
        print(f"  ⚠️  Erro ao buscar Simples Nacional: {e}")
        return {}
    finally:
        cur.close()
        conn.close()

def collect_company_data(base_cnpj, company_data):
    """Coleta todos os dados relacionados a uma empresa"""
    print(f"  Coletando dados da empresa {base_cnpj}...")
    
    # Buscar estabelecimentos
    establishments = get_establishments_for_company(base_cnpj)
    
    # Buscar sócios
    partners = get_partners_for_company(base_cnpj)
    
    # Buscar Simples Nacional
    simple_national = get_simple_national_for_company(base_cnpj)
    
    # Preparar dados consolidados
    consolidated_data = {
        # Dados da empresa
        'base_cnpj': company_data.get('base_cnpj'),
        'razao_social': company_data.get('razao_social'),
        'natureza_juridica': company_data.get('natureza_juridica'),
        'data_abertura': company_data.get('data_abertura'),
        'capital': company_data.get('capital'),
        'porte': company_data.get('porte'),
        'uf_responsavel': company_data.get('uf_responsavel'),
        
        # Dados do estabelecimento matriz (se existir)
        'cnpj_completo': '',
        'nome_fantasia': '',
        'cnae_principal': '',
        'descricao_cnae_principal': '',
        'cnaes_secundarios': '',
        'logradouro': '',
        'numero': '',
        'complemento': '',
        'bairro': '',
        'cep': '',
        'uf': '',
        'municipio': '',
        'telefone': '',
        'email': '',
        
        # Dados do Simples Nacional
        'optou_simples': simple_national.get('optou_simples', ''),
        'data_opcao_simples': simple_national.get('data_opcao_simples', ''),
        'optou_mei': simple_national.get('optou_mei', ''),
        'data_opcao_mei': simple_national.get('data_opcao_mei', ''),
        
        # Sócios (concatenados)
        'socios': '',
        'cpf_cnpj_socios': '',
        'tipo_socios': '',
        'qualificacao_socios': '',
        'data_entrada_socios': '',
        'pais_socios': '',
    }
    
    # Pegar estabelecimento matriz (se existir)
    matriz = next((e for e in establishments if e.get('tipo') == 'Matriz'), None)
    if matriz:
        consolidated_data.update({
            'cnpj_completo': matriz.get('cnpj_completo', ''),
            'nome_fantasia': matriz.get('nome_fantasia', ''),
            'cnae_principal': matriz.get('cnae_principal', ''),
            'descricao_cnae_principal': matriz.get('descricao_cnae_principal', ''),
            'cnaes_secundarios': matriz.get('cnaes_secundarios', ''),
            'logradouro': f"{matriz.get('tipo_logradouro', '')} {matriz.get('logradouro', '')}".strip(),
            'numero': matriz.get('numero', ''),
            'complemento': matriz.get('complemento', ''),
            'bairro': matriz.get('bairro', ''),
            'cep': matriz.get('cep', ''),
            'uf': matriz.get('uf', ''),
            'municipio': matriz.get('municipio', ''),
            'telefone': f"({matriz.get('ddd_1', '')}) {matriz.get('telefone_1', '')}".strip() if matriz.get('ddd_1') else '',
            'email': matriz.get('email', ''),
        })
    
    # Concatenar sócios
    if partners:
        socios_nomes = [p.get('nome_socio', '') for p in partners if p.get('nome_socio')]
        socios_cpf_cnpj = [p.get('cpf_cnpj_socio', '') for p in partners if p.get('cpf_cnpj_socio')]
        consolidated_data['socios'] = '; '.join(socios_nomes)
        socios_tipos = [p.get('tipo_socio', '') for p in partners if p.get('tipo_socio')]
        socios_qualificacoes = [p.get('qualificacao', '') for p in partners if p.get('qualificacao')]
        socios_datas = [str(p.get('data_entrada_sociedade', '')) for p in partners if p.get('data_entrada_sociedade')]
        socios_paises = [p.get('pais', '') for p in partners if p.get('pais')]
        
        consolidated_data['cpf_cnpj_socios'] = '; '.join(socios_cpf_cnpj)
        consolidated_data['tipo_socios'] = '; '.join(socios_tipos)
        consolidated_data['qualificacao_socios'] = '; '.join(socios_qualificacoes)
        consolidated_data['data_entrada_socios'] = '; '.join(socios_datas)
        consolidated_data['pais_socios'] = '; '.join(socios_paises)
    
    return consolidated_data

def export_to_csv(data, filename):
    """Exporta dados para CSV"""
    if not data:
        print("❌ Nenhum dado para exportar!")
        return
    
    # Definir colunas na ordem desejada
    columns = [
        'base_cnpj',
        'cnpj_completo',
        'razao_social',
        'nome_fantasia',
        'natureza_juridica',
        'data_abertura',
        'capital',
        'porte',
        'uf_responsavel',
        'cnae_principal',
        'descricao_cnae_principal',
        'cnaes_secundarios',
        'logradouro',
        'numero',
        'complemento',
        'bairro',
        'cep',
        'uf',
        'municipio',
        'telefone',
        'email',
        'optou_simples',
        'data_opcao_simples',
        'optou_mei',
        'data_opcao_mei',
        'socios',
        'cpf_cnpj_socios',
        'tipo_socios',
        'qualificacao_socios',
        'data_entrada_socios',
        'pais_socios',
    ]
    
    # Criar DataFrame
    df = pd.DataFrame(data)
    
    # Reordenar colunas (apenas as que existem)
    existing_columns = [col for col in columns if col in df.columns]
    df = df[existing_columns]
    
    # Exportar para CSV
    df.to_csv(filename, index=False, encoding='utf-8-sig', sep=';')
    print(f"\n✓ Arquivo exportado: {filename}")
    print(f"  Total de empresas: {len(data)}")

def main():
    print("=" * 80)
    print("BUSCA DE EMPRESAS ATIVAS - CNPJ")
    print("=" * 80)
    print("\nEste script busca empresas ATIVAS e relaciona os dados importantes:")
    print("  - Dados da empresa")
    print("  - Estabelecimento matriz")
    print("  - Sócios")
    print("  - Simples Nacional/MEI")
    print("\nOs resultados serão exportados para um arquivo CSV.\n")
    
    # Coletar filtros
    filters = {}
    
    print("📋 FILTROS DE BUSCA")
    print("-" * 80)
    
    # CNPJ
    cnpj = ask_question("CNPJ (base ou completo) - deixe em branco para buscar todos")
    if cnpj:
        filters['cnpj'] = cnpj
    
    # Nome
    nome = ask_question("Nome/Razão Social (busca parcial) - deixe em branco para ignorar")
    if nome:
        filters['nome'] = nome
    
    # Estado
    estado = ask_question("Estado (UF) - deixe em branco para todos")
    if estado:
        filters['estado'] = estado.upper()
    
    # Data de abertura
    data_inicio = ask_question("Data de abertura inicial (YYYY-MM-DD) - deixe em branco para ignorar")
    if data_inicio:
        filters['data_inicio'] = data_inicio
    
    data_fim = ask_question("Data de abertura final (YYYY-MM-DD) - deixe em branco para ignorar")
    if data_fim:
        filters['data_fim'] = data_fim
    
    # Capital
    capital_min = ask_question("Capital mínimo - deixe em branco para ignorar")
    if capital_min:
        try:
            filters['capital_min'] = float(capital_min)
        except:
            print("⚠️  Valor inválido, ignorando...")
    
    capital_max = ask_question("Capital máximo - deixe em branco para ignorar")
    if capital_max:
        try:
            filters['capital_max'] = float(capital_max)
        except:
            print("⚠️  Valor inválido, ignorando...")
    
    # Natureza jurídica
    natureza = ask_question("Código da natureza jurídica - deixe em branco para ignorar")
    if natureza:
        try:
            filters['natureza_juridica'] = int(natureza)
        except:
            print("⚠️  Valor inválido, ignorando...")
    
    # Porte
    porte = ask_question("Código do porte - deixe em branco para ignorar")
    if porte:
        try:
            filters['porte'] = int(porte)
        except:
            print("⚠️  Valor inválido, ignorando...")
    
    # Tamanho do lote
    print("\n📦 CONFIGURAÇÃO DE PROCESSAMENTO")
    print("-" * 80)
    batch_size = ask_question("Tamanho do lote (empresas por vez)", default="1000")
    try:
        batch_size = int(batch_size)
    except:
        batch_size = 1000
    
    # Nome do arquivo de saída
    print("\n💾 ARQUIVO DE SAÍDA")
    print("-" * 80)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_filename = f"empresas_ativas_{timestamp}.csv"
    filename = ask_question("Nome do arquivo CSV", default=default_filename)
    
    # Confirmar busca
    print("\n" + "=" * 80)
    print("RESUMO DA BUSCA")
    print("=" * 80)
    print(f"Filtros aplicados:")
    if filters:
        for key, value in filters.items():
            print(f"  - {key}: {value}")
    else:
        print("  - Nenhum filtro (buscar todas as empresas ativas)")
    print(f"Tamanho do lote: {batch_size}")
    print(f"Arquivo de saída: {filename}")
    print("=" * 80)
    
    if not ask_yes_no("\nDeseja continuar com a busca?", default=True):
        print("❌ Busca cancelada.")
        return
    
    # Executar busca em lotes
    print("\n🔍 INICIANDO BUSCA...")
    print("=" * 80)
    
    all_data = []
    offset = 0
    total_found = 0
    
    while True:
        print(f"\n📊 Buscando lote {offset // batch_size + 1} (offset: {offset})...")
        
        # Buscar empresas
        companies = search_companies_batch(filters, offset=offset, limit=batch_size)
        
        if not companies:
            print("✓ Nenhuma empresa encontrada neste lote. Busca finalizada.")
            break
        
        print(f"  ✓ Encontradas {len(companies)} empresas neste lote")
        total_found += len(companies)
        
        # Processar cada empresa
        for i, company in enumerate(companies, 1):
            base_cnpj = company.get('base_cnpj')
            print(f"  [{i}/{len(companies)}] Processando {base_cnpj} - {company.get('razao_social', '')[:50]}...")
            
            # Coletar dados relacionados
            consolidated = collect_company_data(base_cnpj, company)
            all_data.append(consolidated)
        
        # Se retornou menos que o lote, chegou ao fim
        if len(companies) < batch_size:
            break
        
        offset += batch_size
    
    print("\n" + "=" * 80)
    print(f"✓ BUSCA FINALIZADA!")
    print(f"  Total de empresas processadas: {total_found}")
    print("=" * 80)
    
    # Exportar para CSV
    if all_data:
        export_to_csv(all_data, filename)
        print(f"\n✓ Processo concluído com sucesso!")
    else:
        print("\n❌ Nenhuma empresa encontrada com os filtros especificados.")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Processo interrompido pelo usuário.")
        sys.exit(0)
