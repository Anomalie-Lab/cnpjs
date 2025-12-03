#!/bin/bash

# Script para executar o projeto CNPJ ETL
# Este script configura o ambiente e executa o processo ETL

set -e  # Para na primeira erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função para imprimir mensagens
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar se Python está instalado
print_info "Verificando Python..."
if ! command -v python3 &> /dev/null; then
    print_error "Python3 não encontrado! Por favor, instale Python 3.8 ou superior."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
print_info "Python encontrado: $(python3 --version)"

# Verificar se pip está instalado
if ! command -v pip3 &> /dev/null; then
    print_error "pip3 não encontrado! Por favor, instale pip."
    exit 1
fi

# Obter diretório do script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Verificar se requirements.txt existe
if [ ! -f "requirements.txt" ]; then
    print_error "Arquivo requirements.txt não encontrado!"
    exit 1
fi

# Verificar se src/main.py existe
if [ ! -f "src/main.py" ]; then
    print_error "Arquivo src/main.py não encontrado!"
    exit 1
fi

# Criar/verificar ambiente virtual (opcional)
USE_VENV=${USE_VENV:-true}
if [ "$USE_VENV" = "true" ]; then
    if [ ! -d "venv" ]; then
        print_info "Criando ambiente virtual..."
        python3 -m venv venv
    fi
    
    print_info "Ativando ambiente virtual..."
    source venv/bin/activate
fi

# Instalar/atualizar dependências
print_info "Instalando dependências do requirements.txt..."
pip3 install --quiet --upgrade pip
pip3 install --quiet -r requirements.txt

# Verificar/criar arquivo .env
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    print_warn "Arquivo .env não encontrado. Criando template..."
    
    # Valores padrão
    DB_HOST=${DB_HOST:-localhost}
    DB_PORT=${DB_PORT:-5432}
    DB_USER=${DB_USER:-postgres}
    DB_PASSWORD=${DB_PASSWORD:-postgres}
    DB_NAME=${DB_NAME:-cnpj_data}
    OUTPUT_FILES_PATH=${OUTPUT_FILES_PATH:-src/data/downloads}
    EXTRACTED_FILES_PATH=${EXTRACTED_FILES_PATH:-src/data/extracted}
    
    cat > "$ENV_FILE" << EOF
# Configurações do Banco de Dados PostgreSQL
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_NAME=$DB_NAME

# Caminhos dos arquivos
OUTPUT_FILES_PATH=$OUTPUT_FILES_PATH
EXTRACTED_FILES_PATH=$EXTRACTED_FILES_PATH
EOF
    
    print_info "Arquivo .env criado com valores padrão."
    print_warn "Por favor, edite o arquivo .env com suas configurações antes de continuar."
    print_info "Pressione Enter para continuar ou Ctrl+C para cancelar..."
    read
else
    print_info "Arquivo .env encontrado."
fi

# Criar diretórios se não existirem
print_info "Criando diretórios necessários..."
mkdir -p src/data/downloads
mkdir -p src/data/extracted

# Verificar conexão com banco de dados (opcional)
print_info "Verificando conexão com PostgreSQL..."
if command -v psql &> /dev/null; then
    # Tentar ler variáveis do .env
    source "$ENV_FILE" 2>/dev/null || true
    
    if psql -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" -U "${DB_USER:-postgres}" -d "${DB_NAME:-cnpj_data}" -c "SELECT 1;" &> /dev/null; then
        print_info "Conexão com PostgreSQL OK!"
    else
        print_warn "Não foi possível conectar ao PostgreSQL. Verifique suas configurações no .env"
        print_warn "Certifique-se de que o PostgreSQL está rodando e o banco de dados existe."
    fi
else
    print_warn "psql não encontrado. Pulando verificação de conexão."
fi

# Executar o script principal
print_info "Iniciando processo ETL..."
print_info "Executando: python3 src/main.py"
echo ""

cd "$SCRIPT_DIR"
python3 src/main.py

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    print_info "Processo ETL concluído com sucesso!"
else
    print_error "Processo ETL falhou com código de saída: $EXIT_CODE"
    exit $EXIT_CODE
fi

