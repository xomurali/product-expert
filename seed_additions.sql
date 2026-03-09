-- ============================================================
-- seed_additions.sql — FIXED for actual database schema
-- New brands, families, patterns, and specs
-- for ARES Scientific, CME Corp, DAI, and Corepoint CRT products
-- Run AFTER the original 01-schema.sql and 02-seed.sql
-- ============================================================

BEGIN;

-- ============================================================
-- 1. NEW BRANDS
-- ============================================================
INSERT INTO brands (code, name, parent_org) VALUES
    ('ARES',  'ARES Scientific',               'Horizon Scientific'),
    ('DAI',   'D.A.I. Scientific Equipment',    'Horizon Scientific'),
    ('CME',   'CME Corp',                       'CME Corp'),
    ('BSI',   'BSI',                            'Horizon Scientific'),
    ('VWR',   'VWR',                            'Avantor'),
    ('COL',   'COL',                            NULL),
    ('SLW',   'SLW',                            NULL)
ON CONFLICT (code) DO NOTHING;


-- ============================================================
-- 2. NEW PRODUCT FAMILIES
--    Schema: product_families(code, name, super_category, description)
--    NO brand_id column exists
-- ============================================================
INSERT INTO product_families (code, name, super_category, description) VALUES

    ('controlled_room_temp',   'Controlled Room Temperature Cabinet',  'refrigerator',
     'Controlled room temperature cabinets maintaining 68-77F (20-25C). Cooling only, no heating. Used for medication storage at room temperature.'),

    ('hazardous_location_ref', 'Hazardous Location Refrigerator',     'refrigerator',
     'NFPA/OSHA compliant hazardous location refrigerators, Class 1, Division II. Non-sparking/ATEX rated for volatile environments.'),

    ('hazardous_location_frz', 'Hazardous Location Freezer',          'freezer',
     'NFPA/OSHA compliant hazardous location freezers, Class 1, Division II. Non-sparking/ATEX rated for volatile environments.'),

    ('pharmacy_nsf_frz',       'Pharmacy/Vaccine NSF Freezer',        'freezer',
     'NSF/ANSI 456 certified vaccine freezers with validated temperature performance.'),

    ('flammable_storage_frz',  'Flammable Material Storage Freezer',  'freezer',
     'Spark-free interior freezers for flammable/combustible materials. NFPA 45/30 compliant.'),

    ('premium_lab_ref',        'Premium Laboratory Refrigerator',     'refrigerator',
     'Premium series with variable speed compressors, PID controllers, RS-485 MODBUS, USB data transfer, and battery backup.'),

    ('combo_ref_frz',          'Refrigerator/Freezer Combination',    'refrigerator',
     'Combined refrigerator and freezer units in a single cabinet.'),

    ('undercounter_ref',       'Undercounter Refrigerator',           'refrigerator',
     'Compact undercounter units for space-constrained installations.')

ON CONFLICT (code) DO NOTHING;


-- ============================================================
-- 3. NEW MODEL NUMBER PATTERNS
--    Schema: model_patterns(brand_id UUID, pattern_regex TEXT, family_id UUID, product_line TEXT, field_map JSONB, value_map JSONB)
-- ============================================================
INSERT INTO model_patterns (brand_id, pattern_regex, family_id, product_line, field_map, value_map) VALUES

-- === ARES CRT Upright: CRT-ARS-HC-S{cap}{door} ===
((SELECT id FROM brands WHERE code = 'ARES'),
 '^CRT-ARS-HC-S(\d+)(S|G)$',
 (SELECT id FROM product_families WHERE code = 'controlled_room_temp'),
 'CRT',
 '{"group_1": "capacity", "group_2": "door_type"}'::jsonb,
 '{"S": "solid", "G": "glass"}'::jsonb),

-- === ARES CRT Undercounter Built-In ===
((SELECT id FROM brands WHERE code = 'ARES'),
 '^CRT-ARS-HC-UCBI-(\d+)(-LH)?$',
 (SELECT id FROM product_families WHERE code = 'controlled_room_temp'),
 'CRT',
 '{"group_1": "size_code", "group_2": "hinge"}'::jsonb,
 '{"-LH": "left"}'::jsonb),

-- === ARES CRT Undercounter Freestanding ===
((SELECT id FROM brands WHERE code = 'ARES'),
 '^CRT-ARS-HC-UCFS-(\d+)(G)?$',
 (SELECT id FROM product_families WHERE code = 'controlled_room_temp'),
 'CRT',
 '{"group_1": "size_code", "group_2": "door_type"}'::jsonb,
 '{"G": "glass"}'::jsonb),

-- === DAI CRT Undercounter Built-In ===
((SELECT id FROM brands WHERE code = 'DAI'),
 '^CRT-DAI-HC-UCBI-(\d+)(-LH)?$',
 (SELECT id FROM product_families WHERE code = 'controlled_room_temp'),
 'CRT',
 '{"group_1": "size_code", "group_2": "hinge"}'::jsonb,
 '{"-LH": "left"}'::jsonb),

-- === DAI CRT Undercounter Freestanding ===
((SELECT id FROM brands WHERE code = 'DAI'),
 '^CRT-DAI-HC-UCFS-(\d+)(G)?$',
 (SELECT id FROM product_families WHERE code = 'controlled_room_temp'),
 'CRT',
 '{"group_1": "size_code", "group_2": "door_type"}'::jsonb,
 '{"G": "glass"}'::jsonb),

-- === Corepoint CRT legacy: CRTPR{size}{colors}/{variant} ===
((SELECT id FROM brands WHERE code = 'Corepoint'),
 '^CRTPR(\d+)(\w+)/(\w+)$',
 (SELECT id FROM product_families WHERE code = 'controlled_room_temp'),
 'CRT',
 '{"group_1": "size_code", "group_2": "color_code", "group_3": "variant"}'::jsonb,
 '{"WWG": "glass", "WWW": "solid", "0FB": "built_in"}'::jsonb),

-- === CME Standard Refrigerator ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-REF-(\d+(?:PT\d+)?)-([A-Z]+)-HCF(-LH)?$',
 (SELECT id FROM product_families WHERE code = 'premier_lab_ref'),
 'Standard',
 '{"group_1": "capacity", "group_2": "door_type", "group_3": "hinge"}'::jsonb,
 '{"S": "solid", "G": "glass", "SS": "stainless_steel", "-LH": "left"}'::jsonb),

-- === CME Premium Refrigerator ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-REF-PRM-(\d+)-([A-Z]+)$',
 (SELECT id FROM product_families WHERE code = 'premium_lab_ref'),
 'Premium',
 '{"group_1": "capacity", "group_2": "door_type"}'::jsonb,
 '{"S": "solid", "G": "glass"}'::jsonb),

-- === CME High Performance NSF Refrigerator ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-REF-P-(\d+(?:PT\d+)?)-([A-Z]+)-NSF$',
 (SELECT id FROM product_families WHERE code = 'pharmacy_nsf_ref'),
 'High Performance',
 '{"group_1": "capacity", "group_2": "door_type"}'::jsonb,
 '{"S": "solid", "G": "glass"}'::jsonb),

-- === CME NSF Refrigerator (standard) ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-REF-(\d+(?:PT\d+)?)-([A-Z]+)-NSF(-LH)?$',
 (SELECT id FROM product_families WHERE code = 'pharmacy_nsf_ref'),
 'NSF Vaccine',
 '{"group_1": "capacity", "group_2": "door_type", "group_3": "hinge"}'::jsonb,
 '{"S": "solid", "G": "glass", "SS": "stainless_steel", "-LH": "left"}'::jsonb),

-- === CME Standard Freezer ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-FRZ-(\d+(?:PT\d+)?)-([A-Z]+)-HCF(-LH)?$',
 (SELECT id FROM product_families WHERE code = 'manual_defrost_freezer'),
 'Standard',
 '{"group_1": "capacity", "group_2": "door_type", "group_3": "hinge"}'::jsonb,
 '{"S": "solid", "G": "glass", "-LH": "left"}'::jsonb),

-- === CME NSF Freezer ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-FRZ-(\d+(?:PT\d+)?)-([A-Z]+)-NSF(-LH)?$',
 (SELECT id FROM product_families WHERE code = 'pharmacy_nsf_frz'),
 'NSF Vaccine',
 '{"group_1": "capacity", "group_2": "door_type", "group_3": "hinge"}'::jsonb,
 '{"S": "solid", "G": "glass", "SS": "stainless_steel", "-LH": "left"}'::jsonb),

-- === CME Flammable Freezer ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-FRZ-FLM-(\d+)-([A-Z]+)-HCF$',
 (SELECT id FROM product_families WHERE code = 'flammable_storage_frz'),
 'Premier',
 '{"group_1": "capacity", "group_2": "door_type"}'::jsonb,
 '{"S": "solid", "G": "glass", "P": "premier"}'::jsonb),

-- === CME Hazardous Location Refrigerator ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-REF-EXP-(\d+)-([A-Z]+)-HCF$',
 (SELECT id FROM product_families WHERE code = 'hazardous_location_ref'),
 'Standard',
 '{"group_1": "capacity", "group_2": "door_type"}'::jsonb,
 '{"S": "solid"}'::jsonb),

-- === CME Hazardous Location Freezer ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-FRZ-EXP-(\d+)-([A-Z]+)-HCF$',
 (SELECT id FROM product_families WHERE code = 'hazardous_location_frz'),
 'Standard',
 '{"group_1": "capacity", "group_2": "door_type"}'::jsonb,
 '{"S": "solid"}'::jsonb),

-- === CME Combo Ref/Freezer ===
((SELECT id FROM brands WHERE code = 'CME'),
 '^CMEB-REF-FRZ-(\d+)-([A-Z]+)-HCF(-LH)?$',
 (SELECT id FROM product_families WHERE code = 'combo_ref_frz'),
 'Standard',
 '{"group_1": "capacity", "group_2": "door_type", "group_3": "hinge"}'::jsonb,
 '{"SG": "solid_glass", "-LH": "left"}'::jsonb)

ON CONFLICT DO NOTHING;


-- ============================================================
-- 4. NEW SPEC REGISTRY ENTRIES
--    Only specs NOT already in the schema's built-in list
-- ============================================================
INSERT INTO spec_registry (
    canonical_name, display_name, data_type, unit, unit_system,
    family_scope, synonyms, unit_conversions,
    is_filterable, is_comparable, is_searchable, sort_order
) VALUES

('calibration', 'Calibration', 'text', '', 'none',
 '{}',
 ARRAY['NIST', 'traceable', 'calibration certificate', 'calibrated'],
 '{}'::jsonb,
 true, true, true, 106),

('controller_probe', 'Controller Probe', 'text', '', 'none',
 '{}',
 ARRAY['probe', 'temperature probe', 'sensor', 'controller probe'],
 '{}'::jsonb,
 false, false, false, 107),

('simulator_ballast', 'Simulator Ballast', 'text', '', 'none',
 '{}',
 ARRAY['ballast', 'thermal media', 'glass bead', 'simulator'],
 '{}'::jsonb,
 false, true, false, 108),

('uniformity_ballast_c', 'Uniformity (Simulator Ballast)', 'numeric', '±°C', 'metric',
 '{}',
 ARRAY['uniformity ballast', 'uniformity simulator'],
 '{}'::jsonb,
 false, true, false, 91),

('stability_ballast_c', 'Stability (Simulator Ballast)', 'numeric', '±°C', 'metric',
 '{}',
 ARRAY['stability ballast', 'stability simulator'],
 '{}'::jsonb,
 false, true, false, 92),

('temp_rise_door_notes', 'Temperature Rise (Door Openings)', 'text', '', 'none',
 '{}',
 ARRAY['door opening', 'temperature rise', 'door open recovery'],
 '{}'::jsonb,
 false, true, false, 97),

('recovery_notes', 'Recovery After Door Opening', 'text', '', 'none',
 '{}',
 ARRAY['recovery', 'door opening recovery'],
 '{}'::jsonb,
 false, true, false, 98),

('freezer_compartments', 'Freezer Compartments', 'text', '', 'none',
 '{}',
 ARRAY['inner doors', 'compartments', 'freezer compartments'],
 '{}'::jsonb,
 false, true, false, 42),

('included_accessories', 'Included Accessories', 'text', '', 'none',
 '{}',
 ARRAY['accessories', 'toolkit', 'included'],
 '{}'::jsonb,
 false, false, false, 140),

('operational_environment', 'Operational Environment', 'text', '', 'none',
 '{}',
 ARRAY['ambient', 'operating environment', 'indoor use'],
 '{}'::jsonb,
 false, false, false, 141)

ON CONFLICT (canonical_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    synonyms     = EXCLUDED.synonyms;


-- ============================================================
-- 5. NEW EQUIVALENCE RULES
--    Schema: equivalence_rules(family_id UUID, rule_name, required_match, tolerance_map, priority_specs)
-- ============================================================
INSERT INTO equivalence_rules (family_id, rule_name, required_match, tolerance_map, priority_specs) VALUES

((SELECT id FROM product_families WHERE code = 'controlled_room_temp'),
 'crt_match',
 ARRAY['door_type', 'voltage_v'],
 '{"storage_capacity_cuft": 0.20, "amperage": 0.25}'::jsonb,
 ARRAY['storage_capacity_cuft', 'temp_range_min_c', 'mounting_type']),

((SELECT id FROM product_families WHERE code = 'hazardous_location_ref'),
 'hazardous_ref_match',
 ARRAY['certifications', 'voltage_v'],
 '{"storage_capacity_cuft": 0.15}'::jsonb,
 ARRAY['storage_capacity_cuft', 'temp_range_min_c']),

((SELECT id FROM product_families WHERE code = 'hazardous_location_frz'),
 'hazardous_frz_match',
 ARRAY['certifications', 'voltage_v'],
 '{"storage_capacity_cuft": 0.15}'::jsonb,
 ARRAY['storage_capacity_cuft', 'temp_range_min_c']),

((SELECT id FROM product_families WHERE code = 'flammable_storage_frz'),
 'flammable_frz_match',
 ARRAY['certifications', 'voltage_v', 'door_type'],
 '{"storage_capacity_cuft": 0.15, "temp_range_min_c": 0.10}'::jsonb,
 ARRAY['storage_capacity_cuft', 'temp_range_min_c', 'energy_kwh_day']),

((SELECT id FROM product_families WHERE code = 'premium_lab_ref'),
 'premium_ref_match',
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
