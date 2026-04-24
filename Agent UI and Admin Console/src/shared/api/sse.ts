import { parseMaybeJson } from '../lib/json'

export interface SseHandlers {
  onOpen?: (response: Response) => void
  onEvent: (eventName: string, data: string, parsed?: unknown) => void
}

export async function streamSse(
  url: string,
  init: RequestInit,
  handlers: SseHandlers,
): Promise<void> {
  const response = await fetch(url, init)
  handlers.onOpen?.(response)

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `SSE request failed (${response.status})`)
  }

  if (!response.body) {
    throw new Error('Missing readable body in SSE response')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  let buffer = ''
  let eventName = 'message'
  let dataLines: string[] = []

  const flush = () => {
    if (!dataLines.length) return
    const data = dataLines.join('\n')
    handlers.onEvent(eventName, data, parseMaybeJson(data))
    eventName = 'message'
    dataLines = []
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    while (true) {
      const lineBreak = buffer.indexOf('\n')
      if (lineBreak === -1) break

      let line = buffer.slice(0, lineBreak)
      buffer = buffer.slice(lineBreak + 1)

      if (line.endsWith('\r')) {
        line = line.slice(0, -1)
      }

      if (!line) {
        flush()
        continue
      }

      if (line.startsWith(':')) continue

      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim() || 'message'
        continue
      }

      if (line.startsWith('data:')) {
        // Fix: Strictly remove only one optional leading space per the SSE spec.
        // Using trimStart() was destroying spaces inside/between LLM tokens.
        const dataStr = line.slice(5)
        dataLines.push(dataStr.startsWith(' ') ? dataStr.slice(1) : dataStr)
      }
    }
  }

  flush()
}
