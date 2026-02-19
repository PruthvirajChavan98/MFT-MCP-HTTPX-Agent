import { Component, createMemo, Show, For } from 'solid-js';
import { Sparkles, ChevronDown } from 'lucide-solid';
import clsx from 'clsx';

type TopPair = [string, number];

export interface RouterLabelScore {
  label?: string;
  score?: number;
  top?: TopPair[];
  override?: boolean;
  override_reason?: string | null;
}

export interface RouterBackendResult {
  backend: string;
  sentiment?: RouterLabelScore;
  reason?: RouterLabelScore;
  meta?: any;
}

export interface RouterEvent {
  mode?: string;
  chosen_backend?: string;
  results: RouterBackendResult[];
  raw?: any;
}

function asNum(v: unknown): number | undefined {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string') {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return undefined;
}

function asTop(v: any): TopPair[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const out: TopPair[] = [];
  for (const it of v) {
    if (Array.isArray(it) && it.length >= 2) {
      const k = String(it[0]);
      const s = asNum(it[1]);
      if (k && s != null) out.push([k, s]);
    } else if (it && typeof it === 'object') {
      const k = String((it as any).label ?? (it as any).name ?? '');
      const s = asNum((it as any).score);
      if (k && s != null) out.push([k, s]);
    }
  }
  return out.length ? out : undefined;
}

function normalizeLabelScore(raw: any): RouterLabelScore | undefined {
  if (!raw) return undefined;

  // Already in our format
  if (typeof raw === 'object' && (raw.label != null || raw.score != null || raw.top != null)) {
    return {
      label: raw.label != null ? String(raw.label) : undefined,
      score: asNum(raw.score),
      top: asTop(raw.top),
      override: raw.override === true,
      override_reason: raw.override_reason != null ? String(raw.override_reason) : null,
    };
  }

  // Sometimes backend sends: { "SENTIMENT": "negative (score=0.84) top: [...]"}
  if (typeof raw === 'string') {
    const m = raw.match(/^\s*([a-z_:-]+)\s*\(score\s*=\s*([0-9.]+)\)/i);
    if (m) {
      return { label: m[1], score: asNum(m[2]) };
    }
  }

  return undefined;
}

function normalizeRouter(raw: any): RouterEvent | null {
  if (!raw) return null;

  // Case A: { results: [...] }
  if (raw && typeof raw === 'object' && Array.isArray(raw.results)) {
    const results: RouterBackendResult[] = raw.results
      .map((r: any) => {
        const backend = String(r?.backend ?? r?.name ?? r?.provider ?? 'unknown');
        return {
          backend,
          sentiment: normalizeLabelScore(r?.sentiment ?? r?.SENTIMENT),
          reason: normalizeLabelScore(r?.reason ?? r?.REASON),
          meta: r?.meta ?? r?.META ?? undefined,
        };
      })
      .filter((x: any) => x && x.backend);

    return {
      mode: raw.mode != null ? String(raw.mode) : undefined,
      chosen_backend: raw.chosen_backend != null ? String(raw.chosen_backend) : undefined,
      results: results.length ? results : [{ backend: 'unknown', meta: raw }],
      raw,
    };
  }

  // Case B: single backend payload: { backend: "...", sentiment:..., reason:... }
  if (raw && typeof raw === 'object' && (raw.backend || raw.sentiment || raw.reason || raw.SENTIMENT || raw.REASON)) {
    const backend = String(raw.backend ?? raw.name ?? 'backend');
    return {
      mode: raw.mode != null ? String(raw.mode) : undefined,
      chosen_backend: raw.chosen_backend != null ? String(raw.chosen_backend) : undefined,
      results: [
        {
          backend,
          sentiment: normalizeLabelScore(raw.sentiment ?? raw.SENTIMENT),
          reason: normalizeLabelScore(raw.reason ?? raw.REASON),
          meta: raw.meta ?? raw.META ?? undefined,
        },
      ],
      raw,
    };
  }

  // Case C: string / unknown -> keep raw
  return { results: [{ backend: 'unknown', meta: raw }], raw };
}

function pct(n: number | undefined) {
  if (typeof n !== 'number' || !Number.isFinite(n)) return '—';
  return `${Math.round(n * 100)}%`;
}

function badgeForSentiment(label?: string) {
  const l = (label || '').toLowerCase();
  if (l.includes('neg')) return 'bg-rose-500/10 text-rose-300 border-rose-500/20';
  if (l.includes('pos')) return 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20';
  if (l.includes('neu')) return 'bg-slate-500/10 text-slate-300 border-slate-500/20';
  return 'bg-amber-500/10 text-amber-300 border-amber-500/20';
}

const Chip: Component<{ label: string; value?: string; sub?: string; cls?: string }> = (p) => (
  <span
    class={clsx(
      'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
      p.cls ?? 'bg-slate-800/40 text-slate-300 border-slate-700',
    )}
    title={p.sub ?? ''}
  >
    <span class="opacity-70">{p.label}</span>
    <span class="opacity-95">{p.value ?? '—'}</span>
  </span>
);

const RouterWidget: Component<{ payload: any }> = (props) => {
  const normalized = createMemo(() => normalizeRouter(props.payload));

  const headline = createMemo(() => {
    const n = normalized();
    if (!n || !n.results?.length) return null;
    // prefer chosen backend
    const chosen =
      (n.chosen_backend && n.results.find((r) => r.backend === n.chosen_backend)) ||
      n.results[0];

    const s = chosen?.sentiment;
    const r = chosen?.reason;

    return {
      backend: chosen?.backend ?? '—',
      sentiment: s?.label ?? '—',
      sScore: s?.score,
      reason: r?.label ?? '—',
      rScore: r?.score,
      override: s?.override ? true : false,
      overrideReason: s?.override_reason ?? null,
      mode: n.mode ?? undefined,
    };
  });

  return (
    <Show when={normalized()}>
      {(n) => (
        <details class="my-3 rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3 text-xs dark:border-slate-800 dark:bg-slate-900/40">
          <summary class="list-none cursor-pointer select-none flex items-center justify-between gap-3">
            <div class="flex items-center gap-2 text-slate-700 dark:text-slate-200">
              <Sparkles size={14} class="text-indigo-500" />
              <span class="font-semibold">Router</span>
              <Show when={headline()?.mode}>
                <span class="text-[10px] font-mono text-slate-500 dark:text-slate-400">
                  mode={headline()!.mode}
                </span>
              </Show>
            </div>

            <div class="flex items-center gap-2">
              <Show when={headline()}>
                {(h) => (
                  <>
                    <Chip label="backend" value={h().backend} />
                    <Chip
                      label="sent"
                      value={`${h().sentiment} ${pct(h().sScore)}`}
                      cls={badgeForSentiment(h().sentiment)}
                    />
                    <Show when={h().reason && h().reason !== '—'}>
                      <Chip label="reason" value={`${h().reason} ${pct(h().rScore)}`} />
                    </Show>
                    <Show when={h().override}>
                      <Chip
                        label="override"
                        value={h().overrideReason ? String(h().overrideReason) : 'true'}
                        cls="bg-amber-500/10 text-amber-300 border-amber-500/20"
                      />
                    </Show>
                  </>
                )}
              </Show>
              <ChevronDown size={14} class="text-slate-400" />
            </div>
          </summary>

          <div class="mt-3 space-y-3">
            <div class="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
              Backends ({n().results.length})
            </div>

            <div class="space-y-2">
              <For each={n().results}>
                {(r) => (
                  <div class="rounded-lg border border-slate-200 bg-white/60 p-3 dark:border-slate-800 dark:bg-slate-950/40">
                    <div class="flex flex-wrap items-center justify-between gap-2">
                      <div class="font-mono text-[11px] text-slate-700 dark:text-slate-200">
                        {r.backend}
                      </div>
                      <div class="flex flex-wrap items-center gap-2">
                        <Show when={r.sentiment?.label}>
                          <Chip
                            label="sent"
                            value={`${r.sentiment?.label} ${pct(r.sentiment?.score)}`}
                            cls={badgeForSentiment(r.sentiment?.label)}
                          />
                        </Show>
                        <Show when={r.reason?.label}>
                          <Chip
                            label="reason"
                            value={`${r.reason?.label} ${pct(r.reason?.score)}`}
                          />
                        </Show>
                      </div>
                    </div>

                    <Show when={r.meta}>
                      <div class="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
                        meta: <span class="font-mono">{JSON.stringify(r.meta)}</span>
                      </div>
                    </Show>

                    <Show when={Array.isArray(r.sentiment?.top) && (r.sentiment?.top?.length ?? 0) > 0}>
                      <div class="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
                        top sentiment:
                        <span class="ml-2 font-mono text-slate-600 dark:text-slate-300">
                          {JSON.stringify(r.sentiment?.top)}
                        </span>
                      </div>
                    </Show>

                    <Show when={Array.isArray(r.reason?.top) && (r.reason?.top?.length ?? 0) > 0}>
                      <div class="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
                        top reason:
                        <span class="ml-2 font-mono text-slate-600 dark:text-slate-300">
                          {JSON.stringify(r.reason?.top)}
                        </span>
                      </div>
                    </Show>
                  </div>
                )}
              </For>
            </div>
          </div>
        </details>
      )}
    </Show>
  );
};

export default RouterWidget;
