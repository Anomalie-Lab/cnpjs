# CNPJ Public Data - Brazilian Federal Revenue

ETL process to download, extract, process and insert Brazilian Federal Revenue public CNPJ data into a PostgreSQL database.

## Requirements

- Python 3.8+
- Docker and Docker Compose
- PostgreSQL 14.2 (via Docker)

## Quick Start

### 1. Start the Database

```bash
# Start PostgreSQL container
docker compose up -d

# Verify it's running
docker compose ps

# Check database connection
docker compose exec postgres psql -U postgres -d cnpj_data -c "SELECT version();"
```

### 2. Setup Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Create/edit `.env` file in `src/` directory:

```env
# Database Configuration
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cnpj_data

# File Paths
OUTPUT_FILES_PATH=./data/downloads
EXTRACTED_FILES_PATH=./data/extracted
```

### 4. Run the ETL Script

```bash
# Make sure you're in the src directory
cd src

# Activate virtual environment (if not already activated)
source ../venv/bin/activate

# Run the script
python main.py
```

## Project Structure

```
.
├── docker-compose.yml          # Docker configuration for PostgreSQL
├── requirements.txt            # Python dependencies
├── src/
│   ├── main.py                # Main ETL script
│   ├── schema.sql             # Database schema definition
│   ├── init.sql               # Database initialization script
│   └── .env                   # Environment variables (create this)
├── misc/
│   └── query.sql              # Example queries
└── data/                      # Created automatically
    ├── downloads/             # Downloaded ZIP files
    └── extracted/             # Extracted CSV files
```

## Database Schema

The database `cnpj_data` contains the following tables:

- `companies` - Company data at headquarters level
- `establishments` - Company data by unit/establishment
- `partners` - Company partners registration data
- `simple_national` - MEI and Simple National data
- `cnae_codes` - CNAE codes and descriptions
- `registration_status_reasons` - Registration status reason codes
- `municipalities` - Municipality codes and descriptions
- `legal_natures` - Legal nature codes and descriptions
- `countries` - Country codes and descriptions
- `qualifications` - Qualification codes

## How It Works

1. **Download**: Downloads ZIP files from Brazilian Federal Revenue FTP server
2. **Extract**: Extracts CSV files from ZIP archives
3. **Process**: Reads and processes CSV files
4. **Load**: Inserts data into PostgreSQL database tables

The script:
- Creates database schema automatically using `schema.sql`
- Downloads files only if they don't exist or have changed
- Processes files in chunks to handle large datasets
- Creates indexes for performance optimization

## Execution Time

⚠️ **Warning**: The complete ETL process can take **several hours** due to the large volume of data:
- Files from 08/05/2021: `4.68 GB` compressed and `17.1 GB` uncompressed
- Millions of records to process

## Useful Commands

### Docker Commands

```bash
# Start database
docker compose up -d

# Stop database
docker compose down

# Stop and remove volumes (deletes data)
docker compose down -v

# View logs
docker compose logs -f postgres

# Connect to database
docker compose exec postgres psql -U postgres -d cnpj_data
```

### Database Queries

```bash
# List all tables
docker compose exec postgres psql -U postgres -d cnpj_data -c "\dt"

# Count records in companies table
docker compose exec postgres psql -U postgres -d cnpj_data -c "SELECT COUNT(*) FROM companies;"

# Check indexes
docker compose exec postgres psql -U postgres -d cnpj_data -c "\di"
```

## Troubleshooting

### Database Connection Issues

```bash
# Check if container is running
docker compose ps

# Check database logs
docker compose logs postgres

# Restart container
docker compose restart postgres
```

### Python Dependencies

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### File Permissions

```bash
# Ensure data directories exist and are writable
mkdir -p src/data/downloads src/data/extracted
chmod -R 755 src/data
```

## Notes

- The script creates tables automatically using the schema.sql file
- Data is truncated (not dropped) before each run to preserve table structure
- The process can be interrupted and resumed (files are checked before download)
- Large files are processed in chunks to manage memory usage



