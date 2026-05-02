import { DiagramFallback } from './DiagramFallback'

/**
 * LangGraph supervisor diagram — the llm_step ↔ run_tools loop with the
 * iteration counter and the AsyncRedisSaver checkpointer below.
 */
export function LangGraphDiagram() {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#0c1322]/60 p-2 shadow-2xl shadow-black/40 backdrop-blur">
      <div className="overflow-x-auto">
        <svg
          viewBox="0 0 720 420"
          role="img"
          aria-labelledby="lg-title lg-desc"
          xmlns="http://www.w3.org/2000/svg"
          className="block h-auto w-full min-w-[640px]"
        >
          <title id="lg-title">LangGraph supervisor — recursive RAG state graph</title>
          <desc id="lg-desc">
            The supervisor alternates between an llm_step node that decides the next action and a
            run_tools node that executes any tool calls via DedupToolNode. The loop bounds at
            max_iterations equal to six. State is checkpointed in Redis via AsyncRedisSaver,
            keyed by thread_id which equals session_id, with a seven day TTL.
          </desc>

          <defs>
            <marker id="lg-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#22d3ee" />
            </marker>
            <marker id="lg-arrow-emerald" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0,0 L10,5 L0,10 z" fill="#34d399" />
            </marker>
            <linearGradient id="lg-loop" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#22d3ee" stopOpacity="0.05" />
              <stop offset="100%" stopColor="#22d3ee" stopOpacity="0" />
            </linearGradient>
          </defs>

          <text x="40" y="40" fontFamily="JetBrains Mono, monospace" fontSize="10" letterSpacing="2.5" fill="#475569">
            STATE
          </text>
          <line x1="40" y1="48" x2="180" y2="48" stroke="#1e293b" />

          {/* START */}
          <circle cx="100" cy="180" r="22" fill="#0c1322" stroke="#22d3ee" strokeWidth="1.5" />
          <text x="100" y="184" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="11" fill="#22d3ee">
            START
          </text>

          {/* llm_step */}
          <rect x="220" y="140" width="160" height="80" rx="10" fill="#0c1322" stroke="#22d3ee" />
          <text x="300" y="166" textAnchor="middle" fontFamily="IBM Plex Sans, sans-serif" fontSize="14" fontWeight="600" fill="#f1f5f9">
            llm_step
          </text>
          <text x="300" y="184" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#94a3b8">
            picks next action
          </text>
          <text x="300" y="200" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#94a3b8">
            recursive_rag_graph.py
          </text>

          {/* run_tools */}
          <rect x="480" y="140" width="180" height="80" rx="10" fill="#0c1322" stroke="#34d399" />
          <text x="570" y="166" textAnchor="middle" fontFamily="IBM Plex Sans, sans-serif" fontSize="14" fontWeight="600" fill="#f1f5f9">
            run_tools
          </text>
          <text x="570" y="184" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#94a3b8">
            DedupToolNode
          </text>
          <text x="570" y="200" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#94a3b8">
            same-turn dedupe
          </text>

          {/* START → llm_step */}
          <line x1="122" y1="180" x2="220" y2="180" stroke="#22d3ee" strokeWidth="1.5" markerEnd="url(#lg-arrow)" />

          {/* llm_step → run_tools */}
          <line x1="380" y1="180" x2="480" y2="180" stroke="#22d3ee" strokeWidth="1.5" markerEnd="url(#lg-arrow)" />
          <text x="430" y="172" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#cbd5e1">
            tool_calls
          </text>

          {/* run_tools → llm_step (loop) */}
          <path
            d="M 480 200 Q 380 280, 300 220"
            fill="none"
            stroke="#34d399"
            strokeWidth="1.5"
            markerEnd="url(#lg-arrow-emerald)"
          />
          <rect x="358" y="246" width="74" height="22" rx="4" fill="url(#lg-loop)" stroke="#22d3ee" strokeOpacity="0.3" />
          <text x="395" y="260" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#22d3ee">
            loop ≤ 6
          </text>

          {/* llm_step → END */}
          <line x1="300" y1="140" x2="300" y2="100" stroke="#22d3ee" strokeWidth="1.5" markerEnd="url(#lg-arrow)" />
          <circle cx="300" cy="80" r="22" fill="#0c1322" stroke="#22d3ee" strokeWidth="1.5" />
          <text x="300" y="84" textAnchor="middle" fontFamily="JetBrains Mono, monospace" fontSize="11" fill="#22d3ee">
            END
          </text>
          <text x="335" y="120" fontFamily="JetBrains Mono, monospace" fontSize="9" fill="#94a3b8">
            no tool_calls
          </text>

          {/* Checkpointer plate */}
          <rect x="40" y="320" width="640" height="76" rx="10" fill="#0c1322" stroke="#1e293b" strokeWidth="1" />
          <text x="58" y="346" fontFamily="JetBrains Mono, monospace" fontSize="10" letterSpacing="2.5" fill="#475569">
            CHECKPOINTER
          </text>
          <text x="58" y="370" fontFamily="IBM Plex Sans, sans-serif" fontSize="13" fontWeight="600" fill="#f1f5f9">
            AsyncRedisSaver
          </text>
          <text x="58" y="386" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#94a3b8">
            thread_id ≡ session_id  ·  TTL 10080 min  ·  app_factory.py:77
          </text>
          <text x="450" y="370" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#22d3ee">
            messages, iteration, max_iterations,
          </text>
          <text x="450" y="386" fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#22d3ee">
            tool_execution_cache
          </text>
        </svg>
      </div>

      <DiagramFallback title="Text equivalent of LangGraph supervisor">
        START transitions to llm_step. The llm_step node either emits an END condition (no tool
        calls) or routes to run_tools. The run_tools node (DedupToolNode) loops back to llm_step
        with same-turn dedupe by tool name and serialized args hash. The loop is bounded by
        max_iterations=6. State (messages, iteration, max_iterations, tool_execution_cache) is
        persisted in Redis via AsyncRedisSaver wired in app_factory.py:77, keyed by thread_id
        which equals session_id, with a 7-day TTL.
      </DiagramFallback>
    </div>
  )
}
