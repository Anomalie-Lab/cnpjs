-- Create database "anomalie_db" (Anomalie Data)
CREATE DATABASE "anomalie_db"
    WITH
    OWNER = postgres
    ENCODING = 'UTF8'
    CONNECTION LIMIT = -1;

COMMENT ON DATABASE "anomalie_db"
    IS 'Database for storing anomalie data';

-- Connect to the database
\c anomalie_db

-- Table: companies (empresas)
CREATE TABLE IF NOT EXISTS companies (
    base_cnpj VARCHAR(8) NOT NULL,
    company_name VARCHAR(255),
    legal_nature_code INTEGER,
    responsible_qualification_code INTEGER,
    responsible_cpf VARCHAR(11),
    capital NUMERIC(20, 2),
    company_size_code INTEGER,
    responsible_federative_entity VARCHAR(255),
    registration_status INTEGER,
    registration_status_date DATE,
    activity_start_date DATE,
    PRIMARY KEY (base_cnpj)
);

COMMENT ON TABLE companies IS 'Company data at headquarters level';
COMMENT ON COLUMN companies.base_cnpj IS 'Base CNPJ (first 8 digits)';
COMMENT ON COLUMN companies.company_name IS 'Company legal name';
COMMENT ON COLUMN companies.legal_nature_code IS 'Legal nature code';
COMMENT ON COLUMN companies.responsible_qualification_code IS 'Responsible person qualification code';
COMMENT ON COLUMN companies.responsible_cpf IS 'CPF of the responsible person (extracted from company_name field)';
COMMENT ON COLUMN companies.capital IS 'Company capital';
COMMENT ON COLUMN companies.company_size_code IS 'Company size code';
COMMENT ON COLUMN companies.responsible_federative_entity IS 'Responsible federative entity';
COMMENT ON COLUMN companies.registration_status IS 'Registration status (2=Ativa, 3=Suspensa, 4=Inapta, 8=Baixada)';
COMMENT ON COLUMN companies.registration_status_date IS 'Date of registration status';
COMMENT ON COLUMN companies.activity_start_date IS 'Company opening date / start of activities date';

-- Table: establishments (estabelecimentos)
CREATE TABLE IF NOT EXISTS establishments (
    base_cnpj VARCHAR(8) NOT NULL,
    cnpj_order VARCHAR(4),
    cnpj_check_digit VARCHAR(2),
    matrix_branch_identifier INTEGER,
    trade_name VARCHAR(255),
    registration_status INTEGER,
    registration_status_date DATE,
    registration_status_reason_code INTEGER,
    foreign_city_name VARCHAR(255),
    country_code INTEGER,
    activity_start_date DATE,
    main_cnae_code VARCHAR(7),
    secondary_cnae_codes TEXT,
    street_type VARCHAR(20),
    street_name VARCHAR(255),
    number VARCHAR(20),
    complement VARCHAR(255),
    neighborhood VARCHAR(100),
    zip_code VARCHAR(8),
    state_code VARCHAR(2),
    city_code INTEGER,
    area_code_1 VARCHAR(2),
    phone_1 VARCHAR(9),
    area_code_2 VARCHAR(2),
    phone_2 VARCHAR(9),
    fax_area_code VARCHAR(2),
    fax_number VARCHAR(9),
    email VARCHAR(255),
    special_situation VARCHAR(255),
    special_situation_date DATE
);

COMMENT ON TABLE establishments IS 'Company data by unit/establishment (phones, address, branch, etc)';
COMMENT ON COLUMN establishments.base_cnpj IS 'Base CNPJ (first 8 digits)';
COMMENT ON COLUMN establishments.cnpj_order IS 'CNPJ order (digits 9-12)';
COMMENT ON COLUMN establishments.cnpj_check_digit IS 'CNPJ check digit (digits 13-14)';
COMMENT ON COLUMN establishments.matrix_branch_identifier IS 'Matrix (1) or Branch (2) identifier';
COMMENT ON COLUMN establishments.trade_name IS 'Trade name';
COMMENT ON COLUMN establishments.registration_status IS 'Registration status';
COMMENT ON COLUMN establishments.main_cnae_code IS 'Main CNAE fiscal code';
COMMENT ON COLUMN establishments.secondary_cnae_codes IS 'Secondary CNAE fiscal codes (comma separated)';

-- Table: partners (socios)
CREATE TABLE IF NOT EXISTS partners (
    base_cnpj VARCHAR(8) NOT NULL,
    partner_identifier INTEGER,
    partner_name_or_company_name VARCHAR(255),
    partner_cpf_cnpj VARCHAR(14),
    partner_qualification_code INTEGER,
    partnership_start_date DATE,
    country_code INTEGER,
    legal_representative_cpf VARCHAR(11),
    representative_name VARCHAR(255),
    legal_representative_qualification_code INTEGER,
    age_range_code INTEGER
);

COMMENT ON TABLE partners IS 'Company partners registration data';
COMMENT ON COLUMN partners.base_cnpj IS 'Base CNPJ (first 8 digits)';
COMMENT ON COLUMN partners.partner_identifier IS 'Partner identifier (1=Individual, 2=Company)';
COMMENT ON COLUMN partners.partner_name_or_company_name IS 'Partner name or company name';
COMMENT ON COLUMN partners.partner_cpf_cnpj IS 'Partner CPF or CNPJ';

-- Table: simple_national (simples nacional)
CREATE TABLE IF NOT EXISTS simple_national (
    base_cnpj VARCHAR(8) NOT NULL,
    opted_for_simple_national VARCHAR(1),
    simple_national_option_date DATE,
    simple_national_exclusion_date DATE,
    opted_for_mei VARCHAR(1),
    mei_option_date DATE,
    mei_exclusion_date DATE
);

COMMENT ON TABLE simple_national IS 'MEI and Simple National data';
COMMENT ON COLUMN simple_national.base_cnpj IS 'Base CNPJ (first 8 digits)';
COMMENT ON COLUMN simple_national.opted_for_simple_national IS 'Opted for Simple National (S=Yes, N=No)';
COMMENT ON COLUMN simple_national.opted_for_mei IS 'Opted for MEI (S=Yes, N=No)';

-- Table: cnae_codes (códigos CNAE)
CREATE TABLE IF NOT EXISTS cnae_codes (
    code VARCHAR(7) NOT NULL,
    description VARCHAR(255),
    PRIMARY KEY (code)
);

COMMENT ON TABLE cnae_codes IS 'CNAE code and description';

-- Table: registration_status_reasons (motivos situação cadastral)
CREATE TABLE IF NOT EXISTS registration_status_reasons (
    code INTEGER NOT NULL,
    description VARCHAR(255),
    PRIMARY KEY (code)
);

COMMENT ON TABLE registration_status_reasons IS 'Registration status reason codes and descriptions';

-- Table: municipalities (municípios)
CREATE TABLE IF NOT EXISTS municipalities (
    code INTEGER NOT NULL,
    description VARCHAR(255),
    PRIMARY KEY (code)
);

COMMENT ON TABLE municipalities IS 'Municipality codes and descriptions';

-- Table: legal_natures (naturezas jurídicas)
CREATE TABLE IF NOT EXISTS legal_natures (
    code INTEGER NOT NULL,
    description VARCHAR(255),
    PRIMARY KEY (code)
);

COMMENT ON TABLE legal_natures IS 'Legal nature codes and descriptions';

-- Table: countries (países)
CREATE TABLE IF NOT EXISTS countries (
    code INTEGER NOT NULL,
    description VARCHAR(255),
    PRIMARY KEY (code)
);

COMMENT ON TABLE countries IS 'Country codes and descriptions';

-- Table: qualifications (qualificações)
CREATE TABLE IF NOT EXISTS qualifications (
    code INTEGER NOT NULL,
    description VARCHAR(255),
    PRIMARY KEY (code)
);

COMMENT ON TABLE qualifications IS 'Qualification codes for individuals - partners, responsible and legal representative';

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_companies_base_cnpj ON companies(base_cnpj);
CREATE INDEX IF NOT EXISTS idx_establishments_base_cnpj ON establishments(base_cnpj);
CREATE INDEX IF NOT EXISTS idx_partners_base_cnpj ON partners(base_cnpj);
CREATE INDEX IF NOT EXISTS idx_simple_national_base_cnpj ON simple_national(base_cnpj);

-- Foreign key constraints (optional, can be added if referential integrity is needed)
-- ALTER TABLE companies ADD CONSTRAINT fk_companies_legal_nature 
--     FOREIGN KEY (legal_nature_code) REFERENCES legal_natures(code);
-- ALTER TABLE establishments ADD CONSTRAINT fk_establishments_company 
--     FOREIGN KEY (base_cnpj) REFERENCES companies(base_cnpj);
-- ALTER TABLE establishments ADD CONSTRAINT fk_establishments_city 
--     FOREIGN KEY (city_code) REFERENCES municipalities(code);
-- ALTER TABLE establishments ADD CONSTRAINT fk_establishments_country 
--     FOREIGN KEY (country_code) REFERENCES countries(code);
-- ALTER TABLE partners ADD CONSTRAINT fk_partners_company 
--     FOREIGN KEY (base_cnpj) REFERENCES companies(base_cnpj);
-- ALTER TABLE partners ADD CONSTRAINT fk_partners_qualification 
--     FOREIGN KEY (partner_qualification_code) REFERENCES qualifications(code);
-- ALTER TABLE simple_national ADD CONSTRAINT fk_simple_national_company 
--     FOREIGN KEY (base_cnpj) REFERENCES companies(base_cnpj);
