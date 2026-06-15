import React from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  BarChart3,
  Bell,
  Binary,
  Boxes,
  CalendarCheck,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Database,
  Eye,
  FileJson,
  FlaskConical,
  Play,
  Power,
  RefreshCw,
  Search,
  Send,
  Trash2,
  Wrench,
  X
} from "lucide-react";
import {
  tomApi,
  type ApiResponse,
  type Asset,
  type AssetMutationRequest,
  type CoverageGroup,
  type EditableRecommendationStatus,
  type EtfStrategyAlternative,
  type EtfStrategyReviewPayload,
  type ForeignEquitySourcePayload,
  type MissingTickerCandidate,
  type PhaseCoveragePayload,
  type ResearchRecommendation,
  type ResearchPreparationPayload,
  type ResearchRecommendationTriagePayload,
  type ResearchTriageGroup,
  type ResearchTickerPlanPayload,
  type ResearchTickerRequest,
  type ResearchTickerStatusPayload,
  type SignalCoveragePayload,
  type SignalLane
} from "./api/tomApi";
import "./styles.css";

type RouteKey =
  | "overview"
  | "signals"
  | "coverage"
  | "assets"
  | "research"
  | "ops"
  | "loop"
  | "scheduler"
  | "notifications"
  | "activation"
  | "backfills"
  | "options"
  | "dashboard-data";

type LoadState<T> =
  | { status: "loading" }
  | { status: "ready"; value: T }
  | { status: "error"; message: string; warnings: string[] };

type ResearchPreparationAction =
  | "scan"
  | "discover_sources"
  | "stage_source_rows"
  | "load_staged_sources"
  | "compute_ready"
  | "prepare_ready"
  | "ignore_already_scoreable"
  | "all_safe";

type OverviewData = {
  health: Awaited<ReturnType<typeof tomApi.health>>;
  status: Awaited<ReturnType<typeof tomApi.status>>;
  recommendations: Awaited<ReturnType<typeof tomApi.researchRecommendations>>;
  options: Awaited<ReturnType<typeof tomApi.optionsStatus>>;
  provider: Awaited<ReturnType<typeof tomApi.providerStatus>>;
};

const routes: Array<{
  key: RouteKey;
  label: string;
  path: string;
  icon: React.ComponentType<{ size?: number }>;
}> = [
  { key: "overview", label: "Overview", path: "/", icon: Activity },
  { key: "signals", label: "Signals", path: "/signals", icon: BarChart3 },
  { key: "coverage", label: "Coverage", path: "/coverage", icon: Check },
  { key: "assets", label: "Assets", path: "/assets", icon: Boxes },
  { key: "research", label: "Research", path: "/research", icon: FlaskConical },
  { key: "ops", label: "Ops", path: "/ops", icon: Clock },
  { key: "loop", label: "Loop", path: "/loop", icon: Power },
  { key: "scheduler", label: "Scheduler", path: "/scheduler", icon: CalendarCheck },
  { key: "notifications", label: "Notifications", path: "/notifications", icon: Bell },
  { key: "activation", label: "Activation", path: "/activation", icon: Database },
  { key: "backfills", label: "Backfills", path: "/backfills", icon: FileJson },
  { key: "options", label: "Options", path: "/options", icon: Binary },
  { key: "dashboard-data", label: "Dashboard Data", path: "/dashboard-data", icon: FileJson }
];

function routeFromPath(pathname: string): RouteKey {
  const match = routes.find((route) => route.path === pathname);
  return match?.key ?? "overview";
}

function unwrap<T>(response: ApiResponse<T>): T | null {
  return response.ok ? response.data : null;
}

function apiErrorMessage<T>(response: ApiResponse<T>): string | null {
  return response.ok ? null : response.message;
}

function apiWarnings<T>(response: ApiResponse<T>): string[] {
  return response.ok ? response.warnings ?? [] : response.warnings ?? [];
}

function useResource<T>(load: () => Promise<T>, deps: React.DependencyList): LoadState<T> {
  const [state, setState] = React.useState<LoadState<T>>({ status: "loading" });
  React.useEffect(() => {
    let active = true;
    setState({ status: "loading" });
    load()
      .then((value) => {
        if (active) setState({ status: "ready", value });
      })
      .catch((error) => {
        if (!active) return;
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Unknown error",
          warnings: []
        });
      });
    return () => {
      active = false;
    };
  }, deps);
  return state;
}

function Shell() {
  const [route, setRoute] = React.useState<RouteKey>(() => routeFromPath(window.location.pathname));

  React.useEffect(() => {
    const onPopState = () => setRoute(routeFromPath(window.location.pathname));
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = (next: RouteKey) => {
    const target = routes.find((item) => item.key === next);
    if (!target) return;
    window.history.pushState(null, "", target.path);
    setRoute(next);
  };

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary">
        <div className="brand">
          <Database size={22} />
          <div>
            <strong>TOM</strong>
            <span>Control Center</span>
          </div>
        </div>
        <nav>
          {routes.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                className={route === item.key ? "active" : ""}
                type="button"
                onClick={() => navigate(item.key)}
                title={item.label}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="api-base">
          <span>API</span>
          <code>{tomApi.apiBaseUrl}</code>
        </div>
      </aside>
      <main className="workspace">
        {route === "overview" && <OverviewPage />}
        {route === "signals" && <SignalsPage />}
        {route === "coverage" && <CoveragePage />}
        {route === "assets" && <AssetsPage />}
        {route === "research" && <ResearchPage />}
        {route === "ops" && <OpsPage />}
        {route === "loop" && <LoopPage />}
        {route === "scheduler" && <SchedulerPage />}
        {route === "notifications" && <NotificationsPage />}
        {route === "activation" && <ActivationPage />}
        {route === "backfills" && <BackfillsPage />}
        {route === "options" && <OptionsPage />}
        {route === "dashboard-data" && <DashboardDataPage />}
      </main>
    </div>
  );
}

function OverviewPage() {
  const state = useResource<OverviewData>(
    async () => {
      const [health, status, recommendations, options, provider] = await Promise.all([
        tomApi.health(),
        tomApi.status(),
        tomApi.researchRecommendations(),
        tomApi.optionsStatus(),
        tomApi.providerStatus()
      ]);
      return { health, status, recommendations, options, provider };
    },
    []
  );

  return (
    <PageFrame title="Overview" subtitle="Local API, data freshness, recommendations, and provider health.">
      <Resource state={state}>
        {(data) => {
          const health = unwrap(data.health);
          const status = unwrap(data.status);
          const recommendations = unwrap(data.recommendations);
          const provider = unwrap(data.provider);
          const optionProvider = provider?.options as Record<string, unknown> | undefined;
          const allErrors = [
            apiErrorMessage(data.health),
            apiErrorMessage(data.status),
            apiErrorMessage(data.recommendations),
            apiErrorMessage(data.options),
            apiErrorMessage(data.provider)
          ].filter((item): item is string => Boolean(item));
          const warnings = [
            ...apiWarnings(data.health),
            ...apiWarnings(data.status),
            ...apiWarnings(data.recommendations),
            ...apiWarnings(data.options),
            ...apiWarnings(data.provider)
          ];
          return (
            <>
              {allErrors.length > 0 && <Banner tone="danger" items={allErrors} />}
              {warnings.length > 0 && <Banner tone="warning" items={warnings} />}
              <section className="metric-grid">
                <Metric label="API" value={health?.required_tables_present ? "Healthy" : "Check"} detail={`${health?.existing_table_count ?? "-"} tables`} />
                <Metric label="Latest Price" value={status?.latest.price_date ?? "none"} detail="daily close" />
                <Metric label="Latest Quote" value={status?.latest.quote_timestamp ?? "none"} detail="intraday source" />
                <Metric label="Latest Range" value={status?.latest.range_snapshot_timestamp ?? "none"} detail="range monitor" />
                <Metric label="TOM Loop" value={String(status?.loop?.health_status ?? "unknown")} detail={String(status?.loop?.status ?? "loop status")} />
                <Metric label="Pending Research" value={String(recommendations?.count ?? 0)} detail="queue rows" />
                <Metric label="Notifications" value={String(status?.pending_notifications ?? 0)} detail="pending local events" />
                <Metric label="Option Chains" value={String(optionProvider?.chain_rows ?? "-")} detail={String(optionProvider?.readiness_status ?? "provider")} />
                <Metric label="Provider Blocker" value={String(optionProvider?.blocked_reason ?? "none")} detail="options provider" />
              </section>
            </>
          );
        }}
      </Resource>
    </PageFrame>
  );
}

function SignalsPage() {
  const [selectedKey, setSelectedKey] = React.useState("analyst_revisions");
  const state = useResource(() => tomApi.signalCoverage(), []);

  return (
    <PageFrame title="Signals" subtitle="Signal lane readiness, source blockers, and evidence state.">
      <Resource state={state}>
        {(response) => {
          if (!response.ok) return <Offline message={response.message} warnings={response.warnings} />;
          const data: SignalCoveragePayload = response.data;
          const selected = data.lane_map[selectedKey] ?? data.lanes[0] ?? null;
          const blockerCount = data.lanes.reduce((total, lane) => total + lane.blockers.length, 0);
          const warningCount = data.lanes.reduce((total, lane) => total + lane.warnings.length, 0);
          return (
            <>
              <section className="metric-grid">
                <Metric label="Overall" value={labelize(data.status)} detail="lane readiness" />
                <Metric label="Lanes" value={String(data.lanes.length)} detail={statusCountsText(data.status_counts)} />
                <Metric label="Blockers" value={String(blockerCount)} detail="source and gate codes" />
                <Metric label="Warnings" value={String(warningCount)} detail={data.generated_at} />
              </section>
              <div className="split-panel">
                <section className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Lane</th>
                        <th>Status</th>
                        <th>Coverage</th>
                        <th>Blockers</th>
                        <th>Warnings</th>
                        <th>Notes</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.lanes.map((lane) => (
                        <tr
                          key={lane.key}
                          className={selected?.key === lane.key ? "selected-row" : ""}
                          onClick={() => setSelectedKey(lane.key)}
                        >
                          <td><strong>{lane.label}</strong></td>
                          <td><StatusPill value={lane.status} /></td>
                          <td>{lane.coverage_label}</td>
                          <td>{listText(lane.blockers)}</td>
                          <td>{listText(lane.warnings)}</td>
                          <td>{listText(lane.notes)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
                <SignalLaneDetail lane={selected} />
              </div>
            </>
          );
        }}
      </Resource>
    </PageFrame>
  );
}

function SignalLaneDetail({ lane }: { lane: SignalLane | null }) {
  if (!lane) return <aside className="detail-panel empty">No signal lane selected.</aside>;
  return (
    <aside className="detail-panel">
      <header>
        <div>
          <span>{lane.key}</span>
          <h2>{lane.label}</h2>
        </div>
        <StatusPill value={lane.status} />
      </header>
      <dl>
        <dt>Coverage</dt>
        <dd>{lane.coverage_label}</dd>
        <dt>Blockers</dt>
        <dd>{listText(lane.blockers)}</dd>
        <dt>Warnings</dt>
        <dd>{listText(lane.warnings)}</dd>
        <dt>Notes</dt>
        <dd>{listText(lane.notes)}</dd>
      </dl>
      <KeyValueList values={lane.counts} />
      <CommandList commands={lane.commands} />
      {lane.status_text && <pre className="text-report compact-report">{lane.status_text}</pre>}
    </aside>
  );
}

function CoveragePage() {
  const [selectedKey, setSelectedKey] = React.useState("operational_freshness");
  const state = useResource(() => tomApi.phaseCoverage(), []);

  return (
    <PageFrame title="Coverage" subtitle="Phase readiness by operational gap type.">
      <Resource state={state}>
        {(response) => {
          if (!response.ok) return <Offline message={response.message} warnings={response.warnings} />;
          const data: PhaseCoveragePayload = response.data;
          const selected = data.group_map[selectedKey] ?? data.groups[0] ?? null;
          const blockerCount = data.groups.reduce((total, group) => total + group.blockers.length, 0);
          const warningCount = data.groups.reduce((total, group) => total + group.warnings.length, 0);
          return (
            <>
              <section className="metric-grid">
                <Metric label="Overall" value={labelize(data.status)} detail="phase readiness" />
                <Metric label="Groups" value={String(data.groups.length)} detail={statusCountsText(data.status_counts)} />
                <Metric label="Blockers" value={String(blockerCount)} detail="visible in matrix" />
                <Metric label="Warnings" value={String(warningCount)} detail={data.generated_at} />
              </section>
              <div className="split-panel">
                <section className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Group</th>
                        <th>Status</th>
                        <th>Summary</th>
                        <th>Blockers</th>
                        <th>Warnings</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.groups.map((group) => (
                        <tr
                          key={group.key}
                          className={selected?.key === group.key ? "selected-row" : ""}
                          onClick={() => setSelectedKey(group.key)}
                        >
                          <td><strong>{group.label}</strong></td>
                          <td><StatusPill value={group.status} /></td>
                          <td>{group.summary}</td>
                          <td>{listText(group.blockers)}</td>
                          <td>{listText(group.warnings)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </section>
                <CoverageGroupDetail group={selected} />
              </div>
            </>
          );
        }}
      </Resource>
    </PageFrame>
  );
}

function CoverageGroupDetail({ group }: { group: CoverageGroup | null }) {
  if (!group) return <aside className="detail-panel empty">No coverage group selected.</aside>;
  const optionAvailability = recordArrayValue(group.details, "option_chain_availability_statuses");
  return (
    <aside className="detail-panel">
      <header>
        <div>
          <span>{group.key}</span>
          <h2>{group.label}</h2>
        </div>
        <StatusPill value={group.status} />
      </header>
      <dl>
        <dt>Summary</dt>
        <dd>{group.summary}</dd>
        <dt>Blockers</dt>
        <dd>{listText(group.blockers)}</dd>
        <dt>Warnings</dt>
        <dd>{listText(group.warnings)}</dd>
        <dt>Notes</dt>
        <dd>{listText(group.notes)}</dd>
      </dl>
      <KeyValueList values={group.counts} />
      {optionAvailability.length > 0 && <OptionChainAvailabilityTable statuses={optionAvailability} compact />}
      <CommandList commands={group.commands} />
    </aside>
  );
}

function AssetsPage() {
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [selectedTicker, setSelectedTicker] = React.useState("");
  const [assetStatus, setAssetStatus] = React.useState<ApiResponse<unknown> | null>(null);
  const [form, setForm] = React.useState<AssetMutationRequest>({
    ticker: "",
    asset_type: "equity",
    asset_role: "scoreable",
    currency: "USD",
    country: "US"
  });
  const [confirmAction, setConfirmAction] = React.useState<ConfirmAction | null>(null);
  const [notice, setNotice] = React.useState<ActionNotice | null>(null);
  const state = useResource(() => tomApi.assets(), [refreshKey]);

  const loadAssetStatus = async (ticker: string) => {
    if (!ticker) return;
    setSelectedTicker(ticker);
    const response = await tomApi.assetStatus(ticker);
    setAssetStatus(response as ApiResponse<unknown>);
  };

  const runConfirmedAction = async () => {
    if (!confirmAction) return;
    const action = confirmAction;
    setConfirmAction(null);
    const response = await action.run();
    if (response.ok) {
      setNotice({
        tone: "success",
        title: "Action completed",
        message: action.title,
        details: response.warnings
      });
      setRefreshKey((value) => value + 1);
      if (selectedTicker) await loadAssetStatus(selectedTicker);
    } else {
      setNotice({
        tone: "danger",
        title: response.error_code,
        message: response.message,
        details: response.warnings
      });
    }
  };

  const selectedAssetFromList = (assets: Asset[]) =>
    assets.find((asset) => asset.ticker === selectedTicker) ?? assets[0] ?? null;

  const requestAssetAction = (
    title: string,
    message: string,
    confirmLabel: string,
    run: () => Promise<ApiResponse<unknown>>
  ) => {
    setConfirmAction({ title, message, confirmLabel, run });
  };

  const cleanAssetForm = (): AssetMutationRequest => {
    const request: AssetMutationRequest = {
      ticker: (form.ticker || "").trim().toUpperCase(),
      asset_type: form.asset_type || "equity",
      asset_role: form.asset_role || "scoreable",
      currency: form.currency || "USD",
      country: form.country || "US"
    };
    for (const key of ["name", "exchange", "sector", "industry", "cik", "reason"] as const) {
      const value = form[key]?.trim();
      if (value) request[key] = value;
    }
    return request;
  };

  return (
    <PageFrame title="Assets" subtitle="Scoreable, reference, active, and inactive instruments with confirmation-gated controls.">
      {notice && <ActionNoticeView notice={notice} onDismiss={() => setNotice(null)} />}
      <Resource state={state}>
        {(response) => {
          if (!response.ok) return <Offline message={response.message} warnings={response.warnings} />;
          const assets = response.data.assets;
          const selected = selectedAssetFromList(assets);
          return (
            <div className="assets-layout">
              <section className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Role</th>
                      <th>Active</th>
                      <th>Sector</th>
                      <th>Industry</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assets.map((asset: Asset) => (
                      <tr
                        key={`${asset.ticker}-${asset.asset_role}`}
                        className={asset.ticker === selected?.ticker ? "selected-row" : ""}
                        onClick={() => void loadAssetStatus(asset.ticker)}
                      >
                        <td><strong>{asset.ticker}</strong></td>
                        <td>{asset.name ?? ""}</td>
                        <td>{asset.asset_type ?? ""}</td>
                        <td><StatusPill value={asset.asset_role} /></td>
                        <td>{asset.active_flag ? "Yes" : "No"}</td>
                        <td>{asset.sector ?? ""}</td>
                        <td>{asset.industry ?? ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
              <aside className="asset-control-stack">
                <section className="detail-panel">
                  <header>
                    <div>
                      <span>Asset detail</span>
                      <h2>{selected?.ticker ?? "None"}</h2>
                    </div>
                    {selected && <StatusPill value={selected.asset_role} />}
                  </header>
                  {selected ? (
                    <>
                      <dl>
                        <dt>Name</dt>
                        <dd>{selected.name || "none"}</dd>
                        <dt>Type</dt>
                        <dd>{selected.asset_type || "none"}</dd>
                        <dt>Active</dt>
                        <dd>{selected.active_flag ? "Yes" : "No"}</dd>
                        <dt>Sector</dt>
                        <dd>{selected.sector || "none"}</dd>
                        <dt>Industry</dt>
                        <dd>{selected.industry || "none"}</dd>
                      </dl>
                      <div className="button-row">
                        <button type="button" onClick={() => void loadAssetStatus(selected.ticker)}><Eye size={15} /> Status</button>
                        <button
                          type="button"
                          onClick={() =>
                            requestAssetAction(
                              `Deactivate ${selected.ticker}`,
                              "This soft-deactivates the asset from active monitoring while preserving historical rows.",
                              "Deactivate",
                              () => tomApi.deactivateAsset(selected.ticker, "phase14d_ui_deactivate", true) as Promise<ApiResponse<unknown>>
                            )
                          }
                        >
                          <X size={15} /> Deactivate
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            requestAssetAction(
                              `Reactivate ${selected.ticker}`,
                              "This reactivates the asset through TOM's existing asset workflow.",
                              "Reactivate",
                              () => tomApi.reactivateAsset(selected.ticker, "phase14d_ui_reactivate", true) as Promise<ApiResponse<unknown>>
                            )
                          }
                        >
                          <Check size={15} /> Reactivate
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            requestAssetAction(
                              `Soft remove ${selected.ticker}`,
                              "This is a soft remove only. Historical TOM rows remain intact.",
                              "Soft remove",
                              () => tomApi.removeAsset(selected.ticker, "phase14d_ui_soft_remove", true) as Promise<ApiResponse<unknown>>
                            )
                          }
                        >
                          <Trash2 size={15} /> Remove
                        </button>
                      </div>
                      {assetStatus && <ApiResult title="Asset Status" response={assetStatus} />}
                    </>
                  ) : (
                    <span>Select an asset to inspect or manage it.</span>
                  )}
                </section>
                <section className="form-panel">
                  <h2>Add or Update</h2>
                  <div className="form-grid">
                    <Field label="Ticker" value={form.ticker} onChange={(value) => setForm({ ...form, ticker: value.toUpperCase() })} />
                    <Field label="Name" value={form.name ?? ""} onChange={(value) => setForm({ ...form, name: value })} />
                    <Field label="Asset Type" value={form.asset_type ?? ""} onChange={(value) => setForm({ ...form, asset_type: value })} />
                    <Field label="Asset Role" value={form.asset_role ?? ""} onChange={(value) => setForm({ ...form, asset_role: value })} />
                    <Field label="Exchange" value={form.exchange ?? ""} onChange={(value) => setForm({ ...form, exchange: value })} />
                    <Field label="Currency" value={form.currency ?? ""} onChange={(value) => setForm({ ...form, currency: value })} />
                    <Field label="Sector" value={form.sector ?? ""} onChange={(value) => setForm({ ...form, sector: value })} />
                    <Field label="Industry" value={form.industry ?? ""} onChange={(value) => setForm({ ...form, industry: value })} />
                    <Field label="Country" value={form.country ?? ""} onChange={(value) => setForm({ ...form, country: value })} />
                    <Field label="CIK" value={form.cik ?? ""} onChange={(value) => setForm({ ...form, cik: value })} />
                    <Field label="Reason" value={form.reason ?? ""} onChange={(value) => setForm({ ...form, reason: value })} />
                  </div>
                  <button
                    type="button"
                    disabled={!cleanAssetForm().ticker}
                    onClick={() =>
                      requestAssetAction(
                        `Add or update ${cleanAssetForm().ticker}`,
                        "This writes through TOM's watchlist, assets table, optional CIK map, and asset-change audit trail.",
                        "Add or update",
                        () => tomApi.addAsset(cleanAssetForm(), true) as Promise<ApiResponse<unknown>>
                      )
                    }
                  >
                    <Check size={15} /> Add or Update
                  </button>
                </section>
              </aside>
            </div>
          );
        }}
      </Resource>
      <ConfirmDialog action={confirmAction} onCancel={() => setConfirmAction(null)} onConfirm={runConfirmedAction} />
    </PageFrame>
  );
}

function OpsPage() {
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [confirmAction, setConfirmAction] = React.useState<ConfirmAction | null>(null);
  const [notice, setNotice] = React.useState<ActionNotice | null>(null);
  const state = useResource(
    async () => {
      const [status, health] = await Promise.all([
        tomApi.intradayStatus(),
        tomApi.intradayHealth()
      ]);
      return { status, health };
    },
    [refreshKey]
  );

  const runConfirmedAction = async () => {
    if (!confirmAction) return;
    const action = confirmAction;
    setConfirmAction(null);
    const response = await action.run();
    if (response.ok) {
      setNotice({ tone: "success", title: "Action completed", message: action.title, details: response.warnings });
      setRefreshKey((value) => value + 1);
    } else {
      setNotice({ tone: "danger", title: response.error_code, message: response.message, details: response.warnings });
    }
  };

  return (
    <PageFrame title="Ops" subtitle="One-shot intraday and manual TOM operations. Use Loop for persistent local operation.">
      {notice && <ActionNoticeView notice={notice} onDismiss={() => setNotice(null)} />}
      <Resource state={state}>
        {(data) => {
          if (!data.status.ok) return <Offline message={data.status.message} warnings={data.status.warnings} />;
          const payload = data.status.data;
          const health = payload.health as Record<string, unknown> | undefined;
          return (
            <>
              <section className="metric-grid">
                <Metric label="Intraday Health" value={String(health?.status ?? "unknown")} detail="health classification" />
                <Metric label="Latest Quote" value={String(payload.latest_quote_timestamp ?? "none")} detail="quote freshness" />
                <Metric label="Latest Range" value={String(payload.latest_range_snapshot_timestamp ?? "none")} detail="range monitor" />
                <Metric label="Pending Alerts" value={String(payload.pending_notifications ?? 0)} detail="notification events" />
              </section>
              <section className="control-strip">
                <button
                  type="button"
                  onClick={() =>
                    setConfirmAction({
                      title: "Run intraday cycle",
                      message: "Runs the one-shot auto-source intraday cycle with drain-first file delivery. It does not place orders.",
                      confirmLabel: "Run cycle",
                      run: () =>
                        tomApi.runIntradayCycle(
                          { source: "auto", drain_first: true, deliver: true, channel: "file" },
                          true
                        ) as Promise<ApiResponse<unknown>>
                    })
                  }
                >
                  <Play size={16} /> Intraday Cycle
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setConfirmAction({
                      title: "Run manual ops cycle",
                      message: "Runs one auto-mode manual ops cycle with file delivery. It does not start the never-ending loop.",
                      confirmLabel: "Run manual ops",
                      run: () =>
                        tomApi.runManualOpsCycle(
                          { mode: "auto", deliver: true, channel: "file" },
                          true
                        ) as Promise<ApiResponse<unknown>>
                    })
                  }
                >
                  <Wrench size={16} /> Manual Ops Cycle
                </button>
                <button type="button" onClick={() => setRefreshKey((value) => value + 1)}>
                  <RefreshCw size={16} /> Refresh Status
                </button>
              </section>
              <section className="operator-command">
                <span>Persistent operator command</span>
                <code>python -m target_opportunity_monitor tom-loop-start --mode auto --deliver --channel file</code>
              </section>
              <div className="two-column">
                <pre className="text-report">{String(payload.status_text ?? "")}</pre>
                <pre className="text-report">{String(payload.manual_ops_status_text ?? "")}</pre>
              </div>
            </>
          );
        }}
      </Resource>
      <ConfirmDialog action={confirmAction} onCancel={() => setConfirmAction(null)} onConfirm={runConfirmedAction} />
    </PageFrame>
  );
}

function LoopPage() {
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [confirmAction, setConfirmAction] = React.useState<ConfirmAction | null>(null);
  const [notice, setNotice] = React.useState<ActionNotice | null>(null);
  const state = useResource(
    async () => {
      const [status, health] = await Promise.all([
        tomApi.loopStatus(),
        tomApi.loopHealth()
      ]);
      return { status, health };
    },
    [refreshKey]
  );

  const runConfirmedAction = async () => {
    if (!confirmAction) return;
    const action = confirmAction;
    setConfirmAction(null);
    const response = await action.run();
    if (response.ok) {
      setNotice({ tone: "success", title: "Action completed", message: action.title, details: response.warnings });
      setRefreshKey((value) => value + 1);
    } else {
      setNotice({ tone: "danger", title: response.error_code, message: response.message, details: response.warnings });
    }
  };

  return (
    <PageFrame title="TOM Loop" subtitle="Persistent local operations loop with lockfile, heartbeat, and cooperative stop control.">
      {notice && <ActionNoticeView notice={notice} onDismiss={() => setNotice(null)} />}
      <Resource state={state}>
        {(data) => {
          if (!data.status.ok) return <Offline message={data.status.message} warnings={data.status.warnings} />;
          if (!data.health.ok) return <Offline message={data.health.message} warnings={data.health.warnings} />;
          const loop = data.status.data.loop;
          const healthLoop = data.health.data.loop;
          return (
            <>
              <section className="metric-grid">
                <Metric label="Loop Health" value={String(loop.health_status ?? "unknown")} detail="persistent loop" />
                <Metric label="Loop Status" value={String(loop.status ?? "unknown")} detail={loop.active ? "active" : "not active"} />
                <Metric label="Heartbeat Age" value={String(loop.heartbeat_age_seconds ?? "none")} detail="seconds" />
                <Metric label="Recovery" value={String(loop.recovery_status ?? "none")} detail={listText(loop.recommended_actions)} />
                <Metric label="PID" value={String(loop.pid ?? "none")} detail="local process" />
                <Metric label="Latest Quote" value={String(loop.quote_timestamp ?? "none")} detail="freshness" />
                <Metric label="Latest Range" value={String(loop.range_snapshot_timestamp ?? "none")} detail="range snapshot" />
                <Metric label="Pending Alerts" value={String(loop.pending_notifications ?? 0)} detail="notification events" />
                <Metric label="Failed Deliveries" value={String(loop.failed_deliveries ?? 0)} detail="delivery rows" />
              </section>
              <section className="control-strip">
                <button
                  type="button"
                  onClick={() =>
                    setConfirmAction({
                      title: "Start TOM loop",
                      message: "Starts a local persistent loop in the API process using auto mode and file delivery. It remains read-only and does not place orders.",
                      confirmLabel: "Start loop",
                      run: () =>
                        tomApi.startLoop(
                          { mode: "auto", deliver: true, channel: "file" },
                          true
                        ) as Promise<ApiResponse<unknown>>
                    })
                  }
                >
                  <Play size={16} /> Start
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setConfirmAction({
                      title: loop.stale_lock ? "Clear stale loop lock" : "Stop TOM loop",
                      message: loop.stale_lock
                        ? "Clears the stale loop lock. This does not start the loop, run a cycle, place trades, or change TOM scores."
                        : "Requests the running TOM loop to stop after its current cycle or sleep interval. Stale locks are cleared when no active loop is found.",
                      confirmLabel: loop.stale_lock ? "Clear stale lock" : "Stop loop",
                      run: () => tomApi.stopLoop(true) as Promise<ApiResponse<unknown>>
                    })
                  }
                >
                  <X size={16} /> {loop.stale_lock ? "Clear Stale Lock" : "Stop"}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setConfirmAction({
                      title: "Run TOM loop once",
                      message: "Runs one safe auto-mode loop cycle with file delivery, then stops. This is the safest manual freshness recovery action.",
                      confirmLabel: "Run once",
                      run: () =>
                        tomApi.runLoopOnce(
                          { mode: "auto", deliver: true, channel: "file" },
                          true
                        ) as Promise<ApiResponse<unknown>>
                    })
                  }
                >
                  <RefreshCw size={16} /> Run Once
                </button>
                <button type="button" onClick={() => setRefreshKey((value) => value + 1)}>
                  <Eye size={16} /> Refresh
                </button>
              </section>
              {loop.stale_lock && (
                <section className="recovery-panel">
                  <header>
                    <div>
                      <span>Stale Lock Recovery</span>
                      <h2>{String(loop.recovery_status ?? "stale_lock_clearable")}</h2>
                    </div>
                    <StatusPill value={String(loop.health_status ?? "blocked")} />
                  </header>
                  <dl>
                    <dt>Actions</dt>
                    <dd>{listText(loop.recommended_actions)}</dd>
                    <dt>Heartbeat Age</dt>
                    <dd>{String(loop.heartbeat_age_seconds ?? "unknown")}</dd>
                    <dt>Clear Command</dt>
                    <dd><code>{String(loop.clear_stale_lock_command ?? "python -m target_opportunity_monitor tom-loop-stop")}</code></dd>
                    <dt>Start Command</dt>
                    <dd><code>{String(loop.recommended_command ?? "python -m target_opportunity_monitor tom-loop-start --mode auto --deliver --channel file")}</code></dd>
                    <dt>Notes</dt>
                    <dd>{listText(loop.recovery_notes)}</dd>
                  </dl>
                  <div className="button-row">
                    <button
                      type="button"
                      onClick={() =>
                        setConfirmAction({
                          title: "Clear stale loop lock",
                          message: "Clears the stale loop lock only. Use Start or Run Once separately after reviewing the refreshed status.",
                          confirmLabel: "Clear stale lock",
                          run: () => tomApi.stopLoop(true) as Promise<ApiResponse<unknown>>
                        })
                      }
                    >
                      <X size={15} /> Clear Stale Lock
                    </button>
                  </div>
                </section>
              )}
              <section className="operator-command">
                <span>Durable foreground command</span>
                <code>{String(loop.recommended_command ?? "python -m target_opportunity_monitor tom-loop-start --mode auto --deliver --channel file")}</code>
              </section>
              <section className="operator-command">
                <span>One-shot recovery command</span>
                <code>{String(loop.run_once_command ?? "python -m target_opportunity_monitor tom-loop-once --mode auto --deliver --channel file")}</code>
              </section>
              <div className="two-column">
                <pre className="text-report">{String(data.status.data.status_text ?? "")}</pre>
                <pre className="text-report">{String(data.health.data.health_text ?? "")}</pre>
              </div>
              <ApiResult title="Loop Snapshot JSON" response={{ ok: true, data: { loop, health: healthLoop } }} />
            </>
          );
        }}
      </Resource>
      <ConfirmDialog action={confirmAction} onCancel={() => setConfirmAction(null)} onConfirm={runConfirmedAction} />
    </PageFrame>
  );
}

function SchedulerPage() {
  const state = useResource(
    async () => {
      const [status, audit] = await Promise.all([
        tomApi.schedulerStatus(),
        tomApi.schedulerAudit()
      ]);
      return { status, audit };
    },
    []
  );
  return (
    <PageFrame title="Scheduler" subtitle="Codex scheduler reconciliation and recommended commands. This page does not mutate automations.">
      <Resource state={state}>
        {(data) => {
          if (!data.status.ok) return <Offline message={data.status.message} warnings={data.status.warnings} />;
          const payload = data.status.data;
          const audit = payload.audit as Record<string, unknown> | undefined;
          const health = payload.health as Record<string, unknown> | undefined;
          const heartbeat = payload.heartbeat_job as Record<string, unknown> | null | undefined;
          return (
            <>
              <section className="metric-grid">
                <Metric label="Reconciliation" value={String(audit?.status ?? "unknown")} detail="scheduler audit" />
                <Metric label="Intraday Health" value={String(health?.status ?? "unknown")} detail="ops health" />
                <Metric label="Heartbeat" value={String(heartbeat?.status ?? "none")} detail={String(heartbeat?.automation_id ?? "automation id")} />
                <Metric label="Pending Alerts" value={String(payload.pending_notifications ?? 0)} detail="notification events" />
              </section>
              <section className="operator-command">
                <span>Intended heartbeat command</span>
                <code>python -m target_opportunity_monitor intraday-cycle --source auto --deliver --channel file</code>
              </section>
              <div className="three-column">
                <pre className="text-report">{String(payload.audit_text ?? "")}</pre>
                <pre className="text-report">{String(payload.repair_plan_text ?? "")}</pre>
                <pre className="text-report">{String(payload.automation_status_text ?? "")}</pre>
              </div>
              {data.audit.ok && <ApiResult title="Scheduler Audit JSON" response={data.audit} />}
            </>
          );
        }}
      </Resource>
    </PageFrame>
  );
}

function NotificationsPage() {
  const [filter, setFilter] = React.useState("pending");
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [confirmAction, setConfirmAction] = React.useState<ConfirmAction | null>(null);
  const [notice, setNotice] = React.useState<ActionNotice | null>(null);
  const state = useResource(
    async () => {
      const [status, report, outbox] = await Promise.all([
        tomApi.notificationsStatus(filter === "all" ? undefined : filter),
        tomApi.notificationDeliveryReport(),
        tomApi.notificationOutboxStatus()
      ]);
      return { status, report, outbox };
    },
    [filter, refreshKey]
  );

  const runConfirmedAction = async () => {
    if (!confirmAction) return;
    const action = confirmAction;
    setConfirmAction(null);
    const response = await action.run();
    if (response.ok) {
      setNotice({ tone: "success", title: "Action completed", message: action.title, details: response.warnings });
      setRefreshKey((value) => value + 1);
    } else {
      setNotice({ tone: "danger", title: response.error_code, message: response.message, details: response.warnings });
    }
  };

  return (
    <PageFrame title="Notifications" subtitle="Local notification event status, file outbox, and confirmation-gated drain controls.">
      <div className="toolbar">
        {["pending", "delivered", "delivery_failed", "all"].map((value) => (
          <button key={value} type="button" className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>
            {value}
          </button>
        ))}
      </div>
      {notice && <ActionNoticeView notice={notice} onDismiss={() => setNotice(null)} />}
      <Resource state={state}>
        {(data) => {
          if (!data.status.ok) return <Offline message={data.status.message} warnings={data.status.warnings} />;
          const payload = data.status.data;
          return (
            <>
              <section className="metric-grid">
                <Metric label="Filtered Events" value={String(payload.count ?? 0)} detail={filter} />
                <Metric label="Pending" value={String(payload.pending_count ?? 0)} detail="event rows" />
                <Metric label="Delivered" value={String(payload.delivered_delivery_count ?? 0)} detail="delivery rows" />
                <Metric label="Failed" value={String(payload.failed_delivery_count ?? 0)} detail="delivery rows" />
              </section>
              <section className="control-strip">
                <button
                  type="button"
                  onClick={() =>
                    setConfirmAction({
                      title: "Drain pending notifications",
                      message: "Delivers pending local notification events to the file outbox and records delivery audit rows.",
                      confirmLabel: "Drain to file",
                      run: () => tomApi.drainNotifications("file", true) as Promise<ApiResponse<unknown>>
                    })
                  }
                >
                  <Send size={16} /> Drain to File
                </button>
                <button type="button" onClick={() => setRefreshKey((value) => value + 1)}>
                  <RefreshCw size={16} /> Refresh Status
                </button>
              </section>
              <div className="two-column">
                <pre className="text-report">{data.report.ok ? data.report.data.report_text ?? "" : data.report.message}</pre>
                <pre className="text-report">{data.outbox.ok ? data.outbox.data.status_text ?? "" : data.outbox.message}</pre>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Ticker</th>
                      <th>Timestamp</th>
                      <th>Type</th>
                      <th>Severity</th>
                      <th>State</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payload.events.map((event) => (
                      <tr key={String(event.notification_event_id)}>
                        <td>{String(event.notification_event_id ?? "")}</td>
                        <td><strong>{String(event.ticker ?? "")}</strong></td>
                        <td>{String(event.event_timestamp ?? "")}</td>
                        <td>{String(event.event_type ?? "")}</td>
                        <td>{String(event.severity ?? "")}</td>
                        <td><StatusPill value={String(event.status ?? "unknown")} /></td>
                        <td>{String(event.reason_codes ?? "")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          );
        }}
      </Resource>
      <ConfirmDialog action={confirmAction} onCancel={() => setConfirmAction(null)} onConfirm={runConfirmedAction} />
    </PageFrame>
  );
}

type AccountRowForms = {
  portfolio: Record<string, string>;
  cash: Record<string, string>;
  option: Record<string, string>;
};

function ActivationPage() {
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [allowPartial, setAllowPartial] = React.useState(true);
  const [accountFetchSource, setAccountFetchSource] = React.useState<"file" | "ibkr">("file");
  const [accountProvider, setAccountProvider] = React.useState("generic");
  const [accountFile, setAccountFile] = React.useState("");
  const [notice, setNotice] = React.useState<ActionNotice | null>(null);
  const [confirmAction, setConfirmAction] = React.useState<ConfirmAction | null>(null);
  const [forms, setForms] = React.useState<AccountRowForms>({
    portfolio: {
      ticker: "",
      quantity: "",
      account: "manual",
      position_date: "",
      currency: "USD",
      source: "ui_manual"
    },
    cash: {
      account: "manual",
      cash_date: "",
      currency: "USD",
      cash_amount: "",
      source: "ui_manual"
    },
    option: {
      ticker: "",
      open_date: "",
      expiration_date: "",
      option_type: "put",
      side: "short_put",
      strike: "",
      contracts: "",
      premium: "",
      account: "manual",
      status: "open",
      source: "ui_manual"
    }
  });
  const state = useResource(() => tomApi.accountContextStatus(), [refreshKey]);
  const providerState = useResource(() => tomApi.accountProviderStatus(), [refreshKey]);

  const runConfirmedAction = async () => {
    if (!confirmAction) return;
    const action = confirmAction;
    setConfirmAction(null);
    const response = await action.run();
    if (response.ok) {
      setNotice({ tone: "success", title: "Action completed", message: action.title, details: response.warnings });
      setRefreshKey((value) => value + 1);
    } else {
      setNotice({ tone: "danger", title: response.error_code, message: response.message, details: response.warnings });
    }
  };

  const runReadOnlyAction = async (title: string, action: () => Promise<ApiResponse<unknown>>) => {
    const response = await action();
    if (response.ok) {
      setNotice({ tone: "success", title, message: "Read-only check completed.", details: response.warnings });
    } else {
      setNotice({ tone: "danger", title: response.error_code, message: response.message, details: response.warnings });
    }
    setRefreshKey((value) => value + 1);
  };

  const appendRowAction = (
    label: string,
    rowType: "portfolio_position" | "portfolio_cash" | "option_position",
    row: Record<string, string>
  ) => {
    setConfirmAction({
      title: `Append ${label}`,
      message: "This appends a source-export row only. TOM still requires validate, preview, and apply before it becomes active account context.",
      confirmLabel: "Append row",
      run: () =>
        tomApi.appendAccountContextRow({ row_type: rowType, row }, true) as Promise<ApiResponse<unknown>>
    });
  };

  const requireAccountFile = () => {
    if (!accountFile.trim()) {
      setNotice({
        tone: "danger",
        title: "Missing file",
        message: "Enter a local account export path before running this action."
      });
      return false;
    }
    return true;
  };

  return (
    <PageFrame title="Activation" subtitle="Account, portfolio, cash, and option-position activation from source-export rows.">
      {notice && <ActionNoticeView notice={notice} onDismiss={() => setNotice(null)} />}
      <Resource state={state}>
        {(response) => {
          if (!response.ok) return <Offline message={response.message} warnings={response.warnings} />;
          const payload = response.data;
          const status = payload.status;
          const preview = payload.preview;
          const validation = payload.validation;
          const optionDiagnostics =
            payload.option_position_diagnostics ??
            (status.option_position_diagnostics as Record<string, unknown> | undefined) ??
            {};
          return (
            <>
              <section className="metric-grid">
                <Metric label="Activation" value={textValue(status, "activation_status")} detail="account context" />
                <Metric label="Portfolio Rows" value={textValue(status, "portfolio_position_rows", "0")} detail="positions" />
                <Metric label="Cash Rows" value={textValue(status, "portfolio_cash_rows", "0")} detail="cash" />
                <Metric label="Option Positions" value={textValue(status, "option_position_rows", "0")} detail="manual ledger" />
                <Metric label="Lifecycle Rows" value={textValue(status, "option_lifecycle_rows", "0")} detail="option lifecycle" />
                <Metric label="Missing Context Risk" value={textValue(status, "option_risk_missing_portfolio_context_rows", "0")} detail="risk rows" />
                <Metric label="Valid Backfill" value={textValue(validation, "valid_rows", "0")} detail="source-export rows" />
                <Metric label="Blocked Reason" value={textValue(preview, "blocked_reason")} detail="preview" />
              </section>
              <section className="detail-panel">
                <header>
                  <div>
                    <span>Option Position Readiness</span>
                    <h2>{textValue(optionDiagnostics, "readiness_status", "source_data_required")}</h2>
                  </div>
                  <StatusPill value={textValue(optionDiagnostics, "readiness_status", "source_data_required")} />
                </header>
                <dl>
                  <dt>Current Rows</dt>
                  <dd>
                    {textValue(optionDiagnostics, "current_option_position_rows", "0")} positions /{" "}
                    {textValue(optionDiagnostics, "current_option_lifecycle_rows", "0")} lifecycle
                  </dd>
                  <dt>Staged Rows</dt>
                  <dd>
                    {textValue(optionDiagnostics, "valid_option_position_rows", "0")} valid /{" "}
                    {textValue(optionDiagnostics, "invalid_option_position_rows", "0")} invalid /{" "}
                    {textValue(optionDiagnostics, "blank_option_position_rows", "0")} blank
                  </dd>
                  <dt>Projected Rows</dt>
                  <dd>
                    {textValue(optionDiagnostics, "projected_option_position_rows", "0")} positions /{" "}
                    {textValue(optionDiagnostics, "projected_option_lifecycle_rows", "0")} lifecycle
                  </dd>
                  <dt>Valid Tickers</dt>
                  <dd>{listValue(optionDiagnostics, "valid_option_tickers")}</dd>
                  <dt>Blockers</dt>
                  <dd>{listValue(optionDiagnostics, "blockers")}</dd>
                  <dt>Actions</dt>
                  <dd>{listValue(optionDiagnostics, "recommended_actions")}</dd>
                  <dt>Required Fields</dt>
                  <dd>{listValue(optionDiagnostics, "required_fields")}</dd>
                  <dt>Append Target</dt>
                  <dd><code>{textValue(optionDiagnostics, "append_target_path")}</code></dd>
                  <dt>Template</dt>
                  <dd><code>{textValue(optionDiagnostics, "template_path")}</code></dd>
                </dl>
              </section>
              <MissingTickerPanel context="activation" />
              <section className="control-strip">
                <label className="check-row">
                  <input checked={allowPartial} type="checkbox" onChange={(event) => setAllowPartial(event.target.checked)} />
                  Allow partial apply
                </label>
                <button
                  type="button"
                  onClick={() =>
                    setConfirmAction({
                      title: "Export account templates",
                      message: "This creates or refreshes fillable account-context template files under TOM's source-export directory.",
                      confirmLabel: "Export templates",
                      run: () => tomApi.exportAccountContextTemplate(true) as Promise<ApiResponse<unknown>>
                    })
                  }
                >
                  <FileJson size={16} /> Export Templates
                </button>
                <button type="button" onClick={() => void runReadOnlyAction("Validate account backfill", () => tomApi.validateAccountContextBackfill() as Promise<ApiResponse<unknown>>)}>
                  <Eye size={16} /> Validate
                </button>
                <button type="button" onClick={() => void runReadOnlyAction("Preview account activation", () => tomApi.previewAccountContextActivation() as Promise<ApiResponse<unknown>>)}>
                  <Search size={16} /> Preview
                </button>
                <button type="button" onClick={() => void runReadOnlyAction("Dry-run apply account context", () => tomApi.applyAccountContextBackfill(false, allowPartial, true) as Promise<ApiResponse<unknown>>)}>
                  <Play size={16} /> Dry Run Apply
                </button>
                <button
                  type="button"
                  onClick={() =>
                    setConfirmAction({
                      title: "Apply account context",
                      message: "This imports valid source-export rows, recomputes portfolio context, option risk/outcomes/lifecycle, and rebuilds outputs.",
                      confirmLabel: "Apply account context",
                      run: () => tomApi.applyAccountContextBackfill(true, allowPartial) as Promise<ApiResponse<unknown>>
                    })
                  }
                >
                  <Check size={16} /> Confirm Apply
                </button>
              </section>
              <section className="form-panel">
                <h2>Read-Only Account Source</h2>
                <Resource state={providerState}>
                  {(providerResponse) => {
                    if (!providerResponse.ok) {
                      return <Offline message={providerResponse.message} warnings={providerResponse.warnings} />;
                    }
                    const providerStatus = providerResponse.data.provider_status;
                    return (
                      <div className="mini-metric-grid">
                        <Metric label="IBKR Available" value={textValue(providerStatus, "ibkr_available")} detail="local API" />
                        <Metric label="IBKR Connected" value={textValue(providerStatus, "ibkr_connected")} detail="status check" />
                        <Metric label="Source Files" value={textValue(providerStatus, "source_export_files", "0")} detail="account exports" />
                        <Metric label="Provider Blockers" value={listValue(providerStatus, "blockers")} detail="readiness" />
                      </div>
                    );
                  }}
                </Resource>
                <div className="form-grid">
                  <label>
                    Source
                    <select value={accountFetchSource} onChange={(event) => setAccountFetchSource(event.target.value as "file" | "ibkr")}>
                      <option value="file">File export</option>
                      <option value="ibkr">IBKR read-only</option>
                    </select>
                  </label>
                  <label>
                    Provider
                    <select value={accountProvider} onChange={(event) => setAccountProvider(event.target.value)}>
                      <option value="generic">Generic</option>
                      <option value="ibkr">IBKR</option>
                      <option value="ibkr-flex">IBKR Flex</option>
                      <option value="ibkr-activity">IBKR Activity</option>
                    </select>
                  </label>
                  <Field label="Export File Path" value={accountFile} onChange={setAccountFile} />
                </div>
                <div className="control-strip">
                  <button
                    type="button"
                    onClick={() => {
                      if (!requireAccountFile()) return;
                      setConfirmAction({
                        title: "Normalize account export",
                        message: "This reads a source-backed account export and writes normalized source-export CSVs under TOM. It does not apply them.",
                        confirmLabel: "Normalize export",
                        run: () => tomApi.normalizeAccountExport(accountProvider, accountFile, true) as Promise<ApiResponse<unknown>>
                      });
                    }}
                  >
                    <FileJson size={16} /> Normalize Export
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      if (accountFetchSource === "file" && !requireAccountFile()) return;
                      setConfirmAction({
                        title: "Fetch account context",
                        message: "This uses a read-only source and stages normalized account-context rows. Apply remains a separate confirmed action.",
                        confirmLabel: "Fetch read-only",
                        run: () =>
                          tomApi.fetchAccountContext(
                            {
                              source: accountFetchSource,
                              read_only: true,
                              provider: accountProvider,
                              file: accountFile || undefined
                            },
                            true
                          ) as Promise<ApiResponse<unknown>>
                      });
                    }}
                  >
                    <Database size={16} /> Fetch Read-Only
                  </button>
                </div>
              </section>
              <div className="row-builder-grid">
                <AccountRowBuilder
                  title="Portfolio Position Row"
                  row={forms.portfolio}
                  fields={["ticker", "quantity", "account", "position_date", "currency", "market_price", "market_value", "cost_basis_total", "source"]}
                  onChange={(row) => setForms({ ...forms, portfolio: row })}
                  onAppend={() => appendRowAction("portfolio position row", "portfolio_position", forms.portfolio)}
                />
                <AccountRowBuilder
                  title="Cash Row"
                  row={forms.cash}
                  fields={["account", "cash_date", "currency", "cash_amount", "base_cash_amount", "source"]}
                  onChange={(row) => setForms({ ...forms, cash: row })}
                  onAppend={() => appendRowAction("cash row", "portfolio_cash", forms.cash)}
                />
                <AccountRowBuilder
                  title="Option Position Row"
                  row={forms.option}
                  fields={["position_id", "ticker", "open_date", "expiration_date", "option_type", "side", "strike", "contracts", "premium", "account", "status", "source"]}
                  onChange={(row) => setForms({ ...forms, option: row })}
                  onAppend={() => appendRowAction("option position row", "option_position", forms.option)}
                />
              </div>
              <div className="two-column">
                <ApiResult title="Account Preview" response={{ ok: true, data: preview }} />
                <ApiResult title="Account Validation" response={{ ok: true, data: validation }} />
              </div>
            </>
          );
        }}
      </Resource>
      <ConfirmDialog action={confirmAction} onCancel={() => setConfirmAction(null)} onConfirm={runConfirmedAction} />
    </PageFrame>
  );
}

function AccountRowBuilder({
  title,
  row,
  fields,
  onChange,
  onAppend
}: {
  title: string;
  row: Record<string, string>;
  fields: string[];
  onChange: (row: Record<string, string>) => void;
  onAppend: () => void;
}) {
  return (
    <section className="form-panel">
      <h2>{title}</h2>
      <div className="form-grid">
        {fields.map((field) => (
          <Field
            key={field}
            label={labelize(field)}
            value={row[field] ?? ""}
            onChange={(value) => onChange({ ...row, [field]: value })}
          />
        ))}
      </div>
      <button type="button" onClick={onAppend}>
        <Check size={15} /> Append Row
      </button>
    </section>
  );
}

const SHORT_INTEREST_ROW_FIELDS = [
  "ticker",
  "settlement_date",
  "publication_date",
  "short_interest",
  "float_shares",
  "percent_float",
  "average_daily_volume",
  "days_to_cover",
  "source",
  "source_url",
  "notes",
  "as_of_date",
  "effective_date",
  "capture_method"
];

const SHORT_INTEREST_SOURCE_CHOICES = ["provider_export", "exchange_manual", "broker_manual"];

const NEWS_PROVIDER_NATIVE_ROW_FIELDS = [
  "ticker",
  "signal_date",
  "source",
  "source_url",
  "headline_or_event",
  "article_datetime",
  "event_date",
  "topic",
  "summary",
  "sentiment_score",
  "catalyst_score",
  "urgency_score",
  "relevance_score",
  "confidence",
  "notes",
  "capture_method"
];

const NEWS_PROVIDER_NATIVE_SOURCE_CHOICES = [
  "marketaux_export",
  "eodhd_export",
  "x_export",
  "licensed_news_provider_export",
  "user_provider_export"
];

function BackfillsPage() {
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [allowPartial, setAllowPartial] = React.useState(true);
  const [notice, setNotice] = React.useState<ActionNotice | null>(null);
  const [confirmAction, setConfirmAction] = React.useState<ConfirmAction | null>(null);
  const [shortInterestRow, setShortInterestRow] = React.useState<Record<string, string>>({
    ticker: "",
    settlement_date: "",
    publication_date: "",
    short_interest: "",
    float_shares: "",
    percent_float: "",
    average_daily_volume: "",
    days_to_cover: "",
    source: "provider_export",
    source_url: "",
    notes: "",
    as_of_date: "",
    effective_date: "",
    capture_method: "ui_manual"
  });
  const [newsRow, setNewsRow] = React.useState<Record<string, string>>({
    ticker: "",
    signal_date: "",
    source: "user_provider_export",
    source_url: "",
    headline_or_event: "",
    article_datetime: "",
    event_date: "",
    topic: "",
    summary: "",
    sentiment_score: "",
    catalyst_score: "",
    urgency_score: "",
    relevance_score: "",
    confidence: "",
    notes: "",
    capture_method: "ui_manual"
  });
  const state = useResource(
    async () => {
      const [options, news, shortInterest] = await Promise.all([
        tomApi.optionsBackfillStatus(),
        tomApi.newsBackfillStatus(),
        tomApi.shortInterestBackfillStatus()
      ]);
      return { options, news, shortInterest };
    },
    [refreshKey]
  );

  const runConfirmedAction = async () => {
    if (!confirmAction) return;
    const action = confirmAction;
    setConfirmAction(null);
    const response = await action.run();
    if (response.ok) {
      setNotice({ tone: "success", title: "Action completed", message: action.title, details: response.warnings });
      setRefreshKey((value) => value + 1);
    } else {
      setNotice({ tone: "danger", title: response.error_code, message: response.message, details: response.warnings });
    }
  };

  const runReadOnlyAction = async (title: string, action: () => Promise<ApiResponse<unknown>>) => {
    const response = await action();
    if (response.ok) {
      setNotice({ tone: "success", title, message: "Read-only check completed.", details: response.warnings });
    } else {
      setNotice({ tone: "danger", title: response.error_code, message: response.message, details: response.warnings });
    }
    setRefreshKey((value) => value + 1);
  };

  const appendShortInterestRowAction = () => {
    setConfirmAction({
      title: "Append short-interest source row",
      message: "This appends one source-export row to the missing-provider short-interest template. It does not import the row or change canonical short-interest data.",
      confirmLabel: "Append source row",
      run: () => tomApi.appendShortInterestMissingRow({ row: shortInterestRow }, true) as Promise<ApiResponse<unknown>>
    });
  };

  const appendNewsRowAction = () => {
    setConfirmAction({
      title: "Append news/catalyst provider-native row",
      message: "This appends one source-export row to the provider-native news/catalyst backfill template. It does not import the row or change canonical news/catalyst data.",
      confirmLabel: "Append source row",
      run: () => tomApi.appendNewsBackfillRow({ row: newsRow }, true) as Promise<ApiResponse<unknown>>
    });
  };

  return (
    <PageFrame title="Backfills" subtitle="Source-data backfill readiness and confirmation-gated apply controls.">
      {notice && <ActionNoticeView notice={notice} onDismiss={() => setNotice(null)} />}
      <label className="check-row">
        <input checked={allowPartial} type="checkbox" onChange={(event) => setAllowPartial(event.target.checked)} />
        Allow partial apply for options and news/catalyst
      </label>
      <Resource state={state}>
        {(data) => {
          if (!data.options.ok) return <Offline message={data.options.message} warnings={data.options.warnings} />;
          if (!data.news.ok) return <Offline message={data.news.message} warnings={data.news.warnings} />;
          if (!data.shortInterest.ok) return <Offline message={data.shortInterest.message} warnings={data.shortInterest.warnings} />;
          const newsData = data.news.data;
          const newsDiagnostics = recordArrayValue(newsData, "diagnostics");
          const newsBlockedTickers = stringArrayValue(newsData, "preview.still_blocked_tickers");
          const shortInterestData = data.shortInterest.data;
          const shortInterestDiagnostics = recordArrayValue(shortInterestData, "missing_plan.diagnostics");
          const shortInterestMissingTickers = stringArrayValue(shortInterestData, "missing_plan.missing_tickers");
          const optionChainAvailability = recordArrayValue(data.options.data, "availability_statuses");
          return (
            <div className="backfill-grid">
              <BackfillPanel
                title="Option Chains"
                subtitle="Broader source-backed option-chain coverage."
                metrics={[
                  ["Coverage", textValue(data.options.data.plan, "effective_coverage_count", "0/0")],
                  ["Raw", textValue(data.options.data.plan, "raw_coverage_count", "0/0")],
                  ["Non-actionable", listValue(data.options.data.plan, "non_actionable_tickers")],
                  ["Valid rows", textValue(data.options.data.validation, "valid_row_count", "0")],
                  ["Blocked", textValue(data.options.data.plan, "blocked_reason")]
                ]}
                status={data.options.data}
                text={String(data.options.data.option_chain_status_text ?? "")}
                onExport={() =>
                  setConfirmAction({
                    title: "Export option-chain missing template",
                    message: "This creates or refreshes the source-export template for missing option-chain rows.",
                    confirmLabel: "Export template",
                    run: () => tomApi.exportOptionsBackfillTemplate(true) as Promise<ApiResponse<unknown>>
                  })
                }
                onValidate={() => void runReadOnlyAction("Validate option-chain backfill", () => tomApi.validateOptionsBackfill() as Promise<ApiResponse<unknown>>)}
                onApply={() =>
                  setConfirmAction({
                    title: "Apply option-chain backfill",
                    message: "This imports valid option-chain rows and recomputes option income, risk, outcomes, and lifecycle.",
                    confirmLabel: "Apply option backfill",
                    run: () => tomApi.applyOptionsBackfill(true, allowPartial) as Promise<ApiResponse<unknown>>
                  })
                }
              >
                <OptionChainAvailabilityTable statuses={optionChainAvailability} />
              </BackfillPanel>
              <BackfillPanel
                title="News/Catalyst Provider-Native"
                subtitle="Upgrade text-derived rows with real provider-native numeric rows."
                metrics={[
                  ["Coverage", `${textValue(newsData.preview, "current_provider_native_ticker_count", "0")}/${textValue(newsData.preview, "active_equity_count", "0")}`],
                  ["Valid rows", textValue(newsData.validation, "valid_row_count", "0")],
                  ["Blocked tickers", listValue(newsData.preview, "still_blocked_tickers")],
                  ["Blocked", textValue(newsData.apply_status, "blocked_apply_reason")]
                ]}
                status={newsData}
                text={String(newsData.diagnostics_text ?? newsData.backfill_status_text ?? "")}
                onExport={() =>
                  setConfirmAction({
                    title: "Export news/catalyst provider-native template",
                    message: "This refreshes the provider-native backfill package for text-derived-only tickers.",
                    confirmLabel: "Export template",
                    run: () => tomApi.exportNewsBackfillTemplate(true) as Promise<ApiResponse<unknown>>
                  })
                }
                onValidate={() => void runReadOnlyAction("Validate news/catalyst provider backfill", () => tomApi.validateNewsBackfill() as Promise<ApiResponse<unknown>>)}
                onApply={() =>
                  setConfirmAction({
                    title: "Apply news/catalyst provider-native backfill",
                    message: "This imports valid provider-native rows and reruns aggregate/load/compute/validate for news/catalyst signals.",
                    confirmLabel: "Apply news backfill",
                    run: () => tomApi.applyNewsBackfill(true, allowPartial) as Promise<ApiResponse<unknown>>
                  })
                }
              >
                <NewsProviderDiagnostics diagnostics={newsDiagnostics} />
                <NewsProviderNativeRowBuilder
                  row={newsRow}
                  stillBlockedTickers={newsBlockedTickers}
                  onChange={setNewsRow}
                  onAppend={appendNewsRowAction}
                />
              </BackfillPanel>
              <BackfillPanel
                title="Short Interest Missing Rows"
                subtitle="Resolve source-backed rows for the remaining missing equities."
                metrics={[
                  ["Coverage", `${textValue(shortInterestData.validation, "current_source_backed_count", "0")}/${textValue(shortInterestData.validation, "active_equity_count", "0")}`],
                  ["Valid rows", textValue(shortInterestData.validation, "valid_row_count", "0")],
                  ["Missing", listValue(shortInterestData.validation, "missing_source_tickers")],
                  ["Blocked", textValue(shortInterestData.missing_plan, "blocked_apply_reason")]
                ]}
                status={shortInterestData}
                text={String(shortInterestData.missing_plan_text ?? shortInterestData.source_status_text ?? "")}
                onExport={() =>
                  setConfirmAction({
                    title: "Export short-interest missing template",
                    message: "This refreshes the missing-provider template for unresolved short-interest tickers.",
                    confirmLabel: "Export template",
                    run: () => tomApi.exportShortInterestBackfillTemplate(true) as Promise<ApiResponse<unknown>>
                  })
                }
                onValidate={() => void runReadOnlyAction("Validate short-interest backfill", () => tomApi.validateShortInterestBackfill() as Promise<ApiResponse<unknown>>)}
                onApply={() =>
                  setConfirmAction({
                    title: "Apply short-interest backfill",
                    message: "This imports valid source-backed short-interest rows only when projected coverage improves.",
                    confirmLabel: "Apply short-interest backfill",
                    run: () => tomApi.applyShortInterestBackfill(true) as Promise<ApiResponse<unknown>>
                  })
                }
              >
                <ShortInterestDiagnostics diagnostics={shortInterestDiagnostics} />
                <ShortInterestRowBuilder
                  row={shortInterestRow}
                  missingTickers={shortInterestMissingTickers}
                  onChange={setShortInterestRow}
                  onAppend={appendShortInterestRowAction}
                />
              </BackfillPanel>
            </div>
          );
        }}
      </Resource>
      <ConfirmDialog action={confirmAction} onCancel={() => setConfirmAction(null)} onConfirm={runConfirmedAction} />
    </PageFrame>
  );
}

function BackfillPanel({
  title,
  subtitle,
  metrics,
  status,
  text,
  children,
  onExport,
  onValidate,
  onApply
}: {
  title: string;
  subtitle: string;
  metrics: Array<[string, string]>;
  status: Record<string, unknown>;
  text: string;
  children?: React.ReactNode;
  onExport: () => void;
  onValidate: () => void;
  onApply: () => void;
}) {
  return (
    <section className="backfill-panel">
      <header>
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
      </header>
      <div className="mini-metric-grid">
        {metrics.map(([label, value]) => (
          <Metric key={label} label={label} value={value} detail="backfill" />
        ))}
      </div>
      <div className="button-row">
        <button type="button" onClick={onExport}><FileJson size={15} /> Export</button>
        <button type="button" onClick={onValidate}><Eye size={15} /> Validate</button>
        <button type="button" onClick={onApply}><Check size={15} /> Apply</button>
      </div>
      {children}
      {text && <pre className="text-report compact-report">{text}</pre>}
      <ApiResult title={`${title} JSON`} response={{ ok: true, data: status }} />
    </section>
  );
}

function OptionChainAvailabilityTable({
  statuses,
  compact = false
}: {
  statuses: Record<string, unknown>[];
  compact?: boolean;
}) {
  const visible = compact
    ? statuses.filter((status) => valueText(status.availability_status) !== "available")
    : statuses;
  return (
    <div className="inline-section">
      <h3>Option-Chain Availability</h3>
      <div className="table-wrap compact-table">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Status</th>
              <th>Reason</th>
              <th>Source</th>
              <th>As Of</th>
              <th>Raw Chain</th>
            </tr>
          </thead>
          <tbody>
            {visible.length ? (
              visible.map((status, index) => {
                const sourceUrl = valueText(status.source_url);
                return (
                  <tr key={`${valueText(status.ticker)}-${index}`}>
                    <td><strong>{valueText(status.ticker)}</strong></td>
                    <td><StatusPill value={valueText(status.availability_status)} /></td>
                    <td>{valueText(status.reason_code)}</td>
                    <td>
                      {sourceUrl !== "none" ? (
                        <a href={sourceUrl} target="_blank" rel="noreferrer">{valueText(status.source)}</a>
                      ) : (
                        valueText(status.source)
                      )}
                    </td>
                    <td>{valueText(status.as_of_date)}</td>
                    <td>{valueText(status.raw_chain_available)}</td>
                  </tr>
                );
              })
            ) : (
              <tr>
                <td colSpan={6}>all available</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {!compact && (
        <p className="panel-note">
          Availability is derived from stored TOM chain rows and validated source-backed non-actionable decisions.
        </p>
      )}
    </div>
  );
}

function NewsProviderDiagnostics({ diagnostics }: { diagnostics: Record<string, unknown>[] }) {
  return (
    <div className="inline-section">
      <h3>Provider-Native Diagnostics</h3>
      <div className="table-wrap compact-table">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Classification</th>
              <th>Rows</th>
              <th>Provider Native</th>
              <th>Action</th>
              <th>Warnings</th>
            </tr>
          </thead>
          <tbody>
            {diagnostics.length ? (
              diagnostics.map((item, index) => (
                <tr key={`${String(item.ticker ?? "news-diagnostic")}-${index}`}>
                  <td><StatusPill value={valueText(item.ticker)} /></td>
                  <td>{valueText(item.classification)}</td>
                  <td>
                    valid {valueText(item.valid_rows)} / blank {valueText(item.blank_placeholder_rows)} / invalid {valueText(item.invalid_rows)}
                  </td>
                  <td>
                    current {valueText(item.current_provider_native)} / text-derived {valueText(item.text_derived_only)}
                  </td>
                  <td>{valueText(item.recommended_action)}</td>
                  <td>{valueText(item.warnings)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6}>No provider-native news/catalyst diagnostics.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function NewsProviderNativeRowBuilder({
  row,
  stillBlockedTickers,
  onChange,
  onAppend
}: {
  row: Record<string, string>;
  stillBlockedTickers: string[];
  onChange: (row: Record<string, string>) => void;
  onAppend: () => void;
}) {
  const tickerChoices = row.ticker && !stillBlockedTickers.includes(row.ticker)
    ? [row.ticker, ...stillBlockedTickers]
    : stillBlockedTickers;
  return (
    <div className="inline-section">
      <h3>Provider-Native Row Intake</h3>
      <div className="form-grid dense-form-grid">
        {NEWS_PROVIDER_NATIVE_ROW_FIELDS.map((field) => {
          if (field === "ticker") {
            return (
              <label className="field" key={field}>
                <span>Ticker</span>
                <select value={row.ticker ?? ""} onChange={(event) => onChange({ ...row, ticker: event.target.value })}>
                  <option value="">Select blocked ticker</option>
                  {tickerChoices.map((ticker) => (
                    <option key={ticker} value={ticker}>{ticker}</option>
                  ))}
                </select>
              </label>
            );
          }
          if (field === "source") {
            return (
              <label className="field" key={field}>
                <span>Source</span>
                <select value={row.source ?? ""} onChange={(event) => onChange({ ...row, source: event.target.value })}>
                  {NEWS_PROVIDER_NATIVE_SOURCE_CHOICES.map((source) => (
                    <option key={source} value={source}>{source}</option>
                  ))}
                </select>
              </label>
            );
          }
          return (
            <Field
              key={field}
              label={labelize(field)}
              value={row[field] ?? ""}
              onChange={(value) => onChange({ ...row, [field]: value })}
            />
          );
        })}
      </div>
      <div className="button-row">
        <button type="button" onClick={onAppend}>
          <Check size={15} /> Append Provider Row
        </button>
      </div>
    </div>
  );
}

function ShortInterestDiagnostics({ diagnostics }: { diagnostics: Record<string, unknown>[] }) {
  return (
    <div className="inline-section">
      <h3>Missing Ticker Diagnostics</h3>
      <div className="table-wrap compact-table">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Classification</th>
              <th>Rows</th>
              <th>Attempted Paths</th>
              <th>Action</th>
              <th>Warnings</th>
            </tr>
          </thead>
          <tbody>
            {diagnostics.length ? (
              diagnostics.map((item, index) => (
                <tr key={`${String(item.ticker ?? "diagnostic")}-${index}`}>
                  <td><StatusPill value={valueText(item.ticker)} /></td>
                  <td>{valueText(item.classification)}</td>
                  <td>
                    valid {valueText(item.valid_export_rows)} / invalid {valueText(item.invalid_export_rows)} / blank {valueText(item.blank_placeholder_rows)}
                  </td>
                  <td>{valueText(item.attempted_paths)}</td>
                  <td>{valueText(item.recommended_action)}</td>
                  <td>{valueText(item.warnings)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6}>No missing short-interest diagnostics.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ShortInterestRowBuilder({
  row,
  missingTickers,
  onChange,
  onAppend
}: {
  row: Record<string, string>;
  missingTickers: string[];
  onChange: (row: Record<string, string>) => void;
  onAppend: () => void;
}) {
  const tickerChoices = row.ticker && !missingTickers.includes(row.ticker)
    ? [row.ticker, ...missingTickers]
    : missingTickers;
  return (
    <div className="inline-section">
      <h3>Source Row Intake</h3>
      <div className="form-grid dense-form-grid">
        {SHORT_INTEREST_ROW_FIELDS.map((field) => {
          if (field === "ticker") {
            return (
              <label className="field" key={field}>
                <span>Ticker</span>
                <select value={row.ticker ?? ""} onChange={(event) => onChange({ ...row, ticker: event.target.value })}>
                  <option value="">Select missing ticker</option>
                  {tickerChoices.map((ticker) => (
                    <option key={ticker} value={ticker}>{ticker}</option>
                  ))}
                </select>
              </label>
            );
          }
          if (field === "source") {
            return (
              <label className="field" key={field}>
                <span>Source</span>
                <select value={row.source ?? ""} onChange={(event) => onChange({ ...row, source: event.target.value })}>
                  {SHORT_INTEREST_SOURCE_CHOICES.map((source) => (
                    <option key={source} value={source}>{source}</option>
                  ))}
                </select>
              </label>
            );
          }
          return (
            <Field
              key={field}
              label={labelize(field)}
              value={row[field] ?? ""}
              onChange={(value) => onChange({ ...row, [field]: value })}
            />
          );
        })}
      </div>
      <div className="button-row">
        <button type="button" onClick={onAppend}>
          <Check size={15} /> Append Source Row
        </button>
      </div>
    </div>
  );
}

function ResearchPage() {
  const [mode, setMode] = React.useState<"queue" | "ticker">("queue");
  return (
    <PageFrame title="Research" subtitle="Approval-gated research recommendations and ticker intake.">
      <div className="toolbar">
        <button className={mode === "queue" ? "active" : ""} type="button" onClick={() => setMode("queue")}>
          <Search size={16} />
          Recommendation Queue
        </button>
        <button className={mode === "ticker" ? "active" : ""} type="button" onClick={() => setMode("ticker")}>
          <FlaskConical size={16} />
          Ticker Intake
        </button>
      </div>
      <MissingTickerPanel context="research" />
      {mode === "queue" ? <ResearchQueue /> : <TickerIntake />}
    </PageFrame>
  );
}

type ConfirmAction = {
  title: string;
  message: string;
  confirmLabel: string;
  run: () => Promise<ApiResponse<unknown>>;
};

type ActionNotice = {
  tone: "success" | "danger" | "warning";
  title: string;
  message: string;
  details?: string[];
};

type ResearchQueueView = "grouped" | "raw";

type ResearchRecommendationGroup = {
  ticker: string;
  items: ResearchRecommendation[];
  ids: number[];
  rowCount: number;
  maxPriorityScore?: number | null;
  sources: string[];
  topics: string[];
  warnings: string[];
  blockers: string[];
  representativeIds: number[];
  classification: string;
  preparationState?: string | null;
  researchPath?: string | null;
  recommendedAction: string;
};

function MissingTickerPanel({ context }: { context: "activation" | "research" }) {
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [notice, setNotice] = React.useState<ActionNotice | null>(null);
  const [confirmAction, setConfirmAction] = React.useState<ConfirmAction | null>(null);
  const state = useResource(() => tomApi.missingTickerStatus(), [refreshKey]);

  const runConfirmedAction = async () => {
    if (!confirmAction) return;
    const action = confirmAction;
    setConfirmAction(null);
    const response = await action.run();
    if (response.ok) {
      setNotice({ tone: "success", title: "Action completed", message: action.title, details: response.warnings });
      setRefreshKey((value) => value + 1);
    } else {
      setNotice({ tone: "danger", title: response.error_code, message: response.message, details: response.warnings });
    }
  };

  return (
    <section className="form-panel">
      <div className="panel-heading">
        <div>
          <h2>Missing Tickers</h2>
          <p>
            Source-backed unknown tickers are staged here before TOM adds or hydrates them. Social and research-only mentions stay review-gated.
          </p>
        </div>
        <div className="button-row">
          <button
            type="button"
            onClick={() =>
              setConfirmAction({
                title: "Resolve missing tickers",
                message: "This stages source-backed missing ticker candidates. It does not place trades or write to brokers.",
                confirmLabel: "Resolve",
                run: () => tomApi.resolveMissingTickers(context === "activation" ? "account_context" : "all", true) as Promise<ApiResponse<unknown>>
              })
            }
          >
            <Search size={16} /> Resolve
          </button>
          <button
            type="button"
            onClick={() =>
              setConfirmAction({
                title: "Apply missing ticker onboarding",
                message: "This adds ready source-backed candidates through TOM's asset and watchlist workflow.",
                confirmLabel: "Apply",
                run: () => tomApi.applyMissingTickerOnboarding("account_context", true) as Promise<ApiResponse<unknown>>
              })
            }
          >
            <Check size={16} /> Apply Ready
          </button>
        </div>
      </div>
      {notice && <ActionNoticeView notice={notice} onDismiss={() => setNotice(null)} />}
      <Resource state={state}>
        {(response) => {
          if (!response.ok) return <Offline message={response.message} warnings={response.warnings} />;
          const status = response.data.status;
          const candidates = status.candidates ?? [];
          return (
            <>
              <section className="mini-metric-grid">
                <Metric label="Candidates" value={String(status.total_candidates ?? 0)} detail="all sources" />
                <Metric label="Ready" value={String(status.ready_to_onboard ?? 0)} detail="can apply" />
                <Metric label="Blocked" value={String(status.blocked ?? 0)} detail="needs metadata" />
                <Metric label="Hydrated" value={String(status.hydrated ?? 0)} detail="data attempted" />
              </section>
              {candidates.length === 0 ? (
                <p className="muted">No missing ticker candidates yet.</p>
              ) : (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Ticker</th>
                        <th>Status</th>
                        <th>Source</th>
                        <th>Type</th>
                        <th>Role</th>
                        <th>Blockers</th>
                        <th>Warnings</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {candidates.slice(0, 12).map((item: MissingTickerCandidate) => (
                        <tr key={`${item.ticker}-${item.first_seen_source}-${item.source_file ?? ""}-${item.source_row ?? ""}`}>
                          <td>{item.ticker}</td>
                          <td><span className="status-pill">{item.status}</span></td>
                          <td>{item.first_seen_source}</td>
                          <td>{item.detected_asset_type || "unknown"}</td>
                          <td>{item.recommended_asset_role || "unknown"}</td>
                          <td>{item.blockers || "none"}</td>
                          <td>{item.warnings || "none"}</td>
                          <td>
                            <button
                              type="button"
                              disabled={item.status !== "onboarded"}
                              onClick={() =>
                                setConfirmAction({
                                  title: `Hydrate ${item.ticker}`,
                                  message: "This runs TOM's read-only data hydration path for the onboarded ticker.",
                                  confirmLabel: "Hydrate",
                                  run: () => tomApi.hydrateMissingTicker(item.ticker, true) as Promise<ApiResponse<unknown>>
                                })
                              }
                            >
                              <RefreshCw size={16} /> Hydrate
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {status.next_actions?.length ? (
                <pre className="text-report compact-report">{status.next_actions.join("\n")}</pre>
              ) : null}
            </>
          );
        }}
      </Resource>
      <ConfirmDialog action={confirmAction} onCancel={() => setConfirmAction(null)} onConfirm={runConfirmedAction} />
    </section>
  );
}

function ResearchQueue() {
  const [filter, setFilter] = React.useState("pending");
  const [query, setQuery] = React.useState("");
  const [queueView, setQueueView] = React.useState<ResearchQueueView>("grouped");
  const [selected, setSelected] = React.useState<ResearchRecommendation | null>(null);
  const [selectedIds, setSelectedIds] = React.useState<Set<number>>(new Set());
  const [expandedTickers, setExpandedTickers] = React.useState<Set<string>>(new Set());
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [confirmAction, setConfirmAction] = React.useState<ConfirmAction | null>(null);
  const [notice, setNotice] = React.useState<ActionNotice | null>(null);
  const [tickerPlan, setTickerPlan] = React.useState<ApiResponse<ResearchTickerPlanPayload> | null>(null);
  const [strategyReview, setStrategyReview] = React.useState<ApiResponse<EtfStrategyReviewPayload> | null>(null);
  const state = useResource(() => tomApi.researchRecommendations(filter), [filter, refreshKey]);
  const triageState = useResource(() => tomApi.researchRecommendationTriage(), [refreshKey]);
  const preparationState = useResource(() => tomApi.researchPreparationStatus("all"), [refreshKey]);
  const foreignSourceState = useResource(() => tomApi.foreignEquitySourceStatus(), [refreshKey]);

  React.useEffect(() => {
    setSelectedIds(new Set());
  }, [filter, query]);

  React.useEffect(() => {
    setQueueView(filter === "pending" ? "grouped" : "raw");
    setExpandedTickers(new Set());
  }, [filter]);

  const runConfirmedAction = async () => {
    if (!confirmAction) return;
    const action = confirmAction;
    setConfirmAction(null);
    const response = await action.run();
    if (response.ok) {
      setNotice({
        tone: "success",
        title: "Action completed",
        message: action.title,
        details: response.warnings
      });
      setSelectedIds(new Set());
      setRefreshKey((value) => value + 1);
    } else {
      setNotice({
        tone: "danger",
        title: response.error_code,
        message: response.message,
        details: response.warnings
      });
    }
  };

  const requestStatusChange = (
    item: ResearchRecommendation,
    nextStatus: EditableRecommendationStatus
  ) => {
    setConfirmAction({
      title: `Set ${item.ticker} to ${nextStatus}`,
      message: `This updates research recommendation ${item.research_recommendation_id}. It does not add the ticker, place trades, or change TOM scores.`,
      confirmLabel: `Set ${nextStatus}`,
      run: () =>
        tomApi.setRecommendationStatus(
          item.research_recommendation_id,
          nextStatus,
          "phase14c_ui_status_update",
          true
        ) as Promise<ApiResponse<unknown>>
    });
  };

  const requestBulkStatusChange = (
    nextStatus: EditableRecommendationStatus,
    explicitIds?: number[],
    contextLabel?: string
  ) => {
    const ids = explicitIds ?? Array.from(selectedIds);
    if (!ids.length) {
      setNotice({
        tone: "warning",
        title: "No rows selected",
        message: "Select one or more recommendation rows first.",
        details: []
      });
      return;
    }
    const title = contextLabel
      ? `Set ${ids.length} ${contextLabel} recommendations to ${nextStatus}`
      : `Set ${ids.length} recommendations to ${nextStatus}`;
    setConfirmAction({
      title,
      message: contextLabel
        ? `This updates exactly ${ids.length} ${contextLabel} recommendation rows. It does not promote tickers, place trades, or change TOM scores.`
        : "This updates review statuses only. It does not promote tickers, place trades, or change TOM scores.",
      confirmLabel: `Set ${nextStatus}`,
      run: () =>
        tomApi.bulkSetRecommendationStatus(
          ids,
          nextStatus,
          "phase14c_ui_bulk_status_update",
          true
        ) as Promise<ApiResponse<unknown>>
    });
  };

  const selectedPreparationTickers = () => {
    if (!selectedIds.size || state.status !== "ready" || !state.value.ok) return [];
    const tickers = state.value.data.candidates
      .filter((item) => selectedIds.has(item.research_recommendation_id))
      .map((item) => item.ticker);
    return Array.from(new Set(tickers));
  };

  const runPreparationNow = async (action: ResearchPreparationAction, confirm: boolean) => {
    const response = await tomApi.runResearchPreparation(
      action,
      "pending",
      confirm,
      selectedPreparationTickers()
    );
    if (response.ok) {
      setNotice({
        tone: "success",
        title: "Preparation updated",
        message: action,
        details: response.warnings
      });
      setRefreshKey((value) => value + 1);
    } else {
      setNotice({
        tone: "danger",
        title: response.error_code,
        message: response.message,
        details: response.warnings
      });
    }
  };

  const requestPreparationRun = (action: ResearchPreparationAction) => {
    if (action === "scan" || action === "discover_sources") {
      void runPreparationNow(action, false);
      return;
    }
    const labels: Record<ResearchPreparationAction, string> = {
      scan: "Run preparation scan",
      discover_sources: "Discover sources",
      stage_source_rows: "Stage source rows",
      load_staged_sources: "Load staged sources",
      compute_ready: "Load and recompute readiness",
      prepare_ready: "Prepare ready tickers",
      ignore_already_scoreable: "Ignore already-scoreable context",
      all_safe: "Run all safe preparation"
    };
    const messages: Record<ResearchPreparationAction, string> = {
      scan: "This refreshes the read-only preparation packet.",
      discover_sources: "This checks allowlisted source adapters and does not write rows.",
      stage_source_rows: "This writes only source-backed rows into TOM's local staging CSVs. It does not approve, promote, or trade.",
      load_staged_sources: "This loads existing staged source rows through TOM validators and refreshes ETF features.",
      compute_ready: "This recomputes derived targets, scores, and ranges for preparation candidates. It does not approve or promote recommendations.",
      prepare_ready: "This applies only tickers whose existing TOM research plan is already apply-ready. It does not approve or promote recommendations.",
      ignore_already_scoreable: "This marks only already-scoreable context rows ignored. It does not approve, promote, or alter score logic.",
      all_safe: "This runs source staging, loading, recompute, ready-ticker apply, and context cleanup only where TOM gates allow."
    };
    const label = labels[action];
    setConfirmAction({
      title: label,
      message: messages[action],
      confirmLabel: label,
      run: () =>
        tomApi.runResearchPreparation(
          action,
          "all",
          true,
          selectedPreparationTickers()
        ) as Promise<ApiResponse<unknown>>
    });
  };

  const runForeignSourceDryRun = async () => {
    const response = await tomApi.applyForeignEquitySource(false, true);
    if (response.ok) {
      setNotice({
        tone: "success",
        title: "Foreign source dry run complete",
        message: "No rows were imported.",
        details: response.warnings
      });
      setRefreshKey((value) => value + 1);
    } else {
      setNotice({
        tone: "danger",
        title: response.error_code,
        message: response.message,
        details: response.warnings
      });
    }
  };

  const requestForeignSourceTemplate = () => {
    setConfirmAction({
      title: "Export foreign-equity templates",
      message: "This creates TOM-controlled source-export CSVs for foreign-equity fundamentals and EPS estimates. It does not import rows.",
      confirmLabel: "Export templates",
      run: () => tomApi.exportForeignEquitySourceTemplate(true) as Promise<ApiResponse<unknown>>
    });
  };

  const requestForeignSourceApply = () => {
    setConfirmAction({
      title: "Apply foreign-equity source rows",
      message: "This imports only valid source-backed foreign-equity fundamentals and EPS estimates. It does not approve recommendations, promote tickers, place trades, or write to brokers.",
      confirmLabel: "Apply source rows",
      run: () => tomApi.applyForeignEquitySource(true, false) as Promise<ApiResponse<unknown>>
    });
  };

  const toggleSelected = (id: number) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const setVisibleSelected = (ids: number[], checked: boolean) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      for (const id of ids) {
        if (checked) next.add(id);
        else next.delete(id);
      }
      return next;
    });
  };

  const toggleExpandedTicker = (ticker: string) => {
    setExpandedTickers((current) => {
      const next = new Set(current);
      if (next.has(ticker)) next.delete(ticker);
      else next.add(ticker);
      return next;
    });
  };

  const selectRecommendationForDetail = (item: ResearchRecommendation) => {
    setSelected(item);
    setTickerPlan(null);
    setStrategyReview(null);
  };

  const preparePromote = async (item: ResearchRecommendation) => {
    setSelected(item);
    setNotice(null);
    setStrategyReview(null);
    const planResponse = await tomApi.researchTickerPlan({
      ticker: item.ticker,
      asset_type: researchAssetTypeForRecommendation(item)
    });
    setTickerPlan(planResponse);
    if (!planResponse.ok) {
      setNotice({
        tone: "danger",
        title: planResponse.error_code,
        message: planResponse.message,
        details: planResponse.warnings
      });
      return;
    }
    const plan = planResponse.data.plan;
    const blockers = plan.blocked_reason ? `Blocked reason: ${plan.blocked_reason}.` : "Plan is apply-ready.";
    setConfirmAction({
      title: `Promote ${item.ticker}`,
      message: `${blockers} Promotion remains approval-gated and may still be blocked by TOM backend validation.`,
      confirmLabel: "Promote",
      run: () =>
        tomApi.promoteRecommendation(item.research_recommendation_id, true) as Promise<ApiResponse<unknown>>
    });
  };

  const loadPlanForRecommendation = async (item: ResearchRecommendation) => {
    setSelected(item);
    setStrategyReview(null);
    const response = await tomApi.researchTickerPlan({
      ticker: item.ticker,
      asset_type: researchAssetTypeForRecommendation(item)
    });
    setTickerPlan(response);
  };

  const loadEtfStrategyReview = async (item: ResearchRecommendation) => {
    setSelected(item);
    setNotice(null);
    const response = await tomApi.etfStrategyReview(item.ticker);
    setStrategyReview(response);
    if (!response.ok) {
      setNotice({
        tone: "danger",
        title: response.error_code,
        message: response.message,
        details: response.warnings
      });
    }
  };

  return (
    <>
      <div className="toolbar">
        {["pending", "approved", "ignored", "rejected", "promoted"].map((value) => (
          <button
            key={value}
            className={filter === value ? "active" : ""}
            type="button"
            onClick={() => setFilter(value)}
          >
            {value}
          </button>
        ))}
      </div>
      <div className="search-row">
        <Search size={17} />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search ticker, source, topic, or rationale"
        />
      </div>
      {notice && <ActionNoticeView notice={notice} onDismiss={() => setNotice(null)} />}
      <Resource state={triageState}>
        {(response) => {
          if (!response.ok) return <Offline message={response.message} warnings={response.warnings} />;
          return <ResearchTriagePanel triage={response.data.triage} />;
        }}
      </Resource>
      <Resource state={preparationState}>
        {(response) => {
          if (!response.ok) return <Offline message={response.message} warnings={response.warnings} />;
          return (
            <ResearchPreparationPanel
              preparation={response.data.preparation}
              onScan={() => requestPreparationRun("scan")}
              onDiscoverSources={() => requestPreparationRun("discover_sources")}
              onStageSources={() => requestPreparationRun("stage_source_rows")}
              onLoadSources={() => requestPreparationRun("load_staged_sources")}
              onComputeReady={() => requestPreparationRun("compute_ready")}
              onPrepareReady={() => requestPreparationRun("prepare_ready")}
              onIgnoreContext={() => requestPreparationRun("ignore_already_scoreable")}
              onAllSafe={() => requestPreparationRun("all_safe")}
            />
          );
        }}
      </Resource>
      <Resource state={foreignSourceState}>
        {(response) => {
          if (!response.ok) return <Offline message={response.message} warnings={response.warnings} />;
          return (
            <ResearchForeignEquitySourcePanel
              payload={response.data}
              onDryRun={() => void runForeignSourceDryRun()}
              onExportTemplate={requestForeignSourceTemplate}
              onApply={requestForeignSourceApply}
            />
          );
        }}
      </Resource>
      <Resource state={state}>
        {(response) => {
          if (!response.ok) return <Offline message={response.message} warnings={response.warnings} />;
          const candidates = filterRecommendations(response.data.candidates, query);
          const visibleIds = candidates.map((item) => item.research_recommendation_id);
          const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id));
          const triageGroups = triageState.status === "ready" && triageState.value.ok
            ? triageState.value.data.triage.groups
            : [];
          const preparationItems = preparationState.status === "ready" && preparationState.value.ok
            ? preparationState.value.data.preparation.items
            : [];
          const groupedCandidates = groupResearchRecommendations(candidates, triageGroups, preparationItems);
          return (
            <>
              <div className="bulk-review-bar">
                <span>{selectedIds.size} selected</span>
                <div className="button-row">
                  <button type="button" onClick={() => requestBulkStatusChange("approved")}><Check size={15} /> Approve</button>
                  <button type="button" onClick={() => requestBulkStatusChange("ignored")}><Eye size={15} /> Ignore</button>
                  <button type="button" onClick={() => requestBulkStatusChange("rejected")}><X size={15} /> Reject</button>
                </div>
              </div>
              <div className="toolbar compact-toolbar">
                <button className={queueView === "grouped" ? "active" : ""} type="button" onClick={() => setQueueView("grouped")}>
                  <Boxes size={15} />
                  Grouped
                </button>
                <button className={queueView === "raw" ? "active" : ""} type="button" onClick={() => setQueueView("raw")}>
                  <Database size={15} />
                  Raw rows
                </button>
              </div>
              <div className="split-panel">
                {queueView === "grouped" ? (
                  <ResearchGroupedRecommendationsTable
                    groups={groupedCandidates}
                    expandedTickers={expandedTickers}
                    selected={selected}
                    selectedIds={selectedIds}
                    onBulkStatus={(group, nextStatus) =>
                      requestBulkStatusChange(nextStatus, group.ids, group.ticker)
                    }
                    onGroupSelected={(group, checked) => setVisibleSelected(group.ids, checked)}
                    onItemSelected={selectRecommendationForDetail}
                    onItemToggled={toggleSelected}
                    onToggleExpanded={toggleExpandedTicker}
                  />
                ) : (
                  <ResearchRawRecommendationsTable
                    allVisibleSelected={allVisibleSelected}
                    candidates={candidates}
                    selected={selected}
                    selectedIds={selectedIds}
                    visibleIds={visibleIds}
                    onAllVisibleSelected={setVisibleSelected}
                    onItemSelected={selectRecommendationForDetail}
                    onItemStatus={requestStatusChange}
                    onItemToggled={toggleSelected}
                    onPromote={(item) => void preparePromote(item)}
                  />
                )}
                <RecommendationDetail
                  item={selected ?? candidates[0] ?? null}
                  tickerPlan={tickerPlan}
                  strategyReview={strategyReview}
                  onPlan={(item) => void loadPlanForRecommendation(item)}
                  onStrategy={(item) => void loadEtfStrategyReview(item)}
                  onStatus={requestStatusChange}
                  onPromote={(item) => void preparePromote(item)}
                />
              </div>
            </>
          );
        }}
      </Resource>
      <ConfirmDialog
        action={confirmAction}
        onCancel={() => setConfirmAction(null)}
        onConfirm={runConfirmedAction}
      />
    </>
  );
}

function ResearchGroupedRecommendationsTable({
  groups,
  expandedTickers,
  selected,
  selectedIds,
  onBulkStatus,
  onGroupSelected,
  onItemSelected,
  onItemToggled,
  onToggleExpanded
}: {
  groups: ResearchRecommendationGroup[];
  expandedTickers: Set<string>;
  selected: ResearchRecommendation | null;
  selectedIds: Set<number>;
  onBulkStatus: (group: ResearchRecommendationGroup, status: EditableRecommendationStatus) => void;
  onGroupSelected: (group: ResearchRecommendationGroup, checked: boolean) => void;
  onItemSelected: (item: ResearchRecommendation) => void;
  onItemToggled: (id: number) => void;
  onToggleExpanded: (ticker: string) => void;
}) {
  return (
    <div className="table-wrap research-grouped-table">
      <table>
        <thead>
          <tr>
            <th>Select</th>
            <th>Ticker</th>
            <th>Rows</th>
            <th>Top Score</th>
            <th>Readiness</th>
            <th>Sources</th>
            <th>Topics</th>
            <th>Warnings</th>
            <th>Blockers</th>
            <th>Representative IDs</th>
            <th>Safe Action</th>
            <th>Review</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => {
            const expanded = expandedTickers.has(group.ticker);
            const allGroupSelected = group.ids.length > 0 && group.ids.every((id) => selectedIds.has(id));
            const statusLabel = group.preparationState || group.classification;
            return (
              <React.Fragment key={group.ticker}>
                <tr className={expanded ? "group-row expanded" : "group-row"} onClick={() => onToggleExpanded(group.ticker)}>
                  <td>
                    <input
                      aria-label={`Select ${group.ticker} recommendations`}
                      checked={allGroupSelected}
                      type="checkbox"
                      onChange={(event) => {
                        event.stopPropagation();
                        onGroupSelected(group, event.target.checked);
                      }}
                      onClick={(event) => event.stopPropagation()}
                    />
                  </td>
                  <td>
                    <button
                      className="icon-button inline-icon-button"
                      type="button"
                      title={expanded ? "Collapse ticker group" : "Expand ticker group"}
                      onClick={(event) => {
                        event.stopPropagation();
                        onToggleExpanded(group.ticker);
                      }}
                    >
                      {expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                    </button>
                    <strong>{group.ticker}</strong>
                  </td>
                  <td>{group.rowCount}</td>
                  <td>{formatNumber(group.maxPriorityScore)}</td>
                  <td><StatusPill value={statusLabel} /></td>
                  <td>{listText(group.sources)}</td>
                  <td>{listText(group.topics)}</td>
                  <td>{listText(group.warnings)}</td>
                  <td>{listText(group.blockers)}</td>
                  <td>{group.representativeIds.join(", ") || "none"}</td>
                  <td>{group.recommendedAction}</td>
                  <td>
                    <div className="row-actions">
                      <button
                        type="button"
                        title={`Approve ${group.ticker} group`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onBulkStatus(group, "approved");
                        }}
                      >
                        <Check size={15} />
                      </button>
                      <button
                        type="button"
                        title={`Ignore ${group.ticker} group`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onBulkStatus(group, "ignored");
                        }}
                      >
                        <Eye size={15} />
                      </button>
                      <button
                        type="button"
                        title={`Reject ${group.ticker} group`}
                        onClick={(event) => {
                          event.stopPropagation();
                          onBulkStatus(group, "rejected");
                        }}
                      >
                        <X size={15} />
                      </button>
                    </div>
                  </td>
                </tr>
                {expanded && (
                  <tr className="group-detail-row">
                    <td colSpan={12}>
                      <div className="table-wrap compact-table nested-table">
                        <table>
                          <thead>
                            <tr>
                              <th>Select</th>
                              <th>ID</th>
                              <th>Priority</th>
                              <th>Source</th>
                              <th>Status</th>
                              <th>Topic</th>
                              <th>Rationale</th>
                              <th>Warnings</th>
                              <th>Blockers</th>
                            </tr>
                          </thead>
                          <tbody>
                            {group.items.map((item) => (
                              <tr
                                key={item.research_recommendation_id}
                                className={selected?.research_recommendation_id === item.research_recommendation_id ? "selected-row" : ""}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  onItemSelected(item);
                                }}
                              >
                                <td>
                                  <input
                                    aria-label={`Select recommendation ${item.research_recommendation_id}`}
                                    checked={selectedIds.has(item.research_recommendation_id)}
                                    type="checkbox"
                                    onChange={(event) => {
                                      event.stopPropagation();
                                      onItemToggled(item.research_recommendation_id);
                                    }}
                                    onClick={(event) => event.stopPropagation()}
                                  />
                                </td>
                                <td>{item.research_recommendation_id}</td>
                                <td>{formatNumber(item.research_priority_score)}</td>
                                <td>{item.source}</td>
                                <td><StatusPill value={item.status} /></td>
                                <td>{item.topic ?? ""}</td>
                                <td>{item.rationale ?? ""}</td>
                                <td>{item.warning_codes || "none"}</td>
                                <td>{item.promotion_blockers || "none"}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
          {!groups.length && (
            <tr>
              <td colSpan={12}>No research recommendation groups match this filter.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ResearchRawRecommendationsTable({
  allVisibleSelected,
  candidates,
  selected,
  selectedIds,
  visibleIds,
  onAllVisibleSelected,
  onItemSelected,
  onItemStatus,
  onItemToggled,
  onPromote
}: {
  allVisibleSelected: boolean;
  candidates: ResearchRecommendation[];
  selected: ResearchRecommendation | null;
  selectedIds: Set<number>;
  visibleIds: number[];
  onAllVisibleSelected: (ids: number[], checked: boolean) => void;
  onItemSelected: (item: ResearchRecommendation) => void;
  onItemStatus: (item: ResearchRecommendation, status: EditableRecommendationStatus) => void;
  onItemToggled: (id: number) => void;
  onPromote: (item: ResearchRecommendation) => void;
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>
              <input
                aria-label="Select visible recommendations"
                checked={allVisibleSelected}
                type="checkbox"
                onChange={(event) => onAllVisibleSelected(visibleIds, event.target.checked)}
              />
            </th>
            <th>ID</th>
            <th>Ticker</th>
            <th>Priority</th>
            <th>Source</th>
            <th>Status</th>
            <th>Topic</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((item: ResearchRecommendation) => (
            <tr
              key={item.research_recommendation_id}
              className={selected?.research_recommendation_id === item.research_recommendation_id ? "selected-row" : ""}
              onClick={() => onItemSelected(item)}
            >
              <td>
                <input
                  aria-label={`Select recommendation ${item.research_recommendation_id}`}
                  checked={selectedIds.has(item.research_recommendation_id)}
                  type="checkbox"
                  onChange={(event) => {
                    event.stopPropagation();
                    onItemToggled(item.research_recommendation_id);
                  }}
                  onClick={(event) => event.stopPropagation()}
                />
              </td>
              <td>{item.research_recommendation_id}</td>
              <td><strong>{item.ticker}</strong></td>
              <td>{formatNumber(item.research_priority_score)}</td>
              <td>{item.source}</td>
              <td><StatusPill value={item.status} /></td>
              <td>{item.topic ?? ""}</td>
              <td>
                <div className="row-actions">
                  <button type="button" title="Approve" onClick={(event) => { event.stopPropagation(); onItemStatus(item, "approved"); }}>
                    <Check size={15} />
                  </button>
                  <button type="button" title="Reject" onClick={(event) => { event.stopPropagation(); onItemStatus(item, "rejected"); }}>
                    <X size={15} />
                  </button>
                  <button type="button" title="Promote" onClick={(event) => { event.stopPropagation(); onPromote(item); }}>
                    <Play size={15} />
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {!candidates.length && (
            <tr>
              <td colSpan={8}>No research recommendations match this filter.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function ResearchTriagePanel({ triage }: { triage: ResearchRecommendationTriagePayload["triage"] }) {
  const classificationCounts = new Map(triage.classification_counts);
  const statusCounts = new Map(triage.status_counts);
  const topGroups = triage.groups.slice(0, 25);
  return (
    <section className="inline-section research-triage">
      <section className="mini-metric-grid">
        <Metric label="Pending" value={String(triage.pending_count)} detail="recommendations" />
        <Metric label="Ticker Groups" value={String(triage.group_count)} detail="pending groups" />
        <Metric
          label="Metadata"
          value={String(classificationCounts.get("metadata_required") ?? 0)}
          detail="groups blocked"
        />
        <Metric
          label="Ready Review"
          value={String(classificationCounts.get("promotion_ready_after_approval") ?? 0)}
          detail="groups unblocked"
        />
      </section>
      <div className="table-wrap compact-table">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Class</th>
              <th>Rows</th>
              <th>Top Score</th>
              <th>Sources</th>
              <th>Warnings</th>
              <th>Blockers</th>
              <th>Representative IDs</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {topGroups.map((group: ResearchTriageGroup) => (
              <tr key={group.ticker}>
                <td><strong>{group.ticker}</strong></td>
                <td><StatusPill value={group.classification} /></td>
                <td>{group.candidate_count}</td>
                <td>{formatNumber(group.max_priority_score)}</td>
                <td>{listText(group.sources)}</td>
                <td>{listText(group.warnings)}</td>
                <td>{listText(group.promotion_blockers)}</td>
                <td>{group.representative_candidate_ids.join(", ") || "none"}</td>
                <td>{group.recommended_action}</td>
              </tr>
            ))}
            {!topGroups.length && (
              <tr>
                <td colSpan={9}>No pending research recommendation groups.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <small>
        Status counts: {Array.from(statusCounts.entries()).map(([key, value]) => `${key} ${value}`).join(", ") || "none"}
      </small>
    </section>
  );
}

function ResearchPreparationPanel({
  preparation,
  onScan,
  onDiscoverSources,
  onStageSources,
  onLoadSources,
  onComputeReady,
  onPrepareReady,
  onIgnoreContext,
  onAllSafe
}: {
  preparation: ResearchPreparationPayload["preparation"];
  onScan: () => void;
  onDiscoverSources: () => void;
  onStageSources: () => void;
  onLoadSources: () => void;
  onComputeReady: () => void;
  onPrepareReady: () => void;
  onIgnoreContext: () => void;
  onAllSafe: () => void;
}) {
  const stateCounts = new Map(preparation.state_counts);
  const topItems = preparation.items.slice(0, 20);
  const sourceCandidateCount = preparation.items.filter((item) => item.can_discover_sources).length;
  const stageableCount = preparation.items.filter((item) => item.can_stage_sources).length;
  const loadableCount = preparation.items.filter((item) => item.can_load_sources).length;
          const etfSourceCount = preparation.items.filter((item) => item.asset_type === "etf").length;
  const autopilot = preparation.autopilot;
  const manualBlockers = preparation.manual_blocker_packets ?? [];
  return (
    <section className="inline-section research-triage">
      <header className="section-header-row">
        <div>
          <h2>Research Preparation</h2>
          <span>Safe readiness scan for pending ticker groups.</span>
        </div>
        <div className="button-row">
          <button type="button" onClick={onScan}>
            <RefreshCw size={15} /> Scan
          </button>
          <button type="button" onClick={onDiscoverSources} disabled={sourceCandidateCount < 1}>
            <Search size={15} /> Discover
          </button>
          <button type="button" onClick={onStageSources} disabled={stageableCount < 1}>
            <FileJson size={15} /> Stage
          </button>
          <button type="button" onClick={onLoadSources} disabled={loadableCount < 1}>
            <Database size={15} /> Load
          </button>
          <button type="button" onClick={onComputeReady} disabled={etfSourceCount < 1}>
            <RefreshCw size={15} /> Recompute
          </button>
          <button type="button" onClick={onPrepareReady} disabled={preparation.ready_to_apply_count < 1}>
            <Check size={15} /> Prepare ready tickers
          </button>
          <button type="button" onClick={onIgnoreContext} disabled={preparation.already_scoreable_count < 1}>
            <Eye size={15} /> Ignore scoreable context
          </button>
          <button type="button" onClick={onAllSafe} disabled={!preparation.total_items}>
            <Play size={15} /> All safe
          </button>
        </div>
      </header>
      <section className="mini-metric-grid">
        <Metric label="Items" value={String(preparation.total_items)} detail={preparation.source} />
        <Metric label="Ready Apply" value={String(preparation.ready_to_apply_count)} detail="confirm required" />
        <Metric label="Scoreable" value={String(preparation.already_scoreable_count)} detail="context-only" />
        <Metric label="Manual" value={String(preparation.manual_blocked_count)} detail="source/user input" />
        <Metric label="Sources" value={String(sourceCandidateCount)} detail="discoverable" />
        <Metric label="Staged" value={String(loadableCount)} detail="loadable rows" />
      </section>
      {autopilot && (
        <div className="plan-box">
          <strong>Autopilot</strong>
          <dl>
            <dt>Status</dt>
            <dd>{autopilot.enabled ? "enabled" : "disabled"}</dd>
            <dt>Source</dt>
            <dd>{autopilot.source}</dd>
            <dt>Due</dt>
            <dd>{String(autopilot.due)}</dd>
            <dt>Throttle</dt>
            <dd>{formatNumber(autopilot.throttle_seconds)}s</dd>
            <dt>Latest</dt>
            <dd>{autopilot.latest_started_at ? `${autopilot.latest_status || "unknown"} ${autopilot.latest_started_at}` : "none"}</dd>
            <dt>Rows</dt>
            <dd>{formatNumber(autopilot.latest_rows_loaded)}</dd>
            <dt>Manual asks</dt>
            <dd>{autopilot.manual_blocker_tickers.length ? autopilot.manual_blocker_tickers.join(", ") : "none"}</dd>
          </dl>
          {autopilot.latest_warnings?.length ? <small>{autopilot.latest_warnings.join("; ")}</small> : null}
        </div>
      )}
      <div className="table-wrap compact-table">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>State</th>
              <th>Automation</th>
              <th>Path</th>
              <th>Rows</th>
              <th>Sources</th>
              <th>Staged</th>
              <th>Blockers</th>
              <th>Warnings</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {topItems.map((item) => (
              <tr key={`${item.source}-${item.ticker}`}>
                <td><strong>{item.ticker}</strong></td>
                <td><StatusPill value={item.preparation_state} /></td>
                <td>{item.automation_stage || "scan"}</td>
                <td>{item.research_path}</td>
                <td>{item.candidate_count}</td>
                <td>{sourceCandidateText(item)}</td>
                <td>{stagedRowText(item)}</td>
                <td>{listText(item.blockers)}</td>
                <td>{listText(item.warnings)}</td>
                <td>{item.recommended_action}{item.cannot_automate_reason ? ` ${item.cannot_automate_reason}` : ""}</td>
              </tr>
            ))}
            {!topItems.length && (
              <tr>
                <td colSpan={10}>No pending research preparation items.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <small>
        State counts: {Array.from(stateCounts.entries()).map(([key, value]) => `${key} ${value}`).join(", ") || "none"}
      </small>
      {preparation.next_actions?.length ? (
        <pre className="text-report compact-report">{preparation.next_actions.join("\n")}</pre>
      ) : null}
      {manualBlockers.length > 0 && (
        <div className="table-wrap compact-table">
          <table>
            <thead>
              <tr>
                <th>Ticker</th>
                <th>State</th>
                <th>Cannot automate</th>
                <th>Required</th>
                <th>Attempted sources</th>
                <th>Blockers</th>
                <th>Safe next action</th>
              </tr>
            </thead>
            <tbody>
              {manualBlockers.map((packet) => (
                <tr key={`manual-${packet.ticker}`}>
                  <td><strong>{packet.ticker}</strong></td>
                  <td><StatusPill value={packet.state} /></td>
                  <td>{packet.cannot_automate_reason}</td>
                  <td>{listText(packet.required_fields)}</td>
                  <td>{packet.attempted_sources?.map((source) => `${source.source}:${source.status}`).join("; ") || "none"}</td>
                  <td>{listText(packet.blockers)}</td>
                  <td>{packet.safe_next_action}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function ResearchForeignEquitySourcePanel({
  payload,
  onDryRun,
  onExportTemplate,
  onApply
}: {
  payload: ForeignEquitySourcePayload;
  onDryRun: () => void;
  onExportTemplate: () => void;
  onApply: () => void;
}) {
  const validation = payload.validation;
  const tickerStatuses = validation.ticker_statuses ?? [];
  const diagnostics = validation.diagnostics ?? [];
  return (
    <section className="inline-section research-triage">
      <header className="section-header-row">
        <div>
          <h2>Foreign Equity Sources</h2>
          <span>Source-backed fundamentals, EPS estimates, and analyst targets for foreign-equity scoreability.</span>
        </div>
        <div className="button-row">
          <button type="button" onClick={onExportTemplate}>
            <FileJson size={15} /> Export templates
          </button>
          <button type="button" onClick={onDryRun}>
            <Eye size={15} /> Dry run
          </button>
          <button type="button" onClick={onApply} disabled={!validation.apply_ready}>
            <Check size={15} /> Apply source rows
          </button>
        </div>
      </header>
      <section className="mini-metric-grid">
        <Metric label="Fund Rows" value={String(validation.valid_fundamental_rows)} detail="valid staged" />
        <Metric label="EPS Rows" value={String(validation.valid_estimate_rows)} detail="valid staged" />
        <Metric label="Target Rows" value={String(validation.valid_analyst_target_rows)} detail="valid staged" />
        <Metric label="Invalid" value={String(validation.invalid_rows)} detail={validation.blocked_reason || "none"} />
        <Metric label="Required" value={String(validation.source_required_tickers.length)} detail={validation.source_required_tickers.join(", ") || "none"} />
      </section>
      <div className="plan-box">
        <dl>
          <dt>Fundamentals</dt>
          <dd>{validation.fundamentals_path}</dd>
          <dt>Estimates</dt>
          <dd>{validation.estimates_path}</dd>
          <dt>Analyst Targets</dt>
          <dd>{validation.analyst_targets_path}</dd>
          <dt>Target Tickers</dt>
          <dd>{validation.valid_analyst_target_tickers.join(", ") || "none"}</dd>
          <dt>Projected Ready</dt>
          <dd>{validation.projected_ready_tickers.join(", ") || "none"}</dd>
          <dt>Apply Ready</dt>
          <dd>{String(validation.apply_ready)}</dd>
        </dl>
      </div>
      <div className="table-wrap compact-table">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Status</th>
              <th>Fundamentals</th>
              <th>EPS Estimate</th>
              <th>Analyst Target</th>
              <th>Target</th>
              <th>Score</th>
              <th>Blockers</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {tickerStatuses.map((item) => (
              <tr key={valueText(item.ticker)}>
                <td><strong>{valueText(item.ticker)}</strong></td>
                <td><StatusPill value={valueText(item.status)} /></td>
                <td>{valueText(item.fundamental_rows)}</td>
                <td>{valueText(item.estimate_available)}</td>
                <td>{valueText(item.analyst_target_available ?? item.projected_analyst_target_available)}</td>
                <td>{valueText(item.target_available)}</td>
                <td>{valueText(item.score_available)}</td>
                <td>{valueText(item.blockers)}</td>
                <td>{valueText(item.recommended_action)}</td>
              </tr>
            ))}
            {!tickerStatuses.length && (
              <tr>
                <td colSpan={9}>No foreign-equity source diagnostics.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {diagnostics.length > 0 && (
        <div className="table-wrap compact-table">
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Row</th>
                <th>Ticker</th>
                <th>Status</th>
                <th>Source</th>
                <th>Blockers</th>
              </tr>
            </thead>
            <tbody>
              {diagnostics.slice(0, 20).map((item, index) => (
                <tr key={`foreign-source-${index}`}>
                  <td>{valueText(item.row_type)}</td>
                  <td>{valueText(item.row_number)}</td>
                  <td>{valueText(item.ticker)}</td>
                  <td><StatusPill value={valueText(item.status)} /></td>
                  <td>{valueText(item.source)}</td>
                  <td>{valueText(item.blockers)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {validation.warnings?.length ? <small>{validation.warnings.join("; ")}</small> : null}
    </section>
  );
}

function RecommendationDetail({
  item,
  tickerPlan,
  strategyReview,
  onPlan,
  onStrategy,
  onStatus,
  onPromote
}: {
  item: ResearchRecommendation | null;
  tickerPlan: ApiResponse<ResearchTickerPlanPayload> | null;
  strategyReview: ApiResponse<EtfStrategyReviewPayload> | null;
  onPlan: (item: ResearchRecommendation) => void;
  onStrategy: (item: ResearchRecommendation) => void;
  onStatus: (item: ResearchRecommendation, status: EditableRecommendationStatus) => void;
  onPromote: (item: ResearchRecommendation) => void;
}) {
  if (!item) {
    return <div className="detail-panel empty">Select a recommendation to review details.</div>;
  }
  const plan = tickerPlan?.ok ? tickerPlan.data.plan : null;
  const isEtfPath = researchAssetTypeForRecommendation(item) === "etf";
  return (
    <aside className="detail-panel">
      <header>
        <div>
          <span>Recommendation {item.research_recommendation_id}</span>
          <h2>{item.ticker}</h2>
        </div>
        <StatusPill value={item.status} />
      </header>
      <dl>
        <dt>Priority</dt>
        <dd>{formatNumber(item.research_priority_score)}</dd>
        <dt>Source</dt>
        <dd>{item.source}</dd>
        <dt>Topic</dt>
        <dd>{item.topic || "none"}</dd>
        <dt>Rationale</dt>
        <dd>{item.rationale || "none"}</dd>
        <dt>Warnings</dt>
        <dd>{item.warning_codes || "none"}</dd>
        <dt>Promotion blockers</dt>
        <dd>{item.promotion_blockers || "none"}</dd>
      </dl>
      <div className="button-row">
        <button type="button" onClick={() => onPlan(item)}><Eye size={15} /> Plan</button>
        {isEtfPath && (
          <button type="button" onClick={() => onStrategy(item)}><BarChart3 size={15} /> Strategy</button>
        )}
        <button type="button" onClick={() => onStatus(item, "approved")}><Check size={15} /> Approve</button>
        <button type="button" onClick={() => onStatus(item, "ignored")}><X size={15} /> Ignore</button>
        <button type="button" onClick={() => onPromote(item)}><Play size={15} /> Promote</button>
      </div>
      {tickerPlan && !tickerPlan.ok && <Offline message={tickerPlan.message} warnings={tickerPlan.warnings} />}
      {plan && (
        <div className="plan-box">
          <strong>{plan.apply_ready ? "Apply ready" : "Blocked"}</strong>
          <span>{plan.blocked_reason || "No blocker reported"}</span>
          <dl>
            <dt>Path</dt>
            <dd>{plan.research_path || "equity"}</dd>
            <dt>Asset type</dt>
            <dd>{plan.asset_type || "equity"}</dd>
            <dt>Name</dt>
            <dd>{plan.metadata.name || "unknown"}</dd>
        <dt>CIK</dt>
        <dd>{plan.metadata.cik || "missing"}</dd>
        <dt>ISIN</dt>
        <dd>{plan.metadata.isin || "missing"}</dd>
        <dt>Sector</dt>
        <dd>{plan.metadata.sector || "missing"}</dd>
        <dt>Industry</dt>
        <dd>{plan.metadata.industry || "missing"}</dd>
        <dt>Source URL</dt>
        <dd>{plan.metadata.source_url || "missing"}</dd>
        <dt>Readiness</dt>
        <dd>{listText(plan.readiness_blockers)}</dd>
          </dl>
          {plan.warnings && plan.warnings.length > 0 && <small>{plan.warnings.join("; ")}</small>}
        </div>
      )}
      {strategyReview && !strategyReview.ok && <Offline message={strategyReview.message} warnings={strategyReview.warnings} />}
      {strategyReview?.ok && <EtfStrategyReviewPanel review={strategyReview.data.review} />}
    </aside>
  );
}

function EtfStrategyReviewPanel({ review }: { review: EtfStrategyReviewPayload["review"] }) {
  return (
    <div className="plan-box etf-strategy-panel">
      <header>
        <div>
          <strong>ETF Strategy Review</strong>
          <span>{review.decision}</span>
        </div>
        <StatusPill value={review.asset_type || "etf"} />
      </header>
      {review.warnings && review.warnings.length > 0 && <small>{review.warnings.join("; ")}</small>}
      <div className="strategy-grid">
        <EtfStrategyAlternativeCard alternative={review.share} />
        <EtfStrategyAlternativeCard alternative={review.long_call} />
        <EtfStrategyAlternativeCard alternative={review.sell_put} />
      </div>
    </div>
  );
}

function EtfStrategyAlternativeCard({ alternative }: { alternative: EtfStrategyAlternative }) {
  return (
    <section className="strategy-card">
      <header>
        <strong>{alternative.label}</strong>
        <StatusPill value={alternative.status} />
      </header>
      <dl>
        <dt>Action</dt>
        <dd>{alternative.action || "none"}</dd>
        <dt>Score</dt>
        <dd>{formatNumber(alternative.score)}</dd>
        <dt>Price</dt>
        <dd>{formatNumber(alternative.current_price)}</dd>
        <dt>Target</dt>
        <dd>{formatNumber(alternative.target_price)}</dd>
        <dt>NAV</dt>
        <dd>{formatNumber(alternative.nav_per_share)}</dd>
        <dt>NAV gap</dt>
        <dd>{formatPercent(alternative.nav_gap)}</dd>
        <dt>Expiry</dt>
        <dd>{alternative.option_expiration || "n/a"}</dd>
        <dt>Strike</dt>
        <dd>{formatNumber(alternative.option_strike)}</dd>
        <dt>Premium</dt>
        <dd>{formatNumber(alternative.premium)}</dd>
        <dt>Breakeven</dt>
        <dd>{formatNumber(alternative.breakeven)}</dd>
        <dt>Max loss</dt>
        <dd>{formatCurrency(alternative.max_loss)}</dd>
        <dt>Premium yld</dt>
        <dd>{formatPercent(alternative.premium_yield)}</dd>
        <dt>Ann. yld</dt>
        <dd>{formatPercent(alternative.annualized_yield)}</dd>
        <dt>Buffer</dt>
        <dd>{formatPercent(alternative.downside_buffer_pct)}</dd>
        <dt>Assign.</dt>
        <dd>{formatCurrency(alternative.assignment_notional)}</dd>
        <dt>Source</dt>
        <dd>{alternative.source || "n/a"}</dd>
        <dt>Blockers</dt>
        <dd>{listText(alternative.blockers)}</dd>
      </dl>
      {alternative.warnings && alternative.warnings.length > 0 && <small>{alternative.warnings.join("; ")}</small>}
    </section>
  );
}

function TickerIntake() {
  const [form, setForm] = React.useState<ResearchTickerRequest>({ ticker: "", asset_type: "equity" });
  const [plan, setPlan] = React.useState<ApiResponse<ResearchTickerPlanPayload> | null>(null);
  const [status, setStatus] = React.useState<ApiResponse<ResearchTickerStatusPayload> | null>(null);
  const [report, setReport] = React.useState<ApiResponse<{ ticker: string; report_markdown: string }> | null>(null);
  const [strategyReview, setStrategyReview] = React.useState<ApiResponse<EtfStrategyReviewPayload> | null>(null);
  const [notice, setNotice] = React.useState<ActionNotice | null>(null);
  const [confirmAction, setConfirmAction] = React.useState<ConfirmAction | null>(null);

  const requestBody = cleanResearchTickerRequest(form);
  const ticker = requestBody.ticker;

  const loadPlan = async () => {
    setNotice(null);
    const response = await tomApi.researchTickerPlan(requestBody);
    setPlan(response);
    if (!response.ok) {
      setNotice({ tone: "danger", title: response.error_code, message: response.message, details: response.warnings });
    }
  };

  const loadStatusAndReport = async () => {
    if (!ticker) return;
    const [statusResponse, reportResponse] = await Promise.all([
      tomApi.researchTickerStatus(ticker),
      tomApi.fundamentalBenchmarkReport(ticker)
    ]);
    setStatus(statusResponse);
    setReport(reportResponse);
  };

  const runConfirmedAction = async () => {
    if (!confirmAction) return;
    const action = confirmAction;
    setConfirmAction(null);
    const response = await action.run();
    if (response.ok) {
      setNotice({ tone: "success", title: "Action completed", message: action.title, details: response.warnings });
      await loadStatusAndReport();
    } else {
      setNotice({ tone: "danger", title: response.error_code, message: response.message, details: response.warnings });
    }
  };

  const loadStrategyReview = async () => {
    if (!ticker) return;
    setNotice(null);
    const response = await tomApi.etfStrategyReview(ticker);
    setStrategyReview(response);
    if (!response.ok) {
      setNotice({ tone: "danger", title: response.error_code, message: response.message, details: response.warnings });
    }
  };

  return (
    <div className="intake-grid">
      <section className="form-panel">
        <h2>Ticker Intake</h2>
        <div className="segmented-control">
          <button
            className={(form.asset_type || "equity") === "equity" ? "active" : ""}
            type="button"
            onClick={() => setForm({ ...form, asset_type: "equity" })}
          >
            Equity
          </button>
          <button
            className={form.asset_type === "foreign_equity" ? "active" : ""}
            type="button"
            onClick={() => setForm({ ...form, asset_type: "foreign_equity" })}
          >
            Foreign Equity
          </button>
          <button
            className={form.asset_type === "etf" ? "active" : ""}
            type="button"
            onClick={() => setForm({ ...form, asset_type: "etf" })}
          >
            ETF
          </button>
        </div>
        <div className="form-grid">
          <Field label="Ticker" value={form.ticker} onChange={(value) => setForm({ ...form, ticker: value.toUpperCase() })} />
          <Field label="Name" value={form.name ?? ""} onChange={(value) => setForm({ ...form, name: value })} />
          <Field label="Sector" value={form.sector ?? ""} onChange={(value) => setForm({ ...form, sector: value })} />
          <Field label="Industry" value={form.industry ?? ""} onChange={(value) => setForm({ ...form, industry: value })} />
          <Field label="CIK" value={form.cik ?? ""} onChange={(value) => setForm({ ...form, cik: value })} />
          <Field label="Exchange" value={form.exchange ?? ""} onChange={(value) => setForm({ ...form, exchange: value })} />
        </div>
        <label className="check-row">
          <input
            type="checkbox"
            checked={Boolean(form.refresh_metadata)}
            onChange={(event) => setForm({ ...form, refresh_metadata: event.target.checked })}
          />
          Refresh metadata before planning
        </label>
        <div className="button-row">
          <button type="button" disabled={!ticker} onClick={() => void loadPlan()}><Eye size={15} /> Plan</button>
          <button type="button" disabled={!ticker} onClick={() => void loadStatusAndReport()}><Search size={15} /> Status</button>
          {requestBody.asset_type === "etf" && (
            <button type="button" disabled={!ticker} onClick={() => void loadStrategyReview()}><BarChart3 size={15} /> Strategy</button>
          )}
          <button
            type="button"
            disabled={!ticker}
            onClick={() =>
              setConfirmAction({
                title: `Apply ${ticker}`,
                message: "This may add or promote a scoreable research asset through TOM's existing backend workflow.",
                confirmLabel: "Apply ticker",
                run: () => tomApi.applyResearchTicker(requestBody, true) as Promise<ApiResponse<unknown>>
              })
            }
          >
            <Check size={15} /> Apply
          </button>
          <button
            type="button"
            disabled={!ticker}
            onClick={() =>
              setConfirmAction({
                title: `Refresh ${ticker}`,
                message: "This runs the bounded per-ticker research refresh and may take a while.",
                confirmLabel: "Refresh ticker",
                run: () => tomApi.refreshResearchTicker(ticker, true) as Promise<ApiResponse<unknown>>
              })
            }
          >
            <RefreshCw size={15} /> Refresh
          </button>
        </div>
      </section>
      <section className="result-panel">
        {notice && <ActionNoticeView notice={notice} onDismiss={() => setNotice(null)} />}
        {plan && <ApiResult title="Ticker Plan" response={plan} />}
        {status && <ApiResult title="Ticker Status" response={status} />}
        {strategyReview?.ok && <EtfStrategyReviewPanel review={strategyReview.data.review} />}
        {strategyReview && !strategyReview.ok && <Offline message={strategyReview.message} warnings={strategyReview.warnings} />}
        {report?.ok && <pre className="text-report">{report.data.report_markdown}</pre>}
        {report && !report.ok && <Offline message={report.message} warnings={report.warnings} />}
      </section>
      <ConfirmDialog action={confirmAction} onCancel={() => setConfirmAction(null)} onConfirm={runConfirmedAction} />
    </div>
  );
}

function OptionsPage() {
  const state = useResource(
    async () => {
      const [options, provider] = await Promise.all([
        tomApi.optionsStatus(),
        tomApi.providerStatus()
      ]);
      return { options, provider };
    },
    []
  );
  return (
    <PageFrame title="Options" subtitle="Read-only options advisory and provider health.">
      <Resource state={state}>
        {(data) => {
          const options = unwrap(data.options);
          const provider = unwrap(data.provider);
          const optionProvider = provider?.options as Record<string, unknown> | undefined;
          return (
            <>
              {apiErrorMessage(data.options) && <Offline message={apiErrorMessage(data.options) ?? ""} warnings={apiWarnings(data.options)} />}
              {apiErrorMessage(data.provider) && <Offline message={apiErrorMessage(data.provider) ?? ""} warnings={apiWarnings(data.provider)} />}
              <section className="metric-grid">
                <Metric label="Readiness" value={String(optionProvider?.readiness_status ?? "unknown")} detail="provider" />
                <Metric label="Blocked Reason" value={String(optionProvider?.blocked_reason ?? "none")} detail="provider" />
                <Metric label="Chain Rows" value={String(optionProvider?.chain_rows ?? "-")} detail="snapshots" />
                <Metric label="Review Rows" value={String(optionProvider?.review_rows ?? "-")} detail="income reviews" />
              </section>
              <pre className="text-report">{options?.summary_text ?? ""}</pre>
            </>
          );
        }}
      </Resource>
    </PageFrame>
  );
}

function DashboardDataPage() {
  const state = useResource(() => tomApi.dashboardData(), []);
  return (
    <PageFrame title="Dashboard Data" subtitle="Raw API payload used by the static TOM dashboard.">
      <Resource state={state}>
        {(response) => {
          if (!response.ok) return <Offline message={response.message} warnings={response.warnings} />;
          return <pre className="json-view">{JSON.stringify(response.data, null, 2)}</pre>;
        }}
      </Resource>
    </PageFrame>
  );
}

function Field({
  label,
  value,
  onChange
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function KeyValueList({ values }: { values: Record<string, unknown> }) {
  const entries = Object.entries(values).filter(([, value]) => value !== undefined && value !== null && value !== "");
  if (!entries.length) return null;
  return (
    <dl>
      {entries.map(([key, value]) => (
        <React.Fragment key={key}>
          <dt>{labelize(key)}</dt>
          <dd>{valueText(value)}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

function CommandList({ commands }: { commands: string[] }) {
  if (!commands.length) return null;
  return (
    <div className="command-stack">
      {commands.map((command) => (
        <div className="operator-command" key={command}>
          <span>Command</span>
          <code>{command}</code>
        </div>
      ))}
    </div>
  );
}

function ActionNoticeView({ notice, onDismiss }: { notice: ActionNotice; onDismiss: () => void }) {
  return (
    <div className={`action-notice ${notice.tone}`}>
      <div>
        <strong>{notice.title}</strong>
        <span>{notice.message}</span>
        {notice.details && notice.details.length > 0 && <small>{notice.details.join("; ")}</small>}
      </div>
      <button type="button" onClick={onDismiss} title="Dismiss">
        <X size={16} />
      </button>
    </div>
  );
}

function ConfirmDialog({
  action,
  onCancel,
  onConfirm
}: {
  action: ConfirmAction | null;
  onCancel: () => void;
  onConfirm: () => void | Promise<void>;
}) {
  if (!action) return null;
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
        <h2 id="confirm-title">{action.title}</h2>
        <p>{action.message}</p>
        <div className="button-row">
          <button type="button" onClick={onCancel}>Cancel</button>
          <button className="danger-action" type="button" onClick={() => void onConfirm()}>
            {action.confirmLabel}
          </button>
        </div>
      </section>
    </div>
  );
}

function ApiResult<T>({ title, response }: { title: string; response: ApiResponse<T> }) {
  if (!response.ok) {
    return <Offline message={response.message} warnings={response.warnings} />;
  }
  return (
    <section className="api-result">
      <h2>{title}</h2>
      <pre className="json-view">{JSON.stringify(response.data, null, 2)}</pre>
    </section>
  );
}

function groupResearchRecommendations(
  items: ResearchRecommendation[],
  triageGroups: ResearchTriageGroup[],
  preparationItems: ResearchPreparationPayload["preparation"]["items"]
): ResearchRecommendationGroup[] {
  const triageByTicker = new Map(triageGroups.map((group) => [group.ticker, group]));
  const preparationByTicker = new Map(preparationItems.map((item) => [item.ticker, item]));
  const grouped = new Map<string, ResearchRecommendation[]>();
  for (const item of items) {
    const ticker = item.ticker || "UNKNOWN";
    grouped.set(ticker, [...(grouped.get(ticker) ?? []), item]);
  }
  return Array.from(grouped.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([ticker, groupItems]) => {
      const triage = triageByTicker.get(ticker);
      const preparation = preparationByTicker.get(ticker);
      const ids = groupItems.map((item) => item.research_recommendation_id);
      const priorities = groupItems
        .map((item) => item.research_priority_score)
        .filter((value): value is number => typeof value === "number");
      const sources = uniqueValues([
        ...groupItems.map((item) => item.source),
        ...(triage?.sources ?? []),
        ...(preparation?.sources ?? [])
      ]);
      const topics = uniqueValues([
        ...groupItems.map((item) => item.topic),
        ...(triage?.topics ?? []),
        ...(preparation?.topics ?? [])
      ]);
      const warnings = uniqueValues([
        ...groupItems.flatMap((item) => splitCodeList(item.warning_codes)),
        ...(triage?.warnings ?? []),
        ...(preparation?.warnings ?? [])
      ]);
      const blockers = uniqueValues([
        ...groupItems.flatMap((item) => splitCodeList(item.promotion_blockers)),
        ...(triage?.promotion_blockers ?? []),
        ...(preparation?.blockers ?? [])
      ]);
      return {
        ticker,
        items: groupItems,
        ids,
        rowCount: groupItems.length,
        maxPriorityScore: priorities.length ? Math.max(...priorities) : triage?.max_priority_score ?? preparation?.max_priority_score,
        sources,
        topics,
        warnings,
        blockers,
        representativeIds: ids.slice(0, 6),
        classification: triage?.classification || preparation?.preparation_state || "grouped",
        preparationState: preparation?.preparation_state,
        researchPath: preparation?.research_path || null,
        recommendedAction: preparation?.recommended_action || triage?.recommended_action || "Review grouped recommendations."
      };
    });
}

function uniqueValues(values: Array<string | null | undefined>) {
  return Array.from(
    new Set(
      values
        .map((value) => (value ?? "").trim())
        .filter(Boolean)
    )
  );
}

function splitCodeList(value?: string | null) {
  if (!value) return [];
  return value
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function filterRecommendations(items: ResearchRecommendation[], query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return items;
  return items.filter((item) =>
    [
      item.ticker,
      item.source,
      item.status,
      item.topic,
      item.rationale,
      item.warning_codes,
      item.promotion_blockers
    ]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(normalized))
  );
}

function researchAssetTypeForRecommendation(item: ResearchRecommendation): "equity" | "foreign_equity" | "etf" {
  const blockers = item.promotion_blockers || "";
  const codes = blockers.split(";").map((value) => value.trim());
  if (codes.includes("etf_research_ticker_requires_etf_path")) {
    return "etf";
  }
  if (codes.includes("foreign_equity_path_required")) {
    return "foreign_equity";
  }
  return "equity";
}

function cleanResearchTickerRequest(form: ResearchTickerRequest): ResearchTickerRequest {
  const request: ResearchTickerRequest = { ticker: (form.ticker || "").trim().toUpperCase() };
  request.asset_type = form.asset_type === "etf" || form.asset_type === "foreign_equity" ? form.asset_type : "equity";
  for (const key of ["name", "sector", "industry", "cik", "exchange", "currency", "country"] as const) {
    const value = form[key]?.trim();
    if (value) request[key] = value;
  }
  if (form.refresh_metadata) request.refresh_metadata = true;
  return request;
}

function PageFrame({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        <BarChart3 size={24} />
      </header>
      {children}
    </div>
  );
}

function Resource<T>({ state, children }: { state: LoadState<T>; children: (value: T) => React.ReactNode }) {
  if (state.status === "loading") return <div className="loading">Loading TOM data...</div>;
  if (state.status === "error") return <Offline message={state.message} warnings={state.warnings} />;
  return <>{children(state.value)}</>;
}

function Offline({ message, warnings = [] }: { message: string; warnings?: string[] }) {
  return (
    <div className="offline">
      <strong>Local backend offline</strong>
      <span>{message || "Start the TOM API server and refresh this page."}</span>
      {warnings.length > 0 && <small>{warnings.join("; ")}</small>}
    </div>
  );
}

function Banner({ tone, items }: { tone: "warning" | "danger"; items: string[] }) {
  return (
    <div className={`banner ${tone}`}>
      {items.map((item) => (
        <span key={item}>{item}</span>
      ))}
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function StatusPill({ value }: { value: string }) {
  return <span className={`pill ${value.replace(/[^a-z0-9_-]/gi, "-").toLowerCase()}`}>{value}</span>;
}

function getPathValue(source: unknown, path: string): unknown {
  let current = source;
  for (const segment of path.split(".")) {
    if (!current || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[segment];
  }
  return current;
}

function textValue(source: unknown, path: string, fallback = "none") {
  const value = getPathValue(source, path);
  if (value === null || value === undefined || value === "") return fallback;
  if (Array.isArray(value)) return value.length ? value.join(", ") : fallback;
  return String(value);
}

function listValue(source: unknown, path: string, fallback = "none") {
  const value = getPathValue(source, path);
  if (Array.isArray(value)) return value.length ? value.join(", ") : fallback;
  return textValue(source, path, fallback);
}

function stringArrayValue(source: unknown, path: string) {
  const value = getPathValue(source, path);
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

function recordArrayValue(source: unknown, path: string) {
  const value = getPathValue(source, path);
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is Record<string, unknown> =>
      Boolean(item) && typeof item === "object" && !Array.isArray(item)
  );
}

function listText(items: unknown[] | undefined, fallback = "none") {
  if (!items || !items.length) return fallback;
  return items.map((item) => String(item)).join(", ");
}

function sourceCandidateText(item: ResearchPreparationPayload["preparation"]["items"][number]) {
  const candidates = item.source_candidates || [];
  if (!candidates.length) return "none";
  return candidates
    .map((candidate) => `${candidate.source}:${candidate.status}`)
    .join(", ");
}

function stagedRowText(item: ResearchPreparationPayload["preparation"]["items"][number]) {
  const rows = item.staged_rows || [];
  if (!rows.length) return "none";
  return rows
    .map((row) => `${row.row_type} ${row.row_count}`)
    .join(", ");
}

function valueText(value: unknown) {
  if (value === null || value === undefined || value === "") return "none";
  if (Array.isArray(value)) return value.length ? value.map((item) => String(item)).join(", ") : "none";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function statusCountsText(counts: Record<string, number>) {
  const entries = Object.entries(counts);
  if (!entries.length) return "no statuses";
  return entries.map(([key, value]) => `${labelize(key)} ${value}`).join(", ");
}

function labelize(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatNumber(value?: number | null) {
  if (typeof value !== "number") return "";
  return value.toFixed(1);
}

function formatPercent(value?: number | null) {
  if (typeof value !== "number") return "";
  return `${(value * 100).toFixed(1)}%`;
}

function formatCurrency(value?: number | null) {
  if (typeof value !== "number") return "";
  return `$${value.toFixed(2)}`;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Shell />
  </React.StrictMode>
);
