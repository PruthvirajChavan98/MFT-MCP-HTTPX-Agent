import { useEffect, useState } from 'react'

export interface TocEntry {
  id: string
  index: string
  label: string
}

interface TocRailProps {
  entries: readonly TocEntry[]
}

export function TocRail({ entries }: TocRailProps) {
  const [active, setActive] = useState<string>(entries[0]?.id ?? '')

  useEffect(() => {
    if (typeof window === 'undefined' || typeof IntersectionObserver === 'undefined') {
      return
    }

    const observer = new IntersectionObserver(
      (records) => {
        const visible = records
          .filter((r) => r.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
        if (visible[0]?.target.id) {
          setActive(visible[0].target.id)
        }
      },
      { rootMargin: '-30% 0px -55% 0px', threshold: [0, 1] },
    )

    entries.forEach(({ id }) => {
      const el = document.getElementById(id)
      if (el) observer.observe(el)
    })

    return () => observer.disconnect()
  }, [entries])

  return (
    <nav
      aria-label="Architecture page sections"
      className="hidden lg:sticky lg:top-24 lg:block lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto"
    >
      <p className="mb-3 font-mono text-[10px] tracking-[0.22em] text-slate-600">CONTENTS</p>
      <ol className="space-y-1.5">
        {entries.map((entry) => {
          const isActive = active === entry.id
          return (
            <li key={entry.id}>
              <a
                href={`#${entry.id}`}
                data-toc-id={entry.id}
                className={`group flex items-baseline gap-3 rounded-md border px-3 py-1.5 text-[12px] transition-colors ${
                  isActive
                    ? 'border-cyan-500/30 bg-cyan-500/5 text-cyan-200'
                    : 'border-transparent text-slate-500 hover:border-slate-800 hover:bg-slate-900/40 hover:text-slate-200'
                }`}
              >
                <span
                  className={`font-mono text-[10px] tracking-wider ${
                    isActive ? 'text-cyan-400' : 'text-slate-600 group-hover:text-slate-400'
                  }`}
                >
                  {entry.index}
                </span>
                <span className="flex-1">{entry.label}</span>
              </a>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
