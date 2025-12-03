#!/bin/bash

# Script para fazer download dos arquivos CNPJ
# Este script instala dependências e executa o download

set +e  # Não parar automaticamente em erros

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Obter diretório do script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Verificar Python
if ! command -v python3 &> /dev/null; then
    print_error "Python3 não encontrado!"
    exit 1
fi

# Verificar pip
if command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
elif python3 -m pip --version &> /dev/null; then
    PIP_CMD="python3 -m pip"
else
    print_error "pip não encontrado!"
    exit 1
fi

# Verificar se requirements.txt existe
if [ ! -f "requirements.txt" ]; then
    print_error "Arquivo requirements.txt não encontrado!"
    exit 1
fi

# Instalar dependências necessárias para download
print_info "Instalando dependências necessárias para download..."
$PIP_CMD install --quiet beautifulsoup4 lxml requests wget python-dotenv

if [ $? -ne 0 ]; then
    print_error "Falha ao instalar dependências!"
    exit 1
fi

# Verificar/criar arquivo .env se necessário
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    print_warn "Arquivo .env não encontrado. Criando com valores padrão..."
    cat > "$ENV_FILE" << EOF
# Configurações do Banco de Dados PostgreSQL
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=cnpj_data

# Caminhos dos arquivos
OUTPUT_FILES_PATH=src/data/downloads
EXTRACTED_FILES_PATH=src/data/extracted
EOF
fi

# Criar diretórios necessários
print_info "Criando diretórios necessários..."
mkdir -p src/data/downloads
mkdir -p src/data/extracted

# Executar download
print_info "Iniciando download dos arquivos..."
python3 src/download.py

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    print_info "Download concluído com sucesso!"
else
    print_error "Download falhou com código de saída: $EXIT_CODE"
    exit $EXIT_CODE
fi

