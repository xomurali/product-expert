-- ============================================================
-- seed.sql — Reference Data for Product Expert System
-- Run after db-schema.sql (docker-entrypoint-initdb.d/02-seed.sql)
-- ============================================================

BEGIN;

-- ============================================================
-- 1. BRANDS (idempotent — schema already inserts these, but ON CONFLICT for safety)
-- ============================================================
INSERT INTO brands (code, name, parent_org) VALUES
    ('ABS',       'American BioTech Supply',  'Horizon Scientific'),
    ('LABRepCo',  'LABRepCo',                 'Horizon Scientific'),
    ('Corepoint', 'Corepoint Scientific',     'Horizon Scientific'),
    ('Celsius',   '°celsius Scientific',      'Horizon Scientific'),
    ('CBS',       'CBS / CryoSafe',           'Horizon Scientific')
ON CONFLICT (code) DO NOTHING;


-- ============================================================
-- 2. PRODUCT FAMILIES
-- ============================================================
INSERT INTO product_families (code, name, super_category, brand_id, description) VALUES
    -- Refrigerators
    ('premier_lab_ref',        'Premier Laboratory Refrigerator',    'refrigerator',
     (SELECT id FROM brands WHERE code = 'ABS'),
     'Full-size premier lab refrigerators with microprocessor control, 1–49 cu.ft.'),

    ('standard_lab_ref',       'Standard Laboratory Refrigerator',   'refrigerator',
     (SELECT id FROM brands WHERE code = 'ABS'),
     'Value-oriented lab refrigerators for general storage.'),

    ('chromatography_ref',     'Chromatography Refrigerator',        'refrigerator',
     (SELECT id FROM brands WHERE code = 'ABS'),
     'Pass-through refrigerators designed for HPLC/GC chromatography systems.'),

    ('pharmacy_vaccine_ref',   'Pharmacy/Vaccine Refrigerator',      'refrigerator',
     NULL,
     'Pharmacy-grade refrigerators for CDC-compliant vaccine storage, 2–8°C.'),

    ('pharmacy_nsf_ref',       'Pharmacy/Vaccine NSF Certified',     'refrigerator',
     NULL,
     'NSF/ANSI 456 certified pharmacy refrigerators with validated temperature performance.'),

    ('blood_bank_ref',         'Blood Bank Refrigerator',            'refrigerator',
     (SELECT id FROM brands WHERE code = 'ABS'),
     'AABB-compliant blood storage refrigerators, 1–6°C.'),

    ('flammable_storage_ref',  'Flammable Material Storage',         'refrigerator',
     (SELECT id FROM brands WHERE code = 'ABS'),
     'Spark-free interior refrigerators and freezers for flammable/volatile chemicals. NFPA 45 compliant.'),

    ('undercounter_ref',       'Undercounter Refrigerator',          'refrigerator',
     NULL,
     'Compact undercounter units for space-constrained installations, ≤34.5" height.'),

    -- Freezers
    ('manual_defrost_freezer',  'Manual Defrost Freezer',            'freezer',
     (SELECT id FROM brands WHERE code = 'ABS'),
     'Manual defrost lab freezers, -15°C to -25°C.'),

    ('auto_defrost_freezer',    'Auto Defrost Freezer',              'freezer',
     (SELECT id FROM brands WHERE code = 'ABS'),
     'Frost-free auto-defrost lab freezers.'),

    ('precision_freezer',       'Precision Series Freezer',          'freezer',
     (SELECT id FROM brands WHERE code = 'ABS'),
     'High-performance freezers with tight uniformity for sensitive samples.'),

    ('ultra_low_freezer',       'Ultra-Low Freezer',                 'freezer',
     NULL,
     'Ultra-low temperature freezers, -40°C to -86°C.'),

    ('plasma_freezer',          'Plasma Storage Freezer',            'freezer',
     (SELECT id FROM brands WHERE code = 'ABS'),
     'Rapid-freeze plasma storage units, -25°C to -40°C.'),

    -- Cryogenic
    ('cryo_dewar',              'Cryogenic Dewar',                   'cryogenic',
     (SELECT id FROM brands WHERE code = 'CBS'),
     'Liquid nitrogen dewars for long-term cryogenic sample storage, -150°C to -196°C.'),

    ('vapor_shipper',           'Vapor Shipper',                     'cryogenic',
     (SELECT id FROM brands WHERE code = 'CBS'),
     'Dry vapor shippers for safe transport of cryogenic samples.'),

    ('cryo_freezer',            'CryoMizer Freezer',                 'cryogenic',
     (SELECT id FROM brands WHERE code = 'CBS'),
     'Mechanical cryogenic freezers as LN2-free alternatives.'),

    -- Accessories
    ('accessory',               'Accessory',                         'accessory',
     NULL,
     'Shelves, drawers, locks, data loggers, and other accessories.')
ON CONFLICT (code) DO NOTHING;


-- ============================================================
-- 3. SPEC REGISTRY — Core specifications across all families
-- ============================================================
INSERT INTO spec_registry (canonical_name, display_name, data_type, unit, unit_system,
                           family_scope, synonyms, unit_conversions,
                           is_filterable, is_comparable, is_critical, sort_order) VALUES

-- ── Capacity ────────────────────────────────────────────────
('storage_capacity_cuft', 'Storage Capacity', 'numeric', 'cu.ft.', 'imperial',
 '{}',
 ARRAY['capacity', 'cu ft', 'cubic feet', 'gross volume', 'cu. ft', 'volume', 'size', 'storage space'],
 '{"liters": 28.3168}'::jsonb,
 true, true, true, 10),

('shelf_count', 'Shelf Count', 'numeric', '', 'none',
 '{}',
 ARRAY['shelves', 'shelf', 'how many shelves', 'number of shelves', 'adjustable shelves'],
 '{}'::jsonb,
 true, true, false, 15),

-- ── Temperature ─────────────────────────────────────────────
('temp_range_min_c', 'Min Temperature', 'numeric', '°C', 'metric',
 '{}',
 ARRAY['minimum temperature', 'low temp', 'lowest temp', 'coldest', 'min temp', 'setpoint range low'],
 '{"F": "convert_f_to_c"}'::jsonb,
 true, true, true, 20),

('temp_range_max_c', 'Max Temperature', 'numeric', '°C', 'metric',
 '{}',
 ARRAY['maximum temperature', 'high temp', 'highest temp', 'warmest', 'max temp', 'setpoint range high'],
 '{"F": "convert_f_to_c"}'::jsonb,
 true, true, true, 21),

('uniformity_c', 'Temperature Uniformity', 'numeric', '°C', 'metric',
 '{}',
 ARRAY['uniformity', 'temperature uniformity', 'temp uniformity', 'even temperature', 'consistent temp'],
 '{}'::jsonb,
 true, true, true, 22),

('stability_c', 'Temperature Stability', 'numeric', '°C', 'metric',
 '{}',
 ARRAY['stability', 'temperature stability', 'temp stability', 'temperature fluctuation'],
 '{}'::jsonb,
 true, true, true, 23),

-- ── Doors ───────────────────────────────────────────────────
('door_type', 'Door Type', 'enum', '', 'none',
 '{}',
 ARRAY['door', 'solid door', 'glass door', 'sliding door', 'door style', 'door configuration'],
 '{}'::jsonb,
 true, true, false, 30),

('door_count', 'Number of Doors', 'numeric', '', 'none',
 '{}',
 ARRAY['doors', 'door quantity', 'how many doors'],
 '{}'::jsonb,
 true, true, false, 31),

-- ── Dimensions ──────────────────────────────────────────────
('ext_width_in', 'Width (Exterior)', 'numeric', 'in', 'imperial',
 '{}',
 ARRAY['width', 'w', 'external width', 'wide', 'how wide'],
 '{"mm": 0.03937, "cm": 0.3937}'::jsonb,
 true, true, false, 40),

('ext_depth_in', 'Depth (Exterior)', 'numeric', 'in', 'imperial',
 '{}',
 ARRAY['depth', 'd', 'external depth', 'deep', 'how deep'],
 '{"mm": 0.03937, "cm": 0.3937}'::jsonb,
 true, true, false, 41),

('ext_height_in', 'Height (Exterior)', 'numeric', 'in', 'imperial',
 '{}',
 ARRAY['height', 'h', 'external height', 'tall', 'how tall'],
 '{"mm": 0.03937, "cm": 0.3937}'::jsonb,
 true, true, false, 42),

('product_weight_lbs', 'Product Weight', 'numeric', 'lbs', 'imperial',
 '{}',
 ARRAY['weight', 'heavy', 'how heavy', 'lbs', 'net weight', 'shipping weight'],
 '{"kg": 2.20462}'::jsonb,
 true, true, false, 43),

-- ── Electrical ──────────────────────────────────────────────
('voltage_v', 'Voltage', 'numeric', 'V', 'none',
 '{}',
 ARRAY['voltage', 'volts', 'VAC', 'supply voltage', '115v', '220v'],
 '{}'::jsonb,
 true, true, true, 50),

('amperage', 'Rated Amperage', 'numeric', 'A', 'none',
 '{}',
 ARRAY['amps', 'rated amps', 'current draw', 'rated amperage', 'electrical'],
 '{}'::jsonb,
 true, true, false, 51),

('plug_type', 'Power Plug', 'enum', '', 'none',
 '{}',
 ARRAY['plug', 'power cord', 'NEMA plug', 'power connector', 'receptacle'],
 '{}'::jsonb,
 false, true, false, 52),

('frequency_hz', 'Line Frequency', 'numeric', 'Hz', 'none',
 '{}',
 ARRAY['frequency', 'hertz', 'hz', 'cycles'],
 '{}'::jsonb,
 false, true, false, 53),

-- ── Performance ─────────────────────────────────────────────
('energy_kwh_day', 'Energy Consumption', 'numeric', 'kWh/day', 'none',
 '{}',
 ARRAY['energy', 'power consumption', 'energy consumption', 'electricity', 'kwh', 'energy efficient', 'running cost'],
 '{"kwh_year": 365}'::jsonb,
 true, true, false, 60),

('noise_dba', 'Noise Level', 'numeric', 'dBA', 'none',
 '{}',
 ARRAY['noise', 'sound', 'decibel', 'dba', 'how loud', 'quiet', 'sound level'],
 '{}'::jsonb,
 true, true, false, 61),

('pulldown_time_min', 'Pulldown Time', 'numeric', 'min', 'none',
 '{}',
 ARRAY['pulldown', 'pull down', 'cool down time', 'recovery time'],
 '{}'::jsonb,
 false, true, false, 62),

-- ── Refrigeration System ────────────────────────────────────
('refrigerant', 'Refrigerant', 'enum', '', 'none',
 '{}',
 ARRAY['refrigerant', 'r290', 'r600a', 'r134a', 'hydrocarbon', 'natural refrigerant', 'gas type'],
 '{}'::jsonb,
 true, true, false, 70),

('compressor_type', 'Compressor', 'text', '', 'none',
 '{}',
 ARRAY['compressor', 'compressor type', 'hermetic compressor'],
 '{}'::jsonb,
 false, true, false, 71),

('condenser_type', 'Condenser', 'text', '', 'none',
 '{}',
 ARRAY['condenser', 'condenser type', 'fan-cooled condenser'],
 '{}'::jsonb,
 false, true, false, 72),

('evaporator_type', 'Evaporator', 'text', '', 'none',
 '{}',
 ARRAY['evaporator', 'evaporator type'],
 '{}'::jsonb,
 false, true, false, 73),

('defrost_type', 'Defrost Type', 'enum', '', 'none',
 '{}',
 ARRAY['defrost', 'manual defrost', 'auto defrost', 'cycle defrost', 'frost free', 'automatic defrost'],
 '{}'::jsonb,
 true, true, false, 74),

-- ── Controller & Display ────────────────────────────────────
('controller_type', 'Controller Technology', 'enum', '', 'none',
 '{}',
 ARRAY['controller', 'controller technology', 'temperature controller', 'microprocessor'],
 '{}'::jsonb,
 true, true, false, 80),

('display_type', 'Display Type', 'enum', '', 'none',
 '{}',
 ARRAY['display', 'readout', 'screen', 'LED display', 'LCD display', 'touchscreen'],
 '{}'::jsonb,
 false, true, false, 81),

('digital_communication', 'Digital Communication', 'enum', '', 'none',
 ARRAY['premier_lab_ref'],
 ARRAY['communication', 'data interface', 'MODBUS', 'RS-485', 'RS485'],
 '{}'::jsonb,
 false, true, false, 82),

('data_transfer', 'Data Transfer', 'enum', '', 'none',
 '{}',
 ARRAY['data transfer', 'USB', 'data logging', 'data download'],
 '{}'::jsonb,
 false, true, false, 83),

-- ── Construction ────────────────────────────────────────────
('exterior_material', 'Exterior Material', 'text', '', 'none',
 '{}',
 ARRAY['exterior', 'exterior finish', 'cabinet material', 'housing material'],
 '{}'::jsonb,
 false, true, false, 90),

('insulation_type', 'Insulation', 'text', '', 'none',
 '{}',
 ARRAY['insulation', 'foam', 'CFC-free', 'HFC-free'],
 '{}'::jsonb,
 false, true, false, 91),

('interior_lighting', 'Interior Lighting', 'text', '', 'none',
 '{}',
 ARRAY['lighting', 'interior light', 'LED light', 'lamp'],
 '{}'::jsonb,
 false, false, false, 92),

('airflow_type', 'Airflow Type', 'enum', '', 'none',
 '{}',
 ARRAY['airflow', 'forced air', 'natural convection', 'fan circulation'],
 '{}'::jsonb,
 false, true, false, 93),

-- ── Certifications ──────────────────────────────────────────
('certifications', 'Certifications', 'list', '', 'none',
 '{}',
 ARRAY['certification', 'certified', 'listed', 'etl', 'ul', 'energy star', 'nsf', 'fda', 'aabb', 'nfpa', 'agency listing'],
 '{}'::jsonb,
 true, true, true, 100),

-- ── Access & Security ───────────────────────────────────────
('access_control', 'Access Control', 'text', '', 'none',
 '{}',
 ARRAY['lock', 'key lock', 'access control', 'security', 'PIN pad'],
 '{}'::jsonb,
 false, true, false, 110),

('probe_access', 'Probe Access Port', 'text', '', 'none',
 '{}',
 ARRAY['probe port', 'probe access', 'cord access', 'access port'],
 '{}'::jsonb,
 false, false, false, 111),

-- ── Warranty ────────────────────────────────────────────────
('warranty_general_years', 'General Warranty', 'numeric', 'years', 'none',
 '{}',
 ARRAY['warranty', 'guarantee', 'parts warranty', 'labor warranty'],
 '{}'::jsonb,
 true, true, false, 120),

('warranty_compressor_years', 'Compressor Warranty', 'numeric', 'years', 'none',
 '{}',
 ARRAY['compressor warranty', 'extended warranty'],
 '{}'::jsonb,
 false, true, false, 121),

-- ── Environment ─────────────────────────────────────────────
('ambient_operating_range', 'Ambient Operating Range', 'text', '', 'none',
 '{}',
 ARRAY['ambient', 'operating environment', 'ambient temperature', 'ambient range'],
 '{}'::jsonb,
 false, false, false, 130),

('mounting_type', 'Mounting Type', 'enum', '', 'none',
 '{}',
 ARRAY['mounting', 'freestanding', 'built-in', 'undercounter', 'stackable'],
 '{}'::jsonb,
 true, true, false, 131)

ON CONFLICT (canonical_name) DO UPDATE SET
    display_name   = EXCLUDED.display_name,
    synonyms       = EXCLUDED.synonyms,
    unit           = EXCLUDED.unit,
    sort_order     = EXCLUDED.sort_order;


-- ============================================================
-- 4. MODEL NUMBER PATTERNS
-- ============================================================
INSERT INTO model_patterns (brand_id, pattern, family_code, product_line, description, example) VALUES

-- ABS Premier Lab Refrigerators: ABT-HC-{capacity}{S|G}
((SELECT id FROM brands WHERE code = 'ABS'),
 '^ABT-HC-(\d+)(S|G)$',
 'premier_lab_ref', 'Premier',
 'Premier lab refrigerators. Group 1 = capacity, Group 2 = S(solid)/G(glass) door.',
 'ABT-HC-26S'),

-- ABS Standard Lab: ABT-HC-{capacity}R
((SELECT id FROM brands WHERE code = 'ABS'),
 '^ABT-HC-(\d+)R$',
 'standard_lab_ref', 'Standard',
 'Standard lab refrigerators. Group 1 = capacity.',
 'ABT-HC-23R'),

-- ABS Chromatography: ABT-HC-CS-{capacity}
((SELECT id FROM brands WHERE code = 'ABS'),
 '^ABT-HC-CS-(\d+)$',
 'chromatography_ref', 'Premier',
 'Chromatography refrigerators. Group 1 = capacity.',
 'ABT-HC-CS-23'),

-- ABS Pharmacy: PH-ABT-HC-{model}
((SELECT id FROM brands WHERE code = 'ABS'),
 '^PH-ABT-HC-([\w-]+)$',
 'pharmacy_vaccine_ref', 'Pharmacy',
 'Pharmacy/vaccine refrigerators.',
 'PH-ABT-HC-RFC1030G'),

-- ABS Pharmacy NSF: PH-ABT-NSF-{model}
((SELECT id FROM brands WHERE code = 'ABS'),
 '^PH-ABT-NSF-([\w-]+)$',
 'pharmacy_nsf_ref', 'Pharmacy NSF',
 'NSF/ANSI 456 certified pharmacy units.',
 'PH-ABT-NSF-DERA-15'),

-- ABS Undercounter: ABT-HC-UCBI-{capacity}
((SELECT id FROM brands WHERE code = 'ABS'),
 '^ABT-HC-UCBI-(\d+)$',
 'undercounter_ref', 'Premier',
 'Undercounter built-in refrigerators. Group 1 = capacity (x100 = cu.ft x 100).',
 'ABT-HC-UCBI-0420'),

-- ABS Manual Defrost Freezer: ABT-HC-MFP-{capacity}
((SELECT id FROM brands WHERE code = 'ABS'),
 '^ABT-HC-MFP-(\d+)(-TS)?$',
 'manual_defrost_freezer', 'Premier',
 'Manual defrost freezers. -TS suffix = TempLog model.',
 'ABT-HC-MFP-23-TS'),

-- ABS Flammable: ABT-HC-FFP-{capacity}
((SELECT id FROM brands WHERE code = 'ABS'),
 '^ABT-HC-FFP-(\d+)$',
 'flammable_storage_ref', 'Premier',
 'Flammable material storage freezers.',
 'ABT-HC-FFP-14'),

-- ABS Plasma Freezer: ABT-HC-PFP-{capacity}
((SELECT id FROM brands WHERE code = 'ABS'),
 '^ABT-HC-PFP-(\d+)$',
 'plasma_freezer', 'Premier',
 'Plasma storage freezers.',
 'ABT-HC-PFP-20'),

-- LABRepCo: LHT-{capacity}-{suffix}
((SELECT id FROM brands WHERE code = 'LABRepCo'),
 '^LHT-(\d+)-([A-Z]+)$',
 'premier_lab_ref', 'Futura Silver',
 'LABRepCo Futura Silver refrigerators.',
 'LHT-23-?"'),

-- LABRepCo: LRP-HC-RFC-{model}
((SELECT id FROM brands WHERE code = 'LABRepCo'),
 '^LRP-HC-RFC-([\w-]+)$',
 'premier_lab_ref', 'Futura Silver',
 'LABRepCo Futura Silver refrigerators (new naming).',
 'LRP-HC-RFC-2304G'),

-- LABRepCo Vaccine: LPVT-{capacity}-{suffix}
((SELECT id FROM brands WHERE code = 'LABRepCo'),
 '^LPVT-(\d+)-([A-Z]+)$',
 'pharmacy_vaccine_ref', 'Futura Platinum',
 'LABRepCo pharmacy/vaccine refrigerators.',
 'LPVT-16-NSG'),

-- Corepoint: CP-HC-{model}
((SELECT id FROM brands WHERE code = 'Corepoint'),
 '^CP-HC-([\w-]+)$',
 'premier_lab_ref', 'Corepoint',
 'Corepoint Scientific refrigerators and freezers.',
 'CP-HC-16NSGA'),

-- Corepoint NSF: NSBR{capacity}{suffix}
((SELECT id FROM brands WHERE code = 'Corepoint'),
 '^NSBR(\d+)(\w+)/(\d)$',
 'pharmacy_nsf_ref', 'NSF Vaccine',
 'Corepoint NSF/ANSI 456 vaccine units.',
 'NSBR161WSW/0'),

-- Celsius: CEL-{model}
((SELECT id FROM brands WHERE code = 'Celsius'),
 '^CEL-([\w-]+)$',
 'premier_lab_ref', 'Celsius',
 '°celsius Scientific refrigerators.',
 'CEL-HC-23G'),

-- CBS Cryogenic Dewars: CBS-{model}
((SELECT id FROM brands WHERE code = 'CBS'),
 '^CBS-(\d+)(-[A-Z]+)?$',
 'cryo_dewar', 'CryoSafe',
 'CBS/CryoSafe cryogenic dewars and vapor shippers.',
 'CBS-2105-PA')

ON CONFLICT DO NOTHING;


-- ============================================================
-- 5. DEFAULT USERS (API key auth mapping)
-- ============================================================
INSERT INTO users (username, email, role, api_key_hash, is_active) VALUES
    ('dev_admin',       'dev@horizonscientific.com',    'admin',            encode(digest('dev-key-001', 'sha256'), 'hex'),            true),
    ('sales_engineer',  'sales@horizonscientific.com',  'sales_engineer',   encode(digest('sales-key-001', 'sha256'), 'hex'),          true),
    ('product_manager', 'pm@horizonscientific.com',     'product_manager',  encode(digest('pm-key-001', 'sha256'), 'hex'),             true),
    ('customer_demo',   'demo@laboratory.com',          'customer',         encode(digest('customer-key-001', 'sha256'), 'hex'),       true)
ON CONFLICT (username) DO NOTHING;


-- ============================================================
-- 6. EQUIVALENCE RULES (cross-brand matching configuration)
-- ============================================================
INSERT INTO equivalence_rules (family, rule_name, required_match, tolerance_map, priority_specs) VALUES

('premier_lab_ref', 'capacity_match',
 ARRAY['door_type', 'refrigerant', 'voltage_v'],
 '{"storage_capacity_cuft": 0.15, "amperage": 0.20, "product_weight_lbs": 0.30}'::jsonb,
 ARRAY['storage_capacity_cuft', 'energy_kwh_day', 'shelf_count']),

('pharmacy_vaccine_ref', 'vaccine_storage_match',
 ARRAY['certifications', 'voltage_v', 'door_type'],
 '{"storage_capacity_cuft": 0.20, "uniformity_c": 0.15}'::jsonb,
 ARRAY['uniformity_c', 'stability_c', 'storage_capacity_cuft']),

('pharmacy_nsf_ref', 'nsf_certified_match',
 ARRAY['certifications', 'voltage_v'],
 '{"storage_capacity_cuft": 0.20, "uniformity_c": 0.10}'::jsonb,
 ARRAY['uniformity_c', 'stability_c', 'storage_capacity_cuft', 'energy_kwh_day']),

('standard_lab_ref', 'standard_match',
 ARRAY['refrigerant', 'voltage_v'],
 '{"storage_capacity_cuft": 0.15, "amperage": 0.25}'::jsonb,
 ARRAY['energy_kwh_day', 'storage_capacity_cuft', 'uniformity_c']),

('manual_defrost_freezer', 'freezer_match',
 ARRAY['voltage_v', 'door_type'],
 '{"storage_capacity_cuft": 0.15, "temp_range_min_c": 0.10}'::jsonb,
 ARRAY['storage_capacity_cuft', 'temp_range_min_c', 'energy_kwh_day']),

('cryo_dewar', 'cryo_match',
 ARRAY['door_type'],
 '{"storage_capacity_cuft": 0.25}'::jsonb,
 ARRAY['storage_capacity_cuft', 'temp_range_min_c'])

ON CONFLICT DO NOTHING;


COMMIT;

-- ============================================================
-- Verify seed data
-- ============================================================
DO $$
DECLARE
    b_count INTEGER;
    f_count INTEGER;
    s_count INTEGER;
    m_count INTEGER;
    u_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO b_count FROM brands;
    SELECT COUNT(*) INTO f_count FROM product_families;
    SELECT COUNT(*) INTO s_count FROM spec_registry;
    SELECT COUNT(*) INTO m_count FROM model_patterns;
    SELECT COUNT(*) INTO u_count FROM users;

    RAISE NOTICE '══════════════════════════════════════════';
    RAISE NOTICE ' Seed data loaded successfully';
    RAISE NOTICE '   Brands:          %', b_count;
    RAISE NOTICE '   Product families: %', f_count;
    RAISE NOTICE '   Spec registry:    %', s_count;
    RAISE NOTICE '   Model patterns:   %', m_count;
    RAISE NOTICE '   Users:            %', u_count;
    RAISE NOTICE '══════════════════════════════════════════';
END $$;
