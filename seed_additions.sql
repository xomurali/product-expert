-- ============================================================
-- seed_additions.sql — New brands, families, patterns, and specs
-- for ARES Scientific, CME Corp, DAI, and Corepoint CRT products
-- Run AFTER the original seed.sql
-- ============================================================

BEGIN;

-- ============================================================
-- 1. NEW BRANDS
-- ============================================================
INSERT INTO brands (code, name, parent_org) VALUES
    ('ARES',  'ARES Scientific',      'Horizon Scientific'),
    ('DAI',   'D.A.I. Scientific Equipment', 'Horizon Scientific'),
    ('CME',   'CME Corp',             'CME Corp'),
    ('BSI',   'BSI',                  'Horizon Scientific'),
    ('VWR',   'VWR',                  'Avantor'),
    ('COL',   'COL',                  NULL),
    ('SLW',   'SLW',                  NULL)
ON CONFLICT (code) DO NOTHING;


-- ============================================================
-- 2. NEW PRODUCT FAMILIES
-- ============================================================
INSERT INTO product_families (code, name, super_category, brand_id, description) VALUES

    -- Controlled Room Temperature (new family for CRT products)
    ('controlled_room_temp',   'Controlled Room Temperature Cabinet',  'refrigerator',
     NULL,
     'Controlled room temperature cabinets maintaining 68-77°F (20-25°C). Cooling only, no heating. '
     'Used for medication storage at room temperature. Available as undercounter and upright.'),

    -- Hazardous Location (explosion-proof)
    ('hazardous_location_ref', 'Hazardous Location Refrigerator',     'refrigerator',
     NULL,
     'NFPA/OSHA compliant hazardous location refrigerators, Class 1, Division II. '
     'Non-sparking/ATEX rated for volatile environments. Hardwired power.'),

    ('hazardous_location_frz', 'Hazardous Location Freezer',          'freezer',
     NULL,
     'NFPA/OSHA compliant hazardous location freezers, Class 1, Division II. '
     'Non-sparking/ATEX rated for volatile environments.'),

    -- NSF/ANSI 456 Vaccine Freezer
    ('pharmacy_nsf_frz',       'Pharmacy/Vaccine NSF Freezer',        'freezer',
     NULL,
     'NSF/ANSI 456 certified vaccine freezers with validated temperature performance.'),

    -- Flammable Material Storage Freezer
    ('flammable_storage_frz',  'Flammable Material Storage Freezer',  'freezer',
     NULL,
     'Spark-free interior freezers for flammable/combustible materials. NFPA 45/30 compliant.'),

    -- Premium Lab (CME PRM series with VSC, PID, battery backup)
    ('premium_lab_ref',        'Premium Laboratory Refrigerator',     'refrigerator',
     (SELECT id FROM brands WHERE code = 'CME'),
     'CME Premium series with variable speed compressors, PID controllers, '
     'RS-485 MODBUS communication, USB data transfer, and 24V battery backup.'),

    -- Combo Ref/Freezer
    ('combo_ref_frz',          'Refrigerator/Freezer Combination',    'refrigerator',
     NULL,
     'Combined refrigerator and freezer units in a single cabinet.')

ON CONFLICT (code) DO NOTHING;


-- ============================================================
-- 3. NEW MODEL NUMBER PATTERNS
-- ============================================================
INSERT INTO model_patterns (brand_id, pattern, family_code, product_line, description, example) VALUES

-- === ARES CRT Upright: CRT-ARS-HC-S{cap}{door} ===
((SELECT id FROM brands WHERE code = 'ARES'),
 '^CRT-ARS-HC-S(\d+)(S|G)$',
 'controlled_room_temp', 'CRT',
 'ARES CRT upright cabinets. Group 1 = capacity, Group 2 = S(solid)/G(glass).',
 'CRT-ARS-HC-S26S'),

-- === ARES CRT Undercounter Built-In: CRT-ARS-HC-UCBI-{code}[-LH] ===
((SELECT id FROM brands WHERE code = 'ARES'),
 '^CRT-ARS-HC-UCBI-(\d+)(-LH)?$',
 'controlled_room_temp', 'CRT',
 'ARES CRT undercounter built-in. Group 1 = size code, Group 2 = left-hinged.',
 'CRT-ARS-HC-UCBI-0204-LH'),

-- === ARES CRT Undercounter Freestanding: CRT-ARS-HC-UCFS-{code}[G] ===
((SELECT id FROM brands WHERE code = 'ARES'),
 '^CRT-ARS-HC-UCFS-(\d+)(G)?$',
 'controlled_room_temp', 'CRT',
 'ARES CRT undercounter freestanding. Group 1 = size code, Group 2 = glass door.',
 'CRT-ARS-HC-UCFS-0504'),

-- === DAI CRT patterns (same structure as ARES) ===
((SELECT id FROM brands WHERE code = 'DAI'),
 '^CRT-DAI-HC-UCBI-(\d+)(-LH)?$',
 'controlled_room_temp', 'CRT',
 'DAI CRT undercounter built-in.',
 'CRT-DAI-HC-UCBI-0204-LH'),

((SELECT id FROM brands WHERE code = 'DAI'),
 '^CRT-DAI-HC-UCFS-(\d+)(G)?$',
 'controlled_room_temp', 'CRT',
 'DAI CRT undercounter freestanding.',
 'CRT-DAI-HC-UCFS-0204'),

-- === Corepoint CRT legacy: CRTPR{size}{colors}/{variant} ===
((SELECT id FROM brands WHERE code = 'Corepoint'),
 '^CRTPR(\d+)(\w+)/(\w+)$',
 'controlled_room_temp', 'CRT',
 'Corepoint CRT units. Group 1 = size, Group 2 = color codes (WWG=glass, WWW=solid), Group 3 = variant (0=base, 0FB=built-in).',
 'CRTPR031WWG/0'),

-- === CME Standard Refrigerator: CMEB-REF-{cap}-{door}-HCF[-LH] ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-REF-(\d+(?:PT\d+)?)-([SGW]+)-HCF(-LH)?$',
 'premier_lab_ref', 'Standard',
 'CME standard refrigerators. Group 1 = capacity (PT for decimal), Group 2 = door type.',
 'CMEB-REF-20-S-HCF'),

-- === CME Premium Refrigerator: CMEB-REF-PRM-{cap}-{door} ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-REF-PRM-(\d+)-([SGW]+)$',
 'premium_lab_ref', 'Premium',
 'CME Premium series with VSC, PID, battery backup. Group 1 = capacity.',
 'CMEB-REF-PRM-23-S'),

-- === CME High Performance NSF Ref: CMEB-REF-P-{cap}-{door}-NSF ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-REF-P-(\d+(?:PT\d+)?)-([SGW]+)-NSF$',
 'pharmacy_nsf_ref', 'High Performance',
 'CME high-performance NSF/ANSI 456 certified. Group 1 = capacity.',
 'CMEB-REF-P-10PT5-G-NSF'),

-- === CME NSF Refrigerator: CMEB-REF-{cap}-{door}-NSF[-LH] ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-REF-(\d+(?:PT\d+)?)-([A-Z]+)-NSF(-LH)?$',
 'pharmacy_nsf_ref', 'NSF Vaccine',
 'CME NSF/ANSI 456 certified refrigerators.',
 'CMEB-REF-1-S-NSF-LH'),

-- === CME Standard Freezer: CMEB-FRZ-{cap}-{door}-HCF[-LH] ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-FRZ-(\d+(?:PT\d+)?)-([A-Z]+)-HCF(-LH)?$',
 'manual_defrost_freezer', 'Standard',
 'CME standard freezers.',
 'CMEB-FRZ-14-S-HCF'),

-- === CME NSF Freezer: CMEB-FRZ-{cap}-{door}-NSF[-LH] ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-FRZ-(\d+(?:PT\d+)?)-([A-Z]+)-NSF(-LH)?$',
 'pharmacy_nsf_frz', 'NSF Vaccine',
 'CME NSF/ANSI 456 certified freezers.',
 'CMEB-FRZ-1PT7-NSF'),

-- === CME Flammable Freezer: CMEB-FRZ-FLM-{cap}-{door}-HCF ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-FRZ-FLM-(\d+)-([A-Z]+)-HCF$',
 'flammable_storage_frz', 'Premier',
 'CME flammable material storage freezers. NFPA 45/30 compliant.',
 'CMEB-FRZ-FLM-14-P-HCF'),

-- === CME Hazardous Location Ref: CMEB-REF-EXP-{cap}-{door}-HCF ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-REF-EXP-(\d+)-([A-Z]+)-HCF$',
 'hazardous_location_ref', 'Standard',
 'CME hazardous location refrigerators. Class 1, Div II.',
 'CMEB-REF-EXP-20-S-HCF'),

-- === CME Hazardous Location Frz: CMEB-FRZ-EXP-{cap}-{door}-HCF ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-FRZ-EXP-(\d+)-([A-Z]+)-HCF$',
 'hazardous_location_frz', 'Standard',
 'CME hazardous location freezers. Class 1, Div II.',
 'CMEB-FRZ-EXP-20-S-HCF'),

-- === CME Combo: CMEB-REF-FRZ-{cap}-{door}-HCF[-LH] ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-REF-FRZ-(\d+)-([A-Z]+)-HCF(-LH)?$',
 'combo_ref_frz', 'Standard',
 'CME combination refrigerator/freezer units.',
 'CMEB-REF-FRZ-9-SG-HCF-LH')

ON CONFLICT DO NOTHING;


-- ============================================================
-- 4. NEW SPEC REGISTRY ENTRIES (CME-specific fields)
-- ============================================================
INSERT INTO spec_registry (
    canonical_name, display_name, data_type, unit, unit_system,
    family_scope, synonyms, unit_conversions, is_filterable,
    is_comparable, is_searchable, sort_order
) VALUES

('battery_backup', 'Battery Backup', 'text', '', 'none',
 '{}',
 ARRAY['battery', 'backup power', 'UPS', 'battery backup'],
 '{}'::jsonb,
 true, true, true, 70),

('digital_comm', 'Digital Communication', 'text', '', 'none',
 '{}',
 ARRAY['RS-485', 'MODBUS', 'RS485', 'digital communication', 'serial communication'],
 '{}'::jsonb,
 true, true, true, 71),

('data_transfer', 'Data Transfer', 'text', '', 'none',
 '{}',
 ARRAY['USB', 'data port', 'data transfer', 'USB port'],
 '{}'::jsonb,
 false, true, false, 72),

('condenser_type', 'Condenser Type', 'text', '', 'none',
 '{}',
 ARRAY['condenser', 'condenser construction'],
 '{}'::jsonb,
 false, true, false, 55),

('evaporator_type', 'Evaporator Type', 'text', '', 'none',
 '{}',
 ARRAY['evaporator', 'evaporator construction'],
 '{}'::jsonb,
 false, true, false, 56),

('calibration', 'Calibration', 'text', '', 'none',
 '{}',
 ARRAY['NIST', 'traceable', 'calibration certificate', 'calibrated'],
 '{}'::jsonb,
 true, true, true, 73),

('controller_probe', 'Controller Probe', 'text', '', 'none',
 '{}',
 ARRAY['probe', 'temperature probe', 'sensor', 'controller probe'],
 '{}'::jsonb,
 false, false, false, 74),

('simulator_ballast', 'Simulator Ballast', 'text', '', 'none',
 '{}',
 ARRAY['ballast', 'thermal media', 'glass bead', 'simulator'],
 '{}'::jsonb,
 false, true, false, 75),

('uniformity_ballast_c', 'Uniformity (Simulator Ballast)', 'numeric', '±°C', 'metric',
 '{}',
 ARRAY['uniformity ballast', 'uniformity simulator'],
 '{}'::jsonb,
 false, true, false, 46),

('stability_ballast_c', 'Stability (Simulator Ballast)', 'numeric', '±°C', 'metric',
 '{}',
 ARRAY['stability ballast', 'stability simulator'],
 '{}'::jsonb,
 false, true, false, 47),

('temp_rise_door_notes', 'Temperature Rise (Door Openings)', 'text', '', 'none',
 '{}',
 ARRAY['door opening', 'temperature rise', 'door open recovery'],
 '{}'::jsonb,
 false, true, false, 49),

('freezer_compartments', 'Freezer Compartments', 'text', '', 'none',
 '{}',
 ARRAY['inner doors', 'compartments', 'freezer compartments'],
 '{}'::jsonb,
 false, true, false, 17)

ON CONFLICT (canonical_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    synonyms     = EXCLUDED.synonyms;


-- ============================================================
-- 5. NEW EQUIVALENCE RULES
-- ============================================================
INSERT INTO equivalence_rules (family, rule_name, required_match, tolerance_map, priority_specs) VALUES

('controlled_room_temp', 'crt_match',
 ARRAY['door_type', 'voltage_v'],
 '{"storage_capacity_cuft": 0.20, "amperage": 0.25}'::jsonb,
 ARRAY['storage_capacity_cuft', 'temp_range_min_c', 'mounting_type']),

('hazardous_location_ref', 'hazardous_ref_match',
 ARRAY['certifications', 'voltage_v'],
 '{"storage_capacity_cuft": 0.15}'::jsonb,
 ARRAY['storage_capacity_cuft', 'temp_range_min_c']),

('hazardous_location_frz', 'hazardous_frz_match',
 ARRAY['certifications', 'voltage_v'],
 '{"storage_capacity_cuft": 0.15}'::jsonb,
 ARRAY['storage_capacity_cuft', 'temp_range_min_c']),

('flammable_storage_frz', 'flammable_frz_match',
 ARRAY['certifications', 'voltage_v', 'door_type'],
 '{"storage_capacity_cuft": 0.15, "temp_range_min_c": 0.10}'::jsonb,
 ARRAY['storage_capacity_cuft', 'temp_range_min_c', 'energy_kwh_day']),

('premium_lab_ref', 'premium_ref_match',
 ARRAY['voltage_v', 'door_type'],
 '{"storage_capacity_cuft": 0.15, "energy_kwh_day": 0.20}'::jsonb,
 ARRAY['storage_capacity_cuft', 'energy_kwh_day', 'uniformity_c', 'noise_dba'])

ON CONFLICT DO NOTHING;


COMMIT;

-- ============================================================
-- Verify additions
-- ============================================================
DO $$
DECLARE
    b_count INTEGER;
    f_count INTEGER;
    m_count INTEGER;
    s_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO b_count FROM brands;
    SELECT COUNT(*) INTO f_count FROM product_families;
    SELECT COUNT(*) INTO m_count FROM model_patterns;
    SELECT COUNT(*) INTO s_count FROM spec_registry;

    RAISE NOTICE '══════════════════════════════════════════';
    RAISE NOTICE ' Seed additions loaded successfully';
    RAISE NOTICE '   Total Brands:          %', b_count;
    RAISE NOTICE '   Total Product families: %', f_count;
    RAISE NOTICE '   Total Model patterns:   %', m_count;
    RAISE NOTICE '   Total Spec registry:    %', s_count;
    RAISE NOTICE '══════════════════════════════════════════';
END $$;
