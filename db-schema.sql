-- ============================================================
-- Product Expert System — Core Database Schema
-- 001_database_schema.sql
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";  -- pgvector for embeddings

-- ============================================================
-- 1. BRANDS
-- ============================================================
CREATE TABLE brands (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            TEXT NOT NULL UNIQUE,        -- 'ABS', 'LABRepCo', 'Corepoint', 'Celsius', 'CBS'
    name            TEXT NOT NULL,               -- 'American BioTech Supply'
    parent_org      TEXT,                        -- 'Standex Scientific'
    logo_uri        TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

INSERT INTO brands (code, name, parent_org) VALUES
('ABS',       'American BioTech Supply',  'Horizon Scientific'),
('LABRepCo',  'LABRepCo',                 'Horizon Scientific'),
('Corepoint', 'Corepoint Scientific',     'Horizon Scientific'),
('Celsius',   '°celsius Scientific',      'Horizon Scientific'),
('CBS',       'CBS / CryoSafe',           'Horizon Scientific');

-- ============================================================
-- 2. PRODUCT FAMILIES
-- ============================================================
CREATE TABLE product_families (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    super_category  TEXT NOT NULL CHECK (super_category IN (
        'refrigerator', 'freezer', 'cryogenic', 'accessory'
    )),
    description     TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

INSERT INTO product_families (code, name, super_category) VALUES
('premier_lab_ref',         'Premier Laboratory Refrigerator',           'refrigerator'),
('standard_lab_ref',        'Standard Laboratory Refrigerator',          'refrigerator'),
('chromatography_ref',      'Chromatography Refrigerator',               'refrigerator'),
('pharmacy_vaccine_ref',    'Pharmacy/Vaccine Refrigerator',             'refrigerator'),
('pharmacy_nsf_ref',        'Pharmacy/Vaccine NSF Certified',            'refrigerator'),
('flammable_storage_ref',   'Flammable Material Storage Refrigerator',   'refrigerator'),
('blood_bank_ref',          'Blood Bank Refrigerator',                   'refrigerator'),
('manual_defrost_freezer',  'Manual Defrost Laboratory Freezer',         'freezer'),
('auto_defrost_freezer',    'Auto Defrost Laboratory Freezer',           'freezer'),
('precision_freezer',       'Precision Series Laboratory Freezer',       'freezer'),
('ultra_low_freezer',       'Ultra-Low Temperature Freezer',             'freezer'),
('plasma_freezer',          'Plasma Storage Freezer',                    'freezer'),
('cryo_dewar',              'Cryogenic Dewar / LN2 Storage',             'cryogenic'),
('vapor_shipper',           'Cryogenic Vapor Shipper',                   'cryogenic'),
('cryo_freezer',            'CryoMizer Cryogenic Freezer',               'cryogenic'),
('accessory',               'Accessory',                                 'accessory');

-- ============================================================
-- 3. SPEC REGISTRY (Dynamic — auto-populated during ingestion)
-- ============================================================
CREATE TABLE spec_registry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name  TEXT NOT NULL UNIQUE,         -- 'storage_capacity_cuft'
    display_name    TEXT NOT NULL,                -- 'Storage Capacity'
    data_type       TEXT NOT NULL CHECK (data_type IN (
        'numeric', 'text', 'boolean', 'enum', 'range', 'list'
    )),
    unit            TEXT,                         -- 'cu.ft.', '°C', 'inches', 'liters'
    unit_system     TEXT DEFAULT 'imperial',      -- 'imperial', 'metric', 'none'
    family_scope    TEXT[] DEFAULT '{}',          -- which families use this; empty = all
    synonyms        TEXT[] DEFAULT '{}',          -- alternate names found in docs
    unit_conversions JSONB DEFAULT '{}',          -- {"liters": 28.3168} for cu.ft → liters
    allowed_values  JSONB,                       -- for enums: ["R290","R600a"]; numeric: {"min":0,"max":999}
    is_filterable   BOOLEAN DEFAULT true,         -- available as search filter
    is_comparable   BOOLEAN DEFAULT true,         -- shown in comparison views
    is_searchable   BOOLEAN DEFAULT true,         -- included in search index
    sort_order      INTEGER DEFAULT 100,          -- display ordering within a family
    auto_discovered BOOLEAN DEFAULT false,        -- true if found by pipeline, not manually defined
    approved        BOOLEAN DEFAULT true,         -- false until human reviews auto-discovered specs
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- Seed core specs that apply across most families
INSERT INTO spec_registry (canonical_name, display_name, data_type, unit, family_scope, synonyms, sort_order) VALUES
-- Capacity
('storage_capacity_cuft',   'Storage Capacity',         'numeric', 'cu.ft.',  '{}',
 ARRAY['capacity', 'cu ft', 'cubic feet', 'gross volume', 'cu. ft'], 10),
-- Temperature
('temp_range_min_c',        'Min Temperature',          'numeric', '°C',      '{}',
 ARRAY['minimum temperature', 'low temp', 'setpoint low'], 20),
('temp_range_max_c',        'Max Temperature',          'numeric', '°C',      '{}',
 ARRAY['maximum temperature', 'high temp', 'setpoint high'], 21),
-- Door
('door_count',              'Number of Doors',          'numeric', '',        '{}',
 ARRAY['doors'], 30),
('door_type',               'Door Type',                'enum',    '',        '{}',
 ARRAY['door style'], 31),
('door_hinge',              'Door Hinge',               'text',    '',        '{}',
 ARRAY['hinge side'], 32),
-- Shelves
('shelf_count',             'Number of Shelves',        'numeric', '',        '{}',
 ARRAY['shelves', 'shelf quantity'], 40),
('shelf_type',              'Shelf Type',               'enum',    '',        '{}',
 ARRAY['shelf configuration'], 41),
-- Exterior dimensions
('ext_width_in',            'Width (Exterior)',          'numeric', 'in',      '{}',
 ARRAY['width', 'external width', 'W"'], 50),
('ext_depth_in',            'Depth (Exterior)',          'numeric', 'in',      '{}',
 ARRAY['depth', 'external depth', 'D"'], 51),
('ext_height_in',           'Height (Exterior)',         'numeric', 'in',      '{}',
 ARRAY['height', 'external height', 'H"'], 52),
-- Interior dimensions
('int_width_in',            'Width (Interior)',          'numeric', 'in',      '{}',
 ARRAY['interior width'], 53),
('int_depth_in',            'Depth (Interior)',          'numeric', 'in',      '{}',
 ARRAY['interior depth'], 54),
('int_height_in',           'Height (Interior)',         'numeric', 'in',      '{}',
 ARRAY['interior height'], 55),
('door_swing_in',           'Door Swing',               'numeric', 'in',      '{}',
 ARRAY['door swing'], 56),
('total_open_depth_in',     'Total Open Depth',         'numeric', 'in',      '{}',
 ARRAY['total open depth'], 57),
-- Weight
('product_weight_lbs',      'Product Weight',           'numeric', 'lbs',     '{}',
 ARRAY['weight', 'unit weight', 'net weight'], 60),
('shipping_weight_lbs',     'Shipping Weight',          'numeric', 'lbs',     '{}',
 ARRAY['shipping weight'], 61),
-- Electrical
('voltage_v',               'Voltage',                  'numeric', 'V',       '{}',
 ARRAY['volts', 'VAC', 'supply voltage'], 70),
('frequency_hz',            'Frequency',                'numeric', 'Hz',      '{}',
 ARRAY['hertz'], 71),
('phase',                   'Phase',                    'numeric', '',        '{}',
 ARRAY['PH'], 72),
('amperage',                'Rated Amperage',           'numeric', 'A',       '{}',
 ARRAY['amps', 'rated amps'], 73),
('horsepower',              'Horsepower',               'text',    'HP',      '{}',
 ARRAY['H.P.', 'hp', 'motor'], 74),
('plug_type',               'Power Plug',               'text',    '',        '{}',
 ARRAY['NEMA', 'power cord', 'plug'], 75),
-- Refrigeration
('refrigerant',             'Refrigerant',              'text',    '',        '{}',
 ARRAY['refrigerant type', 'gas type'], 80),
('compressor_type',         'Compressor Type',          'text',    '',        '{}',
 ARRAY['compressor'], 81),
('defrost_type',            'Defrost Method',           'text',    '',        '{}',
 ARRAY['defrost'], 82),
('condenser_type',          'Condenser Type',           'text',    '',        '{}',
 ARRAY['condenser'], 83),
('evaporator_type',         'Evaporator Type',          'text',    '',        '{}',
 ARRAY['evaporator'], 84),
-- Performance
('uniformity_c',            'Temperature Uniformity',   'numeric', '±°C',     '{}',
 ARRAY['uniformity', 'cabinet air uniformity'], 90),
('stability_c',             'Temperature Stability',    'numeric', '±°C',     '{}',
 ARRAY['stability', 'cabinet air stability'], 91),
('max_temp_variation_c',    'Max Temp Variation',       'numeric', '°C',      '{}',
 ARRAY['maximum temperature variation'], 92),
('energy_kwh_day',          'Energy Consumption',       'numeric', 'kWh/day', '{}',
 ARRAY['energy consumption', 'daily energy'], 93),
('heat_rejection_btu_hr',   'Heat Rejection',           'numeric', 'BTU/hr',  '{}',
 ARRAY['average heat rejection'], 94),
('noise_dba',               'Noise Level',              'numeric', 'dBA',     '{}',
 ARRAY['noise', 'sound level', 'noise pressure'], 95),
('pulldown_time_min',       'Pull Down Time',           'numeric', 'min',     '{}',
 ARRAY['pull down time', 'pulldown', 'cool down'], 96),
-- Controller
('controller_type',         'Controller Technology',    'text',    '',        '{}',
 ARRAY['controller', 'temperature controller'], 100),
('display_type',            'Display Type',             'text',    '',        '{}',
 ARRAY['display technology', 'display'], 101),
('digital_comm',            'Digital Communication',    'text',    '',        '{}',
 ARRAY['RS-485', 'MODBUS', 'communication'], 102),
('data_transfer',           'Data Transfer',            'text',    '',        '{}',
 ARRAY['USB', 'data port'], 103),
('chart_recorder',          'Chart Recorder',           'text',    '',        '{}',
 ARRAY['chart recorder type'], 104),
('battery_backup',          'Battery Backup',           'text',    '',        '{}',
 ARRAY['battery', 'backup power'], 105),
-- Certifications
('certifications',          'Certifications',           'list',    '',        '{}',
 ARRAY['agency listing', 'listings', 'certified', 'agency listing and certification'], 110),
-- Warranty
('warranty_general_years',  'General Warranty',         'numeric', 'years',   '{}',
 ARRAY['general warranty', 'parts and labor warranty'], 120),
('warranty_compressor_years','Compressor Warranty',     'numeric', 'years',   '{}',
 ARRAY['compressor warranty', 'compressor parts warranty'], 121),
-- Construction
('mounting_type',           'Mounting/Installation',    'text',    '',        '{}',
 ARRAY['mounting', 'installation', 'casters', 'leveling legs'], 130),
('interior_lighting',       'Interior Lighting',        'text',    '',        '{}',
 ARRAY['interior light', 'LED'], 131),
('airflow_type',            'Airflow Management',       'text',    '',        '{}',
 ARRAY['airflow', 'forced draft', 'forced air', 'circulation'], 132),
('probe_access',            'Probe Access Port',        'text',    '',        '{}',
 ARRAY['probe access', 'probe hole', 'external probe'], 133),
('insulation_type',         'Insulation',               'text',    '',        '{}',
 ARRAY['insulation', 'urethane foam'], 134),
('exterior_material',       'Exterior Material',        'text',    '',        '{}',
 ARRAY['exterior materials', 'cabinet material'], 135),
('access_control',          'Access Control',           'text',    '',        '{}',
 ARRAY['door lock', 'keyed lock', 'key lock', 'access'], 136),
-- Cryogenic-specific
('ln2_capacity_liters',     'LN2 Capacity',             'numeric', 'liters',
 ARRAY['cryo_dewar','vapor_shipper','cryo_freezer'],
 ARRAY['liquid nitrogen capacity'], 200),
('static_holding_time_days','Static Holding Time',      'numeric', 'days',
 ARRAY['cryo_dewar','vapor_shipper','cryo_freezer'],
 ARRAY['holding time', 'working time'], 201),
('evaporation_rate_l_day',  'Static Evaporation Rate',  'numeric', 'L/day',
 ARRAY['cryo_dewar','vapor_shipper','cryo_freezer'],
 ARRAY['evaporation rate'], 202),
('neck_diameter_in',        'Neck Diameter',            'numeric', 'in',
 ARRAY['cryo_dewar','vapor_shipper','cryo_freezer'],
 ARRAY['inner neck diameter', 'neck diameter'], 203),
('vial_capacity_2ml',       'Vial Capacity (2ml)',      'numeric', '',
 ARRAY['cryo_dewar','vapor_shipper','cryo_freezer'],
 ARRAY['total vial capacity', 'vial capacity'], 204),
('box_capacity',            'Box Capacity',             'numeric', '',
 ARRAY['cryo_dewar','cryo_freezer'],
 ARRAY['box capacity'], 205),
('rack_capacity',           'Rack Capacity',            'numeric', '',
 ARRAY['cryo_dewar','cryo_freezer'],
 ARRAY['rack capacity'], 206),
('vacuum_warranty_years',   'Vacuum Warranty',          'numeric', 'years',
 ARRAY['cryo_dewar','vapor_shipper','cryo_freezer'],
 ARRAY['vacuum warranty'], 207),
-- Blood bank specific
('fda_class',               'FDA Device Class',         'text',    '',
 ARRAY['blood_bank_ref','plasma_freezer'],
 ARRAY['FDA class', 'FDA listed'], 210),
('cfr_compliance',          'CFR Compliance',           'text',    '',
 ARRAY['blood_bank_ref','plasma_freezer'],
 ARRAY['21CFR', 'CFR part 820'], 211),
('aabb_compliant',          'AABB Compliant',           'boolean', '',
 ARRAY['blood_bank_ref'],
 ARRAY['AABB', 'AABB standards'], 212),
('drawer_count',            'Drawer Count',             'numeric', '',
 ARRAY['blood_bank_ref'],
 ARRAY['drawers', 'drawer quantity'], 213),
('drawer_material',         'Drawer Material',          'text',    '',
 ARRAY['blood_bank_ref'],
 ARRAY['304 SS', 'stainless steel drawers'], 214),
('drawer_capacity_lbs',     'Drawer Capacity',          'numeric', 'lbs',
 ARRAY['blood_bank_ref'],
 ARRAY['drawer capacity', 'lb capacity'], 215),
-- Flammable specific
('nfpa_compliance',         'NFPA Compliance',          'list',    '',
 ARRAY['flammable_storage_ref'],
 ARRAY['NFPA 45', 'NFPA 30'], 220),
('intrinsically_safe',      'Intrinsically Safe Interior','boolean','',
 ARRAY['flammable_storage_ref'],
 ARRAY['intrinsically safe', 'non-sparking', 'ATEX'], 221),
-- Freezer specific
('freezer_compartments',    'Freezer Compartments',     'numeric', '',
 ARRAY['manual_defrost_freezer'],
 ARRAY['inner doors', 'fast-freeze compartments'], 230),
('compressor_speed_range',  'Compressor Speed Range',   'text',    'RPM',
 ARRAY['precision_freezer','blood_bank_ref'],
 ARRAY['rated speed range', 'VSC'], 231);

-- ============================================================
-- 4. PRODUCTS (core table)
-- ============================================================
CREATE TABLE products (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_number        TEXT NOT NULL,
    brand_id            UUID NOT NULL REFERENCES brands(id),
    family_id           UUID NOT NULL REFERENCES product_families(id),
    product_line        TEXT,                    -- 'Premier', 'Ultra Touch', 'Precision', 'FUTURA'
    controller_tier     TEXT,                    -- 'standard', 'ultra_touch', 'precision', 'pid_blood_bank'
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN (
        'draft', 'pending_review', 'active', 'discontinued', 'deprecated'
    )),

    -- Universal fixed columns (queryable, indexed)
    storage_capacity_cuft   NUMERIC,
    temp_range_min_c        NUMERIC,
    temp_range_max_c        NUMERIC,
    door_count              INTEGER,
    door_type               TEXT,                -- 'solid', 'glass', 'glass_sliding'
    shelf_count             INTEGER,
    refrigerant             TEXT,                -- 'R290', 'R600a', 'R134a', null (cryogenic)
    voltage_v               INTEGER,
    amperage                NUMERIC,
    product_weight_lbs      NUMERIC,
    ext_width_in            NUMERIC,
    ext_depth_in            NUMERIC,
    ext_height_in           NUMERIC,

    -- Dynamic specs (family-specific, validated against spec_registry)
    specs                   JSONB NOT NULL DEFAULT '{}',

    -- Certifications as searchable array
    certifications          TEXT[] DEFAULT '{}',

    -- Lifecycle
    effective_from          DATE DEFAULT CURRENT_DATE,
    effective_to            DATE,
    version                 INTEGER NOT NULL DEFAULT 1,
    replaced_by             UUID[],
    replaces                UUID[],

    -- Metadata
    description             TEXT,
    revision                TEXT,               -- 'Rev_03.18.25'
    approval_status         TEXT DEFAULT 'approved' CHECK (approval_status IN (
        'draft', 'pending_review', 'approved', 'rejected'
    )),
    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now(),
    updated_by              TEXT,

    UNIQUE(model_number, version)
);

CREATE INDEX idx_products_brand ON products(brand_id);
CREATE INDEX idx_products_family ON products(family_id);
CREATE INDEX idx_products_status ON products(status);
CREATE INDEX idx_products_model ON products(model_number);
CREATE INDEX idx_products_capacity ON products(storage_capacity_cuft);
CREATE INDEX idx_products_temp ON products(temp_range_min_c, temp_range_max_c);
CREATE INDEX idx_products_door ON products(door_type);
CREATE INDEX idx_products_refrigerant ON products(refrigerant);
CREATE INDEX idx_products_certs ON products USING gin(certifications);
CREATE INDEX idx_products_specs ON products USING gin(specs jsonb_path_ops);

-- Full text search on model number and description
ALTER TABLE products ADD COLUMN search_vector TSVECTOR
    GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(model_number, '') || ' ' ||
            coalesce(product_line, '') || ' ' ||
            coalesce(description, '')
        )
    ) STORED;
CREATE INDEX idx_products_fts ON products USING gin(search_vector);

-- ============================================================
-- 5. PRODUCT RELATIONSHIPS
-- ============================================================
CREATE TABLE product_relationships (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       UUID NOT NULL REFERENCES products(id),
    target_id       UUID NOT NULL REFERENCES products(id),
    relationship    TEXT NOT NULL CHECK (relationship IN (
        'supersedes', 'equivalent_to', 'compatible_with',
        'accessory_for', 'variant_of', 'rebrand_of'
    )),
    confidence      FLOAT DEFAULT 1.0,
    notes           TEXT,
    auto_detected   BOOLEAN DEFAULT false,
    created_at      TIMESTAMPTZ DEFAULT now(),
    created_by      TEXT,
    UNIQUE(source_id, target_id, relationship)
);

CREATE INDEX idx_rel_source ON product_relationships(source_id);
CREATE INDEX idx_rel_target ON product_relationships(target_id);

-- ============================================================
-- 6. DOCUMENTS
-- ============================================================
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename        TEXT NOT NULL,
    doc_type        TEXT NOT NULL CHECK (doc_type IN (
        'product_data_sheet', 'cut_sheet', 'feature_list',
        'performance_data_sheet', 'product_image',
        'dimensional_drawing', 'selection_guide',
        'install_manual', 'marketing', 'catalog', 'other'
    )),
    mime_type       TEXT NOT NULL,
    source_uri      TEXT NOT NULL,               -- blob://container/path
    checksum_sha256 TEXT NOT NULL,
    file_size_bytes BIGINT,
    page_count      INTEGER,
    extracted_text  TEXT,
    metadata        JSONB DEFAULT '{}',
    brand_id        UUID REFERENCES brands(id),
    status          TEXT DEFAULT 'processed' CHECK (status IN (
        'pending', 'processing', 'processed', 'failed',
        'superseded', 'quarantined'
    )),
    processing_log  JSONB DEFAULT '[]',          -- [{stage, status, message, timestamp}]
    version         INTEGER DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT now(),
    processed_at    TIMESTAMPTZ,
    UNIQUE(checksum_sha256)
);

CREATE INDEX idx_docs_status ON documents(status);
CREATE INDEX idx_docs_type ON documents(doc_type);
CREATE INDEX idx_docs_brand ON documents(brand_id);

-- ============================================================
-- 7. DOCUMENT ↔ PRODUCT LINKAGE
-- ============================================================
CREATE TABLE document_products (
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    product_id      UUID NOT NULL REFERENCES products(id),
    relevance       TEXT DEFAULT 'primary' CHECK (relevance IN (
        'primary', 'mentioned', 'accessory', 'related'
    )),
    extracted_specs JSONB DEFAULT '{}',          -- specs extracted from THIS doc for THIS product
    confidence      FLOAT DEFAULT 1.0,
    created_at      TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (document_id, product_id)
);

-- ============================================================
-- 8. DOCUMENT CHUNKS (for RAG retrieval)
-- ============================================================
CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,
    chunk_type      TEXT DEFAULT 'text' CHECK (chunk_type IN (
        'text', 'table', 'spec_block', 'header',
        'performance_data', 'dimensional', 'description'
    )),
    page_number     INTEGER,
    section_title   TEXT,
    product_ids     UUID[] DEFAULT '{}',
    spec_names      TEXT[] DEFAULT '{}',          -- canonical spec names mentioned
    metadata        JSONB DEFAULT '{}',
    embedding       VECTOR(1024),                -- e5-large-v2 or equivalent
    token_count     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_chunks_doc ON document_chunks(document_id);
CREATE INDEX idx_chunks_type ON document_chunks(chunk_type);
CREATE INDEX idx_chunks_products ON document_chunks USING gin(product_ids);
CREATE INDEX idx_chunks_embedding ON document_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- 9. EQUIVALENCE RULES (configurable per family)
-- ============================================================
CREATE TABLE equivalence_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    family_id       UUID NOT NULL REFERENCES product_families(id),
    rule_name       TEXT NOT NULL,
    required_match  TEXT[] NOT NULL,              -- spec names that must match exactly
    tolerance_map   JSONB NOT NULL DEFAULT '{}',  -- {"storage_capacity_cuft": 0.15}
    priority_specs  TEXT[] DEFAULT '{}',          -- tiebreaker ordering
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_by      TEXT
);

-- ============================================================
-- 10. PRODUCT VERSION HISTORY
-- ============================================================
CREATE TABLE product_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id      UUID NOT NULL REFERENCES products(id),
    version         INTEGER NOT NULL,
    snapshot        JSONB NOT NULL,               -- full product record as JSON
    change_summary  TEXT,
    changed_by      TEXT,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_pv_product ON product_versions(product_id);

-- ============================================================
-- 11. INGESTION JOBS
-- ============================================================
CREATE TABLE ingestion_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status          TEXT NOT NULL DEFAULT 'queued' CHECK (status IN (
        'queued', 'processing', 'completed', 'failed', 'cancelled'
    )),
    total_files     INTEGER DEFAULT 0,
    processed_files INTEGER DEFAULT 0,
    failed_files    INTEGER DEFAULT 0,
    new_products    INTEGER DEFAULT 0,
    updated_products INTEGER DEFAULT 0,
    new_specs_discovered INTEGER DEFAULT 0,
    conflicts_found INTEGER DEFAULT 0,
    submitted_by    TEXT,
    metadata        JSONB DEFAULT '{}',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 12. SPEC CONFLICTS (flagged for human review)
-- ============================================================
CREATE TABLE spec_conflicts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id      UUID NOT NULL REFERENCES products(id),
    spec_name       TEXT NOT NULL,
    existing_value  TEXT,
    new_value       TEXT,
    source_doc_id   UUID REFERENCES documents(id),
    existing_doc_id UUID REFERENCES documents(id),
    severity        TEXT DEFAULT 'medium' CHECK (severity IN ('low','medium','high','critical')),
    resolution      TEXT CHECK (resolution IN (
        'pending', 'keep_existing', 'accept_new', 'manual_override', 'dismissed'
    )) DEFAULT 'pending',
    resolved_value  TEXT,
    resolved_by     TEXT,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_conflicts_product ON spec_conflicts(product_id);
CREATE INDEX idx_conflicts_status ON spec_conflicts(resolution);

-- ============================================================
-- 13. AUDIT LOG (append-only)
-- ============================================================
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id         TEXT NOT NULL,
    user_role       TEXT NOT NULL,
    action          TEXT NOT NULL,
    entity_type     TEXT,
    entity_id       TEXT,
    request_summary JSONB,
    response_summary JSONB,
    retrieved_doc_ids TEXT[],
    ip_address      INET,
    session_id      TEXT,
    response_time_ms INTEGER,
    llm_calls       JSONB
);

-- Partition by month for performance
CREATE INDEX idx_audit_time ON audit_log(timestamp);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_user ON audit_log(user_id);

-- Prevent deletes/updates on audit log
CREATE RULE no_update_audit AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
CREATE RULE no_delete_audit AS ON DELETE TO audit_log DO INSTEAD NOTHING;

-- ============================================================
-- 14. USERS & ROLES (basic RBAC)
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN (
        'customer', 'sales_engineer', 'product_manager', 'admin'
    )),
    brand_access    TEXT[] DEFAULT '{}',          -- empty = all brands
    region          TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- 15. MODEL NUMBER PATTERNS (configurable, not hardcoded)
-- ============================================================
CREATE TABLE model_patterns (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id        UUID NOT NULL REFERENCES brands(id),
    pattern_regex   TEXT NOT NULL,
    family_id       UUID NOT NULL REFERENCES product_families(id),
    product_line    TEXT,
    controller_tier TEXT,
    field_map       JSONB DEFAULT '{}',          -- {"group_1": "capacity", "group_2": "door_type"}
    value_map       JSONB DEFAULT '{}',          -- {"S": "solid", "G": "glass"}
    priority        INTEGER DEFAULT 0,           -- higher = checked first
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Function to auto-register a new spec during ingestion
CREATE OR REPLACE FUNCTION register_spec_if_new(
    p_name TEXT, p_display TEXT, p_type TEXT,
    p_unit TEXT DEFAULT '', p_families TEXT[] DEFAULT '{}'
) RETURNS UUID AS $$
DECLARE
    v_id UUID;
BEGIN
    SELECT id INTO v_id FROM spec_registry WHERE canonical_name = p_name;
    IF v_id IS NULL THEN
        INSERT INTO spec_registry (canonical_name, display_name, data_type, unit, family_scope, auto_discovered, approved)
        VALUES (p_name, p_display, p_type, p_unit, p_families, true, false)
        RETURNING id INTO v_id;
    END IF;
    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

-- Function to create product version snapshot before update
CREATE OR REPLACE FUNCTION snapshot_product_version()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.version <> NEW.version OR OLD.specs <> NEW.specs THEN
        INSERT INTO product_versions (product_id, version, snapshot, change_summary, changed_by)
        VALUES (OLD.id, OLD.version, to_jsonb(OLD), 'Auto-snapshot before update', NEW.updated_by);
    END IF;
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_product_version
    BEFORE UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION snapshot_product_version();
