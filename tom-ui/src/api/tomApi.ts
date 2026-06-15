export type ApiError = {
  ok: false;
  error_code: string;
  message: string;
  warnings?: string[];
  data?: unknown;
};

export type ApiSuccess<T> = {
  ok: true;
  data: T;
  warnings?: string[];
};

export type ApiResponse<T> = ApiSuccess<T> | ApiError;

export type TomHealth = {
  service: string;
  database_exists: boolean;
  required_tables_present: boolean;
  existing_table_count: number;
  missing_tables: string[];
  api: {
    host: string;
    port: number;
    local_only: boolean;
    endpoints: string[];
  };
};

export type TomStatus = {
  database: TomHealth;
  rows: Record<string, number | null>;
  latest: {
    price_date?: string | null;
    quote_timestamp?: string | null;
    range_snapshot_timestamp?: string | null;
    research_recommendation_date?: string | null;
    pipeline_run?: Record<string, unknown> | null;
    intraday_cycle?: Record<string, unknown> | null;
  };
  pending_notifications: number | null;
  loop?: TomLoopSnapshot;
};

export type Asset = {
  ticker: string;
  name?: string | null;
  asset_type?: string | null;
  exchange?: string | null;
  currency?: string | null;
  sector?: string | null;
  industry?: string | null;
  country?: string | null;
  active_flag: number;
  asset_role: string;
  source?: string | null;
  as_of_date?: string | null;
  effective_date?: string | null;
};

export type AssetsPayload = {
  count: number;
  assets: Asset[];
};

export type MissingTickerCandidate = {
  missing_ticker_candidate_id?: number | null;
  ticker: string;
  first_seen_source: string;
  source_file?: string | null;
  source_row?: string | null;
  detected_asset_type?: string | null;
  recommended_asset_role?: string | null;
  confidence?: number | null;
  blockers?: string | null;
  warnings?: string | null;
  status: string;
  next_command?: string | null;
  metadata_name?: string | null;
  metadata_exchange?: string | null;
  metadata_currency?: string | null;
  metadata_sector?: string | null;
  metadata_industry?: string | null;
  metadata_country?: string | null;
  source_url?: string | null;
};

export type MissingTickerStatusPayload = {
  status: {
    total_candidates: number;
    pending_candidates: number;
    ready_to_onboard: number;
    onboarded: number;
    hydrated: number;
    blocked: number;
    account_context_candidates: number;
    candidates: MissingTickerCandidate[];
    next_actions: string[];
  };
};

export type ResearchRecommendation = {
  research_recommendation_id: number;
  ticker: string;
  recommendation_date: string;
  source: string;
  status: string;
  topic?: string | null;
  rationale?: string | null;
  research_priority_score?: number | null;
  confidence?: number | null;
  source_count?: number | null;
  evidence_count?: number | null;
  source_mix?: string | null;
  metadata_status?: string | null;
  warning_codes?: string | null;
  promotion_blockers?: string | null;
  promoted_asset_role?: string | null;
  source_url?: string | null;
};

export type ResearchRecommendationsPayload = {
  count: number;
  candidates: ResearchRecommendation[];
};

export type ResearchTriageGroup = {
  ticker: string;
  classification: string;
  candidate_count: number;
  max_priority_score?: number | null;
  recommendation_ids: number[];
  representative_candidate_ids: number[];
  sources: string[];
  topics: string[];
  warnings: string[];
  promotion_blockers: string[];
  recommended_action: string;
};

export type ResearchRecommendationTriagePayload = {
  triage: {
    total_count: number;
    pending_count: number;
    approved_count: number;
    promoted_count: number;
    ignored_count: number;
    rejected_count: number;
    status_counts: Array<[string, number]>;
    source_mix: Array<[string, number]>;
    group_count: number;
    groups: ResearchTriageGroup[];
    classification_counts: Array<[string, number]>;
  };
};

export type ResearchPreparationState =
  | "prepared_already_scoreable"
  | "prepared_ready_for_review"
  | "ready_to_apply"
  | "source_data_required"
  | "metadata_required"
  | "identity_required"
  | "manual_review_required"
  | "evidence_gated"
  | "blocked";

export type ResearchSourceCandidate = {
  ticker: string;
  source_type: string;
  source: string;
  source_url: string;
  status: string;
  reason: string;
  as_of_date?: string | null;
  can_stage: boolean;
  warnings?: string[];
  blockers?: string[];
};

export type ResearchStagedSourceRow = {
  ticker: string;
  row_type: string;
  path: string;
  row_count: number;
  source: string;
  source_url: string;
  status: string;
  warnings?: string[];
};

export type ResearchManualBlockerPacket = {
  ticker: string;
  state: string;
  asset_type: string;
  research_path: string;
  pending_recommendation_rows: number;
  attempted_sources: ResearchSourceCandidate[];
  cannot_automate_reason: string;
  required_fields: string[];
  blockers: string[];
  warnings: string[];
  safe_next_action: string;
};

export type ResearchPreparationAutopilot = {
  enabled: boolean;
  source: string;
  throttle_seconds: number;
  due: boolean;
  latest_status?: string | null;
  latest_started_at?: string | null;
  latest_finished_at?: string | null;
  latest_rows_loaded?: number | null;
  latest_warnings?: string[];
  seconds_since_latest?: number | null;
  manual_blocker_count: number;
  manual_blocker_tickers: string[];
  cannot_automate_reasons: Array<[string, string]>;
  applied_tickers: string[];
  ignored_context_rows: number;
};

export type ResearchPreparationItem = {
  ticker: string;
  source: string;
  asset_type: string;
  research_path: string;
  preparation_state: ResearchPreparationState | string;
  candidate_count: number;
  recommendation_ids: number[];
  representative_candidate_ids: number[];
  missing_candidate_ids?: number[];
  max_priority_score?: number | null;
  sources?: string[];
  topics?: string[];
  warnings?: string[];
  blockers?: string[];
  recommended_action: string;
  action_kind: string;
  can_apply: boolean;
  can_ignore_context: boolean;
  can_refresh: boolean;
  source_candidates?: ResearchSourceCandidate[];
  staged_rows?: ResearchStagedSourceRow[];
  automation_stage?: string;
  can_discover_sources?: boolean;
  can_stage_sources?: boolean;
  can_load_sources?: boolean;
  cannot_automate_reason?: string | null;
  plan?: ResearchTickerPlanPayload["plan"] | null;
  status?: ResearchTickerStatusPayload["status"] | null;
  strategy_review?: EtfStrategyReviewPayload["review"] | null;
};

export type ResearchPreparationPayload = {
  preparation: {
    source: string;
    total_items: number;
    pending_recommendation_count: number;
    ready_to_apply_count: number;
    already_scoreable_count: number;
    manual_blocked_count: number;
    state_counts: Array<[string, number]>;
    items: ResearchPreparationItem[];
    warnings?: string[];
    next_actions?: string[];
    autopilot?: ResearchPreparationAutopilot | null;
    manual_blocker_packets?: ResearchManualBlockerPacket[];
  };
};

export type ResearchPreparationRunPayload = {
  result: {
    source: string;
    action: string;
    confirm: boolean;
    dry_run: boolean;
    ignored_count: number;
    applied_count: number;
    refreshed_count: number;
    discovered_count?: number;
    staged_count?: number;
    loaded_source_count?: number;
    computed_count?: number;
    blocked_count: number;
    updated_recommendation_ids: number[];
    applied_tickers: string[];
    refreshed_tickers: string[];
    discovered_tickers?: string[];
    staged_tickers?: string[];
    loaded_source_tickers?: string[];
    computed_tickers?: string[];
    blocked_reason?: string | null;
    warnings?: string[];
    status: ResearchPreparationPayload["preparation"];
  };
};

export type BulkRecommendationStatusPayload = {
  result: {
    requested_ids: number[];
    target_status: string;
    reason: string;
    updated_count: number;
    updated_candidates: ResearchRecommendation[];
    blocked_reason?: string | null;
    warnings: string[];
  };
};

export type ResearchTickerMetadata = {
  ticker: string;
  name?: string | null;
  cik?: string | null;
  exchange?: string | null;
  currency?: string | null;
  sector?: string | null;
  industry?: string | null;
  country?: string | null;
  isin?: string | null;
  source_url?: string | null;
  sources?: string[];
  warnings?: string[];
};

export type ResearchTickerPlanPayload = {
  plan: {
    ticker: string;
    metadata: ResearchTickerMetadata;
    existing_asset?: Asset | null;
    asset_type?: string;
    research_path?: string;
    apply_ready: boolean;
    blocked_reason?: string | null;
    readiness_blockers?: string[];
    warnings?: string[];
  };
};

export type FundamentalComparison = Record<string, unknown> & {
  comparison_date?: string | null;
  sector?: string | null;
  industry?: string | null;
  sector_benchmark_ticker?: string | null;
  sector_peer_count?: number | null;
  industry_peer_count?: number | null;
  sector_forward_pe_discount_pct?: number | null;
  relative_strength_vs_spy?: number | null;
  relative_strength_vs_qqq?: number | null;
  relative_strength_vs_sector?: number | null;
  benchmark_status?: string | null;
  data_warnings?: string | null;
};

export type ResearchTickerStatusPayload = {
  ticker: string;
  status: {
    ticker: string;
    asset?: Asset | null;
    cik?: string | null;
    price_available: boolean;
    fundamental_count: number;
    estimate_available: boolean;
    target_available: boolean;
    score_available: boolean;
    etf_feature_available?: boolean;
    etf_nav_available?: boolean;
    range_available?: boolean;
    option_chain_available?: boolean;
    foreign_identity_available?: boolean;
    foreign_identity_isin?: string | null;
    foreign_identity_source_url?: string | null;
    comparison?: FundamentalComparison | null;
    readiness_blockers: string[];
    asset_type?: string | null;
  };
  status_text: string;
};

export type FundamentalBenchmarkReportPayload = {
  ticker: string;
  report_markdown: string;
};

export type ResearchApplyPayload = {
  result: {
    ticker: string;
    dry_run: boolean;
    applied: boolean;
    blocked_reason?: string | null;
    asset_type?: string;
    research_path?: string;
    readiness_blockers?: string[];
    warnings?: string[];
  };
};

export type EtfStrategyAlternative = {
  key: string;
  label: string;
  status: string;
  score?: number | null;
  action?: string | null;
  current_price?: number | null;
  target_price?: number | null;
  nav_per_share?: number | null;
  nav_gap?: number | null;
  option_expiration?: string | null;
  option_strike?: number | null;
  premium?: number | null;
  breakeven?: number | null;
  max_loss?: number | null;
  premium_yield?: number | null;
  annualized_yield?: number | null;
  downside_buffer_pct?: number | null;
  assignment_notional?: number | null;
  source?: string | null;
  blockers?: string[];
  warnings?: string[];
};

export type EtfStrategyReviewPayload = {
  ticker: string;
  review: {
    ticker: string;
    asset_type?: string | null;
    decision: string;
    share: EtfStrategyAlternative;
    long_call: EtfStrategyAlternative;
    sell_put: EtfStrategyAlternative;
    warnings?: string[];
  };
  review_text: string;
};

export type ResearchRefreshPayload = {
  result: Record<string, unknown>;
  readiness_blockers: string[];
  status: ResearchTickerStatusPayload["status"];
};

export type ForeignEquitySourcePayload = {
  validation: {
    fundamentals_path: string;
    estimates_path: string;
    analyst_targets_path: string;
    valid_fundamental_rows: number;
    valid_estimate_rows: number;
    valid_analyst_target_rows: number;
    invalid_rows: number;
    blank_rows: number;
    valid_fundamental_tickers: string[];
    valid_estimate_tickers: string[];
    valid_analyst_target_tickers: string[];
    source_required_tickers: string[];
    projected_ready_tickers: string[];
    apply_ready: boolean;
    blocked_reason?: string | null;
    diagnostics: Record<string, unknown>[];
    ticker_statuses: Record<string, unknown>[];
    warnings?: string[];
  };
  status_text: string;
};

export type ForeignEquitySourceApplyPayload = {
  result: Record<string, unknown>;
  apply_text: string;
};

export type AssetStatusPayload = {
  ticker: string;
  asset: Asset;
  readiness?: Record<string, unknown>;
  latest_range?: Record<string, unknown> | null;
  range_count: number;
};

export type AssetMutationRequest = {
  ticker: string;
  name?: string;
  asset_type?: string;
  exchange?: string;
  currency?: string;
  sector?: string;
  industry?: string;
  country?: string;
  asset_role?: string;
  cik?: string;
  reason?: string;
};

export type AssetMutationPayload = {
  previous_asset?: Asset | null;
  asset?: Asset | null;
};

export type IntradayStatusPayload = Record<string, unknown> & {
  health?: Record<string, unknown>;
  scheduler?: Record<string, unknown>;
  manual_ops?: Record<string, unknown>;
  loop?: TomLoopSnapshot;
  status_text?: string;
  manual_ops_status_text?: string;
};

export type IntradayHealthPayload = {
  health: Record<string, unknown>;
  health_text: string;
};

export type TomLoopSnapshot = Record<string, unknown> & {
  status: string;
  health_status: string;
  active: boolean;
  lock_exists: boolean;
  stale_lock: boolean;
  stop_requested: boolean;
  pid?: number | null;
  mode?: string | null;
  deliver?: boolean | null;
  channel?: string | null;
  started_at?: string | null;
  last_heartbeat_at?: string | null;
  heartbeat_age_seconds?: number | null;
  last_cycle_mode?: string | null;
  last_cycle_finished_at?: string | null;
  last_result_status?: string | null;
  last_result_summary?: string | null;
  quote_timestamp?: string | null;
  quote_age_seconds?: number | null;
  range_snapshot_timestamp?: string | null;
  pending_notifications?: number | null;
  failed_deliveries?: number | null;
  latest_successful_delivery?: string | null;
  stale_blockers?: string[];
  warnings?: string[];
  notes?: string[];
  recommended_command?: string;
  run_once_command?: string;
  clear_stale_lock_command?: string;
  recovery_status?: string;
  recommended_actions?: string[];
  recovery_notes?: string[];
};

export type TomLoopStatusPayload = {
  loop: TomLoopSnapshot;
  status_text?: string;
  health_text?: string;
};

export type TomLoopRequest = {
  mode?: string;
  deliver?: boolean;
  channel?: string;
  interval_seconds?: number;
  max_cycles?: number;
};

export type SchedulerStatusPayload = Record<string, unknown> & {
  health?: Record<string, unknown>;
  audit?: Record<string, unknown>;
  heartbeat_job?: Record<string, unknown> | null;
  audit_text?: string;
  repair_plan_text?: string;
  automation_status_text?: string;
};

export type SchedulerAuditPayload = {
  audit: Record<string, unknown>;
  audit_text: string;
  repair_plan_text: string;
  automation_status_text: string;
};

export type NotificationStatusPayload = {
  count: number;
  events: Array<Record<string, unknown>>;
  pending_count: number;
  delivered_delivery_count: number;
  failed_delivery_count: number;
  latest_successful_delivery?: string | null;
};

export type NotificationTextPayload = {
  report_text?: string;
  status_text?: string;
};

export type AccountContextPayload = {
  status: Record<string, unknown>;
  validation: Record<string, unknown>;
  preview: Record<string, unknown>;
  option_position_diagnostics?: Record<string, unknown>;
};

export type AccountRowType = "portfolio_position" | "portfolio_cash" | "option_position";

export type AccountAppendRowRequest = {
  row_type: AccountRowType;
  row: Record<string, string>;
};

export type BackfillStatusPayload = Record<string, unknown>;

export type BackfillActionPayload = {
  result: Record<string, unknown>;
  apply_text?: string;
};

export type ShortInterestAppendRowRequest = {
  row: Record<string, string>;
};

export type NewsBackfillAppendRowRequest = {
  row: Record<string, string>;
};

export type AccountFetchRequest = {
  source: "ibkr" | "file";
  read_only: boolean;
  provider?: string;
  file?: string;
};

export type OpsCycleRequest = {
  source?: string;
  ticker?: string;
  deliver?: boolean;
  channel?: string;
  include_options?: boolean;
  drain_first?: boolean;
};

export type ManualOpsCycleRequest = {
  mode?: string;
  deliver?: boolean;
  channel?: string;
  dry_run?: boolean;
};

export type RecommendationStatus = "pending" | "approved" | "ignored" | "rejected" | "promoted";
export type EditableRecommendationStatus = Exclude<RecommendationStatus, "promoted">;

export type OptionsStatusPayload = {
  provider: Record<string, unknown>;
  summary_text: string;
};

export type ProviderStatusPayload = {
  options: Record<string, unknown>;
};

export type DashboardData = Record<string, unknown>;

export type SignalLane = {
  key: string;
  label: string;
  status: string;
  coverage: Record<string, unknown>;
  coverage_label: string;
  counts: Record<string, unknown>;
  blockers: string[];
  warnings: string[];
  notes: string[];
  details: Record<string, unknown>;
  status_text: string;
  commands: string[];
};

export type SignalCoveragePayload = {
  generated_at: string;
  status: string;
  lane_keys: string[];
  status_counts: Record<string, number>;
  lanes: SignalLane[];
  lane_map: Record<string, SignalLane>;
};

export type CoverageGroup = {
  key: string;
  label: string;
  status: string;
  summary: string;
  blockers: string[];
  warnings: string[];
  notes: string[];
  counts: Record<string, unknown>;
  details: Record<string, unknown>;
  commands: string[];
};

export type PhaseCoveragePayload = {
  generated_at: string;
  status: string;
  group_keys: string[];
  status_counts: Record<string, number>;
  groups: CoverageGroup[];
  group_map: Record<string, CoverageGroup>;
};

const API_BASE_URL =
  import.meta.env.VITE_TOM_API_BASE_URL?.replace(/\/+$/, "") ??
  "http://127.0.0.1:8765";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers ?? {})
      }
    });
    const payload = (await response.json()) as ApiResponse<T>;
    return payload;
  } catch (error) {
    return {
      ok: false,
      error_code: "tom_api_unreachable",
      message:
        error instanceof Error
          ? error.message
          : "Unable to reach the local TOM API.",
      warnings: ["local_backend_offline"]
    };
  }
}

function confirmedBody(body: Record<string, unknown>): BodyInit {
  return JSON.stringify({ ...body, confirm: true });
}

function unconfirmedBody(body: Record<string, unknown>): BodyInit {
  return JSON.stringify(body);
}

export type ResearchTickerRequest = {
  ticker: string;
  asset_type?: "equity" | "foreign_equity" | "etf";
  refresh_metadata?: boolean;
  name?: string;
  sector?: string;
  industry?: string;
  cik?: string;
  exchange?: string;
  currency?: string;
  country?: string;
};

export const tomApi = {
  apiBaseUrl: API_BASE_URL,
  health: () => request<TomHealth>("/api/health"),
  status: () => request<TomStatus>("/api/status"),
  dashboardData: () => request<DashboardData>("/api/dashboard-data"),
  signalCoverage: () => request<SignalCoveragePayload>("/api/signals/status"),
  phaseCoverage: () => request<PhaseCoveragePayload>("/api/coverage/status"),
  assets: () => request<AssetsPayload>("/api/assets"),
  assetStatus: (ticker: string) =>
    request<AssetStatusPayload>(
      `/api/assets/status?ticker=${encodeURIComponent(ticker)}`
    ),
  addAsset: (requestBody: AssetMutationRequest, confirm: boolean) =>
    request<AssetMutationPayload>("/api/assets/add", {
      method: "POST",
      body: confirm ? confirmedBody(requestBody) : unconfirmedBody(requestBody)
    }),
  deactivateAsset: (ticker: string, reason: string, confirm: boolean) =>
    request<AssetMutationPayload>("/api/assets/deactivate", {
      method: "POST",
      body: confirm ? confirmedBody({ ticker, reason }) : unconfirmedBody({ ticker, reason })
    }),
  reactivateAsset: (ticker: string, reason: string, confirm: boolean) =>
    request<AssetMutationPayload>("/api/assets/reactivate", {
      method: "POST",
      body: confirm ? confirmedBody({ ticker, reason }) : unconfirmedBody({ ticker, reason })
    }),
  removeAsset: (ticker: string, reason: string, confirm: boolean) =>
    request<AssetMutationPayload>("/api/assets/remove", {
      method: "POST",
      body: confirm ? confirmedBody({ ticker, reason }) : unconfirmedBody({ ticker, reason })
    }),
  researchRecommendations: (status?: string) => {
    const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
    return request<ResearchRecommendationsPayload>(
      `/api/research/recommendations${suffix}`
    );
  },
  researchRecommendationTriage: () =>
    request<ResearchRecommendationTriagePayload>("/api/research/recommendations/triage"),
  researchPreparationStatus: (source = "pending", tickers: string[] = []) => {
    const params = new URLSearchParams({ source });
    tickers.forEach((ticker) => params.append("ticker", ticker));
    return request<ResearchPreparationPayload>(
      `/api/research/preparation/status?${params.toString()}`
    );
  },
  runResearchPreparation: (action: string, source: string, confirm: boolean, tickers: string[] = []) =>
    request<ResearchPreparationRunPayload>("/api/research/preparation/run", {
      method: "POST",
      body: confirm ? confirmedBody({ action, source, tickers }) : unconfirmedBody({ action, source, tickers })
    }),
  optionsStatus: () => request<OptionsStatusPayload>("/api/options/status"),
  providerStatus: () => request<ProviderStatusPayload>("/api/provider/status"),
  setRecommendationStatus: (id: number, status: EditableRecommendationStatus, reason: string, confirm: boolean) =>
    request<{ candidate: ResearchRecommendation }>(`/api/research/recommendations/${id}/status`, {
      method: "POST",
      body: confirm ? confirmedBody({ status, reason }) : unconfirmedBody({ status, reason })
    }),
  bulkSetRecommendationStatus: (ids: number[], status: EditableRecommendationStatus, reason: string, confirm: boolean) =>
    request<BulkRecommendationStatusPayload>("/api/research/recommendations/bulk-status", {
      method: "POST",
      body: confirm ? confirmedBody({ ids, status, reason }) : unconfirmedBody({ ids, status, reason })
    }),
  promoteRecommendation: (id: number, confirm: boolean) =>
    request<{ promotion: Record<string, unknown> }>(`/api/research/recommendations/${id}/promote`, {
      method: "POST",
      body: confirm ? confirmedBody({}) : unconfirmedBody({})
    }),
  researchTickerPlan: (requestBody: ResearchTickerRequest) =>
    request<ResearchTickerPlanPayload>("/api/research/ticker-plan", {
      method: "POST",
      body: unconfirmedBody(requestBody)
    }),
  applyResearchTicker: (requestBody: ResearchTickerRequest, confirm: boolean) =>
    request<ResearchApplyPayload>("/api/research/apply-ticker", {
      method: "POST",
      body: confirm ? confirmedBody(requestBody) : unconfirmedBody(requestBody)
    }),
  refreshResearchTicker: (ticker: string, confirm: boolean) =>
    request<ResearchRefreshPayload>("/api/research/refresh-ticker", {
      method: "POST",
      body: confirm ? confirmedBody({ ticker }) : unconfirmedBody({ ticker })
    }),
  researchTickerStatus: (ticker: string) =>
    request<ResearchTickerStatusPayload>(
      `/api/research/ticker-status?ticker=${encodeURIComponent(ticker)}`
    ),
  etfStrategyReview: (ticker: string) =>
    request<EtfStrategyReviewPayload>(
      `/api/research/etf-strategy-review?ticker=${encodeURIComponent(ticker)}`
    ),
  fundamentalBenchmarkReport: (ticker: string) =>
    request<FundamentalBenchmarkReportPayload>(
      `/api/research/fundamental-benchmark-report?ticker=${encodeURIComponent(ticker)}`
    ),
  foreignEquitySourceStatus: () =>
    request<ForeignEquitySourcePayload>("/api/research/foreign-equity-source-status"),
  exportForeignEquitySourceTemplate: (confirm: boolean) =>
    request<Record<string, string>>("/api/research/foreign-equity-source-template", {
      method: "POST",
      body: confirm ? confirmedBody({}) : unconfirmedBody({})
    }),
  applyForeignEquitySource: (confirm: boolean, dryRun = false) =>
    request<ForeignEquitySourceApplyPayload>("/api/research/foreign-equity-source-apply", {
      method: "POST",
      body: confirm ? confirmedBody({ dry_run: dryRun }) : unconfirmedBody({ dry_run: dryRun })
    }),
  intradayStatus: () => request<IntradayStatusPayload>("/api/ops/intraday-status"),
  intradayHealth: () => request<IntradayHealthPayload>("/api/ops/intraday-health"),
  loopStatus: () => request<TomLoopStatusPayload>("/api/loop/status"),
  loopHealth: () => request<TomLoopStatusPayload>("/api/loop/health"),
  runLoopOnce: (requestBody: TomLoopRequest = { mode: "auto", deliver: true, channel: "file" }, confirm = true) =>
    request<{ result: Record<string, unknown> }>("/api/loop/run-once", {
      method: "POST",
      body: confirm ? confirmedBody(requestBody) : unconfirmedBody(requestBody)
    }),
  startLoop: (requestBody: TomLoopRequest = { mode: "auto", deliver: true, channel: "file" }, confirm = true) =>
    request<{ result: Record<string, unknown> }>("/api/loop/start", {
      method: "POST",
      body: confirm ? confirmedBody(requestBody) : unconfirmedBody(requestBody)
    }),
  stopLoop: (confirm = true) =>
    request<{ result: Record<string, unknown> }>("/api/loop/stop", {
      method: "POST",
      body: confirm ? confirmedBody({}) : unconfirmedBody({})
    }),
  schedulerStatus: () => request<SchedulerStatusPayload>("/api/scheduler/status"),
  schedulerAudit: () => request<SchedulerAuditPayload>("/api/scheduler/audit"),
  notificationsStatus: (status?: string) => {
    const suffix = status ? `?status=${encodeURIComponent(status)}` : "";
    return request<NotificationStatusPayload>(`/api/notifications/status${suffix}`);
  },
  notificationDeliveryReport: () =>
    request<NotificationTextPayload>("/api/notifications/delivery-report"),
  notificationOutboxStatus: () =>
    request<NotificationTextPayload>("/api/notifications/outbox-status"),
  runIntradayCycle: (requestBody: OpsCycleRequest = { source: "auto", deliver: true, channel: "file" }, confirm = true) =>
    request<{ result: Record<string, unknown> }>("/api/ops/intraday-cycle", {
      method: "POST",
      body: confirm ? confirmedBody(requestBody) : unconfirmedBody(requestBody)
    }),
  runManualOpsCycle: (requestBody: ManualOpsCycleRequest = { mode: "auto", deliver: true, channel: "file" }, confirm = true) =>
    request<{ result: Record<string, unknown> }>("/api/ops/manual-cycle", {
      method: "POST",
      body: confirm ? confirmedBody(requestBody) : unconfirmedBody(requestBody)
    }),
  drainNotifications: (channel = "file", confirm = true) =>
    request<{ result: Record<string, unknown> }>("/api/notifications/drain", {
      method: "POST",
      body: confirm ? confirmedBody({ channel }) : unconfirmedBody({ channel })
    }),
  accountContextStatus: () =>
    request<AccountContextPayload>("/api/account/context-status"),
  accountProviderStatus: () =>
    request<{ provider_status: Record<string, unknown> }>("/api/account/provider-status"),
  exportAccountContextTemplate: (confirm: boolean) =>
    request<{ result: Record<string, unknown> }>("/api/account/export-template", {
      method: "POST",
      body: confirm ? confirmedBody({}) : unconfirmedBody({})
    }),
  validateAccountContextBackfill: () =>
    request<{ validation: Record<string, unknown> }>("/api/account/validate-backfill"),
  previewAccountContextActivation: () =>
    request<{ preview: Record<string, unknown> }>("/api/account/preview-activation"),
  applyAccountContextBackfill: (confirm: boolean, allowPartial: boolean, dryRun = false) =>
    request<{ result: Record<string, unknown> }>("/api/account/apply-backfill", {
      method: "POST",
      body: confirm
        ? confirmedBody({ allow_partial: allowPartial, dry_run: dryRun })
        : unconfirmedBody({ allow_partial: allowPartial, dry_run: dryRun })
    }),
  normalizeAccountExport: (provider: string, file: string, confirm: boolean) =>
    request<{ result: Record<string, unknown> }>("/api/account/normalize-export", {
      method: "POST",
      body: confirm
        ? confirmedBody({ provider, file })
        : unconfirmedBody({ provider, file })
    }),
  fetchAccountContext: (requestBody: AccountFetchRequest, confirm: boolean) =>
    request<{ result: Record<string, unknown> }>("/api/account/fetch-context", {
      method: "POST",
      body: confirm ? confirmedBody(requestBody) : unconfirmedBody(requestBody)
    }),
  missingTickerStatus: () =>
    request<MissingTickerStatusPayload>("/api/missing-tickers/status"),
  resolveMissingTickers: (source = "account_context", confirm = true) =>
    request<{ result: Record<string, unknown> }>("/api/missing-tickers/resolve", {
      method: "POST",
      body: confirm ? confirmedBody({ source }) : unconfirmedBody({ source })
    }),
  applyMissingTickerOnboarding: (source = "account_context", confirm = true) =>
    request<{ result: Record<string, unknown> }>("/api/missing-tickers/apply", {
      method: "POST",
      body: confirm ? confirmedBody({ source }) : unconfirmedBody({ source })
    }),
  hydrateMissingTicker: (ticker: string, confirm = true) =>
    request<{ result: Record<string, unknown> }>("/api/missing-tickers/hydrate", {
      method: "POST",
      body: confirm ? confirmedBody({ ticker }) : unconfirmedBody({ ticker })
    }),
  appendAccountContextRow: (requestBody: AccountAppendRowRequest, confirm: boolean) =>
    request<{ result: Record<string, unknown> }>("/api/account/append-row", {
      method: "POST",
      body: confirm ? confirmedBody(requestBody) : unconfirmedBody(requestBody)
    }),
  optionsBackfillStatus: () =>
    request<BackfillStatusPayload>("/api/backfills/options/status"),
  exportOptionsBackfillTemplate: (confirm: boolean) =>
    request<{ result: Record<string, unknown> }>("/api/backfills/options/export-template", {
      method: "POST",
      body: confirm ? confirmedBody({}) : unconfirmedBody({})
    }),
  validateOptionsBackfill: () =>
    request<{ validation: Record<string, unknown> }>("/api/backfills/options/validate"),
  applyOptionsBackfill: (confirm: boolean, allowPartial: boolean) =>
    request<BackfillActionPayload>("/api/backfills/options/apply", {
      method: "POST",
      body: confirm
        ? confirmedBody({ allow_partial: allowPartial })
        : unconfirmedBody({ allow_partial: allowPartial })
    }),
  newsBackfillStatus: () =>
    request<BackfillStatusPayload>("/api/backfills/news/status"),
  exportNewsBackfillTemplate: (confirm: boolean) =>
    request<{ result: Record<string, unknown> }>("/api/backfills/news/export-template", {
      method: "POST",
      body: confirm ? confirmedBody({}) : unconfirmedBody({})
    }),
  validateNewsBackfill: () =>
    request<{ validation: Record<string, unknown>; validation_text?: string }>("/api/backfills/news/validate"),
  appendNewsBackfillRow: (requestBody: NewsBackfillAppendRowRequest, confirm: boolean) =>
    request<{ result: Record<string, unknown> }>("/api/backfills/news/append-row", {
      method: "POST",
      body: confirm ? confirmedBody(requestBody) : unconfirmedBody(requestBody)
    }),
  applyNewsBackfill: (confirm: boolean, allowPartial: boolean) =>
    request<BackfillActionPayload>("/api/backfills/news/apply", {
      method: "POST",
      body: confirm
        ? confirmedBody({ allow_partial: allowPartial })
        : unconfirmedBody({ allow_partial: allowPartial })
    }),
  shortInterestBackfillStatus: () =>
    request<BackfillStatusPayload>("/api/backfills/short-interest/status"),
  exportShortInterestBackfillTemplate: (confirm: boolean) =>
    request<{ result: Record<string, unknown> }>("/api/backfills/short-interest/export-template", {
      method: "POST",
      body: confirm ? confirmedBody({}) : unconfirmedBody({})
    }),
  validateShortInterestBackfill: () =>
    request<{ validation: Record<string, unknown>; validation_text?: string }>("/api/backfills/short-interest/validate"),
  appendShortInterestMissingRow: (requestBody: ShortInterestAppendRowRequest, confirm: boolean) =>
    request<{ result: Record<string, unknown> }>("/api/backfills/short-interest/append-row", {
      method: "POST",
      body: confirm ? confirmedBody(requestBody) : unconfirmedBody(requestBody)
    }),
  applyShortInterestBackfill: (confirm: boolean) =>
    request<BackfillActionPayload>("/api/backfills/short-interest/apply", {
      method: "POST",
      body: confirm ? confirmedBody({}) : unconfirmedBody({})
    })
};
