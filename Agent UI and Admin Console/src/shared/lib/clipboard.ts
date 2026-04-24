export type CopyPayloadKind = 'table' | 'code'

export interface ManualCopyPayload {
  kind: CopyPayloadKind
  content: string
  reason: string
}

export type ClipboardCopyResult =
  | { status: 'success' }
  | { status: 'manual'; reason: string }
  | { status: 'error'; message: string }

function normalizeClipboardReason(raw: unknown): string {
  if (raw instanceof Error && raw.message.trim()) return raw.message
  if (typeof raw === 'string' && raw.trim()) return raw
  return 'Clipboard write failed in this environment.'
}

export async function copyToClipboard(content: string): Promise<ClipboardCopyResult> {
  if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) {
    return {
      status: 'manual',
      reason: 'Clipboard API is unavailable in this environment.',
    }
  }

  try {
    await navigator.clipboard.writeText(content)
    return { status: 'success' }
  } catch (error) {
    return {
      status: 'manual',
      reason: normalizeClipboardReason(error),
    }
  }
}

function sanitizeTableCell(value: string): string {
  return value
    .replaceAll('\n', ' ')
    .replaceAll('\r', ' ')
    .replace(/\s+/g, ' ')
    .replaceAll('|', '\\|')
    .trim()
}

function tableRowToMarkdown(cells: string[]): string {
  return `| ${cells.join(' | ')} |`
}

export function tableElementToMarkdown(table: HTMLTableElement): string {
  const rows = Array.from(table.querySelectorAll('tr'))
  if (rows.length === 0) return ''

  const parsedRows = rows.map((row) =>
    Array.from(row.querySelectorAll('th, td')).map((cell) => sanitizeTableCell(cell.textContent ?? '')),
  )

  const header = parsedRows[0] ?? []
  const body = parsedRows.slice(1)
  const width = Math.max(header.length, ...body.map((row) => row.length), 1)

  const normalizeRow = (row: string[]) =>
    Array.from({ length: width }, (_, index) => row[index] ?? '')

  const normalizedHeader = normalizeRow(header)
  const divider = Array.from({ length: width }, () => '---')
  const markdownRows = [tableRowToMarkdown(normalizedHeader), tableRowToMarkdown(divider)]

  for (const row of body) {
    markdownRows.push(tableRowToMarkdown(normalizeRow(row)))
  }

  return markdownRows.join('\n')
}
