import { Component, For, Show, createMemo } from 'solid-js';
import clsx from 'clsx';
import type { EvalSearchItem } from '../../types/eval';
import { Sparkles } from 'lucide-solid';

function humanizeReason(s: string) {
  const x = (s || '').trim();
  if (!x) return 'Unknown';
  return x
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

type Row = { key: string; label: string; count: number; pct: number };

const QuestionTypeViz: Component<{ items: EvalSearchItem[]; topN?: number }> = (props) => {
  const topN = () => props.topN ?? 10;

  const stats = createMemo(() => {
    const items = props.items ?? [];
    const total = items.length;

    const counts = new Map<string, number>();
    let withReason = 0;

    for (const t of items) {
      const r = (t.router_reason ?? '').trim();
      const key = r || 'unknown';
      if (r) withReason += 1;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }

    const rowsAll: Row[] = Array.from(counts.entries())
      .map(([key, count]) => ({
        key,
        label: humanizeReason(key),
        count,
        pct: total > 0 ? count / total : 0,
      }))
      .sort((a, b) => b.count - a.count);

    const head = rowsAll.slice(0, topN());
    const tail = rowsAll.slice(topN());

    const otherCount = tail.reduce((acc, r) => acc + r.count, 0);
    const rows = otherCount > 0
      ? [...head, { key: 'other', label: 'Other', count: otherCount, pct: total > 0 ? otherCount / total : 0 }]
      : head;

    const coverage = total > 0 ? withReason / total : 0;

    return { total, withReason, coverage, rows };
  });

  const pctText = (x: number) => `${Math.round(x * 100)}%`;

  return (
    <div class="rounded-xl border border-slate-800 bg-[#0F1117] p-6">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h3 class="text-sm font-semibold text-white flex items-center gap-2">
            <Sparkles size={16} class="text-purple-400" />
            Question Types
          </h3>
          <div class="text-xs text-slate-500 mt-1">
            Last {stats().total} traces • Router coverage: {pctText(stats().coverage)}
          </div>
        </div>

        <Show when={stats().coverage < 0.3 && stats().total > 0}>
          <span class="text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
            Missing router_reason in /eval/search
          </span>
        </Show>
      </div>

      <Show
        when={stats().total > 0 && stats().rows.length > 0 && (stats().withReason > 0 || stats().rows.some(r => r.key === 'unknown'))}
        fallback={
          <div class="text-xs text-slate-500">
            No data yet. Once your backend returns <span class="font-mono">router_reason</span> in <span class="font-mono">/eval/search</span>, this fills automatically.
          </div>
        }
      >
        <div class="space-y-3">
          <For each={stats().rows}>
            {(r) => {
              const w = Math.max(0, Math.min(100, Math.round(r.pct * 100)));
              const barCls = clsx(
                'h-2 rounded-full transition-all',
                r.key === 'unknown' && 'bg-slate-600/60',
                r.key === 'other' && 'bg-slate-500/50',
                r.key !== 'unknown' && r.key !== 'other' && 'bg-purple-500/70',
              );

              return (
                <div>
                  <div class="flex items-center justify-between gap-3 mb-1">
                    <div class="text-xs text-slate-300 truncate" title={r.label}>
                      {r.label}
                    </div>
                    <div class="text-[11px] font-mono text-slate-400 whitespace-nowrap">
                      {r.count} • {w}%
                    </div>
                  </div>

                  <div
                    class="w-full bg-slate-800 rounded-full overflow-hidden"
                    role="progressbar"
                    aria-valuemin="0"
                    aria-valuemax="100"
                    aria-valuenow={w}
                    aria-label={r.label}
                    title={`${r.count} / ${stats().total}`}
                  >
                    <div class={barCls} style={{ width: `${w}%` }} />
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

export default QuestionTypeViz;
