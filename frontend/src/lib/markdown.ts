const ENTITY_MAP: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }

function escapeHtml(text: string): string {
  return text.replace(/[&<>"]/g, (ch) => ENTITY_MAP[ch])
}

function processInline(text: string): string {
  let out = text
  // bold
  out = out.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  out = out.replace(/__(.+?)__/g, '<strong>$1</strong>')
  // italic
  out = out.replace(/\*(.+?)\*/g, '<em>$1</em>')
  out = out.replace(/_(.+?)_/g, '<em>$1</em>')
  // inline code
  out = out.replace(/`([^`]+?)`/g, '<code class="chat-inline-code">$1</code>')
  // links — only allow http/https
  out = out.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
  return out
}

export function renderMarkdown(source: string): string {
  if (!source) return ''

  const lines = source.split('\n')
  const blocks: string[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]

    // fenced code block
    const fenceMatch = line.match(/^```(\w*)/)
    if (fenceMatch) {
      const lang = fenceMatch[1]
      const codeLines: string[] = []
      i++
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeLines.push(lines[i])
        i++
      }
      i++ // skip closing ```
      const langAttr = lang ? ` data-lang="${escapeHtml(lang)}"` : ''
      blocks.push(`<pre class="code-block"${langAttr}><code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
      continue
    }

    // heading
    const headingMatch = line.match(/^(#{1,3})\s+(.+)/)
    if (headingMatch) {
      const level = headingMatch[1].length + 2 // h3, h4, h5
      const tag = `h${Math.min(level, 6)}`
      blocks.push(`<${tag}>${processInline(escapeHtml(headingMatch[2]))}</${tag}>`)
      i++
      continue
    }

    // unordered list
    if (line.match(/^[\-\*]\s+/)) {
      const items: string[] = []
      while (i < lines.length && lines[i].match(/^[\-\*]\s+/)) {
        items.push(lines[i].replace(/^[\-\*]\s+/, ''))
        i++
      }
      const lis = items.map((item) => `<li>${processInline(escapeHtml(item))}</li>`).join('')
      blocks.push(`<ul>${lis}</ul>`)
      continue
    }

    // ordered list
    if (line.match(/^\d+\.\s+/)) {
      const items: string[] = []
      while (i < lines.length && lines[i].match(/^\d+\.\s+/)) {
        items.push(lines[i].replace(/^\d+\.\s+/, ''))
        i++
      }
      const lis = items.map((item) => `<li>${processInline(escapeHtml(item))}</li>`).join('')
      blocks.push(`<ol>${lis}</ol>`)
      continue
    }

    // empty line — skip
    if (!line.trim()) {
      i++
      continue
    }

    // paragraph — collect consecutive non-empty, non-block lines
    const paraLines: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].match(/^```/) &&
      !lines[i].match(/^#{1,3}\s+/) &&
      !lines[i].match(/^[\-\*]\s+/) &&
      !lines[i].match(/^\d+\.\s+/)
    ) {
      paraLines.push(lines[i])
      i++
    }
    const paraHtml = paraLines.map((l) => processInline(escapeHtml(l))).join('<br>')
    blocks.push(`<p>${paraHtml}</p>`)
  }

  return blocks.join('')
}
