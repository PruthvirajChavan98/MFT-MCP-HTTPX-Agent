import { parseMaybeJson } from './json'

export function readResponseHeaders(headers: Headers): Record<string, string> {
  const output: Record<string, string> = {}
  headers.forEach((value, key) => {
    output[key] = value
  })
  return output
}

export async function streamSse(
  url: string,
  init: RequestInit,
  handlers: {
    onOpen: (response: Response) => void
    onEvent: (eventName: string, data: string, parsed?: unknown) => void
  },
): Promise<void> {
  const response = await fetch(url, init)
  handlers.onOpen(response)

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || `SSE request failed with status ${response.status}`)
  }

  if (!response.body) {
    throw new Error('SSE stream unavailable (empty response body)')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  let buffer = ''
  let eventName = 'message'
  let dataLines: string[] = []

  const flushEvent = () => {
    if (!dataLines.length) return
    const data = dataLines.join('\n')
    handlers.onEvent(eventName, data, parseMaybeJson(data))
    eventName = 'message'
    dataLines = []
  }

  while (true) {
    const { value, done } = await reader.read()
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
        flushEvent()
        continue
      }

      if (line.startsWith(':')) {
        continue
      }

      if (line.startsWith('event:')) {
        eventName = line.slice(6).trim() || 'message'
        continue
      }

      if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }
  }

  flushEvent()
}
