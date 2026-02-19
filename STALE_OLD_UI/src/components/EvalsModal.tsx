import { sessionState } from '../stores/sessionStore';
import { Component, For, Show, createEffect, createMemo, createSignal } from 'solid-js';
import { X, BarChart3, Search, RefreshCw, ExternalLink } from 'lucide-solid';
import clsx from 'clsx';
import { EvalService } from '../services/EvalService';
import type {
  EvalSearchItem,
  FulltextItem,
  VectorSearchItem,
  MetricSummaryRow,
  MetricFailureRow,
} from '../types/eval';
import EvalTraceModal from './EvalTraceModal';
import { chatState } from '../stores/chat';

type Tab = 'search' | 'metrics' | 'fulltext' | 'vector';

function pct(x: number) {
  if (!Number.isFinite(x)) return '0%';
  return `${Math.round(x * 100)}%`;
}

function openrouterKeyForVector() {
  const sid = sessionState.sessionId;
  return sid ? (localStorage.getItem(`or_key_${sid}`) || '') : '';
}

const EvalsModal: Component<{ isOpen: boolean; onClose: () => void }> = (props) => {
  const [tab, setTab] = createSignal<Tab>('search');

  // trace drilldown
  const [traceOpen, setTraceOpen] = createSignal(false);
  const [traceId, setTraceId] = createSignal<string>('');

  // SEARCH state
  const [items, setItems] = createSignal<EvalSearchItem[]>([]);
  const [total, setTotal] = createSignal(0);
  const [limit, setLimit] = createSignal(25);
  const [offset, setOffset] = createSignal(0);

  const [sessionId, setSessionId] = createSignal('');
  const [status, setStatus] = createSignal('');
  const [provider, setProvider] = createSignal('');
  const [model, setModel] = createSignal('');
  const [caseId, setCaseId] = createSignal('');
  const [metricName, setMetricName] = createSignal('');
  const [passed, setPassed] = createSignal<'any' | 'true' | 'false'>('any');

  const [loading, setLoading] = createSignal(false);
  const [err, setErr] = createSignal<string | null>(null);

  const canPrev = createMemo(() => offset() > 0);
  const canNext = createMemo(() => offset() + limit() < total());

  const runSearch = async () => {
    setLoading(true);
    setErr(null);
    try {
      const res = await EvalService.search({
        limit: limit(),
        offset: offset(),
        session_id: sessionId() || undefined,
        status: status() || undefined,
        provider: provider() || undefined,
        model: model() || undefined,
        case_id: caseId() || undefined,
        metric_name: metricName() || undefined,
        passed: passed() === 'any' ? undefined : passed() === 'true',
        order: 'desc',
      });
      setItems(res.items ?? []);
      setTotal(res.total ?? 0);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  // METRICS state
  const [summary, setSummary] = createSignal<MetricSummaryRow[]>([]);
  const [overall, setOverall] = createSignal(0);
  const [failures, setFailures] = createSignal<MetricFailureRow[]>([]);

  const runMetrics = async () => {
    setLoading(true);
    setErr(null);
    try {
      const s = await EvalService.metricsSummary();
      setSummary(s.items ?? []);
      setOverall(s.overall_pass_rate ?? 0);

      const f = await EvalService.metricsFailures({ limit: 50, offset: 0 });
      setFailures(f.items ?? []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  // FULLTEXT state
  const [ftQ, setFtQ] = createSignal('');
  const [ftKind, setFtKind] = createSignal<'event' | 'trace' | 'result'>('event');
  const [ftItems, setFtItems] = createSignal<FulltextItem[]>([]);

  const runFulltext = async () => {
    if (!ftQ().trim()) return;
    setLoading(true);
    setErr(null);
    try {
      const r = await EvalService.fulltext({ q: ftQ().trim(), kind: ftKind(), limit: 50, offset: 0 });
      setFtItems(r.items ?? []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  // VECTOR state
  const [vsText, setVsText] = createSignal('');
  const [vsKind, setVsKind] = createSignal<'trace' | 'result'>('trace');
  const [vsItems, setVsItems] = createSignal<VectorSearchItem[]>([]);

  const runVector = async () => {
    if (!vsText().trim()) return;
    setLoading(true);
    setErr(null);
    try {
      const r = await EvalService.vectorSearch(
        { kind: vsKind(), text: vsText().trim(), k: 25, min_score: 0.1 },
        openrouterKeyForVector(),
      );
      setVsItems(r.items ?? []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  // when opened, load current tab
  createEffect(() => {
    if (!props.isOpen) return;
    setOffset(0);
    if (tab() === 'metrics') runMetrics();
    else if (tab() === 'search') runSearch();
  });

  const openTrace = (id: string) => {
    setTraceId(id);
    setTraceOpen(true);
  };

  const TopTabs: Component = () => (
    <div class="flex flex-wrap items-center gap-2">
      <button onClick={() => setTab('search')} class={clsx(btnTab, tab() === 'search' && btnTabActive)}>Search</button>
      <button onClick={() => setTab('metrics')} class={clsx(btnTab, tab() === 'metrics' && btnTabActive)}>Metrics</button>
      <button onClick={() => setTab('fulltext')} class={clsx(btnTab, tab() === 'fulltext' && btnTabActive)}>Fulltext</button>
      <button onClick={() => setTab('vector')} class={clsx(btnTab, tab() === 'vector' && btnTabActive)}>Vector</button>
    </div>
  );

  const refresh = async () => {
    if (tab() === 'metrics') return runMetrics();
    if (tab() === 'search') return runSearch();
  };

  return (
    <Show when={props.isOpen}>
      <div class="fixed inset-0 z-9997 bg-black/60 backdrop-blur-sm" onClick={(e) => e.target === e.currentTarget && props.onClose()}>
        <div class="absolute inset-0 flex items-center justify-center p-3 sm:p-6">
          <div class="w-full max-w-6xl h-[88vh] rounded-2xl border border-slate-700/50 bg-slate-950/90 shadow-2xl overflow-hidden">
            <div class="flex items-center justify-between px-4 py-3 border-b border-slate-800/70">
              <div class="flex items-center gap-2 text-slate-200">
                <BarChart3 size={16} />
                <div class="text-sm font-semibold">Eval Dashboard</div>
                <div class="ml-3">
                  <TopTabs />
                </div>
              </div>

              <div class="flex items-center gap-2">
                <button
                  class="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-semibold text-slate-300 bg-slate-800/40 hover:bg-slate-800/70"
                  onClick={refresh}
                  title="Refresh"
                >
                  <RefreshCw size={14} /> Refresh
                </button>
                <button
                  class="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-semibold text-slate-300 bg-slate-800/40 hover:bg-slate-800/70"
                  onClick={props.onClose}
                >
                  <X size={14} /> Close
                </button>
              </div>
            </div>

            <div class="h-[calc(88vh-52px)] overflow-y-auto p-4 space-y-4">
              <Show when={err()}>
                <div class="rounded-xl border border-rose-900/40 bg-rose-900/10 p-3 text-rose-300 text-sm">
                  {err()}
                </div>
              </Show>

              {/* SEARCH TAB */}
              <Show when={tab() === 'search'}>
                <div class="rounded-2xl border border-slate-800/70 bg-slate-900/30 p-4 space-y-3">
                  <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <Input label="session_id" value={sessionId()} setValue={setSessionId} />
                    <Input label="status" value={status()} setValue={setStatus} />
                    <Input label="provider" value={provider()} setValue={setProvider} />
                    <Input label="model" value={model()} setValue={setModel} />
                    <Input label="case_id" value={caseId()} setValue={setCaseId} />
                    <Input label="metric_name" value={metricName()} setValue={setMetricName} />
                    <div>
                      <div class="text-[11px] text-slate-400 font-semibold mb-1">passed</div>
                      <select
                        class={selectCls}
                        value={passed()}
                        onChange={(e) => setPassed(e.currentTarget.value as any)}
                      >
                        <option value="any">any</option>
                        <option value="true">true</option>
                        <option value="false">false</option>
                      </select>
                    </div>

                    <div class="flex items-end gap-2">
                      <button class={btnPrimary} onClick={() => { setOffset(0); runSearch(); }}>
                        <Search size={14} /> Search
                      </button>
                      <button class={btnSecondary} onClick={() => { setSessionId(''); setStatus(''); setProvider(''); setModel(''); setCaseId(''); setMetricName(''); setPassed('any'); setOffset(0); }}>
                        Clear
                      </button>
                    </div>
                  </div>
                </div>

                <div class="rounded-2xl border border-slate-800/70 bg-slate-900/30 p-4">
                  <div class="flex items-center justify-between mb-3">
                    <div class="text-slate-200 text-sm font-semibold">
                      Traces ({items().length}/{total()})
                    </div>
                    <div class="flex items-center gap-2">
                      <button class={btnSecondary} disabled={!canPrev()} onClick={() => { setOffset(Math.max(0, offset() - limit())); runSearch(); }}>
                        Prev
                      </button>
                      <button class={btnSecondary} disabled={!canNext()} onClick={() => { setOffset(offset() + limit()); runSearch(); }}>
                        Next
                      </button>
                    </div>
                  </div>

                  <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs">
                      <thead class="text-slate-400">
                        <tr>
                          <th class="py-2 pr-3">trace_id</th>
                          <th class="py-2 pr-3">status</th>
                          <th class="py-2 pr-3">provider/model</th>
                          <th class="py-2 pr-3">events</th>
                          <th class="py-2 pr-3">evals</th>
                          <th class="py-2 pr-3">pass</th>
                          <th class="py-2 pr-3"></th>
                        </tr>
                      </thead>
                      <tbody class="text-slate-200">
                        <For each={items()}>
                          {(r) => (
                            <tr class="border-t border-slate-800/60">
                              <td class="py-2 pr-3 font-mono text-[11px]">{r.trace_id}</td>
                              <td class="py-2 pr-3">{r.status ?? ''}</td>
                              <td class="py-2 pr-3">
                                <div class="text-[11px]">{r.provider ?? ''}</div>
                                <div class="font-mono text-[10px] text-slate-400">{r.model ?? ''}</div>
                              </td>
                              <td class="py-2 pr-3 font-mono">{r.event_count}</td>
                              <td class="py-2 pr-3 font-mono">{r.eval_count}</td>
                              <td class="py-2 pr-3 font-mono">{r.pass_count}</td>
                              <td class="py-2 pr-3">
                                <button class={btnLink} onClick={() => openTrace(r.trace_id)}>
                                  Open <ExternalLink size={12} />
                                </button>
                              </td>
                            </tr>
                          )}
                        </For>
                      </tbody>
                    </table>
                  </div>

                  <Show when={loading()}>
                    <div class="mt-3 text-slate-400 text-xs">Loading…</div>
                  </Show>
                </div>
              </Show>

              {/* METRICS TAB */}
              <Show when={tab() === 'metrics'}>
                <div class="rounded-2xl border border-slate-800/70 bg-slate-900/30 p-4">
                  <div class="flex items-center justify-between">
                    <div class="text-slate-200 text-sm font-semibold">Top Panel</div>
                    <div class="text-slate-400 text-xs">Overall pass rate: <span class="text-slate-200 font-semibold">{pct(overall())}</span></div>
                  </div>

                  <div class="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div class="rounded-xl border border-slate-800/60 bg-slate-950/40 p-3">
                      <div class="text-slate-200 text-xs font-semibold mb-2">Pass rate by metric</div>
                      <div class="space-y-2">
                        <For each={summary()}>
                          {(m) => (
                            <div class="flex items-center justify-between gap-3">
                              <div class="font-mono text-[11px] text-slate-200">{m.metric_name}</div>
                              <div class="text-[11px] text-slate-400">
                                {m.pass_count}/{m.total} ({pct(m.pass_rate)})
                              </div>
                            </div>
                          )}
                        </For>
                      </div>
                    </div>

                    <div class="rounded-xl border border-slate-800/60 bg-slate-950/40 p-3">
                      <div class="text-slate-200 text-xs font-semibold mb-2">Latest failures</div>
                      <div class="space-y-2">
                        <For each={failures()}>
                          {(f) => (
                            <button
                              class="w-full text-left rounded-lg border border-slate-800/60 bg-slate-950/50 p-2 hover:bg-slate-900/60 transition-colors"
                              onClick={() => openTrace(f.trace_id)}
                            >
                              <div class="flex items-center justify-between">
                                <div class="font-mono text-[11px] text-slate-200">{f.metric_name}</div>
                                <div class="font-mono text-[10px] text-slate-500">{f.trace_id}</div>
                              </div>
                              <div class="text-[11px] text-slate-400 mt-1">
                                {f.provider ?? ''} {f.model ?? ''} • {f.trace_status ?? ''}
                              </div>
                            </button>
                          )}
                        </For>
                      </div>
                    </div>
                  </div>

                  <Show when={loading()}>
                    <div class="mt-3 text-slate-400 text-xs">Loading…</div>
                  </Show>
                </div>
              </Show>

              {/* FULLTEXT TAB */}
              <Show when={tab() === 'fulltext'}>
                <div class="rounded-2xl border border-slate-800/70 bg-slate-900/30 p-4 space-y-3">
                  <div class="flex flex-wrap items-end gap-2">
                    <div class="flex-1 min-w-55">
                      <div class="text-[11px] text-slate-400 font-semibold mb-1">q</div>
                      <input class={inputCls} value={ftQ()} onInput={(e) => setFtQ(e.currentTarget.value)} placeholder="EMI / otp / tool name…" />
                    </div>
                    <div>
                      <div class="text-[11px] text-slate-400 font-semibold mb-1">kind</div>
                      <select class={selectCls} value={ftKind()} onChange={(e) => setFtKind(e.currentTarget.value as any)}>
                        <option value="event">event</option>
                        <option value="trace">trace</option>
                        <option value="result">result</option>
                      </select>
                    </div>
                    <button class={btnPrimary} onClick={runFulltext}><Search size={14} /> Search</button>
                  </div>

                  <div class="space-y-2">
                    <For each={ftItems()}>
                      {(r) => (
                        <button
                          class="w-full text-left rounded-xl border border-slate-800/60 bg-slate-950/40 p-3 hover:bg-slate-900/60 transition-colors"
                          onClick={() => r.trace_id && openTrace(r.trace_id)}
                        >
                          <div class="flex items-center justify-between">
                            <div class="text-[11px] text-slate-200">{(r.labels ?? []).join(', ')}</div>
                            <div class="text-[11px] text-slate-400">score={r.score?.toFixed?.(3) ?? r.score}</div>
                          </div>
                          <div class="mt-1 font-mono text-[11px] text-slate-500">
                            trace={r.trace_id ?? ''} {r.event_key ? `• ${r.event_key}` : ''} {r.metric_name ? `• ${r.metric_name}` : ''}
                          </div>
                          <div class="mt-2 text-slate-200 text-xs whitespace-pre-wrap">{r.preview ?? ''}</div>
                        </button>
                      )}
                    </For>
                  </div>

                  <Show when={loading()}>
                    <div class="mt-3 text-slate-400 text-xs">Loading…</div>
                  </Show>
                </div>
              </Show>

              {/* VECTOR TAB */}
              <Show when={tab() === 'vector'}>
                <div class="rounded-2xl border border-slate-800/70 bg-slate-900/30 p-4 space-y-3">
                  <div class="flex flex-wrap items-end gap-2">
                    <div class="flex-1 min-w-55">
                      <div class="text-[11px] text-slate-400 font-semibold mb-1">text</div>
                      <input class={inputCls} value={vsText()} onInput={(e) => setVsText(e.currentTarget.value)} placeholder="stolen vehicle stop emi…" />
                    </div>
                    <div>
                      <div class="text-[11px] text-slate-400 font-semibold mb-1">kind</div>
                      <select class={selectCls} value={vsKind()} onChange={(e) => setVsKind(e.currentTarget.value as any)}>
                        <option value="trace">trace</option>
                        <option value="result">result</option>
                      </select>
                    </div>
                    <button class={btnPrimary} onClick={runVector}><Search size={14} /> Search</button>
                  </div>

                  <div class="space-y-2">
                    <For each={vsItems()}>
                      {(r) => (
                        <button
                          class="w-full text-left rounded-xl border border-slate-800/60 bg-slate-950/40 p-3 hover:bg-slate-900/60 transition-colors"
                          onClick={() => r.trace_id && openTrace(r.trace_id)}
                        >
                          <div class="flex items-center justify-between">
                            <div class="text-[11px] text-slate-200">{(r.labels ?? []).join(', ')}</div>
                            <div class="text-[11px] text-slate-400">score={r.score?.toFixed?.(3) ?? r.score}</div>
                          </div>
                          <div class="mt-1 font-mono text-[11px] text-slate-500">
                            trace={r.trace_id ?? ''} {r.metric_name ? `• ${r.metric_name}` : ''} {r.provider ? `• ${r.provider}` : ''} {r.model ? `• ${r.model}` : ''}
                          </div>
                        </button>
                      )}
                    </For>
                  </div>

                  <Show when={loading()}>
                    <div class="mt-3 text-slate-400 text-xs">Loading…</div>
                  </Show>
                </div>
              </Show>
            </div>
          </div>
        </div>

        <EvalTraceModal
          isOpen={traceOpen()}
          traceId={traceId()}
          onClose={() => setTraceOpen(false)}
        />
      </div>
    </Show>
  );
};

const inputCls =
  'w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 placeholder:text-slate-600 focus:border-indigo-500 focus:outline-none';
const selectCls =
  'w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none';
const btnPrimary =
  'inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-700 transition-colors';
const btnSecondary =
  'inline-flex items-center gap-2 rounded-xl bg-slate-800/60 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
const btnLink =
  'inline-flex items-center gap-1 text-xs font-semibold text-indigo-400 hover:text-indigo-300 hover:underline underline-offset-4';
const btnTab =
  'rounded-full border border-slate-700/70 bg-slate-950/60 px-3 py-1 text-[11px] font-semibold text-slate-300 hover:bg-slate-900/60';
const btnTabActive =
  'border-indigo-500/60 text-indigo-300 bg-indigo-900/20';

const Input: Component<{ label: string; value: string; setValue: (s: string) => void }> = (p) => (
  <div>
    <div class="text-[11px] text-slate-400 font-semibold mb-1">{p.label}</div>
    <input class={inputCls} value={p.value} onInput={(e) => p.setValue(e.currentTarget.value)} />
  </div>
);

export default EvalsModal;
