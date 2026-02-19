import { Component, Show, createMemo } from 'solid-js';
import { Sparkles } from 'lucide-solid';
import clsx from 'clsx';

interface Props {
  sentiment?: string | null;
  reason?: string | null;
  backend?: string | null;
  sentiment_score?: number | null;
  reason_score?: number | null;
  override?: boolean | null;
}

function pct(x: number | null | undefined) {
  if (typeof x !== 'number' || !Number.isFinite(x)) return null;
  return `${Math.round(x * 100)}%`;
}

export const RouterBadge: Component<Props> = (props) => {
  const tone = createMemo(() => {
    const s = (props.sentiment ?? '').toLowerCase();
    if (s === 'negative') return 'neg';
    if (s === 'positive') return 'pos';
    if (s === 'neutral') return 'neu';
    return 'unk';
  });

  const cls = createMemo(() => {
    const t = tone();
    return clsx(
      'inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider',
      t === 'neg' && 'bg-rose-500/10 text-rose-300 border-rose-500/20',
      t === 'pos' && 'bg-emerald-500/10 text-emerald-300 border-emerald-500/20',
      t === 'neu' && 'bg-slate-500/10 text-slate-300 border-slate-500/20',
      t === 'unk' && 'bg-slate-800 text-slate-400 border-slate-700',
    );
  });

  const label = createMemo(() => {
    const s = (props.sentiment ?? '').toUpperCase() || 'ROUTER';
    const r = (props.reason ?? '').trim();
    return r ? `${s} • ${r}` : s;
  });

  const detail = createMemo(() => {
    const ss = pct(props.sentiment_score);
    const rs = pct(props.reason_score);
    const parts: string[] = [];
    if (props.backend) parts.push(String(props.backend));
    if (ss) parts.push(`S ${ss}`);
    if (rs) parts.push(`R ${rs}`);
    if (props.override) parts.push('OVERRIDE');
    return parts.join(' · ');
  });

  const shouldShow = createMemo(() => {
    return !!(props.sentiment || props.reason || props.backend);
  });

  return (
    <Show when={shouldShow()}>
      <span class={cls()} title={detail() || undefined}>
        <Sparkles size={12} />
        <span class="max-w-55 truncate">{label()}</span>
      </span>
    </Show>
  );
};

export default RouterBadge;
