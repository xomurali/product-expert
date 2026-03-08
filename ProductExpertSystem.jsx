import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  Search, Snowflake, FlaskConical, ShieldCheck, Zap, ChevronRight, X, Upload,
  CheckCircle, AlertTriangle, AlertCircle, Info, MessageSquare, ArrowLeftRight,
  LayoutDashboard, Package, ChevronDown, Star, Thermometer, Ruler, DoorOpen,
  FileText, Clock, Send, ExternalLink, Loader2, Filter, BarChart3, Eye, Check,
  XCircle, Edit3, RefreshCw, Layers, GitCompare, BadgeCheck, Activity, ChevronUp,
  Gauge, Weight, Volume2, Wrench, Bot, User, Sparkles, Box, CircleDot, Hash,
  TrendingUp, ArrowRight, Minus, Plus, RotateCcw
} from "lucide-react";

// ═══════════════════════════════════════════════════════
// CONFIG & CONSTANTS
// ═══════════════════════════════════════════════════════
const API = "http://localhost:8000";

const MOCK_PRODUCTS = [
  { model_number: "ABT-HC-UCBI-0420", brand: "ABS", family: "Undercounter", product_line: "Premier", storage_capacity_cuft: 4.2, temp_range_min_c: 1, temp_range_max_c: 10, door_count: 1, door_type: "solid", shelf_count: 2, refrigerant: "R-290", voltage_v: 115, amperage: 2.1, product_weight_lbs: 95, ext_width_in: 23.75, ext_depth_in: 24.5, ext_height_in: 34.5, certifications: ["Energy Star"], specs: { energy_kwh_day: 0.89, controller_type: "Microprocessor", display_type: "LED", defrost_type: "Auto", noise_dba: 42, warranty_general_years: 2, warranty_compressor_years: 5 } },
  { model_number: "ABT-HC-LP-47", brand: "ABS", family: "Laboratory", product_line: "Premier", storage_capacity_cuft: 47, temp_range_min_c: 1, temp_range_max_c: 10, door_count: 2, door_type: "glass", shelf_count: 8, refrigerant: "R-290", voltage_v: 115, amperage: 5.2, product_weight_lbs: 320, ext_width_in: 54, ext_depth_in: 32.5, ext_height_in: 84, certifications: ["Energy Star", "NSF/ANSI 456"], specs: { energy_kwh_day: 2.1, controller_type: "Microprocessor", display_type: "LED", defrost_type: "Auto-Cycle", noise_dba: 52, uniformity_c: 1.5, stability_c: 0.5, warranty_general_years: 2, warranty_compressor_years: 5 } },
  { model_number: "PH-ABT-HC-RFC1030G", brand: "ABS", family: "Pharmacy", product_line: "Pharmacy", storage_capacity_cuft: 10.5, temp_range_min_c: 2, temp_range_max_c: 8, door_count: 1, door_type: "glass", shelf_count: 4, refrigerant: "R-290", voltage_v: 115, amperage: 2.8, product_weight_lbs: 155, ext_width_in: 24, ext_depth_in: 26, ext_height_in: 62, certifications: ["NSF/ANSI 456", "FDA"], specs: { energy_kwh_day: 1.3, controller_type: "Digital PID", display_type: "Touchscreen", defrost_type: "Frost-Free", noise_dba: 45, uniformity_c: 0.8, stability_c: 0.3, warranty_general_years: 3, warranty_compressor_years: 5, access_control: "Key Lock + PIN" } },
  { model_number: "LRP-HC-RFC-2304G", brand: "LABRepCo", family: "Laboratory", product_line: "Futura Silver", storage_capacity_cuft: 23, temp_range_min_c: 1, temp_range_max_c: 10, door_count: 1, door_type: "glass", shelf_count: 5, refrigerant: "R-290", voltage_v: 115, amperage: 3.8, product_weight_lbs: 235, ext_width_in: 27.5, ext_depth_in: 31, ext_height_in: 78, certifications: ["Energy Star"], specs: { energy_kwh_day: 1.65, controller_type: "Microprocessor", display_type: "LED", defrost_type: "Auto-Cycle", noise_dba: 48, uniformity_c: 1.2, stability_c: 0.5, warranty_general_years: 2, warranty_compressor_years: 5 } },
  { model_number: "CP-HC-?"+ "?"+ "-16NSGA", brand: "Corepoint", family: "Vaccine", product_line: "NSF Vaccine", storage_capacity_cuft: 16, temp_range_min_c: 2, temp_range_max_c: 8, door_count: 1, door_type: "glass", shelf_count: 4, refrigerant: "R-290", voltage_v: 115, amperage: 3.0, product_weight_lbs: 185, ext_width_in: 25, ext_depth_in: 28, ext_height_in: 72, certifications: ["NSF/ANSI 456", "Energy Star", "CDC/VFC"], specs: { energy_kwh_day: 1.2, controller_type: "Digital PID", display_type: "Touchscreen LCD", defrost_type: "Frost-Free", noise_dba: 43, uniformity_c: 0.7, stability_c: 0.25, warranty_general_years: 3, warranty_compressor_years: 7, access_control: "Key Lock" } },
  { model_number: "ABT-HC-FFP-14", brand: "ABS", family: "Flammable", product_line: "Premier", storage_capacity_cuft: 14, temp_range_min_c: -25, temp_range_max_c: -15, door_count: 1, door_type: "solid", shelf_count: 3, refrigerant: "R-290", voltage_v: 115, amperage: 4.5, product_weight_lbs: 210, ext_width_in: 25, ext_depth_in: 27, ext_height_in: 68, certifications: ["NFPA 45"], specs: { energy_kwh_day: 2.8, controller_type: "Microprocessor", display_type: "LED", defrost_type: "Manual", noise_dba: 50, warranty_general_years: 2, warranty_compressor_years: 5, interior_lighting: "Spark-free" } },
  { model_number: "ABT-HC-MFP-23-TS", brand: "ABS", family: "Freezer", product_line: "TempLog", storage_capacity_cuft: 23, temp_range_min_c: -30, temp_range_max_c: -15, door_count: 1, door_type: "solid", shelf_count: 5, refrigerant: "R-290", voltage_v: 115, amperage: 5.0, product_weight_lbs: 260, ext_width_in: 27, ext_depth_in: 31, ext_height_in: 78, certifications: ["Energy Star"], specs: { energy_kwh_day: 3.2, controller_type: "Microprocessor w/ TempLog", display_type: "LCD", defrost_type: "Manual", noise_dba: 52, data_transfer: "USB", warranty_general_years: 2, warranty_compressor_years: 5 } },
  { model_number: "CBS-2105-PA", brand: "CBS/CryoSafe", family: "Cryogenic", product_line: "Cryogenic Dewar", storage_capacity_cuft: 5.8, temp_range_min_c: -196, temp_range_max_c: -150, door_count: 1, door_type: "solid", shelf_count: 6, refrigerant: "LN2", voltage_v: 0, amperage: 0, product_weight_lbs: 48, ext_width_in: 18, ext_depth_in: 18, ext_height_in: 32, certifications: [], specs: { insulation_type: "Vacuum", warranty_general_years: 1 } },
];

const USE_CASES = [
  { id: "vaccine_storage", label: "Vaccine Storage", icon: "💉", desc: "CDC/VFC compliant units" },
  { id: "pharmacy_general", label: "Pharmacy General", icon: "💊", desc: "NSF 456 certified" },
  { id: "laboratory_general", label: "Laboratory General", icon: "🔬", desc: "Research-grade cold storage" },
  { id: "chromatography", label: "Chromatography", icon: "📊", desc: "Column & sample storage" },
  { id: "blood_bank", label: "Blood Bank", icon: "🩸", desc: "Precise 1-6°C range" },
  { id: "flammable_storage", label: "Flammable Storage", icon: "🔥", desc: "NFPA 45 spark-free" },
  { id: "sample_freezing", label: "Sample Freezing", icon: "❄️", desc: "-20°C to -30°C units" },
  { id: "plasma_storage", label: "Plasma Storage", icon: "🧊", desc: "Ultra-low temperature" },
  { id: "undercounter", label: "Undercounter", icon: "📦", desc: "Space-saving compact" },
  { id: "cryogenic_storage", label: "Cryogenic Storage", icon: "🧪", desc: "LN2 dewars, -196°C" },
  { id: "energy_efficient", label: "Energy Efficient", icon: "⚡", desc: "Energy Star certified" },
];

const MOCK_CONFLICTS = [
  { id: 1, product_model: "ABT-HC-LP-47", spec_name: "storage_capacity_cuft", existing: "47", new_val: "49", severity: "medium", source_doc: "ABS_PDS_Rev_01.15.26.pdf", status: "pending" },
  { id: 2, product_model: "PH-ABT-HC-RFC1030G", spec_name: "temp_range_min_c", existing: "2", new_val: "1", severity: "high", source_doc: "Pharmacy_Spec_Update.pdf", status: "pending" },
  { id: 3, product_model: "LRP-HC-RFC-2304G", spec_name: "energy_kwh_day", existing: "1.65", new_val: "1.72", severity: "low", source_doc: "LABRepCo_Energy_Data.csv", status: "pending" },
];

const BRAND_PALETTE = {
  ABS: { bg: "#1e3a5f", fg: "#60a5fa", accent: "#3b82f6" },
  LABRepCo: { bg: "#1a3a2a", fg: "#6ee7b7", accent: "#10b981" },
  Corepoint: { bg: "#2d1f4e", fg: "#c4b5fd", accent: "#8b5cf6" },
  "°celsius": { bg: "#3b2f1a", fg: "#fcd34d", accent: "#f59e0b" },
  "CBS/CryoSafe": { bg: "#1a3340", fg: "#67e8f9", accent: "#06b6d4" },
};

const CERT_STYLES = {
  "NSF/ANSI 456": { bg: "rgba(34,197,94,0.12)", color: "#4ade80", border: "rgba(34,197,94,0.25)" },
  "Energy Star": { bg: "rgba(59,130,246,0.12)", color: "#60a5fa", border: "rgba(59,130,246,0.25)" },
  "FDA": { bg: "rgba(168,85,247,0.12)", color: "#c084fc", border: "rgba(168,85,247,0.25)" },
  "NFPA 45": { bg: "rgba(251,146,60,0.12)", color: "#fb923c", border: "rgba(251,146,60,0.25)" },
  "CDC/VFC": { bg: "rgba(45,212,191,0.12)", color: "#2dd4bf", border: "rgba(45,212,191,0.25)" },
};

const SEV = {
  low: { color: "#60a5fa", bg: "rgba(59,130,246,0.1)" },
  medium: { color: "#fbbf24", bg: "rgba(251,191,36,0.1)" },
  high: { color: "#fb923c", bg: "rgba(251,146,60,0.1)" },
  critical: { color: "#f87171", bg: "rgba(248,113,113,0.1)" },
};

// ═══════════════════════════════════════════════════════
// STYLE CONSTANTS
// ═══════════════════════════════════════════════════════
const FONT_LINK = "https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=DM+Sans:wght@400;500;600;700&display=swap";

const THEME = {
  bg: "#0a0e17",
  surface: "#111827",
  surfaceAlt: "#151d2e",
  border: "#1e293b",
  borderLight: "#334155",
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  textDim: "#64748b",
  accent: "#38bdf8",
  accentAlt: "#818cf8",
  success: "#34d399",
  warning: "#fbbf24",
  error: "#f87171",
};

// ═══════════════════════════════════════════════════════
// UTILITY COMPONENTS
// ═══════════════════════════════════════════════════════
function CertBadge({ cert }) {
  const s = CERT_STYLES[cert] || { bg: "rgba(100,116,139,0.12)", color: "#94a3b8", border: "rgba(100,116,139,0.25)" };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px",
      borderRadius: 6, fontSize: 11, fontWeight: 600, letterSpacing: "0.02em",
      background: s.bg, color: s.color, border: `1px solid ${s.border}`,
      fontFamily: "'JetBrains Mono', monospace",
    }}>{cert}</span>
  );
}

function ScoreBar({ score, label, size = "md" }) {
  const pct = Math.round(score * 100);
  const h = size === "sm" ? 4 : 6;
  const color = pct >= 85 ? THEME.success : pct >= 65 ? THEME.accent : pct >= 45 ? THEME.warning : THEME.error;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      {label && <span style={{ fontSize: 11, color: THEME.textDim, width: 52, fontFamily: "'DM Sans'" }}>{label}</span>}
      <div style={{ flex: 1, height: h, background: "rgba(30,41,59,0.8)", borderRadius: h, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct}%`, background: `linear-gradient(90deg, ${color}88, ${color})`, borderRadius: h, transition: "width 0.6s cubic-bezier(0.4,0,0.2,1)" }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono', monospace", color: THEME.textMuted, width: 32, textAlign: "right" }}>{pct}%</span>
    </div>
  );
}

function SeverityBadge({ severity }) {
  const s = SEV[severity] || SEV.low;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", padding: "2px 8px", borderRadius: 6,
      fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.05em",
      background: s.bg, color: s.color, fontFamily: "'JetBrains Mono', monospace",
    }}>{severity}</span>
  );
}

function IconBtn({ icon: Icon, active, onClick, label, count, style }) {
  return (
    <button onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 6, padding: "8px 14px",
      borderRadius: 8, border: "none", cursor: "pointer", fontSize: 13, fontWeight: 500,
      fontFamily: "'DM Sans'", transition: "all 0.2s",
      background: active ? "rgba(56,189,248,0.12)" : "transparent",
      color: active ? THEME.accent : THEME.textMuted,
      ...style,
    }}>
      <Icon size={15} />
      <span>{label}</span>
      {count !== undefined && (
        <span style={{
          padding: "1px 6px", borderRadius: 10, fontSize: 10, fontWeight: 700,
          background: active ? "rgba(56,189,248,0.2)" : "rgba(100,116,139,0.15)",
          color: active ? THEME.accent : THEME.textDim,
          fontFamily: "'JetBrains Mono', monospace",
        }}>{count}</span>
      )}
    </button>
  );
}

function EmptyState({ icon: Icon, title, subtitle }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "64px 24px", color: THEME.textDim }}>
      <Icon size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
      <p style={{ fontSize: 16, fontWeight: 600, color: THEME.textMuted, marginBottom: 4, fontFamily: "'DM Sans'" }}>{title}</p>
      <p style={{ fontSize: 13, fontFamily: "'DM Sans'" }}>{subtitle}</p>
    </div>
  );
}

// ═══════════════════════════════════════════════════════
// PRODUCT CARD
// ═══════════════════════════════════════════════════════
function ProductCard({ product, selected, onSelect, onDetail, comparing }) {
  const [hovered, setHovered] = useState(false);
  const bp = BRAND_PALETTE[product.brand] || BRAND_PALETTE.ABS;
  const score = useMemo(() => 0.55 + Math.random() * 0.44, [product.model_number]);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={() => onDetail(product)}
      style={{
        position: "relative", borderRadius: 12, overflow: "hidden", cursor: "pointer",
        background: selected ? `linear-gradient(135deg, ${bp.bg}, ${THEME.surface})` : THEME.surface,
        border: `1px solid ${selected ? bp.accent + "60" : hovered ? THEME.borderLight : THEME.border}`,
        transition: "all 0.25s cubic-bezier(0.4,0,0.2,1)",
        transform: hovered ? "translateY(-2px)" : "none",
        boxShadow: hovered ? `0 8px 32px rgba(0,0,0,0.3), 0 0 0 1px ${bp.accent}20` : "0 1px 3px rgba(0,0,0,0.2)",
      }}
    >
      {/* Brand accent line */}
      <div style={{ height: 2, background: `linear-gradient(90deg, ${bp.accent}, transparent)` }} />

      <div style={{ padding: 16 }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
              <div style={{ width: 8, height: 8, borderRadius: 4, background: bp.accent }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: bp.fg, fontFamily: "'JetBrains Mono', monospace" }}>{product.brand}</span>
              <span style={{ fontSize: 10, color: THEME.textDim }}>·</span>
              <span style={{ fontSize: 11, color: THEME.textDim }}>{product.family}</span>
            </div>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: THEME.text, fontFamily: "'JetBrains Mono', monospace", lineHeight: 1.3 }}>
              {product.model_number}
            </h3>
            {product.product_line && (
              <span style={{ fontSize: 10, color: THEME.textDim, fontFamily: "'DM Sans'" }}>{product.product_line}</span>
            )}
          </div>
          {comparing && (
            <button
              onClick={e => { e.stopPropagation(); onSelect(product); }}
              style={{
                width: 28, height: 28, borderRadius: 8, border: `1.5px solid ${selected ? bp.accent : THEME.borderLight}`,
                background: selected ? bp.accent : "transparent", display: "flex", alignItems: "center", justifyContent: "center",
                cursor: "pointer", transition: "all 0.2s", color: selected ? "#fff" : THEME.textDim,
              }}
            >
              {selected ? <Check size={14} /> : <Plus size={14} />}
            </button>
          )}
        </div>

        {/* Spec Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 12px", marginBottom: 12 }}>
          {[
            [Package, `${product.storage_capacity_cuft} cu.ft`],
            [Thermometer, `${product.temp_range_min_c}° — ${product.temp_range_max_c}°C`],
            [DoorOpen, `${product.door_count}× ${product.door_type}`],
            [Zap, product.voltage_v > 0 ? `${product.voltage_v}V / ${product.amperage}A` : "Passive"],
          ].map(([Icon, val], i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <Icon size={12} style={{ color: THEME.textDim, flexShrink: 0 }} />
              <span style={{ fontSize: 11, color: THEME.textMuted, fontFamily: "'DM Sans'", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{val}</span>
            </div>
          ))}
        </div>

        {/* Certs */}
        {product.certifications.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 10 }}>
            {product.certifications.map(c => <CertBadge key={c} cert={c} />)}
          </div>
        )}

        {/* Score */}
        <ScoreBar score={score} label="Match" size="sm" />
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════
// PRODUCT DETAIL PANEL
// ═══════════════════════════════════════════════════════
function ProductDetail({ product, onClose }) {
  if (!product) return null;
  const bp = BRAND_PALETTE[product.brand] || BRAND_PALETTE.ABS;
  const sections = [
    { title: "Capacity & Storage", icon: Package, items: [["Storage Capacity", `${product.storage_capacity_cuft} cu.ft`], ["Shelf Count", product.shelf_count], ["Door Count", product.door_count], ["Door Type", product.door_type]] },
    { title: "Temperature", icon: Thermometer, items: [["Range", `${product.temp_range_min_c}°C to ${product.temp_range_max_c}°C`], ["Uniformity", product.specs?.uniformity_c ? `±${product.specs.uniformity_c}°C` : "—"], ["Stability", product.specs?.stability_c ? `±${product.specs.stability_c}°C` : "—"]] },
    { title: "Dimensions & Weight", icon: Ruler, items: [["Width", `${product.ext_width_in}″`], ["Depth", `${product.ext_depth_in}″`], ["Height", `${product.ext_height_in}″`], ["Weight", `${product.product_weight_lbs} lbs`]] },
    { title: "Electrical", icon: Zap, items: [["Voltage", product.voltage_v > 0 ? `${product.voltage_v}V` : "N/A"], ["Amperage", product.amperage > 0 ? `${product.amperage}A` : "N/A"], ["Energy", product.specs?.energy_kwh_day ? `${product.specs.energy_kwh_day} kWh/day` : "—"]] },
    { title: "Performance & Control", icon: Gauge, items: [["Controller", product.specs?.controller_type || "—"], ["Display", product.specs?.display_type || "—"], ["Defrost", product.specs?.defrost_type || "—"], ["Noise", product.specs?.noise_dba ? `${product.specs.noise_dba} dBA` : "—"], ["Refrigerant", product.refrigerant]] },
    { title: "Warranty", icon: ShieldCheck, items: [["General", product.specs?.warranty_general_years ? `${product.specs.warranty_general_years} years` : "—"], ["Compressor", product.specs?.warranty_compressor_years ? `${product.specs.warranty_compressor_years} years` : "—"]] },
  ];

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", justifyContent: "flex-end" }} onClick={onClose}>
      <div style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)" }} />
      <div
        onClick={e => e.stopPropagation()}
        style={{
          position: "relative", width: "100%", maxWidth: 480, background: THEME.bg,
          borderLeft: `1px solid ${THEME.border}`, overflowY: "auto",
          boxShadow: "-8px 0 40px rgba(0,0,0,0.5)",
          animation: "slideIn 0.3s ease-out",
        }}
      >
        {/* Header */}
        <div style={{
          position: "sticky", top: 0, zIndex: 10, padding: "16px 20px",
          background: `linear-gradient(180deg, ${THEME.bg}, ${THEME.bg}ee)`,
          backdropFilter: "blur(12px)", borderBottom: `1px solid ${THEME.border}`,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <div style={{ width: 10, height: 10, borderRadius: 5, background: bp.accent }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: bp.fg, fontFamily: "'JetBrains Mono', monospace" }}>{product.brand}</span>
                <span style={{ fontSize: 12, color: THEME.textDim }}>/ {product.family}</span>
              </div>
              <h2 style={{ fontSize: 18, fontWeight: 700, color: THEME.text, fontFamily: "'JetBrains Mono', monospace" }}>{product.model_number}</h2>
              {product.product_line && <span style={{ fontSize: 12, color: THEME.textDim }}>{product.product_line} Series</span>}
            </div>
            <button onClick={onClose} style={{
              width: 32, height: 32, borderRadius: 8, border: `1px solid ${THEME.border}`,
              background: "transparent", cursor: "pointer", display: "flex", alignItems: "center",
              justifyContent: "center", color: THEME.textDim, transition: "all 0.2s",
            }}><X size={16} /></button>
          </div>
          {product.certifications.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 12 }}>
              {product.certifications.map(c => <CertBadge key={c} cert={c} />)}
            </div>
          )}
        </div>

        {/* Body */}
        <div style={{ padding: "12px 20px 24px" }}>
          {sections.map(sec => (
            <div key={sec.title} style={{
              marginBottom: 12, borderRadius: 10, border: `1px solid ${THEME.border}`,
              overflow: "hidden", background: THEME.surface,
            }}>
              <div style={{
                padding: "10px 14px", borderBottom: `1px solid ${THEME.border}`,
                display: "flex", alignItems: "center", gap: 8,
              }}>
                <sec.icon size={13} style={{ color: THEME.accent }} />
                <span style={{ fontSize: 11, fontWeight: 700, color: THEME.textMuted, textTransform: "uppercase", letterSpacing: "0.06em", fontFamily: "'JetBrains Mono', monospace" }}>{sec.title}</span>
              </div>
              {sec.items.map(([k, v], i) => (
                <div key={k} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "center",
                  padding: "8px 14px",
                  borderBottom: i < sec.items.length - 1 ? `1px solid ${THEME.border}44` : "none",
                }}>
                  <span style={{ fontSize: 13, color: THEME.textDim, fontFamily: "'DM Sans'" }}>{k}</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: THEME.text, fontFamily: "'JetBrains Mono', monospace" }}>{v}</span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════
// COMPARISON VIEW
// ═══════════════════════════════════════════════════════
function ComparisonView({ products, onRemove }) {
  if (products.length < 2) {
    return <EmptyState icon={GitCompare} title="Select 2–4 products to compare" subtitle="Use the Compare toggle in the Product Finder to pick products" />;
  }

  const specRows = [
    { group: "Capacity", rows: [
      ["Storage", p => `${p.storage_capacity_cuft} cu.ft`],
      ["Shelves", p => p.shelf_count],
      ["Door", p => `${p.door_count}× ${p.door_type}`],
    ]},
    { group: "Temperature", rows: [
      ["Range", p => `${p.temp_range_min_c}° — ${p.temp_range_max_c}°C`],
      ["Uniformity", p => p.specs?.uniformity_c ? `±${p.specs.uniformity_c}°C` : "—"],
      ["Stability", p => p.specs?.stability_c ? `±${p.specs.stability_c}°C` : "—"],
    ]},
    { group: "Dimensions", rows: [
      ["W × D × H", p => `${p.ext_width_in}″ × ${p.ext_depth_in}″ × ${p.ext_height_in}″`],
      ["Weight", p => `${p.product_weight_lbs} lbs`],
    ]},
    { group: "Electrical", rows: [
      ["Voltage", p => p.voltage_v > 0 ? `${p.voltage_v}V` : "N/A"],
      ["Amperage", p => p.amperage > 0 ? `${p.amperage}A` : "N/A"],
      ["Energy", p => p.specs?.energy_kwh_day ? `${p.specs.energy_kwh_day} kWh/day` : "—"],
    ]},
    { group: "Performance", rows: [
      ["Noise", p => p.specs?.noise_dba ? `${p.specs.noise_dba} dBA` : "—"],
      ["Refrigerant", p => p.refrigerant],
      ["Controller", p => p.specs?.controller_type || "—"],
      ["Display", p => p.specs?.display_type || "—"],
      ["Defrost", p => p.specs?.defrost_type || "—"],
    ]},
    { group: "Certifications", rows: [
      ["Certs", p => p.certifications.length > 0 ? p.certifications.join(", ") : "None"],
    ]},
    { group: "Warranty", rows: [
      ["General", p => p.specs?.warranty_general_years ? `${p.specs.warranty_general_years} yr` : "—"],
      ["Compressor", p => p.specs?.warranty_compressor_years ? `${p.specs.warranty_compressor_years} yr` : "—"],
    ]},
  ];

  const allSame = fn => { const vals = products.map(fn); return vals.every(v => v === vals[0]); };

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, fontFamily: "'DM Sans'" }}>
        <thead>
          <tr>
            <th style={{ width: 140, padding: 14, textAlign: "left", color: THEME.textDim, fontWeight: 500, borderBottom: `2px solid ${THEME.border}` }}>Specification</th>
            {products.map(p => {
              const bp = BRAND_PALETTE[p.brand] || BRAND_PALETTE.ABS;
              return (
                <th key={p.model_number} style={{ padding: 14, textAlign: "left", borderBottom: `2px solid ${bp.accent}40`, minWidth: 180 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: 4, background: bp.accent }} />
                    <div>
                      <div style={{ fontSize: 10, color: bp.fg, fontFamily: "'JetBrains Mono', monospace" }}>{p.brand}</div>
                      <div style={{ fontSize: 13, fontWeight: 700, color: THEME.text, fontFamily: "'JetBrains Mono', monospace" }}>{p.model_number}</div>
                    </div>
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {specRows.map(group => (
            <>
              <tr key={`g-${group.group}`}>
                <td colSpan={products.length + 1} style={{
                  padding: "10px 14px 6px", fontSize: 10, fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.08em", color: THEME.accent, fontFamily: "'JetBrains Mono', monospace",
                  borderBottom: `1px solid ${THEME.border}`,
                }}>{group.group}</td>
              </tr>
              {group.rows.map(([label, fn]) => {
                const same = allSame(fn);
                return (
                  <tr key={label} style={{ borderBottom: `1px solid ${THEME.border}44` }}>
                    <td style={{ padding: "8px 14px", color: THEME.textDim, fontWeight: 500 }}>{label}</td>
                    {products.map(p => (
                      <td key={p.model_number} style={{
                        padding: "8px 14px",
                        color: same ? THEME.textMuted : THEME.text,
                        fontWeight: same ? 400 : 600,
                        fontFamily: "'JetBrains Mono', monospace", fontSize: 12,
                      }}>
                        {!same && <span style={{ display: "inline-block", width: 5, height: 5, borderRadius: 3, background: THEME.warning, marginRight: 6, verticalAlign: "middle" }} />}
                        {fn(p)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ═══════════════════════════════════════════════════════
// Q&A PANEL
// ═══════════════════════════════════════════════════════
function QAPanel() {
  const [msgs, setMsgs] = useState([
    {
      role: "assistant",
      text: "Welcome to the Product Expert. I can help you find laboratory refrigerators, pharmacy units, freezers, and cryogenic storage — just ask about specs, compare models, or describe your use case.",
      meta: null,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const q = input.trim();
    setInput("");
    setMsgs(prev => [...prev, { role: "user", text: q }]);
    setLoading(true);
    try {
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": "dev-key-001" },
        body: JSON.stringify({ question: q }),
      });
      if (!res.ok) throw new Error("API error");
      const data = await res.json();
      setMsgs(prev => [...prev, { role: "assistant", text: data.answer, meta: data }]);
    } catch {
      const mockResp = `Based on our product database, I found some relevant information for your query about "${q}".\n\nThe ABS Premier and LABRepCo Futura Silver lines are strong candidates. Both offer excellent temperature uniformity (±0.5–1.5°C) and are Energy Star certified.\n\nKey factors to consider include your temperature range requirements, storage capacity needs, certification requirements (NSF/ANSI 456 for pharmacy/vaccine applications), and available space dimensions.\n\nWould you like me to compare specific models or narrow down by use case?`;
      setMsgs(prev => [...prev, {
        role: "assistant", text: mockResp,
        meta: { intent: "recommend", grounding_score: 0.85, sources: ["ABS Product Data Sheet Rev 01.15.26", "LABRepCo Futura Silver Specifications"] },
      }]);
    }
    setLoading(false);
  };

  const groundingColor = s => s >= 0.8 ? THEME.success : s >= 0.5 ? THEME.warning : THEME.error;

  const suggestions = [
    "What vaccine fridges meet NSF 456?",
    "Compare ABS vs LABRepCo 23 cu.ft",
    "Best freezer for plasma storage?",
    "Which units fit under a counter?",
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "'DM Sans'" }}>
      {/* Messages */}
      <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
        {msgs.map((m, i) => (
          <div key={i} style={{
            display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start",
            marginBottom: 12,
          }}>
            {m.role === "assistant" && (
              <div style={{
                width: 28, height: 28, borderRadius: 8, background: `linear-gradient(135deg, ${THEME.accent}, ${THEME.accentAlt})`,
                display: "flex", alignItems: "center", justifyContent: "center", marginRight: 10, flexShrink: 0, marginTop: 2,
              }}>
                <Sparkles size={14} style={{ color: "#fff" }} />
              </div>
            )}
            <div style={{
              maxWidth: 600, borderRadius: 14, padding: "12px 16px",
              background: m.role === "user"
                ? `linear-gradient(135deg, ${THEME.accent}20, ${THEME.accentAlt}20)`
                : THEME.surface,
              border: `1px solid ${m.role === "user" ? THEME.accent + "30" : THEME.border}`,
              color: THEME.text,
            }}>
              <p style={{ fontSize: 13, lineHeight: 1.65, whiteSpace: "pre-wrap", margin: 0 }}>{m.text}</p>
              {m.meta && (
                <div style={{ marginTop: 10, paddingTop: 8, borderTop: `1px solid ${THEME.border}` }}>
                  {m.meta.grounding_score !== undefined && (
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <ShieldCheck size={12} style={{ color: groundingColor(m.meta.grounding_score) }} />
                      <span style={{ fontSize: 11, color: groundingColor(m.meta.grounding_score), fontFamily: "'JetBrains Mono', monospace" }}>
                        Grounding: {Math.round(m.meta.grounding_score * 100)}%
                      </span>
                    </div>
                  )}
                  {m.meta.intent && (
                    <div style={{ fontSize: 11, color: THEME.textDim, marginBottom: 2 }}>Intent: <span style={{ color: THEME.textMuted }}>{m.meta.intent}</span></div>
                  )}
                  {m.meta.sources?.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 4 }}>
                      {m.meta.sources.map((s, j) => (
                        <span key={j} style={{
                          display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px",
                          borderRadius: 6, fontSize: 10, background: "rgba(56,189,248,0.08)",
                          color: THEME.accent, fontFamily: "'JetBrains Mono', monospace",
                        }}>
                          <FileText size={9} />{s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
            {m.role === "user" && (
              <div style={{
                width: 28, height: 28, borderRadius: 8, background: THEME.surfaceAlt,
                border: `1px solid ${THEME.border}`,
                display: "flex", alignItems: "center", justifyContent: "center", marginLeft: 10, flexShrink: 0, marginTop: 2,
              }}>
                <User size={14} style={{ color: THEME.textDim }} />
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <div style={{
              width: 28, height: 28, borderRadius: 8, background: `linear-gradient(135deg, ${THEME.accent}, ${THEME.accentAlt})`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <Sparkles size={14} style={{ color: "#fff" }} />
            </div>
            <div style={{ padding: "12px 16px", borderRadius: 14, background: THEME.surface, border: `1px solid ${THEME.border}` }}>
              <div style={{ display: "flex", gap: 4 }}>
                {[0, 1, 2].map(i => (
                  <div key={i} style={{
                    width: 6, height: 6, borderRadius: 3, background: THEME.accent,
                    animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
                  }} />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <div style={{ borderTop: `1px solid ${THEME.border}`, padding: 16, background: THEME.bg }}>
        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && send()}
            placeholder="Ask about products, specs, comparisons..."
            style={{
              flex: 1, padding: "10px 14px", borderRadius: 10, border: `1px solid ${THEME.border}`,
              background: THEME.surface, color: THEME.text, fontSize: 13, fontFamily: "'DM Sans'",
              outline: "none", transition: "border-color 0.2s",
            }}
            onFocus={e => e.target.style.borderColor = THEME.accent}
            onBlur={e => e.target.style.borderColor = THEME.border}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            style={{
              padding: "10px 16px", borderRadius: 10, border: "none", cursor: loading || !input.trim() ? "default" : "pointer",
              background: loading || !input.trim() ? THEME.surfaceAlt : `linear-gradient(135deg, ${THEME.accent}, ${THEME.accentAlt})`,
              color: loading || !input.trim() ? THEME.textDim : "#fff",
              display: "flex", alignItems: "center", justifyContent: "center", transition: "all 0.2s",
            }}
          >
            <Send size={16} />
          </button>
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {suggestions.map(q => (
            <button
              key={q}
              onClick={() => { setInput(q); inputRef.current?.focus(); }}
              style={{
                padding: "4px 10px", borderRadius: 8, border: `1px solid ${THEME.border}`,
                background: "transparent", color: THEME.textDim, fontSize: 11, cursor: "pointer",
                fontFamily: "'DM Sans'", transition: "all 0.2s", whiteSpace: "nowrap",
              }}
              onMouseEnter={e => { e.target.style.borderColor = THEME.accent; e.target.style.color = THEME.accent; }}
              onMouseLeave={e => { e.target.style.borderColor = THEME.border; e.target.style.color = THEME.textDim; }}
            >{q}</button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════
// INGESTION DASHBOARD
// ═══════════════════════════════════════════════════════
function IngestionDashboard() {
  const [files, setFiles] = useState([
    { name: "ABS_Premier_PDS_Rev_01.15.26.pdf", status: "complete", products: 12, conflicts: 1, time: "2.3s" },
    { name: "LABRepCo_Futura_Silver_Specs.pdf", status: "complete", products: 8, conflicts: 0, time: "1.8s" },
    { name: "Corepoint_NSF_Vaccine_Line.pdf", status: "processing", products: null, conflicts: null, time: null },
  ]);
  const [conflicts, setConflicts] = useState(MOCK_CONFLICTS);
  const [dragging, setDragging] = useState(false);
  const [overrideId, setOverrideId] = useState(null);
  const [overrideVal, setOverrideVal] = useState("");

  const handleDrop = e => {
    e.preventDefault();
    setDragging(false);
    const newFiles = Array.from(e.dataTransfer?.files || []).map(f => ({
      name: f.name, status: "queued", products: null, conflicts: null, time: null,
    }));
    setFiles(prev => [...prev, ...newFiles]);
    setTimeout(() => {
      setFiles(prev => prev.map(f => f.status === "queued" ? { ...f, status: "processing" } : f));
      setTimeout(() => {
        setFiles(prev => prev.map(f => f.status === "processing" ? {
          ...f, status: "complete",
          products: Math.floor(Math.random() * 15) + 1,
          conflicts: Math.floor(Math.random() * 3),
          time: `${(Math.random() * 3 + 0.5).toFixed(1)}s`,
        } : f));
      }, 2000);
    }, 500);
  };

  const resolve = (id, action) => {
    setConflicts(prev => prev.filter(c => c.id !== id));
    setOverrideId(null);
    setOverrideVal("");
  };

  const statusIcon = s => {
    if (s === "complete") return <CheckCircle size={14} style={{ color: THEME.success }} />;
    if (s === "processing") return <Loader2 size={14} style={{ color: THEME.accent, animation: "spin 1s linear infinite" }} />;
    return <Clock size={14} style={{ color: THEME.textDim }} />;
  };

  return (
    <div style={{ padding: "24px 28px", overflowY: "auto", height: "100%", fontFamily: "'DM Sans'" }}>
      {/* Upload Zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        style={{
          border: `2px dashed ${dragging ? THEME.accent : THEME.border}`,
          borderRadius: 14, padding: "40px 24px", textAlign: "center",
          background: dragging ? `${THEME.accent}08` : "transparent",
          transition: "all 0.3s", marginBottom: 24, cursor: "pointer",
        }}
      >
        <Upload size={36} style={{ margin: "0 auto 12px", color: dragging ? THEME.accent : THEME.textDim }} />
        <p style={{ fontSize: 14, fontWeight: 600, color: THEME.text, marginBottom: 4 }}>Drop product documents here</p>
        <p style={{ fontSize: 12, color: THEME.textDim }}>PDF, TXT, Markdown — Product Data Sheets, Cut Sheets, Feature Lists</p>
      </div>

      {/* Processing Queue */}
      <div style={{ marginBottom: 24 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: THEME.textMuted, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
          <FileText size={14} style={{ color: THEME.accent }} /> Processing Queue
        </h3>
        <div style={{ borderRadius: 12, border: `1px solid ${THEME.border}`, overflow: "hidden" }}>
          {files.map((f, i) => (
            <div key={i} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "10px 16px", borderBottom: i < files.length - 1 ? `1px solid ${THEME.border}44` : "none",
              background: i % 2 === 0 ? THEME.surface : "transparent",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                {statusIcon(f.status)}
                <span style={{ fontSize: 13, color: THEME.text, fontFamily: "'JetBrains Mono', monospace" }}>{f.name}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 11, color: THEME.textDim }}>
                {f.products !== null && <span>{f.products} products</span>}
                {f.conflicts !== null && f.conflicts > 0 && <span style={{ color: THEME.warning }}>{f.conflicts} conflicts</span>}
                {f.time && <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>{f.time}</span>}
                <span style={{
                  padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 700,
                  textTransform: "uppercase", letterSpacing: "0.04em",
                  fontFamily: "'JetBrains Mono', monospace",
                  background: f.status === "complete" ? "rgba(52,211,153,0.1)" : f.status === "processing" ? "rgba(56,189,248,0.1)" : "rgba(100,116,139,0.1)",
                  color: f.status === "complete" ? THEME.success : f.status === "processing" ? THEME.accent : THEME.textDim,
                }}>{f.status}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Conflicts */}
      <div>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: THEME.textMuted, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
          <AlertTriangle size={14} style={{ color: THEME.warning }} /> Spec Conflicts
          <span style={{ fontSize: 11, fontWeight: 400, color: THEME.textDim }}>({conflicts.length} pending)</span>
        </h3>
        {conflicts.length === 0 ? (
          <div style={{ textAlign: "center", padding: "32px 0", color: THEME.textDim, fontSize: 13 }}>No pending conflicts</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {conflicts.map(c => (
              <div key={c.id} style={{
                borderRadius: 12, border: `1px solid ${THEME.border}`, background: THEME.surface, padding: 16,
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                      <span style={{ fontSize: 14, fontWeight: 700, color: THEME.text, fontFamily: "'JetBrains Mono', monospace" }}>{c.product_model}</span>
                      <SeverityBadge severity={c.severity} />
                    </div>
                    <p style={{ fontSize: 12, color: THEME.textMuted, marginBottom: 2, fontFamily: "'JetBrains Mono', monospace" }}>
                      {c.spec_name}:&nbsp;
                      <span style={{ color: THEME.error, textDecoration: "line-through" }}>{c.existing}</span>
                      &nbsp;→&nbsp;
                      <span style={{ color: THEME.success }}>{c.new_val}</span>
                    </p>
                    <p style={{ fontSize: 11, color: THEME.textDim }}>Source: {c.source_doc}</p>
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    {[
                      { label: "Keep", action: "keep", bg: THEME.surfaceAlt, color: THEME.textMuted, border: THEME.border },
                      { label: "Accept", action: "accept", bg: "rgba(52,211,153,0.1)", color: THEME.success, border: "rgba(52,211,153,0.2)" },
                      { label: "Override", action: "override", bg: "rgba(56,189,248,0.1)", color: THEME.accent, border: "rgba(56,189,248,0.2)", isOverride: true },
                    ].map(btn => (
                      <button key={btn.action} onClick={() => {
                        if (btn.isOverride) { setOverrideId(overrideId === c.id ? null : c.id); return; }
                        resolve(c.id, btn.action);
                      }} style={{
                        padding: "5px 12px", borderRadius: 8, border: `1px solid ${btn.border}`,
                        background: btn.bg, color: btn.color, fontSize: 11, fontWeight: 600,
                        cursor: "pointer", fontFamily: "'DM Sans'", transition: "all 0.2s",
                      }}>{btn.label}</button>
                    ))}
                  </div>
                </div>
                {overrideId === c.id && (
                  <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
                    <input
                      value={overrideVal}
                      onChange={e => setOverrideVal(e.target.value)}
                      placeholder="Enter override value..."
                      style={{
                        flex: 1, padding: "6px 10px", borderRadius: 8, border: `1px solid ${THEME.border}`,
                        background: THEME.bg, color: THEME.text, fontSize: 12, fontFamily: "'JetBrains Mono', monospace",
                        outline: "none",
                      }}
                    />
                    <button onClick={() => resolve(c.id, "override")} style={{
                      padding: "6px 14px", borderRadius: 8, border: "none",
                      background: THEME.accent, color: "#fff", fontSize: 11, fontWeight: 600,
                      cursor: "pointer", fontFamily: "'DM Sans'",
                    }}>Apply</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════
export default function App() {
  const [tab, setTab] = useState("finder");
  const [products] = useState(MOCK_PRODUCTS);
  const [filtered, setFiltered] = useState(MOCK_PRODUCTS);
  const [detail, setDetail] = useState(null);
  const [compareList, setCompareList] = useState([]);
  const [comparing, setComparing] = useState(false);
  const [useCase, setUseCase] = useState("");
  const [searchText, setSearchText] = useState("");
  const [filters, setFilters] = useState({ capacity_min: 0, capacity_max: 200, door_type: "", voltage: "", certs: [] });
  const [showFilters, setShowFilters] = useState(false);
  const [apiStatus, setApiStatus] = useState("mock");

  // Check API health on mount
  useEffect(() => {
    fetch(`${API}/health`).then(r => r.ok ? setApiStatus("live") : setApiStatus("mock")).catch(() => setApiStatus("mock"));
  }, []);

  const applyFilters = useCallback(() => {
    let res = products;
    if (useCase) {
      const kw = useCase.toLowerCase();
      if (kw.includes("vaccine") || kw.includes("pharmacy")) res = res.filter(p => p.certifications.some(c => c.includes("NSF") || c.includes("FDA") || c.includes("CDC")));
      if (kw.includes("flammable")) res = res.filter(p => p.certifications.includes("NFPA 45"));
      if (kw.includes("cryogenic")) res = res.filter(p => p.temp_range_min_c <= -150);
      if (kw.includes("undercounter")) res = res.filter(p => p.ext_height_in < 40);
      if (kw.includes("freezing") || kw.includes("plasma")) res = res.filter(p => p.temp_range_min_c <= -15);
      if (kw.includes("energy")) res = res.filter(p => p.certifications.includes("Energy Star"));
      if (kw.includes("blood")) res = res.filter(p => p.temp_range_min_c >= 1 && p.temp_range_max_c <= 10);
      if (kw.includes("laboratory")) res = res.filter(p => p.family === "Laboratory" || p.storage_capacity_cuft >= 10);
      if (kw.includes("chromatography")) res = res.filter(p => p.temp_range_min_c >= 1 && p.temp_range_max_c <= 10);
    }
    if (searchText) {
      const q = searchText.toLowerCase();
      res = res.filter(p =>
        p.model_number.toLowerCase().includes(q) ||
        p.brand.toLowerCase().includes(q) ||
        p.family.toLowerCase().includes(q) ||
        p.product_line.toLowerCase().includes(q)
      );
    }
    if (filters.capacity_min > 0) res = res.filter(p => p.storage_capacity_cuft >= filters.capacity_min);
    if (filters.capacity_max < 200) res = res.filter(p => p.storage_capacity_cuft <= filters.capacity_max);
    if (filters.door_type) res = res.filter(p => p.door_type === filters.door_type);
    if (filters.voltage) res = res.filter(p => p.voltage_v === parseInt(filters.voltage));
    if (filters.certs.length > 0) res = res.filter(p => filters.certs.every(c => p.certifications.includes(c)));
    setFiltered(res);
  }, [products, useCase, searchText, filters]);

  useEffect(() => { applyFilters(); }, [applyFilters]);

  const toggleCompare = p => {
    setCompareList(prev =>
      prev.find(x => x.model_number === p.model_number)
        ? prev.filter(x => x.model_number !== p.model_number)
        : prev.length < 4 ? [...prev, p] : prev
    );
  };

  const toggleCert = c => {
    setFilters(prev => ({
      ...prev,
      certs: prev.certs.includes(c) ? prev.certs.filter(x => x !== c) : [...prev.certs, c],
    }));
  };

  return (
    <>
      {/* Font import */}
      <link href={FONT_LINK} rel="stylesheet" />
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 0.3; transform: scale(0.8); } 50% { opacity: 1; transform: scale(1); } }
        @keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${THEME.border}; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: ${THEME.borderLight}; }
        input::placeholder { color: ${THEME.textDim}; }
        select { cursor: pointer; }
        select option { background: ${THEME.surface}; color: ${THEME.text}; }
      `}</style>

      <div style={{
        minHeight: "100vh", background: THEME.bg, color: THEME.text,
        fontFamily: "'DM Sans', sans-serif", display: "flex", flexDirection: "column",
      }}>
        {/* ── HEADER ── */}
        <header style={{
          borderBottom: `1px solid ${THEME.border}`, background: `${THEME.bg}f0`,
          backdropFilter: "blur(12px)", position: "sticky", top: 0, zIndex: 50,
        }}>
          <div style={{
            maxWidth: 1400, margin: "0 auto", padding: "0 20px",
            display: "flex", alignItems: "center", justifyContent: "space-between", height: 56,
          }}>
            {/* Logo */}
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{
                width: 34, height: 34, borderRadius: 10,
                background: `linear-gradient(135deg, ${THEME.accent}, #6366f1)`,
                display: "flex", alignItems: "center", justifyContent: "center",
                boxShadow: `0 2px 12px ${THEME.accent}40`,
              }}>
                <Snowflake size={18} style={{ color: "#fff" }} />
              </div>
              <div>
                <h1 style={{ fontSize: 15, fontWeight: 700, letterSpacing: "-0.02em", lineHeight: 1.2, fontFamily: "'JetBrains Mono', monospace" }}>
                  Product Expert
                </h1>
                <span style={{ fontSize: 10, color: THEME.textDim, fontFamily: "'DM Sans'" }}>Horizon Scientific</span>
              </div>
            </div>

            {/* Nav Tabs */}
            <div style={{
              display: "flex", alignItems: "center", gap: 2,
              background: THEME.surface, borderRadius: 10, padding: 3,
              border: `1px solid ${THEME.border}`,
            }}>
              <IconBtn active={tab === "finder"} onClick={() => setTab("finder")} icon={Search} label="Finder" count={filtered.length} />
              <IconBtn active={tab === "compare"} onClick={() => setTab("compare")} icon={GitCompare} label="Compare" count={compareList.length} />
              <IconBtn active={tab === "qa"} onClick={() => setTab("qa")} icon={MessageSquare} label="Ask" />
              <IconBtn active={tab === "ingest"} onClick={() => setTab("ingest")} icon={LayoutDashboard} label="Ingest" />
            </div>

            {/* Status */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, color: THEME.textDim }}>
              <div style={{
                width: 6, height: 6, borderRadius: 3,
                background: apiStatus === "live" ? THEME.success : THEME.warning,
                boxShadow: apiStatus === "live" ? `0 0 6px ${THEME.success}` : `0 0 6px ${THEME.warning}`,
              }} />
              <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {apiStatus === "live" ? "API Connected" : "Mock Data"}
              </span>
              <span style={{ color: THEME.textDim }}>·</span>
              <span>{products.length} products</span>
            </div>
          </div>
        </header>

        {/* ── CONTENT ── */}
        <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* FINDER TAB */}
          {tab === "finder" && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
              {/* Search Area */}
              <div style={{ borderBottom: `1px solid ${THEME.border}`, padding: "14px 20px", background: THEME.surface + "80" }}>
                <div style={{ maxWidth: 1400, margin: "0 auto" }}>
                  <div style={{ display: "flex", gap: 10, marginBottom: showFilters ? 12 : 0 }}>
                    {/* Search Input */}
                    <div style={{ flex: 1, position: "relative" }}>
                      <Search size={15} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: THEME.textDim }} />
                      <input
                        value={searchText}
                        onChange={e => setSearchText(e.target.value)}
                        placeholder="Search by model, brand, or keyword..."
                        style={{
                          width: "100%", padding: "9px 14px 9px 36px", borderRadius: 10,
                          border: `1px solid ${THEME.border}`, background: THEME.bg,
                          color: THEME.text, fontSize: 13, fontFamily: "'DM Sans'", outline: "none",
                          transition: "border-color 0.2s",
                        }}
                        onFocus={e => e.target.style.borderColor = THEME.accent}
                        onBlur={e => e.target.style.borderColor = THEME.border}
                      />
                    </div>

                    {/* Use Case Select */}
                    <select
                      value={useCase}
                      onChange={e => setUseCase(e.target.value)}
                      style={{
                        padding: "9px 14px", borderRadius: 10, border: `1px solid ${THEME.border}`,
                        background: THEME.bg, color: THEME.text, fontSize: 13, fontFamily: "'DM Sans'",
                        outline: "none", minWidth: 180, appearance: "none",
                      }}
                    >
                      <option value="">All Use Cases</option>
                      {USE_CASES.map(u => <option key={u.id} value={u.id}>{u.icon} {u.label}</option>)}
                    </select>

                    {/* Filter Toggle */}
                    <button
                      onClick={() => setShowFilters(!showFilters)}
                      style={{
                        display: "flex", alignItems: "center", gap: 6, padding: "9px 14px", borderRadius: 10,
                        border: `1px solid ${showFilters ? THEME.accent + "50" : THEME.border}`,
                        background: showFilters ? `${THEME.accent}10` : THEME.bg,
                        color: showFilters ? THEME.accent : THEME.textMuted,
                        fontSize: 13, fontFamily: "'DM Sans'", cursor: "pointer", transition: "all 0.2s",
                      }}
                    >
                      <Filter size={14} />
                      {showFilters ? "Hide Filters" : "Filters"}
                    </button>

                    {/* Compare Toggle */}
                    <button
                      onClick={() => { setComparing(!comparing); if (comparing) setCompareList([]); }}
                      style={{
                        display: "flex", alignItems: "center", gap: 6, padding: "9px 14px", borderRadius: 10,
                        border: `1px solid ${comparing ? THEME.accentAlt + "50" : THEME.border}`,
                        background: comparing ? `${THEME.accentAlt}10` : THEME.bg,
                        color: comparing ? THEME.accentAlt : THEME.textMuted,
                        fontSize: 13, fontFamily: "'DM Sans'", cursor: "pointer", transition: "all 0.2s",
                      }}
                    >
                      <ArrowLeftRight size={14} />
                      {comparing ? `Compare (${compareList.length})` : "Compare"}
                    </button>
                  </div>

                  {/* Expanded Filters */}
                  {showFilters && (
                    <div style={{
                      display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-end",
                      padding: 16, borderRadius: 10, background: THEME.bg, border: `1px solid ${THEME.border}`,
                      animation: "fadeIn 0.2s ease-out",
                    }}>
                      <div>
                        <label style={{ display: "block", fontSize: 11, color: THEME.textDim, marginBottom: 4, fontFamily: "'JetBrains Mono', monospace" }}>Capacity (cu.ft)</label>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <input type="number" value={filters.capacity_min} onChange={e => setFilters(p => ({ ...p, capacity_min: +e.target.value }))}
                            style={{ width: 60, padding: "6px 8px", borderRadius: 8, border: `1px solid ${THEME.border}`, background: THEME.surface, color: THEME.text, fontSize: 12, fontFamily: "'JetBrains Mono', monospace", outline: "none" }} />
                          <span style={{ color: THEME.textDim, fontSize: 11 }}>to</span>
                          <input type="number" value={filters.capacity_max} onChange={e => setFilters(p => ({ ...p, capacity_max: +e.target.value }))}
                            style={{ width: 60, padding: "6px 8px", borderRadius: 8, border: `1px solid ${THEME.border}`, background: THEME.surface, color: THEME.text, fontSize: 12, fontFamily: "'JetBrains Mono', monospace", outline: "none" }} />
                        </div>
                      </div>
                      <div>
                        <label style={{ display: "block", fontSize: 11, color: THEME.textDim, marginBottom: 4, fontFamily: "'JetBrains Mono', monospace" }}>Door Type</label>
                        <select value={filters.door_type} onChange={e => setFilters(p => ({ ...p, door_type: e.target.value }))}
                          style={{ padding: "6px 10px", borderRadius: 8, border: `1px solid ${THEME.border}`, background: THEME.surface, color: THEME.text, fontSize: 12, outline: "none", fontFamily: "'DM Sans'" }}>
                          <option value="">Any</option><option value="solid">Solid</option><option value="glass">Glass</option>
                        </select>
                      </div>
                      <div>
                        <label style={{ display: "block", fontSize: 11, color: THEME.textDim, marginBottom: 4, fontFamily: "'JetBrains Mono', monospace" }}>Voltage</label>
                        <select value={filters.voltage} onChange={e => setFilters(p => ({ ...p, voltage: e.target.value }))}
                          style={{ padding: "6px 10px", borderRadius: 8, border: `1px solid ${THEME.border}`, background: THEME.surface, color: THEME.text, fontSize: 12, outline: "none", fontFamily: "'DM Sans'" }}>
                          <option value="">Any</option><option value="115">115V</option><option value="220">220V</option>
                        </select>
                      </div>
                      <div>
                        <label style={{ display: "block", fontSize: 11, color: THEME.textDim, marginBottom: 4, fontFamily: "'JetBrains Mono', monospace" }}>Certifications</label>
                        <div style={{ display: "flex", gap: 6 }}>
                          {["NSF/ANSI 456", "Energy Star", "FDA", "NFPA 45"].map(c => (
                            <button key={c} onClick={() => toggleCert(c)} style={{
                              padding: "5px 10px", borderRadius: 8, fontSize: 11, fontWeight: 600,
                              border: `1px solid ${filters.certs.includes(c) ? THEME.accent + "50" : THEME.border}`,
                              background: filters.certs.includes(c) ? `${THEME.accent}12` : "transparent",
                              color: filters.certs.includes(c) ? THEME.accent : THEME.textDim,
                              cursor: "pointer", transition: "all 0.2s", fontFamily: "'JetBrains Mono', monospace",
                            }}>{c}</button>
                          ))}
                        </div>
                      </div>
                      {(filters.capacity_min > 0 || filters.capacity_max < 200 || filters.door_type || filters.voltage || filters.certs.length > 0) && (
                        <button onClick={() => setFilters({ capacity_min: 0, capacity_max: 200, door_type: "", voltage: "", certs: [] })}
                          style={{
                            display: "flex", alignItems: "center", gap: 4, padding: "6px 10px", borderRadius: 8,
                            border: "none", background: "rgba(248,113,113,0.1)", color: THEME.error,
                            fontSize: 11, fontWeight: 600, cursor: "pointer", fontFamily: "'DM Sans'",
                          }}><RotateCcw size={11} /> Reset</button>
                      )}
                    </div>
                  )}

                  {/* Compare bar */}
                  {comparing && compareList.length >= 2 && (
                    <button onClick={() => setTab("compare")} style={{
                      width: "100%", padding: "10px 0", borderRadius: 10, border: "none",
                      background: `linear-gradient(135deg, ${THEME.accentAlt}, ${THEME.accent})`,
                      color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer", marginTop: 10,
                      fontFamily: "'DM Sans'", transition: "all 0.2s",
                    }}>
                      Compare {compareList.length} Products →
                    </button>
                  )}
                </div>
              </div>

              {/* Results Grid */}
              <div style={{ flex: 1, overflowY: "auto", padding: 20 }}>
                <div style={{ maxWidth: 1400, margin: "0 auto" }}>
                  {filtered.length === 0 ? (
                    <EmptyState icon={Package} title="No products match your criteria" subtitle="Try adjusting your filters or search terms" />
                  ) : (
                    <div style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                      gap: 12,
                    }}>
                      {filtered.map(p => (
                        <ProductCard
                          key={p.model_number}
                          product={p}
                          selected={compareList.some(x => x.model_number === p.model_number)}
                          onSelect={toggleCompare}
                          onDetail={setDetail}
                          comparing={comparing}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* COMPARE TAB */}
          {tab === "compare" && (
            <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
              <div style={{ maxWidth: 1400, margin: "0 auto" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                  <h2 style={{ fontSize: 18, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>Side-by-Side Comparison</h2>
                  {compareList.length > 0 && (
                    <button onClick={() => setCompareList([])} style={{
                      display: "flex", alignItems: "center", gap: 4, padding: "6px 12px", borderRadius: 8,
                      border: `1px solid ${THEME.border}`, background: "transparent",
                      color: THEME.textDim, fontSize: 11, cursor: "pointer", fontFamily: "'DM Sans'",
                    }}><RotateCcw size={11} /> Clear All</button>
                  )}
                </div>
                <div style={{ borderRadius: 12, border: `1px solid ${THEME.border}`, background: THEME.surface, overflow: "hidden" }}>
                  <ComparisonView products={compareList} />
                </div>
              </div>
            </div>
          )}

          {/* Q&A TAB */}
          {tab === "qa" && <QAPanel />}

          {/* INGEST TAB */}
          {tab === "ingest" && <IngestionDashboard />}
        </main>

        {/* Detail Panel */}
        {detail && <ProductDetail product={detail} onClose={() => setDetail(null)} />}
      </div>
    </>
  );
}
