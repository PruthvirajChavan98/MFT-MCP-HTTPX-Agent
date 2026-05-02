import type { ReactNode } from 'react'

interface DiagramFallbackProps {
  title: string
  children: ReactNode
}

export function DiagramFallback({ title, children }: DiagramFallbackProps) {
  return (
    <details className="group mt-3 rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-2 font-mono text-[12px] text-slate-400">
      <summary className="cursor-pointer list-none select-none text-slate-500 transition-colors hover:text-cyan-300">
        <span className="mr-2 inline-block transition-transform group-open:rotate-90">›</span>
        {title}
      </summary>
      <div className="mt-3 leading-relaxed text-slate-400">{children}</div>
    </details>
  )
}
