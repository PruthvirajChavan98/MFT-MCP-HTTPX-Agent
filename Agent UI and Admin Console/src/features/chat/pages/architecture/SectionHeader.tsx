import type { ReactNode } from 'react'
import { ExternalLink } from 'lucide-react'

interface SectionHeaderProps {
  index: string
  eyebrow: string
  title: string
  source?: { label: string; href: string }
  children?: ReactNode
}

export function SectionHeader({ index, eyebrow, title, source, children }: SectionHeaderProps) {
  return (
    <header className="mb-8 flex flex-col gap-3">
      <div className="flex items-center gap-3 font-mono text-[11px] tracking-[0.22em] text-slate-500">
        <span className="rounded-sm border border-cyan-500/30 bg-cyan-500/5 px-2 py-0.5 text-cyan-300">
          {index}
        </span>
        <span>{eyebrow}</span>
      </div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h2 className="font-display text-3xl font-semibold tracking-tight text-white md:text-4xl">
          {title}
        </h2>
        {source && (
          <a
            href={source.href}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 font-mono text-[11px] tracking-wider text-slate-400 transition-colors hover:text-cyan-300"
          >
            <span className="text-slate-600">jump to source</span>
            <span className="text-cyan-300/80">{source.label}</span>
            <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>
      {children && <div className="max-w-3xl text-[15px] leading-relaxed text-slate-400">{children}</div>}
    </header>
  )
}
