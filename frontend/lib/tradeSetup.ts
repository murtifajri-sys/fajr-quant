export type SetupFilter = "all" | "ready" | "wait_breakout" | "wait_retest" | "buy_on_weakness" | "wait_value_area" | "no_setup";

export type TradeSetup = {
  setup_type: SetupFilter;
  setup_state?: string | null;
  label?: string | null;
  last_price?: number | null;
  trigger_price?: number | null;
  zone_low?: number | null;
  zone_high?: number | null;
  invalidation_price?: number | null;
  distance_pct?: number | null;
  risk_reward?: number | null;
  confirmations: string[];
  confluences: string[];
  blockers: string[];
  warnings: string[];
  as_of_date?: string | null;
};

const EMPTY_SETUP: TradeSetup = {
  setup_type: "no_setup",
  setup_state: "unavailable",
  label: "Data setup belum lengkap",
  confirmations: [],
  confluences: [],
  blockers: ["data_setup_belum_lengkap"],
  warnings: [],
};

function asNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

export function normalizeTradeSetup(row: any, broker: any): TradeSetup {
  const raw = row?.setup_detail || broker?.setup_detail;
  if (!raw || typeof raw !== "object") return EMPTY_SETUP;
  const setupType = String(raw.setup_type || "no_setup") as SetupFilter;
  return {
    setup_type: setupType,
    setup_state: raw.setup_state ? String(raw.setup_state) : null,
    label: raw.label ? String(raw.label) : null,
    last_price: asNumber(raw.last_price),
    trigger_price: asNumber(raw.trigger_price),
    zone_low: asNumber(raw.zone_low),
    zone_high: asNumber(raw.zone_high),
    invalidation_price: asNumber(raw.invalidation_price),
    distance_pct: asNumber(raw.distance_pct),
    risk_reward: asNumber(raw.risk_reward),
    confirmations: asStringArray(raw.confirmations),
    confluences: asStringArray(raw.confluences),
    blockers: asStringArray(raw.blockers),
    warnings: asStringArray(raw.warnings),
    as_of_date: raw.as_of_date ? String(raw.as_of_date) : null,
  };
}

export function setupMatchesFilter(setup: TradeSetup, filter: SetupFilter, tradeCode?: string | null) {
  if (filter === "all") return true;
  if (filter === "ready") return tradeCode === "ready" && setup.setup_state === "confirmed";
  return setup.setup_type === filter;
}

export function setupTargetText(setup: TradeSetup) {
  if (setup.trigger_price !== null && setup.trigger_price !== undefined) {
    return `>${setup.trigger_price.toFixed(0)}`;
  }
  if (setup.zone_low !== null && setup.zone_low !== undefined && setup.zone_high !== null && setup.zone_high !== undefined) {
    return `${setup.zone_low.toFixed(0)}-${setup.zone_high.toFixed(0)}`;
  }
  return "-";
}

export function setupTone(setup: TradeSetup) {
  if (setup.setup_state === "confirmed") return "border-emerald-700/50 bg-emerald-500/10 text-emerald-300";
  if (setup.setup_type === "no_setup") return "border-slate-700 bg-slate-900/70 text-slate-300";
  if (setup.setup_type === "buy_on_weakness") return "border-cyan-700/50 bg-cyan-500/10 text-cyan-300";
  return "border-amber-700/50 bg-amber-500/10 text-amber-200";
}
