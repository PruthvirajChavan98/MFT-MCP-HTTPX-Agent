import { Lock, Unlock, Zap } from 'lucide-react'
import { TOOLS, type ToolEntry } from './data/tools'

const TIER_BADGE: Record<ToolEntry['tier'], string> = {
  public: 'border-emerald-500/30 bg-emerald-500/5 text-emerald-300',
  'session-gated': 'border-cyan-500/30 bg-cyan-500/5 text-cyan-300',
}

const AUTH_LABEL: Record<ToolEntry['auth'], string> = {
  basic: 'Basic',
  bearer: 'Bearer',
  none: '—',
}

export function ToolTable() {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-800 bg-[#0c1322]/60 shadow-2xl shadow-black/40 backdrop-blur">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left text-[13px]">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-900/60 font-mono text-[11px] uppercase tracking-wider text-slate-500">
              <th className="px-4 py-3">Tool</th>
              <th className="px-4 py-3">Tier</th>
              <th className="px-4 py-3">CRM endpoint</th>
              <th className="px-4 py-3">Auth</th>
              <th className="px-4 py-3">Side effect</th>
            </tr>
          </thead>
          <tbody>
            {TOOLS.map((tool) => (
              <tr
                key={tool.name}
                className="border-b border-slate-800/60 transition-colors last:border-0 hover:bg-cyan-500/5"
              >
                <td className="px-4 py-3 align-top">
                  <div className="font-mono text-cyan-300">{tool.name}</div>
                  <div className="mt-1 max-w-md text-[12px] leading-relaxed text-slate-400">
                    {tool.purpose}
                  </div>
                </td>
                <td className="px-4 py-3 align-top">
                  <span
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider ${TIER_BADGE[tool.tier]}`}
                  >
                    {tool.tier === 'public' ? (
                      <Unlock className="h-3 w-3" />
                    ) : (
                      <Lock className="h-3 w-3" />
                    )}
                    {tool.tier}
                  </span>
                </td>
                <td className="px-4 py-3 align-top font-mono text-[11.5px] text-slate-300">
                  {tool.endpoint ?? <span className="text-slate-600">—</span>}
                </td>
                <td className="px-4 py-3 align-top font-mono text-[11.5px] text-slate-300">
                  {AUTH_LABEL[tool.auth]}
                </td>
                <td className="px-4 py-3 align-top text-slate-400">
                  {tool.sideEffect ? (
                    <span className="inline-flex items-center gap-1 text-amber-300">
                      <Zap className="h-3 w-3" />
                      yes
                    </span>
                  ) : (
                    <span className="text-slate-600">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
