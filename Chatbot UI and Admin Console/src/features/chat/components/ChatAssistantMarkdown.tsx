import {
  isValidElement,
  useCallback,
  useMemo,
  useRef,
  useState,
  type HTMLAttributes,
  type ReactElement,
  type ReactNode,
  type TableHTMLAttributes,
} from 'react'
import { toast } from 'sonner'
import { Streamdown, type StreamdownProps } from 'streamdown'
import type { ChatMessage as ChatMessageType } from '@shared/types/chat'
import {
  copyToClipboard,
  tableElementToMarkdown,
  type CopyPayloadKind,
  type ManualCopyPayload,
} from '@shared/lib/clipboard'
import { ClipboardFallbackModal } from './ClipboardFallbackModal'

interface ChatAssistantMarkdownProps {
  content: string
  status: ChatMessageType['status']
  onCopyFallback?: (payload: ManualCopyPayload) => void
}

type CopyOutcome = 'success' | 'manual' | 'error'
type MarkdownComponents = NonNullable<StreamdownProps['components']>

function nodeToText(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(nodeToText).join('')

  if (isValidElement<{ children?: ReactNode }>(node)) {
    return nodeToText(node.props.children)
  }

  return ''
}

function findCodeElement(node: ReactNode): ReactElement<{ className?: string; children?: ReactNode }> | null {
  if (Array.isArray(node)) {
    for (const child of node) {
      const match = findCodeElement(child)
      if (match) return match
    }
    return null
  }

  if (!isValidElement<{ className?: string; children?: ReactNode }>(node)) return null
  if (node.type === 'code') return node

  return findCodeElement(node.props.children)
}

function extractCodePayload(children: ReactNode): { language: string; content: string } {
  const codeElement = findCodeElement(children)
  const rawLanguage = codeElement?.props.className?.match(/language-([\w-]+)/)?.[1] ?? 'text'
  const rawContent = codeElement ? nodeToText(codeElement.props.children) : nodeToText(children)
  return {
    language: rawLanguage,
    content: rawContent.replace(/\n$/, ''),
  }
}

interface CopyableCodeBlockProps extends HTMLAttributes<HTMLPreElement> {
  children?: ReactNode
  onCopyAction: (kind: CopyPayloadKind, content: string) => Promise<CopyOutcome>
}

function CopyableCodeBlock({ children, className, onCopyAction, ...rest }: CopyableCodeBlockProps) {
  const [copied, setCopied] = useState(false)
  const payload = useMemo(() => extractCodePayload(children), [children])

  const handleCopy = useCallback(async () => {
    if (!payload.content.trim()) return
    const result = await onCopyAction('code', payload.content)
    if (result !== 'success') return

    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }, [onCopyAction, payload.content])

  return (
    <div className="tf-chat-code-wrap">
      <div className="tf-chat-block-toolbar">
        <span className="tf-chat-code-lang">{payload.language}</span>
        <button className="tf-chat-copy-btn" onClick={handleCopy} type="button">
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre {...rest} className={`tf-chat-code-pre ${className ?? ''}`.trim()}>
        {children}
      </pre>
    </div>
  )
}

interface CopyableTableProps extends TableHTMLAttributes<HTMLTableElement> {
  children?: ReactNode
  onCopyAction: (kind: CopyPayloadKind, content: string) => Promise<CopyOutcome>
}

function CopyableTable({ children, className, onCopyAction, ...rest }: CopyableTableProps) {
  const tableRef = useRef<HTMLTableElement>(null)
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    const table = tableRef.current
    if (!table) return

    const markdown = tableElementToMarkdown(table)
    if (!markdown.trim()) return

    const result = await onCopyAction('table', markdown)
    if (result !== 'success') return

    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }, [onCopyAction])

  return (
    <div className="tf-chat-table-wrap">
      <div className="tf-chat-block-toolbar">
        <span className="tf-chat-code-lang">Table</span>
        <button className="tf-chat-copy-btn" onClick={handleCopy} type="button">
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <div className="tf-chat-table-scroll">
        <table {...rest} ref={tableRef} className={className}>
          {children}
        </table>
      </div>
    </div>
  )
}

export function ChatAssistantMarkdown({ content, status, onCopyFallback }: ChatAssistantMarkdownProps) {
  const [manualCopy, setManualCopy] = useState<ManualCopyPayload | null>(null)

  const handleCopy = useCallback(
    async (kind: CopyPayloadKind, value: string): Promise<CopyOutcome> => {
      const result = await copyToClipboard(value)
      if (result.status === 'success') return 'success'

      if (result.status === 'manual') {
        const payload: ManualCopyPayload = {
          kind,
          content: value,
          reason: result.reason,
        }
        setManualCopy(payload)
        onCopyFallback?.(payload)
        return 'manual'
      }

      toast.error(result.message)
      return 'error'
    },
    [onCopyFallback],
  )

  const components = useMemo<MarkdownComponents>(
    () => ({
      pre: ({ children, className }) => (
        <CopyableCodeBlock className={className} onCopyAction={handleCopy}>
          {children}
        </CopyableCodeBlock>
      ),
      table: ({ children, className }) => (
        <CopyableTable className={className} onCopyAction={handleCopy}>
          {children}
        </CopyableTable>
      ),
    }),
    [handleCopy],
  )

  if (status === 'streaming' && !content.trim()) {
    return (
      <div className="tf-chat-thinking" role="status" aria-label="Assistant is thinking">
        <span className="tf-chat-thinking-dot" />
        <span className="tf-chat-thinking-dot" />
        <span className="tf-chat-thinking-dot" />
      </div>
    )
  }

  return (
    <>
      <div className="tf-chat-markdown">
        <Streamdown
          caret="block"
          className="tf-chat-streamdown"
          components={components}
          controls={false}
          isAnimating={status === 'streaming'}
          mode={status === 'streaming' ? 'streaming' : 'static'}
        >
          {content || ' '}
        </Streamdown>
      </div>
      <ClipboardFallbackModal onClose={() => setManualCopy(null)} payload={manualCopy} />
    </>
  )
}
