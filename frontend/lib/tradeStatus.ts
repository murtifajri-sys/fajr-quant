export type TradeStatusCode = "ready" | "waiting" | "hold" | "unavailable";

export type TradeStatus = {
  code: TradeStatusCode;
  label: "Siap Entry" | "Tunggu Konfirmasi" | "Hold" | "Data Belum Siap";
  tone: string;
  summary: string;
  passed: string[];
  blockers: string[];
  warnings: string[];
  metrics: {
    conviction: number | null;
    entry: number | null;
    flow: number | null;
    recency: number | null;
  };
};

type TradeStatusOptions = {
  loading?: boolean;
  hasError?: boolean;
};

const TONE: Record<TradeStatusCode, string> = {
  ready: "text-emerald-300 border-emerald-500/30 bg-emerald-500/10",
  waiting: "text-amber-200 border-amber-500/30 bg-amber-500/10",
  hold: "text-slate-200 border-slate-700 bg-slate-900/70",
  unavailable: "text-slate-300 border-slate-700 bg-slate-900/70",
};

const REASONS: Record<string, string> = {
  broker_active: "Broker flow aktif",
  conviction_confirmed: "Label akumulasi valid",
  conviction_strong: "Conviction kuat",
  entry_ready: "Entry readiness memadai",
  flow_quality_good: "Kualitas flow memadai",
  coverage_ok: "Coverage data cukup",
  recent_flow_positive: "Flow 5 sesi masih positif",
  retention_ok: "Retention sehat",
  cluster_ok: "Cluster buyer mendukung",
  data_loading: "Data broker masih dimuat",
  api_error: "Data broker gagal dimuat",
  missing_detail: "Detail broker belum tersedia",
  missing_score: "Score utama belum lengkap",
  missing_window: "Window broker utama belum tersedia",
  insufficient_data: "Coverage broker belum cukup",
  coverage_low: "Coverage data di bawah 80%",
  broker_coverage_low: "Coverage broker utama di bawah 80%",
  no_accumulation: "Belum ada akumulasi bersih",
  stale: "Flow sudah tidak recent",
  reversal_risk: "Ada risiko reversal flow",
  label_none: "Belum berlabel akumulasi",
  recent_flow_negative: "Net 5 sesi terakhir tidak positif",
  retail_distribution_risk: "Terdeteksi risiko distribusi retail",
  flow_quality_bad: "Kualitas flow belum layak",
  weak_technical_phase: "Fase teknikal lemah",
  flow_not_recent: "Last buy terlalu jauh",
  conviction_too_low: "Conviction belum cukup kuat",
  entry_not_ready: "Entry readiness belum cukup",
  entry_phase_not_ready: "Fase entry belum ideal",
  flow_quality_too_low: "Skor kualitas flow belum cukup",
  flow_label_mixed_low: "Flow mixed belum cukup kuat",
  retention_weak: "Retention masih lemah",
  cluster_weak: "Cluster buyer belum kuat",
  directional_purity_weak: "Directional purity masih lemah",
  persistence_weak: "Persistence belum cukup",
  one_week_weak: "Momentum 1W melemah",
  waiting_minimum: "Setup masih perlu konfirmasi",
};

function numberOrNull(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function hasObject(value: unknown): value is Record<string, any> {
  return Boolean(value && typeof value === "object" && Object.keys(value as Record<string, any>).length);
}

function reasonText(codes: string[]) {
  return codes.map((code) => REASONS[code] || code);
}

function buildStatus(
  code: TradeStatusCode,
  summary: string,
  passed: string[],
  blockers: string[],
  warnings: string[],
  metrics: TradeStatus["metrics"],
): TradeStatus {
  const label = code === "ready" ? "Siap Entry" : code === "waiting" ? "Tunggu Konfirmasi" : code === "unavailable" ? "Data Belum Siap" : "Hold";
  return {
    code,
    label,
    tone: TONE[code],
    summary,
    passed: reasonText(passed).slice(0, 3),
    blockers: reasonText(blockers).slice(0, 3),
    warnings: reasonText(warnings).slice(0, 3),
    metrics,
  };
}

export function evaluateTradeStatus(detail: any, options: TradeStatusOptions = {}): TradeStatus {
  const emptyMetrics = { conviction: null, entry: null, flow: null, recency: null };
  if (options.loading) {
    return buildStatus("unavailable", "Menunggu data broker dan scoring selesai dimuat.", [], ["data_loading"], [], emptyMetrics);
  }
  if (options.hasError) {
    return buildStatus("unavailable", "Data broker belum bisa dinilai karena request gagal.", [], ["api_error"], [], emptyMetrics);
  }
  if (!detail) {
    return buildStatus("unavailable", "Detail broker belum tersedia untuk ticker ini.", [], ["missing_detail"], [], emptyMetrics);
  }

  const conviction = detail.broker_conviction || {};
  const flowQuality = detail.flow_quality || {};
  const entry = detail.entry_readiness || {};
  const primaryWindow = hasObject(detail.one_month) ? detail.one_month : hasObject(detail.one_week) ? detail.one_week : null;
  const oneWeek = hasObject(detail.one_week) ? detail.one_week : null;
  const config = conviction.config || {};

  const convictionScore = numberOrNull(conviction.score);
  const entryScore = numberOrNull(entry.score);
  const flowScore = numberOrNull(flowQuality.score);
  const recency = numberOrNull(primaryWindow?.recency_sessions);
  const metrics = { conviction: convictionScore, entry: entryScore, flow: flowScore, recency };

  if (convictionScore === null || entryScore === null || flowScore === null) {
    return buildStatus("unavailable", "Score broker, entry, atau flow belum lengkap.", [], ["missing_score"], [], metrics);
  }
  if (!primaryWindow) {
    return buildStatus("unavailable", "Window broker utama belum tersedia.", [], ["missing_window"], [], metrics);
  }

  const status = String(conviction.status || primaryWindow.status || "");
  const label = String(conviction.label || primaryWindow.broker_conviction_label || "none");
  const flowLabel = String(flowQuality.label || primaryWindow.flow_quality_label || "");
  const entryPhase = String(entry.phase || "");
  const entryTags = Array.isArray(entry.tags) ? entry.tags.map(String) : [];
  const coverage = numberOrNull(primaryWindow.coverage_ratio);
  const brokerCoverage = numberOrNull(primaryWindow.broker_coverage_ratio);
  const recentFiveNet = numberOrNull(primaryWindow.recent_5_session_net);
  const retention = numberOrNull(primaryWindow.retention);
  const clusterRatio = numberOrNull(primaryWindow.cluster_ratio);
  const directionalPurity = numberOrNull(primaryWindow.directional_purity);
  const positiveRatio = numberOrNull(primaryWindow.positive_ratio);
  const minimumClusterRatio = numberOrNull(config.minimum_cluster_ratio) ?? 0.5;

  const unavailableBlockers: string[] = [];
  if (
    coverage === null ||
    brokerCoverage === null ||
    recency === null ||
    recentFiveNet === null ||
    retention === null ||
    clusterRatio === null ||
    directionalPurity === null ||
    positiveRatio === null
  ) unavailableBlockers.push("missing_window");
  if (status === "insufficient_data") unavailableBlockers.push("insufficient_data");
  if (coverage !== null && coverage < 0.8) unavailableBlockers.push("coverage_low");
  if (brokerCoverage !== null && brokerCoverage < 0.8) unavailableBlockers.push("broker_coverage_low");
  if (unavailableBlockers.length) {
    return buildStatus("unavailable", "Data broker belum cukup bersih untuk menilai entry.", [], unavailableBlockers, [], metrics);
  }

  const hardBlockers: string[] = [];
  if (["no_accumulation", "stale", "reversal_risk"].includes(status)) hardBlockers.push(status);
  if (label === "none") hardBlockers.push("label_none");
  if (recentFiveNet !== null && recentFiveNet <= 0) hardBlockers.push("recent_flow_negative");
  if (flowQuality.retail_distribution_risk || primaryWindow.retail_distribution_risk) hardBlockers.push("retail_distribution_risk");
  if (["retail_distribution_risk", "insufficient_flow_quality", "retail_like_accumulation"].includes(flowLabel)) hardBlockers.push("flow_quality_bad");
  if (["Siap Jual", "Exit"].includes(entryPhase) || entryTags.includes("weak_phase")) hardBlockers.push("weak_technical_phase");
  if (recency !== null && recency > 2) hardBlockers.push("flow_not_recent");
  if (hardBlockers.length) {
    return buildStatus("hold", "Setup masuk mode observasi karena ada risiko utama yang belum bersih.", [], [...new Set(hardBlockers)], [], metrics);
  }

  const readyPasses: string[] = [];
  const readyBlockers: string[] = [];
  if (status === "active") readyPasses.push("broker_active");
  else readyBlockers.push("stale");
  if (["big_accumulation", "aggressive_accumulation"].includes(label)) readyPasses.push("conviction_confirmed");
  else readyBlockers.push("conviction_too_low");
  if (convictionScore >= 70) readyPasses.push("conviction_strong");
  else readyBlockers.push("conviction_too_low");
  if (entryScore >= 75) readyPasses.push("entry_ready");
  else readyBlockers.push("entry_not_ready");
  if (["Siap Entry"].includes(entryPhase) || (entryPhase === "Hold" && entryScore >= 80)) readyPasses.push("entry_ready");
  else readyBlockers.push("entry_phase_not_ready");
  if (flowScore >= 60) readyPasses.push("flow_quality_good");
  else readyBlockers.push("flow_quality_too_low");
  if (flowLabel === "smart_like_accumulation" || (flowLabel === "mixed_accumulation" && flowScore >= 70)) readyPasses.push("flow_quality_good");
  else readyBlockers.push("flow_label_mixed_low");
  if ((coverage ?? 0) >= 0.8 && (brokerCoverage ?? 0) >= 0.8) readyPasses.push("coverage_ok");
  if (recency !== null && recency <= 1) readyPasses.push("recent_flow_positive");
  else readyBlockers.push("flow_not_recent");
  if (recentFiveNet !== null && recentFiveNet > 0) readyPasses.push("recent_flow_positive");
  else readyBlockers.push("recent_flow_negative");
  if (retention !== null && retention >= 0.7) readyPasses.push("retention_ok");
  else readyBlockers.push("retention_weak");
  if (clusterRatio !== null && clusterRatio >= minimumClusterRatio) readyPasses.push("cluster_ok");
  else readyBlockers.push("cluster_weak");
  if (directionalPurity !== null && directionalPurity >= 0.2) readyPasses.push("conviction_confirmed");
  else readyBlockers.push("directional_purity_weak");
  if (positiveRatio !== null && positiveRatio >= 0.4) readyPasses.push("conviction_confirmed");
  else readyBlockers.push("persistence_weak");

  const oneWeekWeak = oneWeek && (["reversal_risk", "stale"].includes(String(oneWeek.status || "")) || (numberOrNull(oneWeek.recent_5_session_net) ?? 1) <= 0);
  if (readyBlockers.length === 0 && !oneWeekWeak) {
    return buildStatus("ready", "Conviction, flow, dan entry readiness sudah lolos gate ketat.", [...new Set(readyPasses)], [], [], metrics);
  }

  const accumulationLabels = ["accumulation", "big_accumulation", "aggressive_accumulation"];
  const waitingMinimum =
    status === "active" &&
    accumulationLabels.includes(label) &&
    convictionScore >= 55 &&
    entryScore >= 50 &&
    (recentFiveNet ?? 0) > 0;
  if (waitingMinimum) {
    const warnings = oneWeekWeak ? ["one_week_weak", ...readyBlockers] : readyBlockers;
    return buildStatus("waiting", "Setup terbentuk, tapi masih butuh konfirmasi sebelum entry.", [...new Set(readyPasses)], ["waiting_minimum"], [...new Set(warnings)], metrics);
  }

  return buildStatus("hold", "Belum ideal untuk entry baru; tunggu conviction dan readiness membaik.", [...new Set(readyPasses)], [...new Set(readyBlockers)], [], metrics);
}
