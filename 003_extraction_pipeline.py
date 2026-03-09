"""
Product Expert System — Document Extraction Pipeline (FIXED)
003_extraction_pipeline.py

CHANGELOG from original:
- Added ARES Scientific (ARS), CME Corp (CMEB), Corepoint CRT (CRTPR) brand detection
- Added CRT- product line prefix handling
- Added CMEB model number regex patterns (completely different grammar)
- Model-number-based brand detection (more reliable than text matching)
- Brand detection now checks model numbers FIRST, then falls back to text
- Added missing field mappings for CME-specific specs
- Added 'adjustable cycle temperature' as temp_range_raw synonym
- Added CMEB capacity "PT" notation parser (4PT6 → 4.6)
- Added CRT upright S-series pattern (CRT-ARS-HC-S26S)
- Added UL-C-UL certification pattern
- Fixed parse_certifications to handle 'UL-C-UL', 'UL/C-UL', 'C-UL'
- Fixed hazardous location / explosion-proof detection (CMEB-*-EXP, HC-EFP, HC-ERP)
- Added 'controlled_room_temp' product family detection for CRT- prefix models
- Fixed warranty parser to handle "excluding display probe calibration" text
- Added NSF/ANSI 456 probe data extraction support for CME performance sheets
"""
from __future__ import annotations
import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4
from dataclasses import dataclass, field

# These would be real imports in production:
# import fitz  # PyMuPDF
# from PIL import Image

from models import (
    DocType, ExtractedSpec, ExtractionResult,
    parse_fraction, parse_temp_range, parse_refrigerant,
    parse_electrical, parse_door_config, parse_shelf_config,
    parse_certifications,
)

logger = logging.getLogger(__name__)

# ============================================================
# Brand Detection — FIXED: model-number-first approach
# ============================================================

# Text-based patterns (fallback — less reliable than model number)
BRAND_PATTERNS = [
    # Original brands
    (r'American\s*Bio\s*Tech\s*Supply|(?<!\w)ABS(?!\w)', 'ABS'),
    (r'LABRepCo|LAB\s*Rep\s*Co', 'LABRepCo'),
    (r'Corepoint\s*Scientific|COREPOINT', 'Corepoint'),
    (r'celsius\s*Scientific|°celsius|CEL-', 'Celsius'),
    (r'CryoSafe|CryoMizer|CryoPro|CBS\b', 'CBS'),
    (r'VWR\s*CryoPro', 'CBS'),
    # NEW: ARES Scientific
    (r'ARES\s*SCIENTIFIC', 'ARES'),
    (r'aresscientific\.com', 'ARES'),
    # NEW: CME Corp
    (r'CME\s*CORP', 'CME'),
    (r'cmecorp\.com', 'CME'),
    # NEW: D.A.I. Scientific (text-based)
    (r'D\.?\s*A\.?\s*I\.?\s*SCIENTIFIC', 'DAI'),
    (r'daiscientific\.com', 'DAI'),
]

# Model-number prefix → brand code (checked FIRST, most reliable)
# Order: longest prefixes first to avoid partial matches
MODEL_PREFIX_TO_BRAND: list[tuple[str, str]] = [
    # Multi-level prefixes (longest first)
    ('PH-ABT-', 'ABS'),
    ('PH-BSI-', 'BSI'),
    ('PH-DAI-', 'DAI'),
    ('PH-LRP-', 'LABRepCo'),
    ('PH-ARS-', 'ARES'),
    ('CRT-ARS-', 'ARES'),
    ('CRT-DAI-', 'DAI'),
    ('CRT-ABT-', 'ABS'),
    ('CRT-LRP-', 'LABRepCo'),
    ('CRT-BSI-', 'BSI'),
    ('CRTPR', 'Corepoint'),
    ('CMEB-', 'CME'),
    ('DONOTUSE_', '_deprecated'),
    # Single-level prefixes
    ('ABT-', 'ABS'),
    ('BSI-', 'BSI'),
    ('LRP-', 'LABRepCo'),
    ('DAI-', 'DAI'),
    ('VWR-', 'VWR'),
    ('ARS-', 'ARES'),
    ('CPS-', 'Corepoint'),
    ('CEL-', 'Celsius'),
    ('COL-', 'COL'),
    ('SLW-', 'SLW'),
]


def detect_brand_from_model(model_number: str) -> Optional[str]:
    """Detect brand from model number prefix. Most reliable method."""
    if not model_number:
        return None
    upper = model_number.upper()
    for prefix, brand in MODEL_PREFIX_TO_BRAND:
        if upper.startswith(prefix.upper()):
            return brand
    return None


def detect_brand(text: str, model_numbers: Optional[list[str]] = None) -> Optional[str]:
    """Detect brand. Checks model numbers first, then falls back to text patterns.

    FIXED: The original only used text patterns, which failed for ARES, CME, DAI
    documents that sometimes contain 'ABS' or 'American BioTech Supply' in
    their Product Description text despite being a different brand's document.
    """
    # Strategy 1: Model number prefix (most reliable)
    if model_numbers:
        for mn in model_numbers:
            brand = detect_brand_from_model(mn)
            if brand and brand != '_deprecated':
                return brand

    # Strategy 2: Text patterns (fallback)
    for pat, brand in BRAND_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return brand

    return None


# ============================================================
# Model Number Extraction — FIXED: added ARES, CME, CRT, Corepoint
# ============================================================

MODEL_PATTERNS = [
    # === CME Corp (CMEB) — completely different grammar ===
    # CMEB-REF-PRM-23-S, CMEB-FRZ-1PT7-NSF, CMEB-REF-EXP-20-S-HCF
    # CMEB-REF-FRZ-9-SG-HCF-LH, CMEB-FRZ-4PT2-SS-NSF-LH
    r'(CMEB-(?:REF|FRZ)(?:-(?:REF|FRZ|PRM|FLM|EXP|P))?-[\w-]+)',

    # === CRT prefix (Controlled Room Temperature product line) ===
    # CRT-ARS-HC-S26S, CRT-DAI-HC-UCBI-0204-LH, CRT-ARS-HC-UCFS-0504G
    r'(CRT-(?:ARS|DAI|ABT|LRP|BSI)-HC-[\w-]+)',

    # === Corepoint CRT legacy format ===
    # CRTPR031WWG/0, CRTPR031WWW/0FB
    r'(CRTPR\d+\w+/\w+)',

    # === ARES standalone (seen in document body) ===
    # ARS-HC-UCBI-0204-LH, ARS-HC-S26S
    r'(ARS-HC-[\w-]+)',

    # === Horizon brands (ABT, BSI, LRP, DAI, VWR) ===
    # ABT-HC-26S, ABT-HC-CS-47, ABT-HC-30R, ABT-VS-SLS-12
    r'(ABT-(?:HC|VS)-[\w-]+)',
    # PH-ABT-HC-23S, PH-ABT-NSF-UCFS-0504, PH-DAI-HC-UCBI-0420SS-LH
    r'(PH-(?:ABT|BSI|DAI|LRP|ARS)-(?:HC|NSF)-[\w-]+)',
    # BSI-HC-SLS-12, BSI-SLS-12 (older format without HC)
    r'(BSI-(?:HC-)?[\w-]+)',
    # LRP-HC-30R, LRP-HC-EFP-20, LRP-HC-FFP-17P
    r'(LRP-HC-[\w-]+)',
    # DAI-HC-10S, DAI-HC-FFP-20P, DAI-HC-AFB-1420
    r'(DAI-HC-[\w-]+)',
    # VWR-HC-SLS-12
    r'(VWR-HC-[\w-]+)',
    # LABRepCo formats: LHT-20-FMP, LPVT-49-FA, LPH-5-RFP
    r'(LHT-\d+-[A-Z]+)',
    r'(LPVT-\d+-[A-Z]+)',
    r'(LPH-\d+-[A-Z]+)',
    # Corepoint: NSBR492WSWCR/0
    r'(NSBR\d+\w+/\d)',
    # Celsius: CEL-HC-BB-49
    r'(CEL-[\w-]+)',
    # Corepoint new format: CP-LRP-05-G-HC
    r'(CP-[\w-]+)',
    # Cryogenic: V-500, CM-2, VS-4, BR-4-PROMO14
    r'\b(V-\d+)\b',
    r'\b(CM[\s-]*\d+(?:\s*[A-Z]+)?)\b',
    r'\b(VS[\s-]*\d+)\b',
    r'\b(BR-\d+-\w+)\b',
    # VWR catalog numbers
    r'(VTS-\d+-\w+)',
    # VWR catalog number format (e.g., 76579-154)
    r'(?:Cat#?\s*)(76\d{3}-\d{3})',
    # Accessory: ABS RB1, ABS LLA
    r'(ABS\s+(?:RB|LLA)\d*)',
]

def extract_model_numbers(text: str) -> list[str]:
    """Extract all model numbers from document text."""
    found = []
    for pat in MODEL_PATTERNS:
        matches = re.findall(pat, text)
        found.extend(matches)
    return list(dict.fromkeys(m.strip() for m in found if len(m) > 2))


# ============================================================
# Product Line Detection — NEW
# ============================================================

def detect_product_line(model_numbers: list[str], text: str) -> Optional[str]:
    """Detect the product line prefix (CRT, PH, etc.) from model numbers."""
    for mn in model_numbers:
        upper = mn.upper()
        if upper.startswith('CRT-') or upper.startswith('CRTPR'):
            return 'CRT'  # Controlled Room Temperature
        if upper.startswith('PH-'):
            return 'PH'   # Pharmacy
        if upper.startswith('CMEB-'):
            # Determine CME sub-line from model structure
            if '-EXP-' in upper:
                return 'EXP'  # Hazardous Location
            if '-FLM-' in upper:
                return 'FLM'  # Flammable Material Storage
            if '-PRM-' in upper:
                return 'PRM'  # Premium
            if '-NSF' in upper:
                return 'NSF'  # NSF/ANSI 456 Vaccine
            return 'HCF'     # Standard Healthcare/Lab
    return None


# ============================================================
# CMEB Capacity Parser — NEW
# ============================================================

def parse_cmeb_capacity(model_number: str) -> Optional[float]:
    """Parse capacity from CME Corp model numbers.

    CME uses 'PT' for decimal points: 1PT7=1.7, 4PT2=4.2, 10PT5=10.5
    Also handles whole numbers: 14, 20, 23, 26

    Examples:
        CMEB-FRZ-1PT7-NSF → 1.7
        CMEB-REF-4PT6-G-NSF-LH → 4.6
        CMEB-REF-P-10PT5-G-NSF → 10.5
        CMEB-FRZ-FLM-14-P-HCF → 14
        CMEB-REF-PRM-23-S → 23
    """
    if not model_number or not model_number.upper().startswith('CMEB-'):
        return None

    # Match "PT" notation: digits + PT + digits
    m = re.search(r'(\d+)PT(\d+)', model_number, re.IGNORECASE)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")

    # Match bare capacity number after known segments
    # Strip CMEB-REF/FRZ and optional modifier, then find first standalone number
    stripped = re.sub(
        r'^CMEB-(?:REF|FRZ)(?:-(?:REF|FRZ|PRM|FLM|EXP|P))?-',
        '', model_number, flags=re.IGNORECASE
    )
    m = re.match(r'(\d+)(?:-|$)', stripped)
    if m:
        return float(m.group(1))

    return None


# ============================================================
# Document Type Classification — FIXED
# ============================================================

def classify_document(text: str, filename: str = "") -> DocType:
    """Classify document type from text content and filename.

    FIXED: Added CME NSF performance data sheet detection.
    CME NSF sheets include 15-point probe data that should trigger
    PERFORMANCE_DATA classification even though they also say 'Product Data Sheet'.
    """
    t = text[:3000].upper()  # Increased from 2000 to catch more content
    fn = filename.upper()

    # Image files (no text content)
    if fn.endswith(('.JPG', '.JPEG', '.PNG', '.GIF', '.WEBP')):
        if any(x in fn for x in ['INT_IMAGE', 'EXT_IMAGE', 'IMAGE']):
            return DocType.PRODUCT_IMAGE
        if any(x in fn for x in ['DIM', 'DRAWING']):
            return DocType.DIMENSIONAL_DRAWING
        return DocType.PRODUCT_IMAGE

    # Cut sheets
    if 'CUTSHEET' in t or 'CUT SHEET' in t or 'CUTSHEET' in fn:
        return DocType.CUT_SHEET

    # Performance data sheets (check BEFORE product data sheet)
    # CME NSF sheets have probe data AND say "Product Data Sheet"
    performance_indicators = [
        'TEMPERATURE PROBES', 'UNIFORMITY', 'STABILITY',
        'PROBE LOCATIONS', 'PROBE AVE MIN MAX',
        'TYPICAL CABINET AIR STABILITY',
        'TYPICAL CABINET AIR TEMPERATURE DISTRIBUTION',
    ]
    if any(x in t for x in performance_indicators):
        return DocType.PERFORMANCE_DATA

    if 'PRODUCT DATA SHEET' in t or 'PRODUCT_DATA_SHEET' in fn or 'DATASHEET' in fn:
        return DocType.PRODUCT_DATA_SHEET

    if 'PRODUCT NAME:' in t and t.count('\n') < 60:
        return DocType.FEATURE_LIST

    sections = ['GENERAL DESCRIPTION', 'REFRIGERATION SYSTEM',
                'CONTROLLER', 'DIMENSIONS', 'CERTIFICATIONS']
    if sum(1 for s in sections if s in t) >= 3:
        return DocType.PRODUCT_DATA_SHEET

    if any(x in t for x in ['LIQUID NITROGEN', 'CRYOGENIC', 'CRYOMIZER',
                             'VAPOR SHIPPER', 'DEWAR', 'VIAL CAPACITY']):
        return DocType.FEATURE_LIST

    return DocType.OTHER


# ============================================================
# Key-Value Table Extractor
# ============================================================

# Maps raw field names found in documents to canonical spec names
# FIXED: Added all CME-specific fields, CRT fields, ARES fields
FIELD_MAP: dict[str, str] = {
    # ── Capacity ────────────────────────────────────────────────
    'storage capacity (cu. ft)': 'storage_capacity_cuft',
    'storage capacity (cu. ft.)': 'storage_capacity_cuft',
    'storage capacity': 'storage_capacity_cuft',
    'cu. ft': 'storage_capacity_cuft',

    # ── Door / Shelves / Interior ───────────────────────────────
    'door': 'door_config_raw',
    'int door': 'interior_door',
    'shelves': 'shelf_config_raw',
    'freezer compartments': 'freezer_compartments',
    'drawers': 'drawer_config_raw',
    'baskets': 'baskets',

    # ── Installation ────────────────────────────────────────────
    'mounting': 'mounting_type',
    'mounting and installation': 'mounting_type',
    'interior lighting': 'interior_lighting',
    'airflow management': 'airflow_type',
    'airflow': 'airflow_type',
    'external probe access': 'probe_access',
    'insulation': 'insulation_type',
    'exterior materials': 'exterior_material',
    'access control': 'access_control',

    # ── Warranty ────────────────────────────────────────────────
    'general warranty': 'warranty_general_raw',
    'compressor warranty': 'warranty_compressor_raw',
    'compressor parts warranty': 'warranty_compressor_raw',
    'warranty disclaimer': 'disclaimers',

    # ── Weight / Electrical ─────────────────────────────────────
    'product weight (lbs)': 'product_weight_lbs',
    'product weight': 'product_weight_lbs',
    'shipping weight (lbs)': 'shipping_weight_lbs',
    'shipping weight': 'shipping_weight_lbs',
    'rated amperage': 'amperage',
    'amps': 'amperage',
    'power plug/power cord': 'plug_type_raw',
    'facility electrical requirement': 'electrical_raw',
    'agency listing and certification': 'certifications_raw',

    # ── Refrigeration System ────────────────────────────────────
    'compressor': 'compressor_type',
    'refrigerant': 'refrigerant_raw',
    'condenser': 'condenser_type',
    'evaporator': 'evaporator_type',
    'defrost': 'defrost_type',

    # ── Controller ──────────────────────────────────────────────
    'controller technology': 'controller_type',
    'display technology': 'display_type',
    'digital communication': 'digital_comm',
    'data transfer': 'data_transfer',
    'chart recorder': 'chart_recorder',

    # ── Temperature ─────────────────────────────────────────────
    'adjustable temperature range': 'temp_range_raw',
    'temperature setpoint range': 'temp_range_raw',
    'adjustable cycle temperature': 'temp_range_raw',  # FIXED: new CRT field name

    # ── Alarms ──────────────────────────────────────────────────
    'external alarm connection': 'external_alarm',
    'alarms': 'alarms_raw',
    'alarm management': 'alarms_raw',

    # ── CME-specific fields (NEW) ───────────────────────────────
    'battery backup': 'battery_backup',
    'calibration': 'calibration',
    'controller probe': 'controller_probe',
    'simulator ballast': 'simulator_ballast',
    'display probe': 'display_probe',
    'included accessories': 'included_accessories',
    'operational environment': 'operational_environment',

    # ── Performance metrics ─────────────────────────────────────
    'noise pressure level (dba)': 'noise_dba',
    'uniformity (cabinet air)': 'uniformity_c',
    'uniformity¹ (cabinet air)': 'uniformity_c',
    'uniformity (simulator ballast)': 'uniformity_ballast_c',
    'stability (cabinet air)': 'stability_c',
    'stability² (cabinet air)': 'stability_c',
    'stability (simulator ballast)': 'stability_ballast_c',
    'stability² (simulator ballast)': 'stability_ballast_c',
    'maximum temperature variation': 'max_temp_variation_c',
    'maximum temperature variation (cabinet air)': 'max_temp_variation_c',
    'energy consumption': 'energy_kwh_day',
    'energy consumption (kwh/day)': 'energy_kwh_day',
    'average heat rejection': 'heat_rejection_btu_hr',
    'average heat rejection (btu/hr)': 'heat_rejection_btu_hr',
    'pull down time to nominal operating temp': 'pulldown_time_min',
    'pull down time to 4°c nominal operating temp': 'pulldown_time_min',
    'recovery after short door openings': 'recovery_notes',
    'recovery after 3 min door opening': 'recovery_notes',
    'recovery after 60 sec door opening': 'recovery_notes',
    'temperature rise after 5 sec door openings': 'temp_rise_door_notes',
    'temperature rise after 8 sec door openings': 'temp_rise_door_notes',
    'temperature rise after short door openings': 'temp_rise_door_notes',

    # ── Advanced controller features ────────────────────────────
    'data logging and reporting': 'data_logging_features',
    'real-time graphing': 'realtime_graphing',
    'security and access': 'security_features',
    'advanced controls': 'advanced_controls',
    'visual and user interface': 'ui_features',
    'reliability and compliance': 'reliability_features',

    # ── Disclaimers ─────────────────────────────────────────────
    'disclaimers': 'disclaimers',
    'temperature setpoint range notes': 'temp_setpoint_notes',
}

def extract_kv_pairs(text: str) -> list[tuple[str, str]]:
    """Extract key-value pairs from structured document text."""
    pairs = []
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Pattern 1: "Key    Value" on same line (tab or multi-space separated)
        parts = re.split(r'\t{1,}|\s{3,}', line, maxsplit=1)
        if len(parts) == 2 and len(parts[0]) > 2 and len(parts[1]) > 0:
            pairs.append((parts[0].strip(), parts[1].strip()))
            i += 1
            continue

        # Pattern 2: Key on one line, value on next (common in feature lists)
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            key_lower = line.lower()
            if key_lower in FIELD_MAP and next_line and not any(
                next_line.lower().startswith(k) for k in list(FIELD_MAP.keys())[:10]
            ):
                pairs.append((line, next_line))
                i += 2
                continue

        i += 1
    return pairs


def map_field_name(raw_name: str) -> Optional[str]:
    """Map a raw field name to its canonical name."""
    key = raw_name.strip().lower()
    # Remove superscript markers, footnote numbers
    key = re.sub(r'[¹²³⁴⁵\*]+', '', key).strip()
    # Remove trailing colons
    key = key.rstrip(':').strip()

    if key in FIELD_MAP:
        return FIELD_MAP[key]

    # Fuzzy match: check if any known key is contained
    for known, canonical in FIELD_MAP.items():
        if known in key or key in known:
            return canonical

    return None

# ============================================================
# Cut Sheet Table Parser
# ============================================================

def parse_cut_sheet_table(text: str) -> list[ExtractedSpec]:
    """Parse the compact spec table row from cut sheets.
    Format: Cu. Ft | Defrost | Door | Int Door | Shelves | W" | D" | H" | Refrigerant | H.P. | Amps | Weight
    """
    specs = []

    # Find the table row (numbers/values after header)
    header_pat = r'Cu\.?\s*Ft'
    header_match = re.search(header_pat, text, re.IGNORECASE)
    if not header_match:
        return specs

    # Get text after header, look for data row
    after = text[header_match.start():]
    lines = [l.strip() for l in after.split('\n') if l.strip()]

    if len(lines) < 2:
        return specs

    # Check if header has "Interior Dim." sub-headers (W" D" H")
    header_line = lines[0]
    has_interior = 'interior dim' in header_line.lower()

    # Data line(s) — could be on one line or split
    data_text = ' '.join(lines[1:3])

    # Extract capacity
    cap = re.search(r'(\d+(?:\.\d+)?)\s+(?:Cycle|Manual|Auto)', data_text)
    if cap:
        specs.append(ExtractedSpec(
            name='Cu. Ft', canonical_name='storage_capacity_cuft',
            raw_value=cap.group(1), parsed_value=float(cap.group(1)),
            unit='cu.ft.', section='cut_sheet_table'))

    # Defrost
    defrost = re.search(r'(Cycle|Manual|Auto)', data_text)
    if defrost:
        specs.append(ExtractedSpec(
            name='Defrost', canonical_name='defrost_type',
            raw_value=defrost.group(1), parsed_value=defrost.group(1).lower(),
            section='cut_sheet_table'))

    # Door — FIXED: handle "Solid LH" (left-hinged) variant
    door = re.search(r'\d\s+(Solid(?:\s*LH)?|Glass(?:\s*\(Sliding\))?)', data_text)
    if door:
        raw = door.group(1)
        parsed = raw.lower().replace('(sliding)', '_sliding').strip()
        specs.append(ExtractedSpec(
            name='Door', canonical_name='door_type',
            raw_value=raw, parsed_value=parsed,
            section='cut_sheet_table'))

    # Refrigerant
    ref = re.search(r'(R\d{2,4}[a-zA-Z]?)', data_text)
    if ref:
        specs.append(ExtractedSpec(
            name='Refrigerant', canonical_name='refrigerant',
            raw_value=ref.group(1), parsed_value=ref.group(1).upper(),
            section='cut_sheet_table'))

    # HP
    hp = re.search(r'(\d+[⁄/]\d+)\s+\d', data_text)
    if hp:
        specs.append(ExtractedSpec(
            name='H.P.', canonical_name='horsepower',
            raw_value=hp.group(1), parsed_value=hp.group(1),
            unit='HP', section='cut_sheet_table'))

    # Amps
    amps = re.search(r'\b(\d+(?:\.\d+)?)\s+\d+\s*lbs', data_text)
    if amps:
        specs.append(ExtractedSpec(
            name='Amps', canonical_name='amperage',
            raw_value=amps.group(1), parsed_value=float(amps.group(1)),
            unit='A', section='cut_sheet_table'))

    # Weight
    wt = re.search(r'(\d+)\s*lbs', data_text)
    if wt:
        specs.append(ExtractedSpec(
            name='Weight', canonical_name='product_weight_lbs',
            raw_value=wt.group(1), parsed_value=float(wt.group(1)),
            unit='lbs', section='cut_sheet_table'))

    return specs

# ============================================================
# Dimension Extractor
# ============================================================

def extract_dimensions_table(text: str) -> list[ExtractedSpec]:
    """Extract dimensions from the standard dimensions table format."""
    specs = []

    # Find dimension section
    dim_match = re.search(r'Dimensions', text, re.IGNORECASE)
    if not dim_match:
        return specs

    dim_text = text[dim_match.start():dim_match.start() + 1500]

    # Exterior row
    ext = re.search(
        r'Exterior\s+(\d+[\s\d./⁄½¼¾⅛⅜⅝⅞"\']*)["\s]+(\d+[\s\d./⁄½¼¾⅛⅜⅝⅞"\']*)["\s]+(\d+[\s\d./⁄½¼¾⅛⅜⅝⅞"\']*)',
        dim_text
    )
    if ext:
        for i, (name, canon) in enumerate([
            ('Exterior Width', 'ext_width_in'),
            ('Exterior Depth', 'ext_depth_in'),
            ('Exterior Height', 'ext_height_in'),
        ]):
            val = parse_fraction(ext.group(i + 1))
            if val:
                specs.append(ExtractedSpec(
                    name=name, canonical_name=canon,
                    raw_value=ext.group(i + 1), parsed_value=val,
                    unit='in', section='dimensions'))

    # Interior row
    int_m = re.search(
        r'Interior\s+(\d+[\s\d./⁄½¼¾⅛⅜⅝⅞"\']*)["\s]+(\d+[\s\d./⁄½¼¾⅛⅜⅝⅞"\']*)["\s]+(\d+[\s\d./⁄½¼¾⅛⅜⅝⅞"\']*)',
        dim_text
    )
    if int_m:
        for i, (name, canon) in enumerate([
            ('Interior Width', 'int_width_in'),
            ('Interior Depth', 'int_depth_in'),
            ('Interior Height', 'int_height_in'),
        ]):
            val = parse_fraction(int_m.group(i + 1))
            if val:
                specs.append(ExtractedSpec(
                    name=name, canonical_name=canon,
                    raw_value=int_m.group(i + 1), parsed_value=val,
                    unit='in', section='dimensions'))

    # Door swing and total open depth
    ds = re.search(r'Door Swing[^\d]*(\d+[\s\d./⁄½¼¾⅛⅜⅝⅞"\']*)', dim_text)
    if ds:
        val = parse_fraction(ds.group(1))
        if val:
            specs.append(ExtractedSpec(
                name='Door Swing', canonical_name='door_swing_in',
                raw_value=ds.group(1), parsed_value=val,
                unit='in', section='dimensions'))

    tod = re.search(r'Total open Depth[^\d]*(\d+[\s\d./⁄½¼¾⅛⅜⅝⅞"\']*)', dim_text, re.IGNORECASE)
    if tod:
        val = parse_fraction(tod.group(1))
        if val:
            specs.append(ExtractedSpec(
                name='Total Open Depth', canonical_name='total_open_depth_in',
                raw_value=tod.group(1), parsed_value=val,
                unit='in', section='dimensions'))

    return specs

# ============================================================
# Performance Data Extractor
# ============================================================

def extract_performance_data(text: str) -> list[ExtractedSpec]:
    """Extract uniformity, stability, energy, noise, and probe data."""
    specs = []

    patterns = [
        (r'Uniformity.*?([±+/-]+\s*\d+\.?\d*)\s*°?C', 'uniformity_c', '±°C'),
        (r'Stability.*?([±+/-]+\s*\d+\.?\d*)\s*°?C', 'stability_c', '±°C'),
        (r'Maximum temperature variation.*?([±+/-]?\s*\d+\.?\d*)\s*°?C', 'max_temp_variation_c', '°C'),
        (r'Energy.*?(\d+\.?\d*)\s*K?Wh/day', 'energy_kwh_day', 'kWh/day'),
        (r'Heat Rejection.*?(\d+\.?\d*)\s*BTU', 'heat_rejection_btu_hr', 'BTU/hr'),
        (r'Noise.*?(\d+)\s*(?:or less|dBA)', 'noise_dba', 'dBA'),
        (r'Pull\s*down.*?(\d+)\s*min', 'pulldown_time_min', 'min'),
    ]

    for pat, canon, unit in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            num_str = re.sub(r'[±+/\-\s]+', '', raw)
            try:
                val = float(num_str)
            except ValueError:
                val = raw
            specs.append(ExtractedSpec(
                name=canon, canonical_name=canon,
                raw_value=raw, parsed_value=val,
                unit=unit, section='performance'))

    # Probe temperature data table
    probe_data = []
    probe_matches = re.finditer(
        r'(\d{1,2})\s+(\d+\.?\d+)\s+(\d+\.?\d+)\s+(\d+\.?\d+)', text
    )
    for pm in probe_matches:
        probe_num = int(pm.group(1))
        if 1 <= probe_num <= 20:
            probe_data.append({
                'probe': probe_num,
                'avg': float(pm.group(2)),
                'min': float(pm.group(3)),
                'max': float(pm.group(4)),
            })

    if probe_data:
        specs.append(ExtractedSpec(
            name='probe_temperature_data', canonical_name='probe_temperature_data',
            raw_value=f'{len(probe_data)} probes',
            parsed_value=probe_data,
            section='performance'))

    return specs

# ============================================================
# Cryogenic Product Extractor
# ============================================================

def extract_cryogenic_specs(text: str) -> list[ExtractedSpec]:
    """Extract specs from cryogenic product descriptions."""
    specs = []
    patterns = [
        (r'(\d+)\s*(?:Total\s+)?(?:2ml\s+)?Vial\s*Capacity', 'vial_capacity_2ml', '', 'numeric'),
        (r'(\d+)\s*Box\s*Capacity', 'box_capacity', '', 'numeric'),
        (r'(\d+)\s*Rack\s*Capacity', 'rack_capacity', '', 'numeric'),
        (r'(\d+\.?\d*)\s*Liter\s*(?:Liquid\s*Nitrogen\s*)?Capacity', 'ln2_capacity_liters', 'liters', 'numeric'),
        (r'(\d+\.?\d*)\s*Day\s*(?:Static\s*)?Holding\s*Time', 'static_holding_time_days', 'days', 'numeric'),
        (r'Static\s*Holding\s*Time[:\s]*(\d+)\s*days', 'static_holding_time_days', 'days', 'numeric'),
        (r'Static\s*Evaporation\s*Rate.*?(\d+\.?\d*)', 'evaporation_rate_l_day', 'L/day', 'numeric'),
        (r'Neck\s*Diameter[:\s]*(\d+\.?\d*)"?', 'neck_diameter_in', 'in', 'numeric'),
        (r'Exterior\s*Height[:\s]*(\d+\.?\d*)"?', 'ext_height_in', 'in', 'numeric'),
        (r'Exterior\s*Diameter[:\s]*(\d+\.?\d*)"?', 'ext_diameter_in', 'in', 'numeric'),
        (r'Weight\s*(?:Full|Charged)[:\s]*(\d+\.?\d*)\s*lbs', 'weight_full_lbs', 'lbs', 'numeric'),
        (r'Weight\s*Empty[:\s]*(\d+\.?\d*)\s*lbs', 'product_weight_lbs', 'lbs', 'numeric'),
    ]

    for pat, canon, unit, dtype in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1)
            val = float(raw) if dtype == 'numeric' else raw
            specs.append(ExtractedSpec(
                name=canon, canonical_name=canon,
                raw_value=raw, parsed_value=val,
                unit=unit, section='cryogenic'))

    # Vacuum warranty
    vw = re.search(r'(\w+)\s*[Yy]ear[s]?\s*[Vv]acuum\s*[Ww]arranty', text)
    if vw:
        word_to_num = {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7}
        raw = vw.group(1).lower()
        val = word_to_num.get(raw, raw)
        try:
            val = int(val)
        except (ValueError, TypeError):
            pass
        specs.append(ExtractedSpec(
            name='vacuum_warranty_years', canonical_name='vacuum_warranty_years',
            raw_value=vw.group(0), parsed_value=val,
            unit='years', section='cryogenic'))

    return specs

# ============================================================
# Warranty Parser — FIXED
# ============================================================

def parse_warranty(text: str) -> dict[str, Any]:
    """Parse warranty text into structured data.

    FIXED: handles 'excluding display probe calibration' suffix in CME docs,
    and 'Non-applicable' for compressor warranty in hazardous location units.
    """
    result = {}
    if not text:
        return result
    t = text.lower()

    # Skip non-applicable
    if 'non-applicable' in t or 'non applicable' in t or t.strip() == 'n/a':
        return result

    gen = re.search(r'(\w+)\s*\(?(\d+)\)?\s*years?\s*(?:parts?\s*(?:and|&)\s*labor|general)', t)
    if gen:
        result['warranty_general_years'] = int(gen.group(2))
    else:
        m = re.search(r'(\d+)\s*years?\s*parts', t)
        if m:
            result['warranty_general_years'] = int(m.group(1))

    comp = re.search(r'(\w+)\s*\(?(\d+)\)?\s*years?\s*compressor', t)
    if comp:
        result['warranty_compressor_years'] = int(comp.group(2))
    else:
        m = re.search(r'(\d+)\s*years?\s*compressor', t)
        if m:
            result['warranty_compressor_years'] = int(m.group(1))

    return result

# ============================================================
# Master Extraction Orchestrator — FIXED
# ============================================================

class DocumentExtractor:
    """Main extraction engine. Dispatches to format-specific extractors.

    FIXED: brand detection now uses model numbers first (more reliable),
    and CMEB capacity parsing is integrated.
    """

    def __init__(self, spec_registry: Optional[dict] = None):
        self.spec_registry = spec_registry or {}
        self.newly_discovered_specs: list[str] = []

    def extract(self, text: str, filename: str = "",
                file_bytes: Optional[bytes] = None) -> ExtractionResult:
        start = time.monotonic()
        doc_id = uuid4()

        # Step 1: Classify document type
        doc_type = classify_document(text, filename)

        # Step 2: Extract model numbers FIRST (needed for brand detection)
        models = extract_model_numbers(text)

        # Step 3: Detect brand using model numbers + text
        # FIXED: pass model numbers to brand detection for reliability
        brand = detect_brand(text, model_numbers=models)

        # Step 4: Detect product line (CRT, PH, etc.)
        product_line = detect_product_line(models, text)

        # Step 5: Extract title/description
        title = self._extract_title(text, doc_type)

        # Step 6: Route to format-specific extractors
        all_specs: list[ExtractedSpec] = []
        warnings: list[str] = []

        if doc_type == DocType.CUT_SHEET:
            all_specs.extend(parse_cut_sheet_table(text))
            all_specs.extend(extract_dimensions_table(text))

        elif doc_type == DocType.PRODUCT_DATA_SHEET:
            all_specs.extend(self._extract_data_sheet(text))
            all_specs.extend(extract_dimensions_table(text))
            all_specs.extend(extract_performance_data(text))

        elif doc_type == DocType.PERFORMANCE_DATA:
            all_specs.extend(self._extract_data_sheet(text))
            all_specs.extend(extract_dimensions_table(text))
            all_specs.extend(extract_performance_data(text))

        elif doc_type == DocType.FEATURE_LIST:
            all_specs.extend(self._extract_feature_list(text))
            if any(x in text.upper() for x in ['LIQUID NITROGEN', 'VIAL CAPACITY',
                                                 'CRYOGENIC', 'VAPOR SHIPPER']):
                all_specs.extend(extract_cryogenic_specs(text))

        else:
            all_specs.extend(self._extract_data_sheet(text))
            if any(x in text.upper() for x in ['LIQUID NITROGEN', 'VIAL CAPACITY']):
                all_specs.extend(extract_cryogenic_specs(text))

        # Step 7: CMEB capacity enrichment (NEW)
        # If brand is CME, try to extract capacity from model number
        if brand == 'CME' and models:
            has_capacity = any(s.canonical_name == 'storage_capacity_cuft' for s in all_specs)
            if not has_capacity:
                for mn in models:
                    cap = parse_cmeb_capacity(mn)
                    if cap:
                        all_specs.append(ExtractedSpec(
                            name='CMEB Model Capacity',
                            canonical_name='storage_capacity_cuft',
                            raw_value=mn, parsed_value=cap,
                            unit='cu.ft.', confidence=0.8))
                        break

        # Step 8: Extract certifications
        certs = []
        for spec in all_specs:
            if spec.canonical_name == 'certifications_raw':
                certs.extend(parse_certifications(str(spec.raw_value)))
        certs.extend(parse_certifications(text[:5000]))
        certs = sorted(set(certs))

        # Step 9: Post-process compound fields
        all_specs = self._post_process_specs(all_specs)

        # Step 10: Track any newly discovered specs
        for spec in all_specs:
            if spec.canonical_name and spec.canonical_name not in self.spec_registry:
                self.newly_discovered_specs.append(spec.canonical_name)

        # Step 11: Dedup specs (keep highest confidence)
        seen: dict[str, ExtractedSpec] = {}
        for s in all_specs:
            key = s.canonical_name or s.name
            if key not in seen or s.confidence > seen[key].confidence:
                seen[key] = s
        deduped = list(seen.values())

        elapsed = int((time.monotonic() - start) * 1000)

        return ExtractionResult(
            document_id=doc_id,
            doc_type=doc_type,
            brand_code=brand,
            model_numbers=models,
            title=title,
            specs=deduped,
            certifications=certs,
            warnings=warnings,
            raw_text=text[:500],
            extraction_time_ms=elapsed,
        )

    def _extract_title(self, text: str, doc_type: DocType) -> Optional[str]:
        if doc_type == DocType.FEATURE_LIST:
            m = re.search(r'Product Name:\s*(.+)', text)
            if m:
                return m.group(1).strip()
        m = re.search(r'Product Data Sheet\s*\n(.+)', text)
        if m:
            return m.group(1).strip()
        return None

    def _extract_data_sheet(self, text: str) -> list[ExtractedSpec]:
        """Extract from structured key-value product data sheets."""
        specs = []
        pairs = extract_kv_pairs(text)

        for raw_key, raw_val in pairs:
            canon = map_field_name(raw_key)
            if canon:
                specs.append(ExtractedSpec(
                    name=raw_key.strip(),
                    canonical_name=canon,
                    raw_value=raw_val.strip(),
                    parsed_value=raw_val.strip(),
                    confidence=0.9,
                ))
            elif len(raw_key) > 3 and len(raw_val) > 0:
                sanitized = re.sub(r'[^\w\s]', '', raw_key.lower()).strip()
                sanitized = re.sub(r'\s+', '_', sanitized)
                if sanitized and len(sanitized) > 3:
                    specs.append(ExtractedSpec(
                        name=raw_key.strip(),
                        canonical_name=f'_unknown_{sanitized}',
                        raw_value=raw_val.strip(),
                        parsed_value=raw_val.strip(),
                        confidence=0.5,
                    ))
        return specs

    def _extract_feature_list(self, text: str) -> list[ExtractedSpec]:
        """Extract from unstructured feature list documents."""
        specs = []

        nm = re.search(r'Product Name:\s*(.+)', text)
        if nm:
            specs.append(ExtractedSpec(
                name='product_name', canonical_name='product_name',
                raw_value=nm.group(1).strip(), parsed_value=nm.group(1).strip()))

        desc = re.search(r'Description:\s*(.+?)(?:\n|$)', text)
        if desc:
            specs.append(ExtractedSpec(
                name='description', canonical_name='description',
                raw_value=desc.group(1).strip(), parsed_value=desc.group(1).strip()))

        cap = re.search(r'(\d+\.?\d*)\s*Cu\.?\s*Ft\.?\s*[Cc]apacity', text)
        if cap:
            specs.append(ExtractedSpec(
                name='Capacity', canonical_name='storage_capacity_cuft',
                raw_value=cap.group(1), parsed_value=float(cap.group(1)),
                unit='cu.ft.'))

        for pat in [r'[Oo]perating.*?range[:\s]*(.+?)(?:\n|$)',
                    r'[Tt]emperature.*?range[:\s]*(.+?)(?:\n|$)']:
            m = re.search(pat, text)
            if m:
                tmin, tmax = parse_temp_range(m.group(1))
                if tmin is not None:
                    specs.append(ExtractedSpec(
                        name='Temp Range Min', canonical_name='temp_range_min_c',
                        raw_value=m.group(1), parsed_value=tmin, unit='°C'))
                if tmax is not None:
                    specs.append(ExtractedSpec(
                        name='Temp Range Max', canonical_name='temp_range_max_c',
                        raw_value=m.group(1), parsed_value=tmax, unit='°C'))
                break

        elec = re.search(r'(1\d{2}V.*?HP|1\d{2}V.*?(?:\n|$))', text)
        if elec:
            parsed = parse_electrical(elec.group(1))
            for k, v in parsed.items():
                specs.append(ExtractedSpec(
                    name=k, canonical_name=k,
                    raw_value=elec.group(1), parsed_value=v))

        ref_m = re.search(r'[Rr]efrigerant\s*\(?(R\d{2,4}[a-z]?)\)?', text)
        if ref_m:
            specs.append(ExtractedSpec(
                name='Refrigerant', canonical_name='refrigerant',
                raw_value=ref_m.group(1), parsed_value=ref_m.group(1).upper()))

        defr = re.search(r'(Manual|Auto|Cycle)\s*[Dd]efrost', text)
        if defr:
            specs.append(ExtractedSpec(
                name='Defrost', canonical_name='defrost_type',
                raw_value=defr.group(0), parsed_value=defr.group(1).lower()))

        dim = re.search(
            r'[Ee]xterior\s*dimensions?:?\s*(\d+[\s\d./⁄½¼¾⅛⅜⅝⅞"]*)\s*W\s*x\s*(\d+[\s\d./⁄½¼¾⅛⅜⅝⅞"]*)\s*D\s*x\s*(\d+[\s\d./⁄½¼¾⅛⅜⅝⅞"]*)\s*H',
            text
        )
        if dim:
            for i, (name, canon) in enumerate([
                ('Ext Width', 'ext_width_in'),
                ('Ext Depth', 'ext_depth_in'),
                ('Ext Height', 'ext_height_in'),
            ]):
                val = parse_fraction(dim.group(i + 1))
                if val:
                    specs.append(ExtractedSpec(
                        name=name, canonical_name=canon,
                        raw_value=dim.group(i + 1), parsed_value=val, unit='in'))

        sw = re.search(r'[Ss]hipping\s*[Ww]eight[:\s]*(\d+)\s*lbs', text)
        if sw:
            specs.append(ExtractedSpec(
                name='Shipping Weight', canonical_name='shipping_weight_lbs',
                raw_value=sw.group(1), parsed_value=float(sw.group(1)), unit='lbs'))

        door = re.search(r'[Oo]ne\s+swing\s+(.+?)(?:\n|$)', text)
        if not door:
            door = re.search(r'[Dd]ouble.*?[Dd]oor(.+?)(?:\n|$)', text)
        if door:
            specs.append(ExtractedSpec(
                name='Door', canonical_name='door_config_raw',
                raw_value=door.group(0).strip(), parsed_value=door.group(0).strip()))

        shelf = re.search(r'(\d+\s+(?:total\s+)?shelv.+?)(?:\n|$)', text, re.IGNORECASE)
        if shelf:
            specs.append(ExtractedSpec(
                name='Shelves', canonical_name='shelf_config_raw',
                raw_value=shelf.group(1).strip(), parsed_value=shelf.group(1).strip()))

        return specs

    def _post_process_specs(self, specs: list[ExtractedSpec]) -> list[ExtractedSpec]:
        """Parse compound fields into individual canonical specs."""
        result = list(specs)
        additions = []

        for s in specs:
            cn = s.canonical_name
            raw = str(s.raw_value) if s.raw_value else ''

            if cn == 'door_config_raw':
                parsed = parse_door_config(raw)
                for k, v in parsed.items():
                    additions.append(ExtractedSpec(
                        name=f'door.{k}', canonical_name=k,
                        raw_value=raw, parsed_value=v, confidence=0.85))

            elif cn == 'shelf_config_raw':
                parsed = parse_shelf_config(raw)
                for k, v in parsed.items():
                    additions.append(ExtractedSpec(
                        name=f'shelf.{k}', canonical_name=k,
                        raw_value=raw, parsed_value=v, confidence=0.85))

            elif cn == 'temp_range_raw':
                tmin, tmax = parse_temp_range(raw)
                if tmin is not None:
                    additions.append(ExtractedSpec(
                        name='temp_min', canonical_name='temp_range_min_c',
                        raw_value=raw, parsed_value=tmin, unit='°C'))
                if tmax is not None:
                    additions.append(ExtractedSpec(
                        name='temp_max', canonical_name='temp_range_max_c',
                        raw_value=raw, parsed_value=tmax, unit='°C'))

            elif cn == 'refrigerant_raw':
                ref = parse_refrigerant(raw)
                if ref:
                    additions.append(ExtractedSpec(
                        name='refrigerant', canonical_name='refrigerant',
                        raw_value=raw, parsed_value=ref))

            elif cn == 'electrical_raw':
                parsed = parse_electrical(raw)
                for k, v in parsed.items():
                    additions.append(ExtractedSpec(
                        name=f'electrical.{k}', canonical_name=k,
                        raw_value=raw, parsed_value=v))

            elif cn == 'certifications_raw':
                certs = parse_certifications(raw)
                if certs:
                    additions.append(ExtractedSpec(
                        name='certifications', canonical_name='certifications',
                        raw_value=raw, parsed_value=certs))

            elif cn in ('warranty_general_raw', 'warranty_compressor_raw'):
                parsed = parse_warranty(raw)
                for k, v in parsed.items():
                    additions.append(ExtractedSpec(
                        name=k, canonical_name=k,
                        raw_value=raw, parsed_value=v, unit='years'))

            elif cn == 'storage_capacity_cuft':
                if isinstance(s.parsed_value, str):
                    m = re.search(r'(\d+\.?\d*)', s.parsed_value)
                    if m:
                        s.parsed_value = float(m.group(1))

            elif cn == 'amperage':
                if isinstance(s.parsed_value, str):
                    m = re.search(r'(\d+\.?\d*)', s.parsed_value)
                    if m:
                        s.parsed_value = float(m.group(1))

            elif cn in ('product_weight_lbs', 'shipping_weight_lbs'):
                if isinstance(s.parsed_value, str):
                    m = re.search(r'(\d+\.?\d*)', s.parsed_value)
                    if m:
                        s.parsed_value = float(m.group(1))

        result.extend(additions)
        return result


# ============================================================
# Convenience: Run extraction on raw text
# ============================================================

def extract_document(text: str, filename: str = "") -> ExtractionResult:
    """One-shot extraction from text content."""
    extractor = DocumentExtractor()
    return extractor.extract(text, filename)
