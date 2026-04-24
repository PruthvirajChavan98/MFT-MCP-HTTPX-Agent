import { useState } from 'react'
import { ChevronRight } from 'lucide-react'

interface JsonPropProps {
  paramKey: string
  val: unknown
  depth: number
}

export function JsonProp({ paramKey, val, depth }: JsonPropProps) {
  const [isOpen, setIsOpen] = useState(true)
  const isRecord = val !== null && typeof val === 'object'

  const renderScalar = (v: unknown) => {
    if (typeof v === 'string') return <span className="text-emerald-600 dark:text-emerald-400">"{v}"</span>
    if (typeof v === 'number') return <span className="text-orange-500">{v}</span>
    if (typeof v === 'boolean') return <span className="text-rose-500">{String(v)}</span>
    return <span className="text-foreground/70">{String(v)}</span>
  }

  return (
    <div className="text-[13px] font-mono leading-relaxed">
      <div
        className="flex items-center gap-1.5 cursor-pointer py-[3px] hover:bg-accent/40 rounded transition-colors select-none"
        style={{ paddingLeft: `${depth * 14}px` }}
        onClick={() => setIsOpen(!isOpen)}
      >
        {isRecord ? (
          <ChevronRight
            size={11}
            strokeWidth={2.5}
            className={`shrink-0 text-muted-foreground/60 transition-transform duration-150 ${isOpen ? 'rotate-90' : ''}`}
          />
        ) : (
          <span className="w-[11px] shrink-0" />
        )}

        <span className="text-violet-600 dark:text-violet-400 shrink-0">{paramKey}</span>
        <span className="text-muted-foreground shrink-0">:</span>

        {!isRecord && renderScalar(val)}

        {isRecord && !isOpen && (
          <span className="text-muted-foreground/60 text-[11px]">
            {Array.isArray(val) ? `[ ${(val as unknown[]).length} ]` : `{ … }`}
          </span>
        )}
      </div>

      {isOpen && isRecord && (
        <div>
          {Object.entries(val as Record<string, unknown>).map(([k, v]) => (
            <JsonProp key={k} paramKey={k} val={v} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

export function JsonViewer({ data }: { data: unknown }) {
  if (data === null || data === undefined)
    return <div className="text-muted-foreground p-4 text-[13px] font-mono italic">null</div>

  if (typeof data !== 'object')
    return (
      <div className="text-foreground/80 p-4 text-[13px] font-mono whitespace-pre-wrap break-all">
        {typeof data === 'string' ? data : JSON.stringify(data, null, 2)}
      </div>
    )

  return (
    <div className="py-2 px-2">
      {Object.entries(data as Record<string, unknown>).map(([k, v]) => (
        <JsonProp key={k} paramKey={k} val={v} depth={0} />
      ))}
    </div>
  )
}
