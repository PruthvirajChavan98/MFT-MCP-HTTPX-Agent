import { useState } from "react";
import {
  Search, Filter, ChevronRight, Clock, Zap, AlertTriangle,
  CheckCircle, XCircle, Eye, ArrowRight, X, Code
} from "lucide-react";
import { mockTraces } from "../../lib/api";

interface TraceStep {
  name: string;
  duration_ms: number;
  type: string;
  result: string;
}

interface Trace {
  trace_id: string;
  session_id: string;
  timestamp: string;
  duration_ms: number;
  input: string;
  output: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost: number;
  status: string;
  route: string;
  steps: TraceStep[];
}

const stepColors: Record<string, string> = {
  router: "#818cf8",
  retrieval: "#34d399",
  llm: "#60a5fa",
  guardrail: "#f59e0b",
  post_process: "#f472b6",
};

export function ChatTraces() {
  const [traces] = useState<Trace[]>(mockTraces);
  const [selectedTrace, setSelectedTrace] = useState<Trace | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showJson, setShowJson] = useState(false);

  const filtered = traces.filter((t) => {
    const matchesSearch = !searchQuery ||
      t.input.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.trace_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.session_id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === "all" || t.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-gray-900" style={{ fontWeight: 700 }}>Chat Traces</h1>
        <p className="text-gray-500" style={{ fontSize: 14 }}>Inspect agent execution traces &middot; LangSmith-style viewer</p>
      </div>

      {/* Search & Filters */}
      <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm flex flex-wrap items-center gap-3">
        <div className="flex-1 min-w-[240px] relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search traces by input, trace ID, or session ID..."
            className="w-full pl-9 pr-4 py-2 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:border-brand-main transition-colors"
            style={{ fontSize: 13 }}
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          {["all", "success", "guardrail_blocked"].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-lg ${
                statusFilter === s ? "text-white" : "text-gray-600 bg-gray-100 hover:bg-gray-200"
              }`}
              style={statusFilter === s ? { background: "var(--brand-gradient)", fontSize: 12 } : { fontSize: 12 }}
            >
              {s === "all" ? "All" : s === "success" ? "Success" : "Blocked"}
            </button>
          ))}
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Trace List */}
        <div className="lg:col-span-1 space-y-2 max-h-[calc(100vh-280px)] overflow-y-auto pr-1">
          {filtered.map((trace) => (
            <button
              key={trace.trace_id}
              onClick={() => { setSelectedTrace(trace); setShowJson(false); }}
              className={`w-full text-left p-3 rounded-xl border transition-all ${
                selectedTrace?.trace_id === trace.trace_id
                  ? "border-brand-main bg-brand-light/10 shadow-sm"
                  : "border-gray-100 bg-white hover:border-gray-200 hover:shadow-sm"
              }`}
            >
              <div className="flex items-center justify-between mb-1.5">
                <code className="text-brand-dark" style={{ fontSize: 11 }}>{trace.trace_id}</code>
                {trace.status === "success" ? (
                  <CheckCircle className="w-3.5 h-3.5 text-green-500" />
                ) : (
                  <XCircle className="w-3.5 h-3.5 text-red-500" />
                )}
              </div>
              <p className="text-gray-800 truncate mb-1.5" style={{ fontSize: 13, fontWeight: 500 }}>
                {trace.input}
              </p>
              <div className="flex items-center gap-3 text-gray-400" style={{ fontSize: 11 }}>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" /> {trace.duration_ms}ms
                </span>
                <span className="flex items-center gap-1">
                  <Zap className="w-3 h-3" /> ${trace.cost.toFixed(4)}
                </span>
                <span>{trace.model.split("/")[1]}</span>
              </div>
            </button>
          ))}
        </div>

        {/* Trace Detail */}
        <div className="lg:col-span-2">
          {selectedTrace ? (
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
              {/* Header */}
              <div className="p-5 border-b border-gray-100">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <code className="text-brand-dark bg-brand-light/10 px-2 py-0.5 rounded" style={{ fontSize: 12 }}>
                      {selectedTrace.trace_id}
                    </code>
                    <span
                      className={`px-2 py-0.5 rounded-full ${
                        selectedTrace.status === "success" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                      }`}
                      style={{ fontSize: 11, fontWeight: 500 }}
                    >
                      {selectedTrace.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowJson(!showJson)}
                      className={`px-2 py-1 rounded-lg flex items-center gap-1 transition-all ${
                        showJson ? "bg-gray-800 text-white" : "bg-gray-100 text-gray-600"
                      }`}
                      style={{ fontSize: 11 }}
                    >
                      <Code className="w-3 h-3" /> JSON
                    </button>
                    <button
                      onClick={() => setSelectedTrace(null)}
                      className="w-7 h-7 rounded-lg hover:bg-gray-100 flex items-center justify-center text-gray-400"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {/* Metadata */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { label: "Duration", value: `${selectedTrace.duration_ms}ms` },
                    { label: "Model", value: selectedTrace.model.split("/")[1] },
                    { label: "Tokens", value: `${selectedTrace.tokens_in} in / ${selectedTrace.tokens_out} out` },
                    { label: "Cost", value: `$${selectedTrace.cost.toFixed(4)}` },
                  ].map((m) => (
                    <div key={m.label} className="bg-gray-50 rounded-lg p-2">
                      <div className="text-gray-400" style={{ fontSize: 10 }}>{m.label}</div>
                      <div className="text-gray-900" style={{ fontSize: 13, fontWeight: 500 }}>{m.value}</div>
                    </div>
                  ))}
                </div>
              </div>

              {showJson ? (
                /* JSON View */
                <div className="p-5">
                  <pre className="bg-gray-900 text-green-400 p-4 rounded-lg overflow-x-auto" style={{ fontSize: 12 }}>
                    {JSON.stringify(selectedTrace, null, 2)}
                  </pre>
                </div>
              ) : (
                <>
                  {/* Input / Output */}
                  <div className="p-5 border-b border-gray-100">
                    <div className="grid md:grid-cols-2 gap-4">
                      <div>
                        <div className="text-gray-500 mb-1.5" style={{ fontSize: 11, fontWeight: 500 }}>INPUT</div>
                        <div className="bg-blue-50 rounded-lg p-3 text-gray-800" style={{ fontSize: 13 }}>
                          {selectedTrace.input}
                        </div>
                      </div>
                      <div>
                        <div className="text-gray-500 mb-1.5" style={{ fontSize: 11, fontWeight: 500 }}>OUTPUT</div>
                        <div className="bg-green-50 rounded-lg p-3 text-gray-800" style={{ fontSize: 13 }}>
                          {selectedTrace.output}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Execution Timeline */}
                  <div className="p-5">
                    <h4 className="text-gray-900 mb-4" style={{ fontWeight: 600, fontSize: 14 }}>Execution Timeline</h4>
                    <div className="space-y-2">
                      {selectedTrace.steps.map((step, i) => {
                        const maxDuration = Math.max(...selectedTrace.steps.map((s) => s.duration_ms));
                        const widthPct = (step.duration_ms / maxDuration) * 100;
                        const color = stepColors[step.type] || "#9ca3af";

                        return (
                          <div key={i} className="flex items-center gap-3">
                            <div className="w-32 shrink-0">
                              <div className="text-gray-800" style={{ fontSize: 12, fontWeight: 500 }}>{step.name}</div>
                              <div className="text-gray-400" style={{ fontSize: 10 }}>{step.type}</div>
                            </div>
                            <div className="flex-1">
                              <div className="h-6 bg-gray-50 rounded-lg overflow-hidden relative">
                                <div
                                  className="h-full rounded-lg flex items-center px-2 transition-all"
                                  style={{
                                    width: `${Math.max(widthPct, 8)}%`,
                                    backgroundColor: color + "30",
                                    borderLeft: `3px solid ${color}`,
                                  }}
                                >
                                  <span style={{ fontSize: 10, fontWeight: 500, color }}>{step.duration_ms}ms</span>
                                </div>
                              </div>
                            </div>
                            <div className="w-40 shrink-0 text-right">
                              <span className="text-gray-500" style={{ fontSize: 11 }}>{step.result}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Total Duration */}
                    <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between">
                      <span className="text-gray-500" style={{ fontSize: 12 }}>Total Duration</span>
                      <span className="text-gray-900" style={{ fontSize: 14, fontWeight: 600 }}>{selectedTrace.duration_ms}ms</span>
                    </div>
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-12 text-center">
              <Eye className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500" style={{ fontWeight: 500 }}>Select a trace to inspect</p>
              <p className="text-gray-400 mt-1" style={{ fontSize: 13 }}>
                Click on any trace from the list to view execution details, timeline, and step-by-step breakdown.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
