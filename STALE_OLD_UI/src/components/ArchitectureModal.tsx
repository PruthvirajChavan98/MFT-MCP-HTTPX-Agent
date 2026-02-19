import { Component, createSignal, Show } from 'solid-js';
import {
  X, User, Shield, Bot, Server, Database, BrainCircuit, Building2, ArrowRight, ArrowDown, Info
} from 'lucide-solid';
import clsx from 'clsx';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

// --- Data Stream Lines ---
const DataStreamHorizontal = () => (
  <div class="hidden md:flex relative items-center justify-center w-8 lg:w-10 shrink-0">
    <div class="absolute h-0.5 w-full bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
      <div class="absolute inset-0 w-1/2 bg-linear-to-r from-transparent via-indigo-500 to-transparent animate-flow-right blur-[1px]"></div>
    </div>
    <ArrowRight size={14} class="text-slate-300 dark:text-slate-600 z-10" />
  </div>
);

const DataStreamVertical = () => (
  <div class="flex md:hidden relative items-center justify-center h-8 shrink-0">
    <div class="absolute w-0.5 h-full bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
      <div class="absolute inset-0 h-1/2 bg-linear-to-b from-transparent via-indigo-500 to-transparent animate-flow-down blur-[1px]"></div>
    </div>
    <ArrowDown size={14} class="text-slate-300 dark:text-slate-600 z-10" />
  </div>
);

const NodeCard: Component<{
  icon: any;
  title: string;
  subtitle: string;
  description?: string;
  color: 'purple' | 'blue' | 'amber' | 'rose' | 'green' | 'slate';
  isMain?: boolean;
}> = (props) => {
  const [isHovered, setIsHovered] = createSignal(false);

  const styles = {
    purple: 'from-purple-500/10 to-purple-600/5 border-purple-500/20 text-purple-600 dark:text-purple-300 shadow-purple-500/10',
    blue: 'from-blue-500/10 to-blue-600/5 border-blue-500/20 text-blue-600 dark:text-blue-300 shadow-blue-500/10',
    amber: 'from-amber-500/10 to-amber-600/5 border-amber-500/20 text-amber-600 dark:text-amber-300 shadow-amber-500/10',
    rose: 'from-rose-500/10 to-rose-600/5 border-rose-500/20 text-rose-600 dark:text-rose-300 shadow-rose-500/10',
    green: 'from-emerald-500/10 to-emerald-600/5 border-emerald-500/20 text-emerald-600 dark:text-emerald-300 shadow-emerald-500/10',
    slate: 'from-slate-500/10 to-slate-600/5 border-slate-500/20 text-slate-600 dark:text-slate-400',
  };

  return (
    <div
      class={clsx(
        "relative flex flex-col items-center p-3 rounded-2xl border transition-all duration-500 w-full md:w-40 lg:w-44 text-center backdrop-blur-xl bg-linear-to-br shrink-0",
        styles[props.color],
        props.isMain ? "scale-110 z-10 ring-1 ring-purple-500/30" : "scale-100",
        isHovered() ? "-translate-y-1 shadow-lg" : ""
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div class={clsx(
        "mb-2 p-2.5 rounded-xl bg-white/10 dark:bg-black/20 ring-1 ring-inset ring-white/5 transition-transform duration-500",
        isHovered() ? "scale-110 rotate-3" : ""
      )}>
        <props.icon size={20} strokeWidth={1.5} />
      </div>

      <div class="space-y-0.5">
        <div class="text-[10px] font-bold uppercase tracking-widest opacity-90">{props.title}</div>
        <div class="text-[9px] font-mono opacity-70 leading-tight">{props.subtitle}</div>
      </div>

      <Show when={props.description}>
        <div class={clsx(
          "absolute left-1/2 -translate-x-1/2 bottom-full mb-3 w-52 p-3",
          "bg-slate-900/95 dark:bg-black/95 backdrop-blur-md border border-white/10",
          "text-slate-200 text-[10px] leading-relaxed rounded-xl shadow-2xl",
          "transition-all duration-300 pointer-events-none z-50",
          isHovered() ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
        )}>
          {props.description}
        </div>
      </Show>
    </div>
  );
};

const ArchitectureModal: Component<Props> = (props) => {
  return (
    <div class={clsx("fixed inset-0 z-100 flex items-center justify-center p-2 sm:p-4 transition-all duration-300", props.isOpen ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none")}>

      <div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm transition-opacity duration-500" onClick={props.onClose} />

      <div class={clsx(
        "relative w-full max-w-[95vw] h-[85vh] bg-slate-50 dark:bg-[#0A0F1E]",
        "rounded-3xl shadow-2xl border border-slate-200 dark:border-slate-800",
        "flex flex-col overflow-hidden transition-all duration-500 transform",
        props.isOpen ? "scale-100 translate-y-0" : "scale-95 translate-y-8"
      )}>

        <div class="flex shrink-0 items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-white/5 bg-white/50 dark:bg-white/2">
           <div class="flex items-center gap-3">
            <div class="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-500">
              <Bot size={18} />
            </div>
            <div>
              <h2 class="text-xs font-bold text-slate-900 dark:text-white tracking-wide uppercase">System Architecture</h2>
              <p class="text-[9px] text-slate-500 dark:text-slate-400 font-mono">v1.0.0 • Live Environment</p>
            </div>
          </div>
          <button
            onClick={props.onClose}
            class="p-1.5 rounded-full text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/5 transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* ✅ FIX: Always allow scrolling, remove 'desktop only' message */}
        <div class="flex-1 overflow-auto bg-slate-50 dark:bg-[#0A0F1E] relative">
            <div class="fixed inset-0 bg-grid-pattern opacity-30 pointer-events-none"></div>

            <div class="relative z-10 flex flex-col items-center justify-center min-h-full min-w-fit p-8 gap-10 md:gap-14">
               {/* Diagram Nodes - Simplified for robust display */}
               <div class="flex flex-col md:flex-row gap-2 items-center">
                 <NodeCard icon={User} title="User" subtitle="Browser / Client" description="End-user interface." color="slate" />
                 <DataStreamHorizontal /><DataStreamVertical />
                 <div class="relative group">
                    <NodeCard icon={Bot} title="Agent Service" subtitle="FastAPI + LangGraph" description="Orchestration Layer" color="purple" isMain={true} />
                 </div>
                 <DataStreamHorizontal /><DataStreamVertical />
                 <NodeCard icon={BrainCircuit} title="LLM" subtitle="Groq / Nvidia" description="Intelligence Provider" color="rose" />
               </div>

               <div class="flex flex-col md:flex-row gap-8 items-start justify-center">
                 <div class="p-5 rounded-3xl border border-dashed border-slate-700/50 bg-white/2 flex flex-col gap-4">
                    <div class="text-[9px] text-slate-500 uppercase tracking-widest font-bold text-center mb-2">Docker Network</div>
                    <NodeCard icon={Server} title="MCP Service" subtitle="FastMCP" description="Tools Execution" color="blue" />
                    <NodeCard icon={Database} title="Redis" subtitle="State Store" description="Shared Memory" color="amber" />
                 </div>
                 <div class="flex flex-col justify-center h-full">
                    <NodeCard icon={Building2} title="Mock FinTech" subtitle="Core APIs" description="System of Record" color="green" />
                 </div>
               </div>
            </div>
        </div>
      </div>
    </div>
  );
};

export default ArchitectureModal;
