import { sessionState } from '../stores/sessionStore';
import {
  Component,
  createEffect,
  createMemo,
  createSignal,
  onCleanup,
  onMount,
  Show,
  For,
} from 'solid-js';
import {
  RefreshCw,
  Search,
  LayoutDashboard,
  ArrowLeft,
  Activity,
  List,
  Users,
  Sparkles,
  BrainCircuit,
  Hash,
  Terminal,
  ArrowRight,
  Database,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from 'lucide-solid';
import clsx from 'clsx';
import { EvalService } from '../services/EvalService';
import TraceListItem from '../components/dashboard/TraceListItem';
import EvalTraceModal from '../components/EvalTraceModal';
import type {
  EvalSearchItem,
  MetricSummaryRow,
  SessionClusterItem,
  VectorSearchItem,
  MetricFailureRow,
  QuestionTypeRow,
} from '../types/eval';
import { chatState } from '../stores/chat';

type Tab = 'overview' | 'sessions' | 'traces' | 'semantic';
type AnyOrStatus = 'any' | 'success' | 'error';

const DashboardPage: Component = () => {
  const [activeTab, setActiveTab] = createSignal<Tab>('overview');

  const [loading, setLoading] = createSignal(false);
  const [bgRefreshing, setBgRefreshing] = createSignal(false);
  const [lastRefreshAt, setLastRefreshAt] = createSignal<number>(Date.now());

  // Auto refresh
  const [autoRefresh, setAutoRefresh] = createSignal(false);
  const [refreshEverySec, setRefreshEverySec] = createSignal(30);

  // Data
  const [traceSample, setTraceSample] = createSignal<EvalSearchItem[]>([]);
  const [recentTraces, setRecentTraces] = createSignal<EvalSearchItem[]>([]);
  const [sessions, setSessions] = createSignal<SessionClusterItem[]>([]);
  const [sessionsTotal, setSessionsTotal] = createSignal(0);
  const [metrics, setMetrics] = createSignal<MetricSummaryRow[]>([]);
  const [overallPassRate, setOverallPassRate] = createSignal(0);
  const [totalTraces, setTotalTraces] = createSignal(0);
  const [failures, setFailures] = createSignal<MetricFailureRow[]>([]);
  const [questionTypes, setQuestionTypes] = createSignal<QuestionTypeRow[]>([]);

  // Trace modal
  const [traceId, setTraceId] = createSignal<string>('');
  const [isModalOpen, setIsModalOpen] = createSignal(false);

  // Sessions tab filter
  const [sessionSearchAppId, setSessionSearchAppId] = createSignal('');

  // Traces tab filters
  const [traceFilterSessionId, setTraceFilterSessionId] = createSignal('');
  const [traceProvider, setTraceProvider] = createSignal('');
  const [traceModel, setTraceModel] = createSignal('');
  const [traceStatus, setTraceStatus] = createSignal<AnyOrStatus>('any');

  // Semantic search
  const [vectorQuery, setVectorQuery] = createSignal('');
  const [vectorSessionId, setVectorSessionId] = createSignal('');
  const [vectorAppId, setVectorAppId] = createSignal('');
  const [vectorProvider, setVectorProvider] = createSignal('');
  const [vectorModel, setVectorModel] = createSignal('');
  const [vectorStatus, setVectorStatus] = createSignal<AnyOrStatus>('any');
  const [vectorResults, setVectorResults] = createSignal<VectorSearchItem[]>([]);
  const [isVectorSearching, setIsVectorSearching] = createSignal(false);

  const TRACE_SAMPLE_LIMIT = 200;
  const TRACE_LIST_LIMIT = 50;

  const isRefreshing = createMemo(() => loading() || bgRefreshing());

  const openTrace = (id: string) => {
    setTraceId(id);
    setIsModalOpen(true);
  };

  const navigateTo = (path: string) => {
    window.dispatchEvent(new CustomEvent('navigate', { detail: path }));
  };

  const pctText = (n: number | null | undefined) => {
    if (typeof n !== 'number' || !Number.isFinite(n)) return '0%';
    return `${Math.round(n * 100)}%`;
  };

  const formatTime = (iso: string) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatClock = (ms: number) => {
    const d = new Date(ms);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const sampleFailRate = createMemo(() => {
    const items = traceSample() ?? [];
    if (!items.length) return 0;
    const fail = items.filter((t) => (t.status ?? '').toLowerCase() !== 'success').length;
    return fail / items.length;
  });

  const latestSampleAt = createMemo(() => traceSample()?.[0]?.started_at ?? '');

  const providersInSample = createMemo(() => {
    const set = new Set<string>();
    for (const t of traceSample() ?? []) {
      const p = (t.provider ?? '').trim();
      if (p) set.add(p);
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  });

  const modelsInSample = createMemo(() => {
    const set = new Set<string>();
    for (const t of traceSample() ?? []) {
      const m = (t.model ?? '').trim();
      if (m) set.add(m);
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  });

  const loadData = async (opts?: { silent?: boolean }) => {
    const silent = !!opts?.silent;

    if (silent) setBgRefreshing(true);
    else setLoading(true);

    try {
      const st = traceStatus();
      const statusFilter = st === 'any' ? undefined : st;
      const providerFilter = traceProvider() || undefined;
      const modelFilter = traceModel() || undefined;

      const [searchRes, metricsRes, sessionsRes, failuresRes, qtRes] = await Promise.all([
        EvalService.search({
          limit: TRACE_SAMPLE_LIMIT,
          order: 'desc',
          status: statusFilter,
          provider: providerFilter,
          model: modelFilter,
        }),
        EvalService.metricsSummary(),
        EvalService.sessions({ limit: 50, app_id: sessionSearchAppId() || undefined }),
        EvalService.metricsFailures({
          limit: 12,
          offset: 0,
          status: statusFilter,
          provider: providerFilter,
          model: modelFilter,
        }),
        EvalService.questionTypes({ limit: 12 }),
      ]);

      const items = searchRes.items ?? [];
      setTraceSample(items);
      setRecentTraces(items.slice(0, TRACE_LIST_LIMIT));
      setTotalTraces(searchRes.total ?? 0);

      setMetrics(metricsRes.items ?? []);
      // Ensure backend returns overall_pass_rate, else fallback to 0
      setOverallPassRate(metricsRes.overall_pass_rate ?? 0);

      setSessions(sessionsRes.items ?? []);
      setSessionsTotal(sessionsRes.total ?? (sessionsRes.items ?? []).length);

      setFailures(failuresRes.items ?? []);
      setQuestionTypes(qtRes.items ?? []);

      setLastRefreshAt(Date.now());
    } catch (e) {
      console.error(e);
    } finally {
      if (silent) setBgRefreshing(false);
      else setLoading(false);
    }
  };

  const refreshTraces = async () => {
    setLoading(true);
    try {
      const st = traceStatus();
      const statusFilter = st === 'any' ? undefined : st;

      const res = await EvalService.search({
        limit: TRACE_SAMPLE_LIMIT,
        order: 'desc',
        session_id: traceFilterSessionId() || undefined,
        status: statusFilter,
        provider: traceProvider() || undefined,
        model: traceModel() || undefined,
      });

      const items = res.items ?? [];
      setRecentTraces(items.slice(0, TRACE_LIST_LIMIT));
      setTotalTraces(res.total ?? 0);
      setLastRefreshAt(Date.now());
    } finally {
      setLoading(false);
    }
  };

  const refreshSessions = async () => {
    setLoading(true);
    try {
      const res = await EvalService.sessions({
        limit: 50,
        app_id: sessionSearchAppId() || undefined,
      });
      setSessions(res.items ?? []);
      setSessionsTotal(res.total ?? (res.items ?? []).length);
      setLastRefreshAt(Date.now());
    } finally {
      setLoading(false);
    }
  };

  const handleVectorSearch = async () => {
    if (!vectorQuery().trim()) return;
    setIsVectorSearching(true);
    try {
      const orKey = localStorage.getItem(`or_key_${sessionState.sessionId}`);
      const st = vectorStatus();
      const statusFilter = st === 'any' ? undefined : st;

      const res = await EvalService.vectorSearch(
        {
          kind: 'trace',
          text: vectorQuery(),
          k: 20,
          min_score: 0.25,
          session_id: vectorSessionId() || undefined,
          case_id: vectorAppId() || undefined,
          provider: vectorProvider() || undefined,
          model: vectorModel() || undefined,
          status: statusFilter,
        },
        orKey || undefined,
      );
      setVectorResults(res.items ?? []);
    } catch (e) {
      console.error('Vector search failed', e);
      alert('Search failed. Ensure OpenRouter API Key is set.');
    } finally {
      setIsVectorSearching(false);
    }
  };

  const filterBySession = (sessionId: string) => {
    setTraceFilterSessionId(sessionId);
    setActiveTab('traces');
    refreshTraces();
  };

  // Auto refresh: run silent refresh on interval
  createEffect(() => {
    if (!autoRefresh()) return;
    const ms = Math.max(5, refreshEverySec()) * 1000;
    const id = setInterval(() => loadData({ silent: true }), ms);
    onCleanup(() => clearInterval(id));
  });

  onMount(() => loadData());

  const StatCard: Component<{
    title: string;
    value: string;
    sub?: string;
    icon: any;
    tone?: 'ok' | 'warn' | 'bad' | 'info';
  }> = (p) => {
    const toneCls =
      p.tone === 'ok'
        ? 'border-emerald-500/20 bg-emerald-500/5'
        : p.tone === 'warn'
          ? 'border-amber-500/20 bg-amber-500/5'
          : p.tone === 'bad'
            ? 'border-rose-500/20 bg-rose-500/5'
            : 'border-slate-800 bg-[#0F1117]';

    const iconCls =
      p.tone === 'ok'
        ? 'text-emerald-400'
        : p.tone === 'warn'
          ? 'text-amber-400'
          : p.tone === 'bad'
            ? 'text-rose-400'
            : 'text-indigo-400';

    return (
      <div class={clsx('rounded-xl border p-5', toneCls)}>
        <div class="flex items-center justify-between">
          <div class="text-xs font-semibold text-slate-500 uppercase tracking-wider">{p.title}</div>
          <div class={clsx('h-9 w-9 rounded-lg border border-slate-800 bg-slate-950/30 flex items-center justify-center', iconCls)}>
            {p.icon({ size: 16 })}
          </div>
        </div>
        <div class="mt-3 text-2xl font-bold text-white">{p.value}</div>
        <Show when={p.sub}>
          <div class="mt-1 text-xs text-slate-500">{p.sub}</div>
        </Show>
      </div>
    );
  };

  const QuestionTypesCard: Component = () => {
    const rows = createMemo(() => (questionTypes() ?? []).slice(0, 10));
    const totalPct = createMemo(() => rows().reduce((acc, r) => acc + (r.pct ?? 0), 0));

    return (
      <div class="rounded-xl border border-slate-800 bg-[#0F1117] p-6">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="text-sm font-semibold text-white flex items-center gap-2">
              <Sparkles size={16} class="text-purple-400" />
              Question Types
            </h3>
            <div class="text-xs text-slate-500 mt-1">
              Aggregated (limit {questionTypes().length}) • Coverage: {pctText(totalPct())}
            </div>
          </div>
        </div>

        <Show
          when={rows().length > 0}
          fallback={<div class="text-xs text-slate-500">No router reason stats yet.</div>}
        >
          <div class="space-y-3">
            <For each={rows()}>
              {(r) => {
                const w = Math.max(0, Math.min(100, Math.round((r.pct ?? 0) * 100)));
                return (
                  <div>
                    <div class="flex items-center justify-between gap-3 mb-1">
                      <div class="text-xs text-slate-300 truncate" title={r.reason}>
                        {r.reason || 'unknown'}
                      </div>
                      <div class="text-[11px] font-mono text-slate-400 whitespace-nowrap">
                        {r.count} • {w}%
                      </div>
                    </div>
                    <div class="w-full bg-slate-800 rounded-full overflow-hidden" title={`${r.count}`}>
                      <div class="h-2 rounded-full bg-purple-500/70" style={{ width: `${w}%` }} />
                    </div>
                  </div>
                );
              }}
            </For>
          </div>
        </Show>
      </div>
    );
  };

  return (
    <div class="min-h-screen bg-[#0A0C10] text-slate-200 font-sans selection:bg-indigo-500/30">
      {/* Top Nav */}
      <header class="border-b border-slate-800 bg-[#0F1117] sticky top-0 z-10">
        <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div class="flex h-16 items-center justify-between">
            <div class="flex items-center gap-4">
              <a
                href="/"
                class="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              >
                <ArrowLeft size={20} />
              </a>
              <div>
                <h1 class="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                  <LayoutDashboard size={18} class="text-indigo-500" />
                  Dashboard
                </h1>
                <div class="text-[10px] text-slate-500 font-mono mt-0.5">
                  refreshed {formatClock(lastRefreshAt())}
                </div>
              </div>
            </div>

            <div class="flex items-center gap-3">
              <label class="hidden sm:flex items-center gap-2 text-xs text-slate-400 select-none">
                <input
                  type="checkbox"
                  checked={autoRefresh()}
                  onChange={(e) => setAutoRefresh(e.currentTarget.checked)}
                  class="accent-indigo-500"
                />
                Auto
              </label>

              <select
                value={String(refreshEverySec())}
                onChange={(e) => setRefreshEverySec(parseInt(e.currentTarget.value, 10) || 30)}
                class="hidden sm:block rounded-lg border border-slate-800 bg-slate-950/40 px-2 py-1 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
                title="Auto refresh interval"
              >
                <option value="15">15s</option>
                <option value="30">30s</option>
                <option value="60">60s</option>
              </select>

              <button
                onClick={() => loadData()}
                class={clsx(
                  'p-2 rounded-lg bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 transition-all',
                  isRefreshing() && 'animate-spin',
                )}
                title="Refresh"
              >
                <RefreshCw size={18} />
              </button>
            </div>
          </div>
        </div>
      </header>

      <main class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
        {/* Knowledge Base Toolkit Banner */}
        <div class="mb-6 rounded-xl bg-linear-to-r from-indigo-900/40 to-slate-900/40 border border-indigo-500/20 p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-lg shadow-indigo-900/10">
          <div>
            <h2 class="text-lg font-bold text-white flex items-center gap-2">
              <Database size={20} class="text-indigo-400" /> Knowledge Base Toolkit
            </h2>
            <p class="text-sm text-slate-400 mt-1 max-w-xl">
              Manage FAQs, upload PDFs, and ingest batch data directly into the agent&apos;s memory.
            </p>
          </div>
          <button
            onClick={() => navigateTo('/faqs-toolkit')}
            class="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold transition-all shadow-lg shadow-indigo-900/20 flex items-center gap-2"
          >
            Manage Knowledge Base <ArrowRight size={16} />
          </button>
        </div>

        {/* KPI Row */}
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <StatCard
            title="Total Traces"
            value={String(totalTraces() ?? 0)}
            sub={latestSampleAt() ? `latest: ${formatTime(latestSampleAt())}` : 'latest: —'}
            icon={Hash}
            tone="info"
          />
          <StatCard
            title="Overall Pass Rate"
            value={pctText(overallPassRate())}
            sub={metrics().length ? `${metrics().length} metrics tracked` : 'no metrics yet'}
            icon={CheckCircle2}
            /* ✅ UPDATED THRESHOLD: 80% is green, 50% is amber */
            tone={overallPassRate() >= 0.8 ? 'ok' : overallPassRate() >= 0.5 ? 'warn' : 'bad'}
          />
          <StatCard
            title="Sample Fail Rate"
            value={pctText(sampleFailRate())}
            sub={`last ${traceSample().length} traces`}
            icon={AlertTriangle}
            tone={sampleFailRate() <= 0.1 ? 'ok' : sampleFailRate() <= 0.25 ? 'warn' : 'bad'}
          />
          <StatCard
            title="Active Sessions"
            value={String(sessionsTotal() ?? sessions().length)}
            sub={`showing ${sessions().length} clusters`}
            icon={Users}
            tone="info"
          />
        </div>

        {/* Tabs */}
        <div class="border-b border-slate-800 mb-6 overflow-x-auto no-scrollbar">
          <nav class="-mb-px flex space-x-6 min-w-max px-1" aria-label="Tabs">
            <button
              onClick={() => setActiveTab('overview')}
              class={clsx(
                activeTab() === 'overview'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-500 hover:text-slate-300',
                'whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium flex items-center gap-2 transition-colors',
              )}
            >
              <Activity size={16} /> Overview
            </button>
            <button
              onClick={() => setActiveTab('sessions')}
              class={clsx(
                activeTab() === 'sessions'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-500 hover:text-slate-300',
                'whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium flex items-center gap-2 transition-colors',
              )}
            >
              <Users size={16} /> Sessions
            </button>
            <button
              onClick={() => setActiveTab('traces')}
              class={clsx(
                activeTab() === 'traces'
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-500 hover:text-slate-300',
                'whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium flex items-center gap-2 transition-colors',
              )}
            >
              <List size={16} /> All Traces
            </button>
            <button
              onClick={() => setActiveTab('semantic')}
              class={clsx(
                activeTab() === 'semantic'
                  ? 'border-purple-500 text-purple-400'
                  : 'border-transparent text-slate-500 hover:text-slate-300',
                'whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium flex items-center gap-2 transition-colors',
              )}
            >
              <Sparkles size={16} /> Semantic Search
            </button>
          </nav>
        </div>

        {/* OVERVIEW TAB */}
        <Show when={activeTab() === 'overview'}>
          <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Metric Performance */}
            <div class="rounded-xl border border-slate-800 bg-[#0F1117] p-6">
              <div class="flex items-center justify-between mb-4">
                <h3 class="text-sm font-semibold text-white">Metric Performance</h3>
                <button
                  onClick={() => setActiveTab('traces')}
                  class="text-xs text-indigo-400 hover:underline"
                >
                  View Traces
                </button>
              </div>

              <div class="space-y-4">
                <For each={metrics()}>
                  {(m) => (
                    <div>
                      <div class="flex justify-between mb-1">
                        <span class="text-xs font-mono text-slate-400">{m.metric_name}</span>
                        <span class="text-xs font-bold text-slate-200">{pctText(m.pass_rate)}</span>
                      </div>
                      <div class="w-full bg-slate-800 rounded-full h-2">
                        <div
                          class={clsx(
                            'h-2 rounded-full',
                            /* ✅ UPDATED THRESHOLD: 80% is green, 50% is amber */
                            (m.pass_rate || 0) >= 0.8 ? 'bg-emerald-500' : (m.pass_rate || 0) >= 0.5 ? 'bg-amber-500' : 'bg-rose-500',
                          )}
                          style={{ width: pctText(m.pass_rate) }}
                        ></div>
                      </div>
                    </div>
                  )}
                </For>
                <Show when={metrics().length === 0}>
                  <div class="text-center py-8 text-slate-600 text-sm">No metrics collected yet.</div>
                </Show>
              </div>
            </div>

            {/* Question Types (aggregated) */}
            <QuestionTypesCard />

            {/* Latest Failures */}
            <div class="rounded-xl border border-slate-800 bg-[#0F1117] p-6">
              <div class="flex items-center justify-between mb-4">
                <h3 class="text-sm font-semibold text-white flex items-center gap-2">
                  <XCircle size={16} class="text-rose-400" />
                  Latest Failures
                </h3>
                <button onClick={() => loadData()} class="text-xs text-indigo-400 hover:underline">
                  Refresh
                </button>
              </div>

              <Show
                when={(failures() ?? []).length > 0}
                fallback={<div class="text-xs text-slate-500">No failures found (or none match filters).</div>}
              >
                <div class="space-y-3">
                  <For each={(failures() ?? []).slice(0, 10)}>
                    {(f) => (
                      <button
                        class="w-full text-left rounded-lg border border-slate-800/60 bg-slate-950/40 p-3 hover:bg-slate-900/60 transition-colors"
                        onClick={() => openTrace(f.trace_id)}
                      >
                        <div class="flex items-center justify-between gap-2">
                          <div class="text-[11px] font-mono text-slate-200 truncate">{f.metric_name}</div>
                          <span class="text-[10px] font-mono text-slate-500">{(f.trace_id || '').slice(0, 10)}…</span>
                        </div>
                        <div class="mt-1 text-[11px] text-slate-400">
                          {f.provider ?? '—'} {f.model ?? ''} • {f.trace_status ?? '—'}
                        </div>
                        <Show when={f.reasoning}>
                          <div class="mt-2 text-[11px] text-slate-500 line-clamp-2">
                            {String(f.reasoning)}
                          </div>
                        </Show>
                      </button>
                    )}
                  </For>
                </div>
              </Show>
            </div>

            {/* Recent Activity */}
            <div class="lg:col-span-3 rounded-xl border border-slate-800 bg-[#0F1117] p-6">
              <div class="flex items-center justify-between mb-4">
                <h3 class="text-sm font-semibold text-white flex items-center gap-2">
                  <Clock size={16} class="text-slate-400" />
                  Recent Activity
                </h3>
                <button
                  onClick={() => setActiveTab('traces')}
                  class="text-xs text-indigo-400 hover:underline"
                >
                  View All
                </button>
              </div>

              <Show
                when={recentTraces().length > 0}
                fallback={<div class="text-center py-10 text-slate-600 text-sm">No traces yet.</div>}
              >
                <div class="space-y-2">
                  <For each={recentTraces().slice(0, 8)}>
                    {(t) => <TraceListItem item={t} onClick={openTrace} />}
                  </For>
                </div>
              </Show>
            </div>
          </div>
        </Show>

        {/* SESSIONS TAB */}
        <Show when={activeTab() === 'sessions'}>
          <div class="rounded-xl border border-slate-800 bg-[#0F1117] overflow-hidden">
            <div class="p-4 border-b border-slate-800 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between bg-[#161b22]/50">
              <div class="relative w-full sm:max-w-md">
                <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                  <Search size={14} class="text-slate-500" />
                </div>
                <input
                  type="text"
                  value={sessionSearchAppId()}
                  onInput={(e) => setSessionSearchAppId(e.currentTarget.value)}
                  onKeyDown={(e) => e.key === 'Enter' && refreshSessions()}
                  placeholder="Filter by App ID..."
                  class="w-full bg-[#0d1117] border border-slate-700 rounded-md py-2 pl-9 pr-3 text-sm text-slate-300 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div class="flex w-full sm:w-auto gap-2">
                <button
                  onClick={refreshSessions}
                  class="flex-1 sm:flex-none flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
                >
                  <Search size={14} /> Filter
                </button>
                <button
                  onClick={() => {
                    setSessionSearchAppId('');
                    refreshSessions();
                  }}
                  class="flex-1 sm:flex-none flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-slate-800 text-slate-300 text-xs font-medium hover:bg-slate-700"
                >
                  Clear
                </button>
              </div>
            </div>

            <div class="overflow-x-auto">
              <table class="w-full text-left text-sm text-slate-400">
                <thead class="bg-[#161b22] text-xs uppercase font-medium text-slate-500">
                  <tr>
                    <th class="px-6 py-3 whitespace-nowrap">Session ID</th>
                    <th class="px-6 py-3 whitespace-nowrap">App ID</th>
                    <th class="px-6 py-3 text-right whitespace-nowrap">Traces</th>
                    <th class="px-6 py-3 whitespace-nowrap">Last Active</th>
                    <th class="px-6 py-3 whitespace-nowrap">Action</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-slate-800">
                  <For each={sessions()}>
                    {(sess) => (
                      <tr class="hover:bg-slate-900/50 transition-colors">
                        <td class="px-6 py-4 font-mono text-xs text-slate-300">{sess.session_id}</td>
                        <td class="px-6 py-4">
                          <Show
                            when={!!sess.app_id}
                            fallback={<span class="text-slate-600">—</span>}
                          >
                            <span class="inline-flex items-center rounded-md bg-indigo-400/10 px-2 py-1 text-xs font-medium text-indigo-400 ring-1 ring-inset ring-indigo-400/30 whitespace-nowrap">
                              {sess.app_id}
                            </span>
                          </Show>
                        </td>
                        <td class="px-6 py-4 text-right font-mono">{sess.trace_count}</td>
                        <td class="px-6 py-4 text-xs whitespace-nowrap">{formatTime(sess.last_active)}</td>
                        <td class="px-6 py-4">
                          <button
                            onClick={() => filterBySession(sess.session_id)}
                            class="text-indigo-400 hover:text-indigo-300 text-xs font-medium bg-indigo-500/10 px-3 py-1.5 rounded-md border border-indigo-500/20 hover:border-indigo-500/50 transition-all whitespace-nowrap"
                          >
                            View Traces
                          </button>
                        </td>
                      </tr>
                    )}
                  </For>
                </tbody>
              </table>

              <Show when={sessions().length === 0}>
                <div class="text-center py-12 text-slate-600 text-sm">No sessions recorded yet.</div>
              </Show>
            </div>
          </div>
        </Show>

        {/* TRACES TAB */}
        <Show when={activeTab() === 'traces'}>
          <div class="rounded-xl border border-slate-800 bg-[#0F1117] overflow-hidden">
            <div class="p-4 border-b border-slate-800 flex flex-col gap-3 bg-[#161b22]/50">
              <div class="flex flex-col sm:flex-row gap-3">
                <div class="relative w-full sm:max-w-md">
                  <div class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
                    <Search size={14} class="text-slate-500" />
                  </div>
                  <input
                    type="text"
                    value={traceFilterSessionId()}
                    onInput={(e) => setTraceFilterSessionId(e.currentTarget.value)}
                    onKeyDown={(e) => e.key === 'Enter' && refreshTraces()}
                    placeholder="Filter by Session ID..."
                    class="w-full bg-[#0d1117] border border-slate-700 rounded-md py-2 pl-9 pr-3 text-sm text-slate-300 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div class="flex gap-2 w-full sm:w-auto">
                  <button
                    onClick={refreshTraces}
                    class="flex-1 sm:flex-none flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 transition-colors"
                  >
                    <Search size={14} /> Search
                  </button>
                  <button
                    onClick={() => {
                      setTraceFilterSessionId('');
                      refreshTraces();
                    }}
                    class="flex-1 sm:flex-none flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-slate-800 text-slate-300 text-xs font-medium hover:bg-slate-700"
                  >
                    Clear
                  </button>
                </div>
              </div>

              {/* Advanced filters */}
              <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <div class="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-1">status</div>
                  <select
                    value={traceStatus()}
                    onChange={(e) => setTraceStatus(e.currentTarget.value as AnyOrStatus)}
                    class="w-full rounded-md border border-slate-700 bg-[#0d1117] px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="any">any</option>
                    <option value="success">success</option>
                    <option value="error">error</option>
                  </select>
                </div>

                <div>
                  <div class="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-1">provider</div>
                  <select
                    value={traceProvider()}
                    onChange={(e) => setTraceProvider(e.currentTarget.value)}
                    class="w-full rounded-md border border-slate-700 bg-[#0d1117] px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="">any</option>
                    <For each={providersInSample()}>{(p) => <option value={p}>{p}</option>}</For>
                  </select>
                </div>

                <div>
                  <div class="text-[10px] uppercase tracking-wider font-semibold text-slate-500 mb-1">model</div>
                  <input
                    value={traceModel()}
                    onInput={(e) => setTraceModel(e.currentTarget.value)}
                    list="models-list"
                    placeholder="type or pick…"
                    class="w-full rounded-md border border-slate-700 bg-[#0d1117] px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-indigo-500"
                  />
                  <datalist id="models-list">
                    <For each={modelsInSample()}>{(m) => <option value={m} />}</For>
                  </datalist>
                </div>
              </div>
            </div>

            <div class="p-4 space-y-2">
              <For each={recentTraces()}>{(trace) => <TraceListItem item={trace} onClick={openTrace} />}</For>
              <Show when={recentTraces().length === 0}>
                <div class="text-center py-12 text-slate-600 text-sm">No traces found.</div>
              </Show>
            </div>
          </div>
        </Show>

        {/* SEMANTIC SEARCH TAB */}
        <Show when={activeTab() === 'semantic'}>
          <div class="max-w-3xl mx-auto space-y-6">
            <div class="text-center space-y-4 py-8 px-4">
              <div class="inline-flex items-center justify-center p-3 rounded-2xl bg-purple-500/10 text-purple-400 mb-2">
                <BrainCircuit size={32} />
              </div>
              <h2 class="text-xl font-bold text-white">Semantic Trace Search</h2>
              <p class="text-slate-400 text-sm max-w-md mx-auto">
                Find traces by meaning rather than keywords.
              </p>

              <div class="flex flex-col gap-3 max-w-xl mx-auto mt-6">
                <div class="relative w-full">
                  <input
                    type="text"
                    value={vectorQuery()}
                    onInput={(e) => setVectorQuery(e.currentTarget.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleVectorSearch()}
                    placeholder="Describe problem (e.g. angry user)…"
                    class="w-full bg-[#161b22] border border-slate-700 rounded-xl py-3 pl-5 pr-12 text-slate-200 placeholder:text-slate-600 focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500/50 shadow-lg text-sm"
                  />
                  <button
                    onClick={handleVectorSearch}
                    disabled={isVectorSearching()}
                    class="absolute right-2 top-2 p-1.5 rounded-lg bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 transition-colors"
                  >
                    <Show when={isVectorSearching()} fallback={<Search size={18} />}>
                      <RefreshCw size={18} class="animate-spin" />
                    </Show>
                  </button>
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <input
                    type="text"
                    value={vectorSessionId()}
                    onInput={(e) => setVectorSessionId(e.currentTarget.value)}
                    placeholder="Filter Session ID"
                    class="bg-[#161b22] border border-slate-700 rounded-lg py-2.5 px-3 text-xs text-slate-300 focus:border-slate-500 focus:outline-none"
                  />
                  <input
                    type="text"
                    value={vectorAppId()}
                    onInput={(e) => setVectorAppId(e.currentTarget.value)}
                    placeholder="Filter App ID"
                    class="bg-[#161b22] border border-slate-700 rounded-lg py-2.5 px-3 text-xs text-slate-300 focus:border-slate-500 focus:outline-none"
                  />
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <select
                    value={vectorStatus()}
                    onChange={(e) => setVectorStatus(e.currentTarget.value as AnyOrStatus)}
                    class="bg-[#161b22] border border-slate-700 rounded-lg py-2.5 px-3 text-xs text-slate-300 focus:border-slate-500 focus:outline-none"
                    title="status"
                  >
                    <option value="any">status: any</option>
                    <option value="success">status: success</option>
                    <option value="error">status: error</option>
                  </select>

                  <select
                    value={vectorProvider()}
                    onChange={(e) => setVectorProvider(e.currentTarget.value)}
                    class="bg-[#161b22] border border-slate-700 rounded-lg py-2.5 px-3 text-xs text-slate-300 focus:border-slate-500 focus:outline-none"
                    title="provider"
                  >
                    <option value="">provider: any</option>
                    <For each={providersInSample()}>{(p) => <option value={p}>{p}</option>}</For>
                  </select>

                  <input
                    type="text"
                    value={vectorModel()}
                    onInput={(e) => setVectorModel(e.currentTarget.value)}
                    placeholder="model: any"
                    list="models-list"
                    class="bg-[#161b22] border border-slate-700 rounded-lg py-2.5 px-3 text-xs text-slate-300 focus:border-slate-500 focus:outline-none"
                  />
                </div>

                <div class="text-[11px] text-slate-500 flex items-center justify-center gap-2">
                  <Terminal size={12} />
                  Needs OpenRouter key for embeddings (vector search).
                </div>
              </div>
            </div>

            <div class="space-y-3 px-2 sm:px-0">
              <For each={vectorResults()}>
                {(item) => {
                  const scoreColor =
                    item.score > 0.8
                      ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                      : item.score > 0.6
                        ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
                        : 'text-slate-400 bg-slate-800 border-slate-700';

                  return (
                    <div
                      onClick={() => item.trace_id && openTrace(item.trace_id)}
                      class="group relative flex flex-col gap-3 rounded-xl border border-slate-800/60 bg-[#0F1117] p-4 transition-all hover:border-purple-500/30 hover:bg-[#161b22] cursor-pointer"
                    >
                      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-0">
                        <div class="flex items-center gap-3">
                          <span
                            class={clsx(
                              'text-xs font-bold font-mono px-2 py-0.5 rounded border whitespace-nowrap',
                              scoreColor,
                            )}
                          >
                            {(item.score * 100).toFixed(1)}% Match
                          </span>
                          <span class="text-xs font-mono text-slate-500 flex items-center gap-1 truncate max-w-37.5 sm:max-w-none">
                            <List size={10} /> {item.trace_id?.slice(0, 8)}…
                          </span>
                        </div>
                        <span
                          class={clsx(
                            'text-[10px] uppercase font-bold tracking-wider self-start sm:self-auto',
                            item.status === 'success' ? 'text-emerald-500' : 'text-rose-500',
                          )}
                        >
                          {item.status}
                        </span>
                      </div>

                      <div class="space-y-2">
                        <Show when={item.question} fallback={<div class="text-xs text-slate-500 italic">No user input captured</div>}>
                          <div class="text-sm text-slate-200 font-medium">
                            <span class="text-indigo-400 mr-2 font-bold text-xs uppercase tracking-wide block sm:inline">
                              User:
                            </span>
                            {item.question}
                          </div>
                        </Show>

                        <Show when={item.final_output}>
                          <div class="text-xs text-slate-400 line-clamp-2">
                            <span class="text-emerald-400 mr-2 font-bold text-xs uppercase tracking-wide block sm:inline">
                              AI:
                            </span>
                            {item.final_output?.replace(/<[^>]*>/g, '')}
                          </div>
                        </Show>
                      </div>

                      <div class="flex flex-wrap gap-2 mt-2 pt-2 border-t border-slate-800/50">
                        <Show when={item.session_id}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setVectorSessionId(item.session_id || '');
                            }}
                            class="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono hover:bg-slate-700 hover:text-white transition-colors"
                          >
                            <Hash size={10} /> {item.session_id?.slice(0, 8)}…
                          </button>
                        </Show>

                        <Show when={item.app_id}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setVectorAppId(item.app_id || '');
                            }}
                            class="flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono hover:bg-slate-700 hover:text-white transition-colors"
                          >
                            <Terminal size={10} /> {item.app_id}
                          </button>
                        </Show>

                        <Show when={item.metric_name}>
                          <span class="text-[10px] px-1.5 py-0.5 rounded bg-blue-900/30 text-blue-300 border border-blue-800">
                            {item.metric_name}
                          </span>
                        </Show>

                        <span class="text-[10px] text-purple-400 flex items-center gap-1 ml-auto opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity">
                          View <ArrowRight size={10} />
                        </span>
                      </div>
                    </div>
                  );
                }}
              </For>

              <Show when={!isVectorSearching() && vectorResults().length === 0 && vectorQuery().length > 0}>
                <div class="text-center py-12 text-slate-500 text-sm">
                  No semantically similar traces found.
                </div>
              </Show>
            </div>
          </div>
        </Show>
      </main>

      <EvalTraceModal
        isOpen={isModalOpen()}
        traceId={traceId()}
        onClose={() => setIsModalOpen(false)}
      />
    </div>
  );
};

export default DashboardPage;
