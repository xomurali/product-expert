"""
models_patch.py — Fixes for parse_certifications in 002_models.py

Apply these changes to the parse_certifications function in models.py.
The original missed several certification patterns found in ARES and CME documents.
"""

def parse_certifications(text: str) -> list[str]:
    """Extract certification codes from text.

    FIXED:
    - Added UL-C-UL / UL/C-UL / C-UL patterns (seen in ARES CRT docs)
    - Added Intertek pattern (seen in CME docs)
    - Added NFPA 99 pattern
    - Fixed ETL/C-ETL to avoid double-matching (C-ETL was matching ETL too)
    - Added NSF/ANSI 456 as a filterable certification
    - Added Class 1 Division II hazardous location pattern
    """
    if not text:
        return []
    certs = []
    t = text.upper()

    cert_patterns = [
        # UL family — check specific patterns first
        (r'UL[/-]C[/-]UL', 'UL_C_UL'),         # UL-C-UL or UL/C-UL (ARES format)
        (r'C-?UL\b', 'C_UL'),                    # C-UL standalone
        (r'UL\s*471', 'UL471'),
        (r'UL\s*60335', 'UL60335'),

        # ETL family — check C-ETL before ETL
        (r'C-?ETL', 'C_ETL'),
        (r'(?<!C-?)ETL', 'ETL'),                 # ETL but not preceded by C-

        # CSA
        (r'CSA\s*C22', 'CSA_C22'),

        # Energy Star
        (r'ENERGY\s*STAR', 'Energy_Star'),

        # NSF/ANSI 456
        (r'NSF[\s/]*ANSI\s*456', 'NSF_ANSI_456'),

        # Intertek (testing lab, seen in CME docs)
        (r'INTERTEK', 'Intertek'),

        # FDA / AABB
        (r'FDA', 'FDA'),
        (r'AABB', 'AABB'),

        # CE marking
        (r'CE\b', 'CE'),

        # EPA SNAP
        (r'EPA\s*SNAP', 'EPA_SNAP'),

        # 21 CFR
        (r'21\s*CFR', '21CFR_820'),

        # NFPA fire codes
        (r'NFPA\s*45', 'NFPA_45'),
        (r'NFPA\s*30', 'NFPA_30'),
        (r'NFPA\s*99', 'NFPA_99'),

        # Hazardous location classification
        (r'CLASS\s*1.*?DIVISION\s*II', 'Class1_DivII'),
        (r'CLASS\s*I.*?DIV(?:ISION)?\s*2', 'Class1_DivII'),
    ]
    for pattern, code in cert_patterns:
        if re.search(pattern, t):
            certs.append(code)
    return sorted(set(certs))


# To apply: replace the parse_certifications function in 002_models.py
# with this version. Also add "import re" at the top if not already present.
