import { Component, createEffect, createSignal, Show } from 'solid-js';
import { X, Copy, BrainCircuit, XCircle } from 'lucide-solid';
import { EvalService } from '../services/EvalService';
import type { EvalTraceResponse } from '../types/eval';

interface Props {
  isOpen: boolean;
  traceId: string;
  onClose: () => void;
}

const EvalTraceModal: Component<Props> = (props) => {
  const [data, setData] = createSignal<EvalTraceResponse | null>(null);
  const [loading, setLoading] = createSignal(false);
  const [err, setErr] = createSignal<string | null>(null);

  createEffect(() => {
    if (props.isOpen && props.traceId) {
      setLoading(true);
      setErr(null);
      EvalService.trace(props.traceId)
        .then(setData)
        .catch(e => setErr(e.message))
        .finally(() => setLoading(false));
    }
  });

  return (
    <Show when={props.isOpen}>
      <div class="fixed inset-0 z-9998 bg-black/80 backdrop-blur-sm transition-opacity" onClick={(e) => e.target === e.currentTarget && props.onClose()}>
        <div class="absolute inset-0 flex items-center justify-center p-2 sm:p-6">
          <div class="w-full max-w-6xl h-[90vh] rounded-2xl border border-slate-800 bg-[#0A0C10] shadow-2xl flex flex-col overflow-hidden">

            <div class="flex shrink-0 items-center justify-between px-4 sm:px-6 py-4 border-b border-slate-800 bg-[#0F1117]">
              <div class="flex items-center gap-4">
                <BrainCircuit size={20} class="text-indigo-400" />
                <div class="min-w-0">
                  <div class="text-sm font-semibold text-white truncate">Trace Details</div>
                  <div class="text-[10px] text-slate-500 font-mono truncate max-w-50 sm:max-w-md">{props.traceId}</div>
                </div>
              </div>
              <button onClick={props.onClose} class="p-2 text-slate-400 hover:text-white"><X size={20} /></button>
            </div>

            <div class="flex-1 overflow-y-auto p-4 sm:p-6 custom-scrollbar">
              <Show when={loading()} fallback={
                <Show when={data()}>
                  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div class="lg:col-span-2 space-y-6">
                      <div class="p-4 rounded-xl bg-[#0F1117] border border-slate-800">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Input</h3>
                        <pre class="text-xs sm:text-sm text-slate-200 whitespace-pre-wrap font-mono bg-slate-950/50 p-3 rounded-lg border border-slate-800/50 overflow-x-auto">
                          {JSON.stringify(data()?.trace?.inputs_json, null, 2)}
                        </pre>
                      </div>
                      <div class="p-4 rounded-xl bg-[#0F1117] border border-slate-800">
                        <h3 class="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Output</h3>
                        <div class="text-sm text-slate-200 whitespace-pre-wrap">
                          {data()?.trace?.final_output}
                        </div>
                      </div>
                    </div>

                    <div class="lg:col-span-1 space-y-4">
                      <div class="p-4 rounded-xl bg-[#0F1117] border border-slate-800">
                        <div class="text-xs font-bold text-slate-500 uppercase tracking-widest mb-3">Meta</div>
                        <div class="space-y-2 text-xs">
                          <div class="flex justify-between"><span class="text-slate-400">Status</span> <span class="text-slate-200">{data()?.trace?.status}</span></div>
                          <div class="flex justify-between"><span class="text-slate-400">Latency</span> <span class="text-slate-200">{data()?.trace?.latency_ms}ms</span></div>
                          <div class="flex justify-between"><span class="text-slate-400">Model</span> <span class="text-slate-200">{data()?.trace?.model}</span></div>
                        </div>
                      </div>
                    </div>
                  </div>
                </Show>
              }>
                <div class="flex justify-center py-20"><div class="animate-spin h-6 w-6 border-2 border-indigo-500 border-t-transparent rounded-full"/></div>
              </Show>
              <Show when={err()}>
                <div class="text-rose-400 text-center p-4 bg-rose-900/10 rounded-lg">{err()}</div>
              </Show>
            </div>
          </div>
        </div>
      </div>
    </Show>
  );
};

export default EvalTraceModal;
