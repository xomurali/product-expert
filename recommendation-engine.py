"""
Product Expert System — Recommendation & Matching Engine
005_recommendation_engine.py

Responsibilities:
  1. Use-case → spec requirements translation
  2. Hard constraint filtering (must-match specs)
  3. Soft scoring with weighted tolerance matching
  4. Equivalence detection across brands/families
  5. Comparison engine for side-by-side analysis
  6. Decision trace logging for explainability
  7. Citation linkage back to source documents
"""
from __future__ import annotations
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from models import (
    Product, ProductFamily, Brand, SpecRegistryEntry,
    RecommendRequest, RecommendResponse, ProductRecommendation,
    SpecMatchResult, ComplianceResult, Citation, DecisionTrace,
    CompareRequest, CompareResponse,
    RelationType, SpecDataType,
)

logger = logging.getLogger(__name__)


# ============================================================
# Use-Case Profiles
# ============================================================

@dataclass
class UseCaseProfile:
    """Maps a use-case keyword to required/preferred specs and constraints."""
    name: str
    description: str
    required_families: list[str] = field(default_factory=list)
    excluded_families: list[str] = field(default_factory=list)
    hard_constraints: dict[str, Any] = field(default_factory=dict)
    soft_preferences: dict[str, float] = field(default_factory=dict)
    required_certifications: list[str] = field(default_factory=list)
    spec_minimums: dict[str, float] = field(default_factory=dict)
    spec_maximums: dict[str, float] = field(default_factory=dict)
    notes: str = ""


USE_CASE_PROFILES: dict[str, UseCaseProfile] = {
    'vaccine_storage': UseCaseProfile(
        name='Vaccine Storage',
        description='CDC-compliant vaccine storage per VFC program requirements',
        required_families=['pharmacy_vaccine_ref', 'pharmacy_nsf_ref'],
        hard_constraints={'product_type': 'refrigerator'},
        required_certifications=['NSF_ANSI_456'],
        spec_minimums={'temp_range_min_c': 2.0},
        spec_maximums={'temp_range_max_c': 8.0},
        soft_preferences={
            'uniformity_c': 0.9,
            'stability_c': 0.9,
            'noise_dba': 0.3,
            'energy_kwh_day': 0.4,
        },
        notes='Must meet CDC Vaccine Storage & Handling Toolkit requirements. '
              'NSF/ANSI 456 certification required for VFC compliance.',
    ),

    'pharmacy_general': UseCaseProfile(
        name='General Pharmacy Storage',
        description='Medication storage for retail/hospital pharmacy',
        required_families=[
            'pharmacy_vaccine_ref', 'pharmacy_nsf_ref', 'premier_lab_ref',
        ],
        hard_constraints={'product_type': 'refrigerator'},
        spec_minimums={'temp_range_min_c': 2.0},
        spec_maximums={'temp_range_max_c': 8.0},
        soft_preferences={
            'storage_capacity_cuft': 0.5,
            'uniformity_c': 0.7,
            'noise_dba': 0.6,
            'energy_kwh_day': 0.5,
        },
    ),

    'laboratory_general': UseCaseProfile(
        name='General Laboratory Storage',
        description='Reagent, sample, and media storage for research labs',
        required_families=[
            'premier_lab_ref', 'standard_lab_ref', 'chromatography_ref',
        ],
        hard_constraints={'product_type': 'refrigerator'},
        soft_preferences={
            'storage_capacity_cuft': 0.6,
            'uniformity_c': 0.7,
            'energy_kwh_day': 0.5,
            'shelf_count': 0.3,
        },
    ),

    'chromatography': UseCaseProfile(
        name='Chromatography Column Storage',
        description='Storage for HPLC/FPLC columns requiring stable, uniform temps',
        required_families=['chromatography_ref'],
        hard_constraints={
            'product_type': 'refrigerator',
            'door_type': 'glass',
        },
        soft_preferences={
            'uniformity_c': 0.95,
            'stability_c': 0.95,
            'storage_capacity_cuft': 0.4,
        },
        notes='Glass doors preferred for visual inventory without opening.',
    ),

    'blood_bank': UseCaseProfile(
        name='Blood Bank Storage',
        description='FDA/AABB-compliant blood product storage at 1-6°C',
        required_families=['blood_bank_ref'],
        hard_constraints={'product_type': 'refrigerator'},
        required_certifications=['FDA', 'AABB'],
        spec_minimums={'temp_range_min_c': 1.0},
        spec_maximums={'temp_range_max_c': 6.0},
        soft_preferences={
            'uniformity_c': 0.95,
            'stability_c': 0.95,
            'storage_capacity_cuft': 0.5,
        },
        notes='Must meet 21 CFR Part 820 and AABB standards.',
    ),

    'flammable_storage': UseCaseProfile(
        name='Flammable Material Storage',
        description='Storage of flammable solvents, reagents per NFPA 30/45',
        required_families=['flammable_storage_ref'],
        hard_constraints={'product_type': 'refrigerator'},
        required_certifications=['NFPA_45'],
        soft_preferences={
            'storage_capacity_cuft': 0.6,
            'energy_kwh_day': 0.3,
        },
        notes='Interior must be intrinsically safe / non-sparking.',
    ),

    'sample_freezing': UseCaseProfile(
        name='Laboratory Sample Freezing',
        description='General lab freezer for samples, enzymes, reagents',
        required_families=[
            'manual_defrost_freezer', 'auto_defrost_freezer', 'precision_freezer',
        ],
        hard_constraints={'product_type': 'freezer'},
        soft_preferences={
            'storage_capacity_cuft': 0.6,
            'temp_range_min_c': 0.7,
            'energy_kwh_day': 0.5,
            'uniformity_c': 0.6,
        },
    ),

    'plasma_storage': UseCaseProfile(
        name='Plasma Freezing & Storage',
        description='Plasma storage at -30°C or below per FDA/AABB',
        required_families=['plasma_freezer', 'precision_freezer'],
        hard_constraints={'product_type': 'freezer'},
        required_certifications=['FDA'],
        spec_maximums={'temp_range_min_c': -30.0},
        soft_preferences={
            'uniformity_c': 0.9,
            'stability_c': 0.9,
            'storage_capacity_cuft': 0.5,
        },
    ),

    'undercounter': UseCaseProfile(
        name='Undercounter Installation',
        description='Compact units for built-in or under-bench installation',
        required_families=[
            'pharmacy_nsf_ref', 'pharmacy_vaccine_ref', 'premier_lab_ref',
        ],
        hard_constraints={},
        spec_maximums={'ext_height_in': 36.0},
        soft_preferences={
            'storage_capacity_cuft': 0.5,
            'noise_dba': 0.7,
            'energy_kwh_day': 0.5,
        },
        notes='Height must fit under standard 36" countertop.',
    ),

    'cryogenic_storage': UseCaseProfile(
        name='Cryogenic / LN2 Storage',
        description='Long-term storage in liquid nitrogen dewars',
        required_families=['cryo_dewar', 'vapor_shipper', 'cryo_freezer'],
        hard_constraints={'product_type': 'cryogenic'},
        soft_preferences={
            'ln2_capacity_liters': 0.6,
            'static_holding_time_days': 0.8,
            'vial_capacity_2ml': 0.5,
        },
    ),

    'energy_efficient': UseCaseProfile(
        name='Energy Efficient',
        description='Prioritize low energy consumption and Energy Star certification',
        required_families=[],
        hard_constraints={},
        required_certifications=['Energy_Star'],
        soft_preferences={
            'energy_kwh_day': 0.95,
            'noise_dba': 0.4,
            'storage_capacity_cuft': 0.3,
        },
    ),
}


def resolve_use_case(text: str) -> Optional[UseCaseProfile]:
    """Match free-text description to a use-case profile."""
    if not text:
        return None
    t = text.lower()

    keyword_map = {
        'vaccine': 'vaccine_storage',
        'vfc': 'vaccine_storage',
        'cdc': 'vaccine_storage',
        'immunization': 'vaccine_storage',
        'pharmacy': 'pharmacy_general',
        'medication': 'pharmacy_general',
        'drug storage': 'pharmacy_general',
        'chromatography': 'chromatography',
        'hplc': 'chromatography',
        'fplc': 'chromatography',
        'column storage': 'chromatography',
        'blood bank': 'blood_bank',
        'blood product': 'blood_bank',
        'transfusion': 'blood_bank',
        'flammable': 'flammable_storage',
        'solvent': 'flammable_storage',
        'nfpa': 'flammable_storage',
        'explosion': 'flammable_storage',
        'freezer': 'sample_freezing',
        'freeze': 'sample_freezing',
        'frozen': 'sample_freezing',
        'enzyme': 'sample_freezing',
        'plasma': 'plasma_storage',
        'undercounter': 'undercounter',
        'under counter': 'undercounter',
        'built-in': 'undercounter',
        'compact': 'undercounter',
        'cryogenic': 'cryogenic_storage',
        'liquid nitrogen': 'cryogenic_storage',
        'ln2': 'cryogenic_storage',
        'dewar': 'cryogenic_storage',
        'vapor shipper': 'cryogenic_storage',
        'energy': 'energy_efficient',
        'energy star': 'energy_efficient',
        'green': 'energy_efficient',
        'lab': 'laboratory_general',
        'laboratory': 'laboratory_general',
        'reagent': 'laboratory_general',
        'sample': 'laboratory_general',
        'research': 'laboratory_general',
    }

    # Score each profile by keyword hits
    scores: dict[str, int] = {}
    for kw, profile_key in keyword_map.items():
        if kw in t:
            scores[profile_key] = scores.get(profile_key, 0) + 1

    if not scores:
        return None

    best = max(scores, key=scores.get)
    return USE_CASE_PROFILES.get(best)


# ============================================================
# Scoring Engine
# ============================================================

@dataclass
class ScoringWeights:
    """Configurable weights for the scoring algorithm."""
    hard_match_weight: float = 0.0      # Binary: pass/fail, no partial
    capacity_weight: float = 0.20
    temperature_weight: float = 0.15
    performance_weight: float = 0.20    # uniformity, stability
    efficiency_weight: float = 0.10     # energy, noise
    certification_weight: float = 0.15
    dimensional_weight: float = 0.10
    feature_weight: float = 0.10        # shelves, door type, controller


DEFAULT_WEIGHTS = ScoringWeights()


# Spec importance tiers — higher = more important for matching
SPEC_IMPORTANCE: dict[str, float] = {
    # Tier 1: Critical matching specs
    'storage_capacity_cuft': 1.0,
    'temp_range_min_c': 1.0,
    'temp_range_max_c': 1.0,
    'voltage_v': 1.0,
    'refrigerant': 0.9,

    # Tier 2: Performance differentiators
    'uniformity_c': 0.85,
    'stability_c': 0.85,
    'energy_kwh_day': 0.7,
    'noise_dba': 0.6,
    'pulldown_time_min': 0.5,

    # Tier 3: Physical constraints
    'ext_width_in': 0.8,
    'ext_depth_in': 0.8,
    'ext_height_in': 0.8,
    'product_weight_lbs': 0.4,

    # Tier 4: Features
    'door_type': 0.7,
    'door_count': 0.5,
    'shelf_count': 0.4,
    'controller_type': 0.3,
    'defrost_type': 0.5,
    'amperage': 0.6,

    # Cryogenic
    'ln2_capacity_liters': 0.9,
    'static_holding_time_days': 0.85,
    'vial_capacity_2ml': 0.7,
}


def score_numeric_match(
    required: float,
    actual: float,
    tolerance_pct: float = 0.15,
    prefer_higher: bool = True,
) -> float:
    """
    Score a numeric spec match.
    Returns 0.0-1.0 where 1.0 = perfect match.

    Args:
        required: the requested value
        actual: the product's value
        tolerance_pct: acceptable deviation (0.15 = ±15%)
        prefer_higher: if True, exceeding requirement is better than falling short
    """
    if required == 0:
        return 1.0 if actual == 0 else 0.5

    delta = actual - required
    delta_pct = abs(delta) / abs(required)

    if delta_pct <= 0.02:
        return 1.0  # Near-exact match

    if delta_pct <= tolerance_pct:
        # Within tolerance — linear decay
        return 1.0 - (delta_pct / tolerance_pct) * 0.3

    # Outside tolerance
    if prefer_higher and delta > 0:
        # Over-spec'd — slight penalty but still acceptable
        return max(0.3, 0.7 - (delta_pct - tolerance_pct) * 0.5)
    elif not prefer_higher and delta < 0:
        # Under-spec'd for a "lower is better" metric — slight penalty
        return max(0.3, 0.7 - (delta_pct - tolerance_pct) * 0.5)
    else:
        # Under-spec'd (or over for lower-is-better) — heavier penalty
        return max(0.0, 0.5 - (delta_pct - tolerance_pct) * 1.0)


def score_enum_match(required: str, actual: str) -> float:
    """Score an enum/text spec match."""
    if not required or not actual:
        return 0.5  # Can't compare
    r, a = required.lower().strip(), actual.lower().strip()
    if r == a:
        return 1.0
    # Partial match (e.g., 'glass' in 'glass_sliding')
    if r in a or a in r:
        return 0.7
    return 0.0


def score_range_containment(
    req_min: Optional[float],
    req_max: Optional[float],
    prod_min: Optional[float],
    prod_max: Optional[float],
) -> float:
    """
    Score whether a product's range fully contains the required range.
    Used for temperature ranges — product must cover the required setpoints.
    """
    if prod_min is None or prod_max is None:
        return 0.3  # Unknown range

    score = 1.0

    if req_min is not None and prod_min is not None:
        if prod_min <= req_min:
            score *= 1.0  # Product can go as low as needed
        else:
            gap = prod_min - req_min
            score *= max(0.0, 1.0 - gap * 0.2)

    if req_max is not None and prod_max is not None:
        if prod_max >= req_max:
            score *= 1.0  # Product can go as high as needed
        else:
            gap = req_max - prod_max
            score *= max(0.0, 1.0 - gap * 0.2)

    return score


def score_certification_match(
    required: list[str], actual: list[str]
) -> tuple[float, list[str]]:
    """
    Score certification coverage. Returns (score, missing_certs).
    All required certs must be present for a perfect score.
    """
    if not required:
        return 1.0, []

    actual_set = set(c.upper().replace(' ', '_') for c in actual)
    required_set = set(c.upper().replace(' ', '_') for c in required)

    missing = required_set - actual_set
    if not missing:
        return 1.0, []

    coverage = 1.0 - len(missing) / len(required_set)
    return coverage, sorted(missing)


# ============================================================
# Product Scorer
# ============================================================

@dataclass
class ProductScore:
    """Complete scoring result for one product against a request."""
    product: Product
    total_score: float = 0.0
    hard_pass: bool = True
    hard_fail_reasons: list[str] = field(default_factory=list)
    spec_matches: list[SpecMatchResult] = field(default_factory=list)
    compliance_results: list[ComplianceResult] = field(default_factory=list)
    missing_certs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def score_product(
    product: Product,
    request: RecommendRequest,
    use_case: Optional[UseCaseProfile] = None,
    weights: ScoringWeights = DEFAULT_WEIGHTS,
) -> ProductScore:
    """
    Score a single product against a recommendation request.
    Returns a ProductScore with full breakdown.
    """
    ps = ProductScore(product=product)
    component_scores: list[tuple[float, float]] = []  # (score, weight)

    # Merge use-case constraints with explicit request
    hard_constraints = dict(request.constraints)
    soft_prefs = dict(request.preferences)
    required_certs: list[str] = []
    spec_mins: dict[str, float] = {}
    spec_maxs: dict[str, float] = {}
    family_filter = request.family_filter or []

    if use_case:
        hard_constraints = {**use_case.hard_constraints, **hard_constraints}
        soft_prefs = {**use_case.soft_preferences, **soft_prefs}
        required_certs = list(use_case.required_certifications)
        spec_mins = dict(use_case.spec_minimums)
        spec_maxs = dict(use_case.spec_maximums)
        if use_case.required_families and not family_filter:
            family_filter = use_case.required_families

    # ----------------------------------------------------------
    # Phase 1: Hard Constraints (binary pass/fail)
    # ----------------------------------------------------------

    # Family filter
    # Note: in production, family_id would be resolved to family_code
    # For now we check via product.specs or product attributes

    # Product type filter
    pt = hard_constraints.get('product_type')
    if pt:
        prod_type = _get_spec(product, 'product_type')
        if prod_type and prod_type != pt:
            ps.hard_pass = False
            ps.hard_fail_reasons.append(
                f"Product type mismatch: need {pt}, got {prod_type}")

    # Voltage must match (safety critical)
    req_voltage = request.structured_specs.get('voltage_v') or hard_constraints.get('voltage_v')
    if req_voltage:
        prod_voltage = product.voltage_v
        if prod_voltage and prod_voltage != int(req_voltage):
            ps.hard_pass = False
            ps.hard_fail_reasons.append(
                f"Voltage mismatch: need {req_voltage}V, product is {prod_voltage}V")

    # Door type hard constraint
    req_door = hard_constraints.get('door_type')
    if req_door:
        if product.door_type and product.door_type != req_door:
            ps.hard_pass = False
            ps.hard_fail_reasons.append(
                f"Door type mismatch: need {req_door}, got {product.door_type}")

    # Dimension maximums (must fit in space)
    for dim_spec, dim_col in [
        ('max_width_in', 'ext_width_in'),
        ('max_depth_in', 'ext_depth_in'),
        ('max_height_in', 'ext_height_in'),
    ]:
        max_val = request.structured_specs.get(dim_spec) or spec_maxs.get(dim_col)
        if max_val:
            prod_val = getattr(product, dim_col, None)
            if prod_val and prod_val > float(max_val):
                ps.hard_pass = False
                ps.hard_fail_reasons.append(
                    f"Exceeds max {dim_col}: {prod_val}\" > {max_val}\"")

    # Temperature range must cover requirements
    req_tmin = spec_mins.get('temp_range_min_c')
    req_tmax = spec_maxs.get('temp_range_max_c')
    if req_tmin is not None and product.temp_range_min_c is not None:
        if product.temp_range_min_c > req_tmin + 0.5:
            ps.hard_pass = False
            ps.hard_fail_reasons.append(
                f"Min temp too high: need ≤{req_tmin}°C, product min is {product.temp_range_min_c}°C")
    if req_tmax is not None and product.temp_range_max_c is not None:
        if product.temp_range_max_c < req_tmax - 0.5:
            ps.hard_pass = False
            ps.hard_fail_reasons.append(
                f"Max temp too low: need ≥{req_tmax}°C, product max is {product.temp_range_max_c}°C")

    # Required certifications
    if required_certs:
        cert_score, missing = score_certification_match(
            required_certs, product.certifications
        )
        ps.missing_certs = missing
        if missing:
            ps.hard_pass = False
            ps.hard_fail_reasons.append(
                f"Missing required certifications: {', '.join(missing)}")
        ps.compliance_results.append(ComplianceResult(
            rule='required_certifications',
            status='pass' if not missing else 'fail',
            details=f"Required: {required_certs}. Missing: {missing or 'none'}",
        ))

    # If hard fail, score = 0 and return early
    if not ps.hard_pass:
        ps.total_score = 0.0
        return ps

    # ----------------------------------------------------------
    # Phase 2: Soft Scoring
    # ----------------------------------------------------------

    # Capacity scoring
    req_cap = request.structured_specs.get('storage_capacity_cuft')
    if req_cap and product.storage_capacity_cuft:
        cap_score = score_numeric_match(
            float(req_cap), product.storage_capacity_cuft,
            tolerance_pct=0.20, prefer_higher=True)
        component_scores.append((cap_score, weights.capacity_weight))
        ps.spec_matches.append(SpecMatchResult(
            spec='storage_capacity_cuft',
            display_name='Storage Capacity',
            value_required=req_cap,
            value_product=product.storage_capacity_cuft,
            unit='cu.ft.',
            delta_pct=_delta_pct(float(req_cap), product.storage_capacity_cuft),
            within_tolerance=abs(_delta_pct(float(req_cap), product.storage_capacity_cuft) or 0) <= 20,
            score=cap_score,
        ))

    # Temperature range scoring
    if product.temp_range_min_c is not None and product.temp_range_max_c is not None:
        temp_score = score_range_containment(
            req_tmin, req_tmax,
            product.temp_range_min_c, product.temp_range_max_c,
        )
        component_scores.append((temp_score, weights.temperature_weight))
        ps.spec_matches.append(SpecMatchResult(
            spec='temp_range',
            display_name='Temperature Range',
            value_required=f"{req_tmin or '?'}°C to {req_tmax or '?'}°C",
            value_product=f"{product.temp_range_min_c}°C to {product.temp_range_max_c}°C",
            unit='°C',
            score=temp_score,
        ))

    # Performance specs (uniformity, stability)
    perf_scores = []
    for perf_spec in ['uniformity_c', 'stability_c']:
        prod_val = _get_spec(product, perf_spec)
        pref_weight = soft_prefs.get(perf_spec, 0)
        if prod_val is not None and pref_weight > 0:
            # Lower uniformity/stability = better
            # Score inversely — ±1.0°C is excellent, ±3.0°C is poor
            try:
                val = float(prod_val)
                s = max(0.0, min(1.0, 1.0 - (val - 0.5) / 3.0))
                perf_scores.append(s)
                ps.spec_matches.append(SpecMatchResult(
                    spec=perf_spec,
                    display_name=perf_spec.replace('_', ' ').title(),
                    value_product=f"±{val}°C",
                    unit='±°C',
                    score=s,
                ))
            except (ValueError, TypeError):
                pass

    if perf_scores:
        avg_perf = sum(perf_scores) / len(perf_scores)
        component_scores.append((avg_perf, weights.performance_weight))

    # Efficiency (energy, noise) — lower is better
    eff_scores = []
    energy = _get_spec(product, 'energy_kwh_day')
    if energy is not None:
        try:
            e = float(energy)
            # Typical range: 0.5–3.0 kWh/day
            s = max(0.0, min(1.0, 1.0 - (e - 0.5) / 3.0))
            eff_scores.append(s)
            ps.spec_matches.append(SpecMatchResult(
                spec='energy_kwh_day', display_name='Energy Consumption',
                value_product=f"{e} kWh/day", unit='kWh/day', score=s,
            ))
        except (ValueError, TypeError):
            pass

    noise = _get_spec(product, 'noise_dba')
    if noise is not None:
        try:
            n = float(noise)
            # Typical range: 35–55 dBA
            s = max(0.0, min(1.0, 1.0 - (n - 35) / 25.0))
            eff_scores.append(s)
            ps.spec_matches.append(SpecMatchResult(
                spec='noise_dba', display_name='Noise Level',
                value_product=f"{n} dBA", unit='dBA', score=s,
            ))
        except (ValueError, TypeError):
            pass

    if eff_scores:
        avg_eff = sum(eff_scores) / len(eff_scores)
        component_scores.append((avg_eff, weights.efficiency_weight))

    # Certification bonus (beyond required)
    bonus_certs = ['Energy_Star', 'EPA_SNAP']
    bonus = sum(1 for c in bonus_certs if c in product.certifications)
    if bonus:
        cert_bonus = min(1.0, 0.5 + bonus * 0.25)
        component_scores.append((cert_bonus, weights.certification_weight))
        ps.compliance_results.append(ComplianceResult(
            rule='bonus_certifications',
            status='pass',
            details=f"Has {bonus} bonus certifications: "
                    f"{[c for c in bonus_certs if c in product.certifications]}",
        ))

    # Dimensional fit scoring
    dim_scores = []
    for dim_spec in ['ext_width_in', 'ext_depth_in', 'ext_height_in']:
        req_max = request.structured_specs.get(f'max_{dim_spec.replace("ext_", "")}')
        if not req_max:
            req_max = spec_maxs.get(dim_spec)
        prod_val = getattr(product, dim_spec, None)
        if req_max and prod_val:
            # Closer to max = better fit (uses space efficiently)
            ratio = float(prod_val) / float(req_max)
            if ratio <= 1.0:
                s = 0.5 + ratio * 0.5  # 50-100%
            else:
                s = 0.0  # Doesn't fit (should be caught by hard constraint)
            dim_scores.append(s)

    if dim_scores:
        avg_dim = sum(dim_scores) / len(dim_scores)
        component_scores.append((avg_dim, weights.dimensional_weight))

    # Feature scoring (shelves, door, controller)
    feat_scores = []
    req_shelves = request.structured_specs.get('shelf_count')
    if req_shelves and product.shelf_count:
        feat_scores.append(score_numeric_match(
            float(req_shelves), float(product.shelf_count),
            tolerance_pct=0.30, prefer_higher=True))

    req_door_type = request.structured_specs.get('door_type')
    if req_door_type and product.door_type:
        feat_scores.append(score_enum_match(req_door_type, product.door_type))

    if feat_scores:
        avg_feat = sum(feat_scores) / len(feat_scores)
        component_scores.append((avg_feat, weights.feature_weight))

    # ----------------------------------------------------------
    # Phase 3: Weighted Total
    # ----------------------------------------------------------
    if component_scores:
        total_weight = sum(w for _, w in component_scores)
        if total_weight > 0:
            ps.total_score = sum(s * w for s, w in component_scores) / total_weight
        else:
            ps.total_score = 0.5  # No scored dimensions
    else:
        ps.total_score = 0.5  # No specs to compare — neutral score

    # Apply use-case preference boosts
    for spec_name, pref_weight in soft_prefs.items():
        prod_val = _get_spec(product, spec_name)
        if prod_val is not None and pref_weight > 0.5:
            ps.total_score = min(1.0, ps.total_score * (1.0 + pref_weight * 0.05))

    return ps


# ============================================================
# Recommendation Engine
# ============================================================

class RecommendationEngine:
    """
    Main recommendation engine. Orchestrates:
      request parsing → use-case resolution → candidate filtering →
      scoring → ranking → response assembly
    """

    def __init__(self, repo: Any):
        """
        Args:
            repo: ProductRepository (from ingestion_orchestrator module)
        """
        self.repo = repo

    async def recommend(
        self, request: RecommendRequest
    ) -> RecommendResponse:
        """Generate product recommendations for a request."""
        start = time.monotonic()
        trace: list[DecisionTrace] = []
        warnings: list[str] = []
        clarifications: list[dict] = []

        # --- Step 1: Resolve use case ---
        use_case = None
        if request.use_case:
            use_case = USE_CASE_PROFILES.get(request.use_case)
            if not use_case:
                use_case = resolve_use_case(request.use_case)
        if not use_case and request.free_text:
            use_case = resolve_use_case(request.free_text)

        if use_case:
            trace.append(DecisionTrace(
                step='use_case_resolution',
                detail=f"Resolved to: {use_case.name} — {use_case.description}",
                products_remaining=0,
                timestamp=_now(),
            ))
        else:
            trace.append(DecisionTrace(
                step='use_case_resolution',
                detail='No specific use case matched; using general matching',
                products_remaining=0,
                timestamp=_now(),
            ))

        # --- Step 2: Get candidate products ---
        candidates = await self._get_candidates(request, use_case)
        trace.append(DecisionTrace(
            step='candidate_pool',
            detail=f"Initial candidate pool: {len(candidates)} products",
            products_remaining=len(candidates),
            timestamp=_now(),
        ))

        if not candidates:
            elapsed = int((time.monotonic() - start) * 1000)
            return RecommendResponse(
                query_id=request.query_id or str(uuid4()),
                products=[],
                clarifications_needed=[{
                    'type': 'no_candidates',
                    'message': 'No products match the specified criteria. '
                               'Try relaxing constraints.',
                }],
                decision_trace=trace,
                warnings=['No matching products found'],
                response_time_ms=elapsed,
            )

        # --- Step 3: Score all candidates ---
        scored: list[ProductScore] = []
        for product in candidates:
            ps = score_product(product, request, use_case)
            scored.append(ps)

        # --- Step 4: Separate pass/fail ---
        passing = [s for s in scored if s.hard_pass]
        failing = [s for s in scored if not s.hard_pass]

        trace.append(DecisionTrace(
            step='hard_filter',
            detail=f"{len(passing)} pass hard constraints, "
                   f"{len(failing)} filtered out",
            products_remaining=len(passing),
            timestamp=_now(),
        ))

        # --- Step 5: Rank by score ---
        passing.sort(key=lambda s: s.total_score, reverse=True)

        # --- Step 6: Build response ---
        top_n = request.top_n or 5
        primary = passing[:top_n]
        alternates = passing[top_n:top_n + 3] if request.include_alternates else []

        # If too few passing, suggest best-failing as alternates
        if len(primary) < top_n and failing:
            failing.sort(key=lambda s: s.total_score, reverse=True)
            for f in failing[:3]:
                f.notes.append(
                    f"Does not meet all requirements: "
                    f"{'; '.join(f.hard_fail_reasons)}")
            alternates.extend(failing[:3])

        trace.append(DecisionTrace(
            step='ranking',
            detail=f"Top {len(primary)} recommendations, "
                   f"{len(alternates)} alternates",
            products_remaining=len(primary),
            timestamp=_now(),
        ))

        # --- Step 7: Generate clarifications if needed ---
        if not request.structured_specs.get('storage_capacity_cuft') and not request.use_case:
            clarifications.append({
                'type': 'missing_spec',
                'spec': 'storage_capacity_cuft',
                'message': 'What storage capacity do you need? '
                           'Available sizes: 5, 12, 16, 20, 23, 26, 30, 33, 49 cu.ft.',
            })

        if not request.structured_specs.get('voltage_v'):
            clarifications.append({
                'type': 'assumption',
                'spec': 'voltage_v',
                'message': 'Assuming 115V/60Hz standard US power. '
                           'Confirm if 220V or other is needed.',
            })

        elapsed = int((time.monotonic() - start) * 1000)

        return RecommendResponse(
            query_id=request.query_id or str(uuid4()),
            products=[self._to_recommendation(ps) for ps in primary],
            alternates=[self._to_recommendation(ps) for ps in alternates],
            clarifications_needed=clarifications,
            decision_trace=trace,
            warnings=warnings,
            response_time_ms=elapsed,
        )

    async def compare(self, request: CompareRequest) -> CompareResponse:
        """Compare multiple products side-by-side."""
        products: list[Product] = []
        for pid in request.product_ids:
            p = await self._get_product_by_id(pid)
            if p:
                products.append(p)

        if len(products) < 2:
            return CompareResponse(
                products=[p.model_number for p in products],
                specs_compared=[],
                suitability_scores=[],
                summary='Need at least 2 products to compare.',
            )

        # Determine which specs to compare
        all_specs = set()
        for p in products:
            # Fixed columns
            for col in SPEC_IMPORTANCE:
                val = _get_spec(p, col)
                if val is not None:
                    all_specs.add(col)
            # Dynamic specs
            for k in p.specs:
                if not k.startswith('_unknown_'):
                    all_specs.add(k)

        # Build comparison rows
        specs_compared = []
        for spec in sorted(all_specs, key=lambda s: SPEC_IMPORTANCE.get(s, 0.1), reverse=True):
            row = {
                'spec': spec,
                'display_name': spec.replace('_', ' ').title(),
                'values': {},
                'has_difference': False,
            }
            vals = set()
            for p in products:
                v = _get_spec(p, spec)
                row['values'][p.model_number] = v
                if v is not None:
                    vals.add(str(v))

            row['has_difference'] = len(vals) > 1
            if request.highlight_differences and not row['has_difference']:
                continue  # Skip identical specs if highlighting diffs
            specs_compared.append(row)

        # Score suitability if constraints given
        scores = []
        if request.user_constraints:
            fake_req = RecommendRequest(
                structured_specs=request.user_constraints,
            )
            for p in products:
                ps = score_product(p, fake_req)
                scores.append(round(ps.total_score, 3))
        else:
            scores = [0.0] * len(products)

        # Generate summary
        if scores and max(scores) > 0:
            best_idx = scores.index(max(scores))
            summary = (
                f"Based on your requirements, the {products[best_idx].model_number} "
                f"scores highest at {scores[best_idx]:.0%}. "
                f"Key differences are in: "
                f"{', '.join(r['display_name'] for r in specs_compared[:5] if r.get('has_difference'))}."
            )
        else:
            diffs = [r['display_name'] for r in specs_compared if r.get('has_difference')]
            summary = (
                f"Comparing {len(products)} products. "
                f"They differ in {len(diffs)} specs: {', '.join(diffs[:8])}."
            )

        return CompareResponse(
            products=[p.model_number for p in products],
            specs_compared=specs_compared,
            suitability_scores=scores,
            summary=summary,
        )

    # ----------------------------------------------------------
    # Equivalence Detection
    # ----------------------------------------------------------

    async def find_equivalents(
        self,
        product: Product,
        tolerance_map: Optional[dict[str, float]] = None,
        required_match: Optional[list[str]] = None,
    ) -> list[tuple[Product, float]]:
        """
        Find products equivalent to the given product.
        Used for cross-brand matching and substitution.

        Args:
            product: the reference product
            tolerance_map: spec_name → max_delta_pct (e.g., {'storage_capacity_cuft': 0.15})
            required_match: specs that must match exactly

        Returns:
            List of (product, similarity_score) tuples, sorted by score desc.
        """
        if tolerance_map is None:
            tolerance_map = {
                'storage_capacity_cuft': 0.15,
                'amperage': 0.20,
                'product_weight_lbs': 0.30,
            }
        if required_match is None:
            required_match = ['door_type', 'refrigerant', 'voltage_v']

        all_products = await self._get_all_products()
        equivalents: list[tuple[Product, float]] = []

        for candidate in all_products:
            if candidate.id == product.id:
                continue

            # Check required exact matches
            exact_fail = False
            for spec in required_match:
                ref_val = _get_spec(product, spec)
                cand_val = _get_spec(candidate, spec)
                if ref_val is not None and cand_val is not None:
                    if normalize_val(ref_val) != normalize_val(cand_val):
                        exact_fail = True
                        break
            if exact_fail:
                continue

            # Score similarity
            sim_scores: list[float] = []
            for spec, tol in tolerance_map.items():
                ref_val = _get_spec(product, spec)
                cand_val = _get_spec(candidate, spec)
                if ref_val is not None and cand_val is not None:
                    try:
                        r, c = float(ref_val), float(cand_val)
                        denom = max(abs(r), 1e-9)
                        delta = abs(r - c) / denom
                        if delta > tol * 2:
                            exact_fail = True
                            break
                        sim_scores.append(max(0.0, 1.0 - delta / tol))
                    except (ValueError, TypeError):
                        if normalize_val(ref_val) == normalize_val(cand_val):
                            sim_scores.append(1.0)
                        else:
                            sim_scores.append(0.0)

            if exact_fail:
                continue

            if sim_scores:
                similarity = sum(sim_scores) / len(sim_scores)
                if similarity >= 0.5:
                    equivalents.append((candidate, similarity))

        equivalents.sort(key=lambda x: x[1], reverse=True)
        return equivalents

    # ----------------------------------------------------------
    # Internal Helpers
    # ----------------------------------------------------------

    async def _get_candidates(
        self,
        request: RecommendRequest,
        use_case: Optional[UseCaseProfile],
    ) -> list[Product]:
        """
        Get candidate products from the repository.
        Applies pre-filters to reduce scoring workload.
        """
        # In production, this would be a SQL query with WHERE clauses
        # For now, get all and filter in-memory
        all_products = await self._get_all_products()
        candidates = []

        for p in all_products:
            # Skip discontinued unless requested
            if not request.include_discontinued:
                if hasattr(p, 'status') and p.status in (
                    ProductStatus.DISCONTINUED, ProductStatus.DEPRECATED
                ):
                    continue

            # Brand filter
            if request.brand_filter:
                brand = _get_spec(p, 'brand_code')
                if brand and brand not in request.brand_filter:
                    continue

            # Family filter from use case
            if use_case and use_case.required_families:
                family = _get_spec(p, 'family_code')
                if family and family not in use_case.required_families:
                    # Don't hard-filter on family if not in excluded
                    if use_case.excluded_families and family in use_case.excluded_families:
                        continue

            candidates.append(p)

        return candidates

    async def _get_all_products(self) -> list[Product]:
        """Get all active products. In production: paginated SQL query."""
        if hasattr(self.repo, 'products'):
            return list(self.repo.products.values())
        return []

    async def _get_product_by_id(self, product_id: str) -> Optional[Product]:
        """Get product by ID string."""
        if hasattr(self.repo, 'products'):
            for p in self.repo.products.values():
                if str(p.id) == product_id or p.model_number == product_id:
                    return p
        return None

    def _to_recommendation(self, ps: ProductScore) -> ProductRecommendation:
        """Convert a ProductScore to a ProductRecommendation response."""
        return ProductRecommendation(
            product_id=str(ps.product.id),
            model_number=ps.product.model_number,
            brand='',  # Resolved in production from brand_id
            family='',  # Resolved in production from family_id
            score=round(ps.total_score, 4),
            hard_pass=ps.hard_pass,
            match_breakdown=ps.spec_matches,
            compliance=ps.compliance_results,
            notes='; '.join(ps.notes) if ps.notes else (
                '; '.join(ps.hard_fail_reasons) if not ps.hard_pass else None
            ),
        )


# ============================================================
# Helpers
# ============================================================

def _get_spec(product: Product, spec_name: str) -> Any:
    """Get a spec value from product fixed columns or dynamic specs."""
    # Check fixed columns first
    if hasattr(product, spec_name):
        val = getattr(product, spec_name, None)
        if val is not None:
            return val
    # Check dynamic specs
    return product.specs.get(spec_name)


def _delta_pct(a: float, b: float) -> Optional[float]:
    """Calculate percentage delta between two values."""
    if a == 0:
        return None
    return round((b - a) / abs(a) * 100, 1)


def normalize_val(val: Any) -> str:
    """Normalize a value for comparison."""
    if val is None:
        return ''
    return str(val).strip().lower().replace(' ', '_').replace('-', '_')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# Example / Integration Test
# ============================================================

async def _example():
    """Demonstrate the recommendation engine."""
    from ingestion_orchestrator import InMemoryRepository
    from models import SuperCategory

    repo = InMemoryRepository()

    # Seed brands/families
    repo.brands['ABS'] = Brand(code='ABS', name='American BioTech Supply')
    repo.brands['LABRepCo'] = Brand(code='LABRepCo', name='LABRepCo')
    for code, name, cat in [
        ('premier_lab_ref', 'Premier Lab Refrigerator', SuperCategory.REFRIGERATOR),
        ('pharmacy_vaccine_ref', 'Pharmacy Vaccine Refrigerator', SuperCategory.REFRIGERATOR),
        ('pharmacy_nsf_ref', 'Pharmacy NSF Refrigerator', SuperCategory.REFRIGERATOR),
        ('chromatography_ref', 'Chromatography Refrigerator', SuperCategory.REFRIGERATOR),
        ('flammable_storage_ref', 'Flammable Storage Refrigerator', SuperCategory.REFRIGERATOR),
        ('manual_defrost_freezer', 'Manual Defrost Freezer', SuperCategory.FREEZER),
    ]:
        repo.families[code] = ProductFamily(code=code, name=name, super_category=cat)

    # Create sample products
    products = [
        Product(
            model_number='ABT-HC-26S',
            brand_id=repo.brands['ABS'].id,
            family_id=repo.families['premier_lab_ref'].id,
            product_line='Premier',
            storage_capacity_cuft=26.0,
            temp_range_min_c=1.0, temp_range_max_c=10.0,
            door_count=1, door_type='solid',
            shelf_count=4, refrigerant='R290',
            voltage_v=115, amperage=3.0,
            product_weight_lbs=235.0,
            ext_width_in=28.375, ext_depth_in=36.75, ext_height_in=81.75,
            certifications=['ETL', 'C-ETL', 'UL471', 'Energy_Star'],
            specs={
                'uniformity_c': 1.4, 'stability_c': 1.3,
                'energy_kwh_day': 1.15, 'noise_dba': 41,
                'product_type': 'refrigerator',
                'controller_type': 'microprocessor',
                'defrost_type': 'cycle',
            },
        ),
        Product(
            model_number='ABT-HC-49S',
            brand_id=repo.brands['ABS'].id,
            family_id=repo.families['premier_lab_ref'].id,
            product_line='Premier',
            storage_capacity_cuft=49.0,
            temp_range_min_c=1.0, temp_range_max_c=10.0,
            door_count=2, door_type='solid',
            shelf_count=8, refrigerant='R290',
            voltage_v=115, amperage=4.5,
            product_weight_lbs=396.0,
            ext_width_in=56.0, ext_depth_in=36.75, ext_height_in=81.75,
            certifications=['ETL', 'C-ETL', 'UL471', 'Energy_Star'],
            specs={
                'uniformity_c': 1.6, 'stability_c': 1.5,
                'energy_kwh_day': 1.50, 'noise_dba': 44,
                'product_type': 'refrigerator',
                'controller_type': 'microprocessor',
                'defrost_type': 'cycle',
            },
        ),
        Product(
            model_number='PH-ABT-NSF-UCFS-0504',
            brand_id=repo.brands['ABS'].id,
            family_id=repo.families['pharmacy_nsf_ref'].id,
            product_line='Pharmacy NSF',
            storage_capacity_cuft=5.2,
            temp_range_min_c=2.0, temp_range_max_c=8.0,
            door_count=1, door_type='solid',
            shelf_count=2, refrigerant='R600a',
            voltage_v=115, amperage=1.5,
            product_weight_lbs=90.0,
            ext_width_in=23.75, ext_depth_in=24.0, ext_height_in=34.0,
            certifications=['ETL', 'C-ETL', 'NSF_ANSI_456', 'Energy_Star'],
            specs={
                'uniformity_c': 0.8, 'stability_c': 0.7,
                'energy_kwh_day': 0.65, 'noise_dba': 38,
                'product_type': 'refrigerator',
                'nsf_ansi_456_certified': True,
                'controller_type': 'touchscreen_microprocessor',
            },
        ),
        Product(
            model_number='ABT-HC-26G',
            brand_id=repo.brands['ABS'].id,
            family_id=repo.families['premier_lab_ref'].id,
            product_line='Premier',
            storage_capacity_cuft=26.0,
            temp_range_min_c=1.0, temp_range_max_c=10.0,
            door_count=1, door_type='glass',
            shelf_count=4, refrigerant='R290',
            voltage_v=115, amperage=3.1,
            product_weight_lbs=240.0,
            ext_width_in=28.375, ext_depth_in=36.75, ext_height_in=81.75,
            certifications=['ETL', 'C-ETL', 'UL471', 'Energy_Star'],
            specs={
                'uniformity_c': 1.5, 'stability_c': 1.4,
                'energy_kwh_day': 1.25, 'noise_dba': 42,
                'product_type': 'refrigerator',
                'controller_type': 'microprocessor',
                'defrost_type': 'cycle',
            },
        ),
    ]

    for p in products:
        repo.products[p.id] = p
        repo._model_index[p.model_number] = p.id

    engine = RecommendationEngine(repo)

    # --- Test 1: Vaccine storage recommendation ---
    print("=" * 60)
    print("TEST 1: Vaccine Storage Recommendation")
    print("=" * 60)

    resp = await engine.recommend(RecommendRequest(
        use_case='vaccine_storage',
        structured_specs={'storage_capacity_cuft': 5},
    ))

    print(f"Query ID: {resp.query_id}")
    print(f"Response time: {resp.response_time_ms}ms")
    print(f"\nDecision trace:")
    for t in resp.decision_trace:
        print(f"  [{t.step}] {t.detail}")

    print(f"\nRecommendations ({len(resp.products)}):")
    for r in resp.products:
        print(f"  {r.model_number}: score={r.score:.2%}, pass={r.hard_pass}")
        for m in r.match_breakdown:
            print(f"    {m.display_name}: {m.value_product} (score={m.score:.2f})")
        for c in r.compliance:
            print(f"    [{c.status}] {c.rule}: {c.details}")

    if resp.alternates:
        print(f"\nAlternates ({len(resp.alternates)}):")
        for r in resp.alternates:
            print(f"  {r.model_number}: score={r.score:.2%}, notes={r.notes}")

    if resp.clarifications_needed:
        print(f"\nClarifications needed:")
        for c in resp.clarifications_needed:
            print(f"  {c['message']}")

    # --- Test 2: Lab refrigerator with capacity requirement ---
    print("\n" + "=" * 60)
    print("TEST 2: Lab Refrigerator ~26 cu.ft.")
    print("=" * 60)

    resp2 = await engine.recommend(RecommendRequest(
        free_text='I need a lab refrigerator about 26 cubic feet with a solid door',
        structured_specs={
            'storage_capacity_cuft': 26,
            'door_type': 'solid',
        },
    ))

    print(f"\nRecommendations ({len(resp2.products)}):")
    for r in resp2.products:
        print(f"  {r.model_number}: score={r.score:.2%}")
        for m in r.match_breakdown:
            print(f"    {m.display_name}: req={m.value_required}, "
                  f"got={m.value_product}, score={m.score:.2f}")

    # --- Test 3: Product comparison ---
    print("\n" + "=" * 60)
    print("TEST 3: Compare ABT-HC-26S vs ABT-HC-26G")
    print("=" * 60)

    comp = await engine.compare(CompareRequest(
        product_ids=['ABT-HC-26S', 'ABT-HC-26G'],
        highlight_differences=True,
    ))

    print(f"Summary: {comp.summary}")
    print(f"\nDifferences:")
    for row in comp.specs_compared:
        print(f"  {row['display_name']}: {row['values']}")

    # --- Test 4: Equivalence detection ---
    print("\n" + "=" * 60)
    print("TEST 4: Find equivalents for ABT-HC-26S")
    print("=" * 60)

    ref = products[0]  # ABT-HC-26S
    equivs = await engine.find_equivalents(ref)
    print(f"Equivalents for {ref.model_number}:")
    for eq, sim in equivs:
        print(f"  {eq.model_number}: similarity={sim:.2%}")

    # --- Test 5: Undercounter constraint ---
    print("\n" + "=" * 60)
    print("TEST 5: Undercounter (max height 36\")")
    print("=" * 60)

    resp5 = await engine.recommend(RecommendRequest(
        use_case='undercounter',
        structured_specs={'max_height_in': 36},
    ))

    print(f"Recommendations ({len(resp5.products)}):")
    for r in resp5.products:
        print(f"  {r.model_number}: score={r.score:.2%}")

    if resp5.alternates:
        print(f"Alternates ({len(resp5.alternates)}):")
        for r in resp5.alternates:
            print(f"  {r.model_number}: {r.notes}")


if __name__ == '__main__':
    import asyncio
    asyncio.run(_example())
