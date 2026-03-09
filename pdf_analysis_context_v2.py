"""
Product Expert System — PDF Content Analysis V2
Updated with ARES Scientific (CRT-ARS), DAI (CRT-DAI), Corepoint (CRTPR),
and CME Corp (CMEB) product data sheets.

This file contains:
1. Complete brand/model analysis across ALL uploaded documents (~75+ PDFs)
2. Updated 3-layer pattern architecture
3. New CMEB model number grammar
4. New CRT-prefix model number grammar  
5. Updated FIELD_MAP additions for new brands
6. Updated BRAND_PATTERNS for detection
7. Complete MODEL_PATTERNS regex list
"""

# ============================================================
# SECTION 1: COMPLETE BRAND INVENTORY
# ============================================================

BRAND_INVENTORY = {
    # === Original brands (from first ~50 PDFs) ===
    "ABT": {
        "company": "American BioTech Supply (ABS)",
        "parent": "Horizon Scientific",
        "logo_text": "ABS / American BioTech Supply",
        "prefix_in_model": "ABT",
        "prefix_with_pharmacy": "PH-ABT",
        "contact_domain": "horizonscientific.com",
    },
    "BSI": {
        "company": "BSI",
        "parent": "Horizon Scientific",
        "logo_text": "BSI wave logo",
        "prefix_in_model": "BSI",
        "prefix_with_pharmacy": "PH-BSI",
        "contact_domain": "horizonscientific.com",
    },
    "LRP": {
        "company": "Lab Research Products",
        "parent": "Horizon Scientific",
        "logo_text": "LRP LAB RESEARCH PRODUCTS",
        "prefix_in_model": "LRP",
        "prefix_with_pharmacy": "PH-LRP",
        "contact_domain": "horizonscientific.com",
    },
    "DAI": {
        "company": "D.A.I. Scientific Equipment",
        "parent": "Horizon Scientific",
        "logo_text": "D.A.I. SCIENTIFIC EQUIPMENT hexagon logo",
        "prefix_in_model": "DAI",
        "prefix_with_pharmacy": "PH-DAI",
        "prefix_with_crt": "CRT-DAI",
        "contact_domain": "daiscientific.com",
    },
    "VWR": {
        "company": "VWR",
        "parent": "Avantor",
        "logo_text": "VWR swoosh logo",
        "prefix_in_model": "VWR",
        "catalog_number_format": "76579-###",
        "contact_domain": None,
    },

    # === NEW: ARES Scientific (from CRT-ARS files) ===
    "ARS": {
        "company": "ARES Scientific",
        "parent": "Horizon Scientific (likely)",
        "logo_text": "ARES SCIENTIFIC blue X-logo",
        "prefix_in_model": "ARS",
        "prefix_with_pharmacy": "PH-ARS",
        "prefix_with_crt": "CRT-ARS",
        "contact_email": "info@aresscientific.com",
        "contact_phone": "720-283-0177 Ext 2",
        "notes": (
            "ARES docs use IDENTICAL template to ABS/BSI/LRP/DAI. "
            "Same section headers, same field names, same table structures. "
            "CRT-ARS prefix seen in Controlled Room Temperature products. "
            "Also seen: standard ARS-HC- prefix in product description headers."
        ),
    },

    # === NEW: Corepoint Scientific (from CRTPR files) ===
    "CPS": {
        "company": "Corepoint Scientific",
        "parent": "Horizon Scientific (likely)",
        "logo_text": "COREPOINT SCIENTIFIC swirl logo",
        "prefix_in_model": "CPS",
        "legacy_prefix": "CRTPR",
        "notes": (
            "Corepoint cutsheets use same column layout as DAI/ABS cutsheets. "
            "Model format: CRTPR{code}{door}/{variant}. "
            "031 = size code, WWG = White/White/Glass, WWW = White/White/White(Solid), "
            "/0 = base, /0FB = Front Breathing (built-in)."
        ),
    },

    # === NEW: CME Corp (from CMEB files) ===
    "CMEB": {
        "company": "CME Corp",
        "parent": "CME Corp (independent distributor)",
        "logo_text": "CME CORP red/blue sphere logo",
        "prefix_in_model": "CMEB",
        "contact_email": "customerservice@cmecorp.com",
        "contact_phone": "800-338-2372",
        "notes": (
            "CME Corp uses a COMPLETELY DIFFERENT model number grammar than Horizon brands. "
            "Format: CMEB-{TYPE}-{SIZE}-{DOOR}-{SERIES}[-{MODIFIERS}]. "
            "Document templates are similar but NOT identical to Horizon brands. "
            "CME data sheets include Performance section with 15-point temperature probe data, "
            "temperature charts (stability, distribution, door opening recovery), "
            "and NSF/ANSI 456 compliance data. "
            "Key differences: battery backup, PID controllers, variable speed compressors (VSC), "
            "NIST-traceable calibration certificates, glass bead thermal media ballasts."
        ),
    },

    # === Other known brands ===
    "CEL": {"company": "Celsius Scientific", "prefix_in_model": "CEL"},
    "COL": {"company": "COL (brand)", "prefix_in_model": "COL"},
    "SLW": {"company": "SLW (brand)", "prefix_in_model": "SLW"},
}


# ============================================================
# SECTION 2: MODEL NUMBERS FROM ALL UPLOADED DOCUMENTS
# ============================================================

MODEL_NUMBERS_FROM_DOCUMENTS = {
    # === ARES Scientific (CRT-ARS prefix) ===
    "CRT-ARS-HC-UCBI-0204-LH": {
        "brand": "ARS", "product_line": "CRT",
        "form_factor": "Undercounter Built-In", "capacity_cuft": 2.5,
        "door": "Solid, Left Hinged", "temp_range": "36F-46F (2C-8C)",
        "refrigerant": "R600a", "defrost": "Cycle", "weight_lbs": 69,
        "amperage": 0.90, "certification": "UL-C-UL Listed",
        "dims_ext": {"w": 17.75, "d": 20.875, "h": 30.75},
    },
    "CRT-ARS-HC-UCFS-0504": {
        "brand": "ARS", "product_line": "CRT",
        "form_factor": "Undercounter Freestanding", "capacity_cuft": 5.2,
        "door": "Solid, Left Hinged", "temp_range": "68F-77F (20C-25C)",
        "refrigerant": "R600a", "defrost": "Cycle", "weight_lbs": 93,
        "amperage": 1.3, "dims_ext": {"w": 23.75, "d": 24, "h": 32.125},
    },
    "CRT-ARS-HC-UCFS-0504G": {
        "brand": "ARS", "product_line": "CRT",
        "form_factor": "Undercounter Freestanding", "capacity_cuft": 5.2,
        "door": "Glass, Right Hinged", "temp_range": "68F-77F (20C-25C)",
    },
    "CRT-ARS-HC-S12S": {
        "brand": "ARS", "product_line": "CRT",
        "form_factor": "Upright", "capacity_cuft": 12,
        "door": "Solid, Self-closing, Right Hinged",
        "refrigerant": "R290", "weight_lbs": 187, "amperage": 3,
        "dims_ext": {"w": 25, "d": 29, "h": 65.75},
    },
    "CRT-ARS-HC-S12G": {
        "brand": "ARS", "product_line": "CRT",
        "form_factor": "Upright", "capacity_cuft": 12,
        "door": "Glass, Self-closing, Right Hinged", "weight_lbs": 218,
    },
    "CRT-ARS-HC-S16S": {
        "brand": "ARS", "product_line": "CRT",
        "form_factor": "Upright", "capacity_cuft": 16,
        "door": "Solid, Self-closing, Right Hinged",
        "certification": "ETL, C-ETL, UL471, Energy Star",
        "dims_ext": {"w": 25, "d": 26, "h": 79},
    },
    "CRT-ARS-HC-S16G": {
        "brand": "ARS", "product_line": "CRT",
        "form_factor": "Upright", "capacity_cuft": 16,
        "door": "Glass, Self-closing, Right Hinged", "weight_lbs": 245,
    },
    "CRT-ARS-HC-S26S": {
        "brand": "ARS", "product_line": "CRT",
        "form_factor": "Upright", "capacity_cuft": 26,
        "door": "Solid, Self-closing, Right Hinged",
        "refrigerant": "R290", "weight_lbs": 235,
        "dims_ext": {"w": 28.375, "d": 36.75, "h": 81.75},
    },

    # === DAI CRT Cutsheets ===
    "CRT-DAI-HC-UCFS-0204": {
        "brand": "DAI", "product_line": "CRT",
        "form_factor": "Undercounter Freestanding", "capacity_cuft": 2.5,
        "door": "Solid",
    },
    "CRT-DAI-HC-UCBI-0204-LH": {
        "brand": "DAI", "product_line": "CRT",
        "form_factor": "Undercounter Built-In", "capacity_cuft": 2.5,
        "door": "Solid, Left Hinged",
    },

    # === Corepoint CRT ===
    "CRTPR031WWG/0": {
        "brand": "CPS", "product_line": "CRT",
        "capacity_cuft": 2.5, "door": "Glass",
    },
    "CRTPR031WWW/0FB": {
        "brand": "CPS", "product_line": "CRT",
        "capacity_cuft": 2.5, "door": "Solid",
        "form_factor": "Built-In (Front Breathing)",
    },

    # === CME Corp (CMEB prefix) ===
    "CMEB-REF-PRM-23-S": {
        "brand": "CMEB", "type": "REF", "series": "Premium",
        "capacity_cuft": 23, "door": "Solid, Right Hinged",
        "compressor": "Variable Speed (VSC), 1300-4000 rpm",
        "refrigerant": "R600a", "controller": "PID with LCD",
        "battery_backup": "24V", "digital_comm": "RS-485 MODBUS",
        "weight_lbs": 274, "amperage": 3,
        "warranty_compressor": "7 year", "energy_kwh_day": 1.15,
    },
    "CMEB-FRZ-1PT7-NSF": {
        "brand": "CMEB", "type": "FRZ", "capacity_cuft": 1.7,
        "door": "Solid, Right Hinged", "temp_range": "-15C to -28C",
        "certification": "NSF/ANSI 456, UL/C-UL, Energy Star",
        "refrigerant": "R600a", "defrost": "Manual",
        "calibration": "NIST traceable", "weight_lbs": 80,
    },
    "CMEB-REF-1-S-NSF-LH": {
        "brand": "CMEB", "type": "REF", "capacity_cuft": 1.0,
        "door": "Solid, Left Hinged", "form_factor": "Countertop",
        "certification": "NSF/ANSI 456", "refrigerant": "R600a",
    },
    "CMEB-REF-4PT6-G-NSF-LH": {
        "brand": "CMEB", "type": "REF", "capacity_cuft": 4.6,
        "door": "Glass, Left Hinged", "form_factor": "Undercounter Built-In",
        "certification": "NSF/ANSI 456", "refrigerant": "R600a",
    },
    "CMEB-REF-P-26-G-NSF": {
        "brand": "CMEB", "type": "REF", "series": "High Performance",
        "capacity_cuft": 26, "door": "Glass, Right Hinged",
        "form_factor": "Upright", "certification": "NSF/ANSI 456",
        "refrigerant": "R290", "weight_lbs": 321,
        "shelves": "7 (6 adj/1 fixed)", "energy_kwh_day": 1.68,
    },
    "CMEB-FRZ-FLM-14-P-HCF": {
        "brand": "CMEB", "type": "FRZ", "subtype": "FLM",
        "series": "Premier", "capacity_cuft": 14,
        "door": "Solid, Right Hinged", "temp_range": "-15C to -25C",
        "refrigerant": "R290", "defrost": "Manual",
        "freezer_compartments": "7 Inner Doors",
    },
    "CMEB-REF-20-S-HCF": {
        "brand": "CMEB", "type": "REF", "series": "Standard",
        "capacity_cuft": 20, "door": "Solid, Right Hinged",
        "refrigerant": "R600a", "defrost": "Cycle",
        "weight_lbs": 235,
    },
    "CMEB-REF-EXP-20-S-HCF": {
        "brand": "CMEB", "type": "REF", "subtype": "EXP",
        "capacity_cuft": 20, "door": "Solid, Right Hinged",
        "notes": "Hazardous Location. No power cord - hardwired.",
    },
    "CMEB-FRZ-4PT2-SS-NSF-LH": {
        "brand": "CMEB", "type": "FRZ", "capacity_cuft": 4.2,
        "door": "Solid, Left Hinged", "material": "Stainless Steel",
        "form_factor": "Undercounter Built-In",
        "certification": "NSF/ANSI 456", "defrost": "Manual",
    },
    "CMEB-REF-P-10PT5-G-NSF": {
        "brand": "CMEB", "type": "REF", "series": "High Performance",
        "capacity_cuft": 10.5, "door": "Glass, Right Hinged",
        "form_factor": "Upright Freestanding",
        "certification": "NSF/ANSI 456",
    },
    "CMEB-FRZ-14-S-HCF": {
        "brand": "CMEB", "type": "FRZ", "series": "Standard",
        "capacity_cuft": 14, "door": "Right Hinged",
        "refrigerant": "R290", "defrost": "Manual",
    },
    "CMEB-FRZ-EXP-20-S-HCF": {
        "brand": "CMEB", "type": "FRZ", "subtype": "EXP",
        "capacity_cuft": 20, "door": "Right Hinged",
        "refrigerant": "R290", "defrost": "Manual",
        "notes": "Hazardous Location A,B,C,D. No power cord.",
    },
}


# ============================================================
# SECTION 3: CMEB MODEL NUMBER GRAMMAR
# ============================================================

CMEB_MODEL_GRAMMAR = """
CME Corp model number structure:

  CMEB-{TYPE}-{MODIFIERS}-{CAPACITY}-{DOOR}-{SERIES}[-{EXTRAS}]

SEGMENTS:
  CMEB          = Brand prefix (always)
  TYPE          = REF | FRZ
  MODIFIERS     = PRM (Premium/VSC) | FLM (Flammable) | EXP (Hazardous) | P (High Perf) | (none)
  CAPACITY      = Decimals use PT: 1PT7=1.7, 4PT2=4.2, 4PT6=4.6, 10PT5=10.5
                  Whole numbers: 14, 20, 23, 26
  DOOR/MATERIAL = S=Solid, G=Glass, SS=Stainless Steel, SG=Combo
  SERIES        = HCF (standard) | NSF (NSF/ANSI 456 vaccine)
  EXTRAS        = LH (Left Hinged)

KEY: CMEB grammar is POSITIONAL, not code-based like Horizon.
"""

CRT_PREFIX_GRAMMAR = """
CRT is a PRODUCT LINE prefix (Controlled Room Temperature), not a brand.

  CRT-{BRAND}-HC-{PRODUCT_CODE}

CRT Upright: CRT-{BRAND}-HC-S{CAPACITY}{DOOR}  (S12S, S16G, S26S)
CRT Undercounter: CRT-{BRAND}-HC-UC{BI|FS}-{CODE}[G][-LH]

Corepoint CRT: CRTPR{SIZE}{COLORS}/{VARIANT}
  031=2.5CF, WWG=Glass, WWW=Solid, /0=base, /0FB=Front Breathing

CRT temp ranges: 68-77F (20-25C) for most, 36-46F (2-8C) for UCBI models.
"""


# ============================================================
# SECTION 4: UPDATED PATTERNS & MAPPINGS
# ============================================================

BRAND_PATTERNS_V2 = [
    (r'American\s*Bio\s*Tech\s*Supply|(?<!\w)ABS(?!\w)', 'ABS'),
    (r'LABRepCo|LAB\s*Rep\s*Co', 'LABRepCo'),
    (r'Corepoint\s*Scientific|COREPOINT', 'Corepoint'),
    (r'celsius\s*Scientific|°celsius|CEL-', 'Celsius'),
    (r'CryoSafe|CryoMizer|CryoPro|CBS\b', 'CBS'),
    (r'ARES\s*SCIENTIFIC|(?<!\w)ARES(?!\w)', 'ARES'),
    (r'CME\s*CORP|(?<!\w)CME(?!\w)', 'CME'),
    (r'D\.?A\.?I\.?\s*SCIENTIFIC|DAI\s*Scientific', 'DAI'),
    (r'aresscientific\.com', 'ARES'),
    (r'cmecorp\.com', 'CME'),
    (r'daiscientific\.com', 'DAI'),
]

MODEL_BRAND_PREFIXES = {
    'PH-ABT': 'ABS', 'PH-BSI': 'BSI', 'PH-DAI': 'DAI',
    'PH-LRP': 'LABRepCo', 'PH-ARS': 'ARES',
    'CRT-ARS': 'ARES', 'CRT-DAI': 'DAI', 'CRT-ABT': 'ABS', 'CRT-LRP': 'LABRepCo',
    'CRTPR': 'Corepoint', 'CMEB': 'CME', 'DONOTUSE': 'deprecated',
    'ABT': 'ABS', 'BSI': 'BSI', 'LRP': 'LABRepCo', 'DAI': 'DAI',
    'VWR': 'VWR', 'ARS': 'ARES', 'CPS': 'Corepoint',
    'CEL': 'Celsius', 'COL': 'COL', 'SLW': 'SLW',
}

MODEL_PATTERNS_V2 = [
    # CME Corp
    r'(CMEB-(?:REF|FRZ)(?:-(?:PRM|FLM|EXP|P))?-[\w-]+)',
    # CRT prefix
    r'(CRT-(?:ARS|DAI|ABT|LRP|BSI)-HC-[\w-]+)',
    # Corepoint CRT
    r'(CRTPR\d+\w+/\w+)',
    # ARES standalone
    r'(ARS-HC-[\w-]+)',
    # Horizon brands (ABT/BSI/LRP/DAI/VWR)
    r'(ABT-(?:HC|VS)-[\w-]+)',
    r'(PH-(?:ABT|BSI|DAI|LRP|ARS)-(?:HC|NSF)-[\w-]+)',
    r'(BSI-(?:HC-)?[\w-]+)',
    r'(LRP-HC-[\w-]+)',
    r'(DAI-HC-[\w-]+)',
    r'(VWR-HC-[\w-]+)',
    r'(LHT-\d+-[A-Z]+)',
    r'(LPVT-\d+-[A-Z]+)',
    r'(NSBR\d+\w+/\d)',
    r'(CEL-[\w-]+)',
    r'(CP-[\w-]+)',
    r'\b(V-\d+)\b',
    r'\b(BR-\d+-\w+)\b',
    r'(VTS-\d+-\w+)',
    r'(?:Cat#?\s*)(76\d{3}-\d{3})',
]

FIELD_MAP_ADDITIONS = {
    'battery backup': 'battery_backup',
    'digital communication': 'digital_communication',
    'data transfer': 'data_transfer',
    'chart recorder': 'chart_recorder',
    'controller probe': 'controller_probe',
    'simulator ballast': 'simulator_ballast',
    'calibration': 'calibration',
    'temperature setpoint range': 'temp_range_raw',
    'adjustable cycle temperature': 'temp_range_raw',
    'uniformity¹ (cabinet air)': 'uniformity_cabinet_air',
    'stability² (cabinet air)': 'stability_cabinet_air',
    'maximum temperature variation': 'max_temp_variation',
    'maximum temperature variation (cabinet air)': 'max_temp_variation',
    'recovery after 3 min door opening': 'recovery_3min_door',
    'recovery after 60 sec door opening': 'recovery_60sec_door',
    'temperature rise after 5 sec door openings': 'temp_rise_5sec_door',
    'temperature rise after 8 sec door openings': 'temp_rise_8sec_door',
    'energy consumption': 'energy_consumption_kwh_day',
    'energy consumption (kwh/day)': 'energy_consumption_kwh_day',
    'average heat rejection': 'avg_heat_rejection_btu_hr',
    'average heat rejection (btu/hr)': 'avg_heat_rejection_btu_hr',
    'noise pressure level (dba)': 'noise_dba',
    'pull down time to nominal operating temp': 'pulldown_time_min',
    'condenser': 'condenser_type',
    'evaporator': 'evaporator_type',
    'compressor parts warranty': 'warranty_compressor_years',
    'included accessories': 'included_accessories',
    'operational environment': 'operational_environment',
    'freezer compartments': 'freezer_compartments',
    'drawers': 'drawers',
}


# ============================================================
# SECTION 5: KEY FINDINGS & ARCHITECTURE
# ============================================================

KEY_FINDINGS_V2 = {
    "new_brand_cmeb": (
        "CME Corp (CMEB) uses a COMPLETELY DIFFERENT model grammar. "
        "Needs separate regex branch. Encodes TYPE, MODIFIER, CAPACITY (PT notation), "
        "DOOR, SERIES (HCF/NSF) as suffixes."
    ),
    "crt_is_product_line": (
        "CRT = Controlled Room Temperature product line, not a brand. "
        "Combines with brands: CRT-ARS, CRT-DAI. Maintains 68-77F (20-25C)."
    ),
    "ares_identical_templates": (
        "ARES Scientific docs use 100% identical templates to ABS/BSI/LRP/DAI."
    ),
    "cmeb_nsf_rich_performance": (
        "CME NSF sheets have 15-point probe data, stability/distribution/recovery charts."
    ),
    "cmeb_premium_features": (
        "CME Premium: VSC compressors, PID controllers, RS-485 MODBUS, USB, "
        "24V battery backup, 7-year compressor warranty."
    ),
    "field_labels_90pct_consistent": (
        "CME uses same field labels as Horizon for 90%+ of fields. "
        "New: Battery Backup, Digital Communication, Condenser, Evaporator, etc."
    ),
}

ARCHITECTURE_V2 = """
3-LAYER EXTRACTION ARCHITECTURE V2:

LAYER 1: PREFIX STRIPPING (longest match first)
  PH-{BRAND}-HC/NSF-... | CRT-{BRAND}-HC-... | CRTPR{code} | CMEB-... | {BRAND}-HC/VS-...

LAYER 2A: HORIZON CODES (ABT/BSI/LRP/DAI/VWR/ARS)
  60+ patterns: HC-SLS, HC-CP, HC-UCBI, HC-S{cap}{door} (CRT uprights), etc.

LAYER 2B: CMEB CODES (CME Corp) — separate parser
  CMEB-{TYPE}[-{MOD}]-{CAP}-{DOOR}-{SERIES}[-LH]

LAYER 2C: COREPOINT CRT — CRTPR{size}{colors}/{variant}

LAYER 3: BRAND RESOLUTION → map prefix to entity
"""


if __name__ == "__main__":
    print("=" * 80)
    print("PDF ANALYSIS V2: %d brands, %d models cataloged" % (
        len(BRAND_INVENTORY), len(MODEL_NUMBERS_FROM_DOCUMENTS)))
    print("=" * 80)
    for model, info in MODEL_NUMBERS_FROM_DOCUMENTS.items():
        print(f"  {model:40s} brand={info.get('brand','?')}, "
              f"cap={info.get('capacity_cuft','?')}CF")
