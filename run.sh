#!/bin/bash
# Script para executar o ETL

echo "=== CNPJ ETL Script ==="
echo ""

# Verificar se Docker está rodando
echo "1. Verificando Docker..."
if ! docker compose ps | grep -q "Up"; then
    echo "   Iniciando Docker..."
    docker compose up -d
    sleep 5
else
    echo "   ✓ Docker já está rodando"
fi

# Ativar ambiente virtual
echo ""
echo "2. Ativando ambiente virtual..."
if [ ! -d "venv" ]; then
    echo "   Criando ambiente virtual..."
    python3 -m venv venv
fi

source venv/bin/activate

# Instalar dependências se necessário
echo ""
echo "3. Verificando dependências..."
if ! python -c "import dotenv" 2>/dev/null; then
    echo "   Instalando dependências..."
    pip install -q -r requirements.txt
else
    echo "   ✓ Dependências já instaladas"
fi

# Verificar arquivo .env
echo ""
echo "4. Verificando configuração..."
if [ ! -f "src/.env" ]; then
    echo "   Criando arquivo .env..."
    cat > src/.env << ENVEOF
# Database Configuration
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cnpj_data

# File Paths
OUTPUT_FILES_PATH=./data/downloads
EXTRACTED_FILES_PATH=./data/extracted
ENVEOF
    echo "   ✓ Arquivo .env criado"
else
    echo "   ✓ Arquivo .env encontrado"
fi

# Criar diretórios de dados
echo ""
echo "5. Criando diretórios de dados..."
mkdir -p src/data/downloads src/data/extracted
echo "   ✓ Diretórios criados"

# Executar script
echo ""
echo "6. Executando script ETL..."
echo "   (Este processo pode levar várias horas)"
echo ""
cd src
python main.py

