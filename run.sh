#!/bin/bash

# Script único para executar o projeto CNPJ ETL
# Verifica se o download já foi feito, se não, faz o download primeiro

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
print_info "Verificando Python..."
if ! command -v python3 &> /dev/null; then
    print_error "Python3 não encontrado!"
    exit 1
fi
print_info "Python encontrado: $(python3 --version)"

# Verificar se arquivo .env existe (na raiz ou em src/) - NÃO SOBRESCREVER se já existir!
ENV_FILE=".env"
ENV_FILE_SRC="src/.env"

if [ -f "$ENV_FILE" ]; then
    print_info "Arquivo .env encontrado na raiz do projeto."
elif [ -f "$ENV_FILE_SRC" ]; then
    print_info "Arquivo .env encontrado em src/."
    ENV_FILE="$ENV_FILE_SRC"
else
    print_warn "Arquivo .env não encontrado. Criando com valores padrão na raiz..."
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
    print_info "Arquivo .env criado com valores padrão."
    print_warn "Por favor, edite o arquivo .env com suas configurações antes de continuar."
fi

# Carregar variáveis do .env
source "$ENV_FILE" 2>/dev/null || true
OUTPUT_FILES_PATH=${OUTPUT_FILES_PATH:-src/data/downloads}
EXTRACTED_FILES_PATH=${EXTRACTED_FILES_PATH:-src/data/extracted}

# Criar diretórios necessários
mkdir -p "$OUTPUT_FILES_PATH"
mkdir -p "$EXTRACTED_FILES_PATH"

# Configurar ambiente virtual
USE_VENV=${USE_VENV:-true}
VENV_DIR="venv"

if [ "$USE_VENV" = "true" ]; then
    # Verificar se o módulo venv está disponível
    if ! python3 -m venv --help &> /dev/null; then
        print_warn "Módulo venv não disponível. Continuando sem ambiente virtual..."
        USE_VENV="false"
    else
        # Verificar se venv existe mas está incompleto
        if [ -d "$VENV_DIR" ] && [ ! -f "$VENV_DIR/bin/activate" ]; then
            print_warn "Ambiente virtual incompleto. Removendo..."
            rm -rf "$VENV_DIR"
        fi
        
        # Criar venv se não existe
        if [ ! -d "$VENV_DIR" ]; then
            print_info "Criando ambiente virtual..."
            if ! python3 -m venv "$VENV_DIR" 2>&1; then
                print_error "Falha ao criar ambiente virtual!"
                USE_VENV="false"
            fi
        fi
        
        # Ativar venv se disponível
        if [ "$USE_VENV" = "true" ] && [ -f "$VENV_DIR/bin/activate" ]; then
            print_info "Ativando ambiente virtual..."
            source "$VENV_DIR/bin/activate" || USE_VENV="false"
        fi
    fi
fi

# Configurar comando pip
if [ "$USE_VENV" = "true" ] && [ -f "$VENV_DIR/bin/pip" ]; then
    PIP_CMD="$VENV_DIR/bin/pip"
    PYTHON_CMD="$VENV_DIR/bin/python"
elif [ "$USE_VENV" = "true" ] && [ -f "$VENV_DIR/bin/pip3" ]; then
    PIP_CMD="$VENV_DIR/bin/pip3"
    PYTHON_CMD="$VENV_DIR/bin/python3"
elif command -v pip3 &> /dev/null; then
    PIP_CMD="pip3"
    PYTHON_CMD="python3"
elif python3 -m pip --version &> /dev/null; then
    PIP_CMD="python3 -m pip"
    PYTHON_CMD="python3"
else
    print_error "pip não encontrado!"
    exit 1
fi

# Instalar dependências
print_info "Instalando/atualizando dependências..."
$PIP_CMD install --quiet --upgrade pip
$PIP_CMD install --quiet -r requirements.txt

if [ $? -ne 0 ]; then
    print_error "Falha ao instalar dependências!"
    exit 1
fi

# Verificar se já existe arquivos ZIP baixados
ZIP_COUNT=$(find "$OUTPUT_FILES_PATH" -name "*.zip" 2>/dev/null | wc -l)

if [ "$ZIP_COUNT" -eq 0 ]; then
    print_warn "Nenhum arquivo ZIP encontrado em $OUTPUT_FILES_PATH"
    print_info "Iniciando download dos arquivos..."
    echo ""
    
    $PYTHON_CMD src/download.py
    
    DOWNLOAD_EXIT=$?
    if [ $DOWNLOAD_EXIT -ne 0 ]; then
        print_error "Download falhou!"
        exit $DOWNLOAD_EXIT
    fi
    
    # Verificar novamente após download
    ZIP_COUNT=$(find "$OUTPUT_FILES_PATH" -name "*.zip" 2>/dev/null | wc -l)
    if [ "$ZIP_COUNT" -eq 0 ]; then
        print_error "Nenhum arquivo foi baixado!"
        exit 1
    fi
    
    print_info "Download concluído! $ZIP_COUNT arquivo(s) encontrado(s)."
    echo ""
else
    print_info "Arquivos ZIP já encontrados: $ZIP_COUNT arquivo(s) em $OUTPUT_FILES_PATH"
    print_info "Pulando download. Executando processamento ETL..."
    echo ""
fi

# Executar processo ETL
print_info "Iniciando processo ETL..."
print_info "Executando: $PYTHON_CMD src/main.py"
echo ""

$PYTHON_CMD src/main.py

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    print_info "Processo ETL concluído com sucesso!"
else
    print_error "Processo ETL falhou com código de saída: $EXIT_CODE"
    exit $EXIT_CODE
fi
