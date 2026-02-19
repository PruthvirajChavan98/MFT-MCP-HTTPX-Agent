import { Component, Show } from 'solid-js';
import { ExternalLink, CheckCircle2, XCircle, AlertCircle, Clock, Coins, Hash } from 'lucide-solid';
import clsx from 'clsx';
import type { EvalSearchItem } from '../../types/eval';
import RouterBadge from './RouterBadge';

interface Props {
  item: EvalSearchItem;
  onClick: (id: string) => void;
}

const TraceListItem: Component<Props> = (props) => {
  const duration = () => {
    if (!props.item.latency_ms) return '—';
    const s = props.item.latency_ms / 1000;
    return `${s.toFixed(1)}s`;
  };

  const tokens = () => {
    const est = (props.item.event_count || 0) * 150;
    return est > 1000 ? `${(est / 1000).toFixed(1)}k` : est;
  };

  const cost = () => {
    const est = (props.item.event_count || 0) * 0.0001;
    return `$${est.toFixed(4)}`;
  };

  const timeAgo = () => {
    if (!props.item.started_at) return '';
    return new Date(props.item.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div
      onClick={() => props.onClick(props.item.trace_id)}
      class="group relative flex cursor-pointer flex-col gap-3 rounded-lg border border-slate-800/60 bg-[#0F1117] p-3 transition-all hover:border-slate-700 hover:bg-[#161b22] sm:flex-row sm:items-center sm:justify-between sm:gap-0"
    >
      {/* Left Side: Status + ID */}
      <div class="flex items-start gap-3 sm:items-center sm:gap-4">
        {/* Status Icon */}
        <div
          class={clsx(
            "flex h-8 w-8 shrink-0 items-center justify-center rounded-md border bg-opacity-10 mt-0.5 sm:mt-0",
            props.item.status === 'success'
              ? "border-emerald-900/50 bg-emerald-500/10 text-emerald-500"
              : "border-rose-900/50 bg-rose-500/10 text-rose-500"
          )}
        >
          <Show when={props.item.status === 'success'} fallback={<XCircle size={16} />}>
            <CheckCircle2 size={16} />
          </Show>
        </div>

        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-sm font-medium text-slate-200 font-mono tracking-tight truncate">
              {props.item.trace_id}
            </span>

            <span class="inline-flex rounded text-[10px] bg-slate-800 px-1.5 py-0.5 text-slate-400 font-mono border border-slate-700 whitespace-nowrap">
              {props.item.model?.split('/').pop() || 'model'}
            </span>

            {/* ✅ Router Badge (if backend returns router_* fields) */}
            <RouterBadge
              sentiment={props.item.router_sentiment ?? null}
              sentiment_score={props.item.router_sentiment_score ?? null}
              reason={props.item.router_reason ?? null}
              reason_score={props.item.router_reason_score ?? null}
              backend={props.item.router_backend ?? null}
              override={props.item.router_override ?? null}
            />
          </div>

          <div class="flex items-center gap-2 text-xs text-slate-500 mt-1">
            <span>{timeAgo()}</span>
            <Show when={props.item.error}>
              <span class="flex items-center gap-1 text-rose-400 truncate max-w-37.5 sm:max-w-50">
                <AlertCircle size={10} /> {props.item.error}
              </span>
            </Show>
          </div>
        </div>
      </div>

      {/* Right Side: Metrics */}
      <div class="flex items-center justify-between gap-4 border-t border-slate-800/50 pt-2 sm:border-t-0 sm:pt-0 sm:justify-end md:gap-5">
        <div class="flex items-center gap-3 text-xs font-mono text-slate-300 sm:gap-3">
          <div class="flex items-center gap-1.5" title="Duration">
            <Clock size={10} class="text-slate-500 sm:hidden" />
            <span>{duration()}</span>
          </div>

          <span class="text-slate-700 hidden sm:inline">•</span>

          <div class="flex items-center gap-1.5" title="Tokens">
            <Hash size={10} class="text-slate-500 sm:hidden" />
            <span class="text-slate-400">{tokens()} <span class="hidden sm:inline">tokens</span></span>
          </div>

          <span class="text-slate-700 hidden sm:inline">•</span>

          <div class="flex items-center gap-1.5" title="Cost">
            <Coins size={10} class="text-slate-500 sm:hidden" />
            <span class="text-slate-400">{cost()}</span>
          </div>
        </div>

        <button class="flex shrink-0 items-center gap-1.5 text-xs font-medium text-indigo-400 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100">
          <span class="sm:hidden">View</span>
          <ExternalLink size={12} />
        </button>
      </div>
    </div>
  );
};

export default TraceListItem;
