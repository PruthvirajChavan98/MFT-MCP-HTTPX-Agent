import type { ReactNode } from 'react'
import { CopyButton } from './CopyButton'

export type CodeLanguage = 'python' | 'typescript' | 'bash' | 'plain'

interface CodeBlockProps {
  language: CodeLanguage
  caption?: string
  code: string
  children?: ReactNode
}

const LANGUAGE_LABEL: Record<CodeLanguage, string> = {
  python: 'PYTHON',
  typescript: 'TYPESCRIPT',
  bash: 'BASH',
  plain: 'TEXT',
}

export function CodeBlock({ language, caption, code, children }: CodeBlockProps) {
  return (
    <figure className="group relative overflow-hidden rounded-xl border border-slate-800 bg-[#070912] shadow-lg shadow-black/30">
      <header className="flex items-center justify-between border-b border-slate-800 bg-[#0c1322] px-4 py-2">
        <div className="flex items-baseline gap-3 font-mono text-[11px] tracking-[0.18em] text-slate-500">
          <span className="text-cyan-300/80">{LANGUAGE_LABEL[language]}</span>
          {caption && <span className="text-slate-600">/</span>}
          {caption && <span className="text-slate-400">{caption}</span>}
        </div>
        <CopyButton value={code} label={`Copy ${language} snippet`} />
      </header>
      <pre className="overflow-x-auto px-4 py-4 font-mono text-[12.5px] leading-relaxed text-slate-200">
        <code>{children ?? code}</code>
      </pre>
    </figure>
  )
}
