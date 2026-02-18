import { createEffect, createMemo, createSignal } from 'solid-js'
import type { EndpointDef, HistoryItem, StreamEvent } from '../types/api'
import { buildCurlPreview } from '../lib/curl'
import { cleanHeaderValues, formatPretty, parseObjectJson } from '../lib/json'
import { readResponseHeaders, streamSse } from '../lib/stream'
import { extractPathTokens, resolvePath, toQueryString } from '../lib/url'

export interface UseApiWorkbenchOptions {
  endpoints: EndpointDef[]
  initialBaseUrl?: string
}

export function useApiWorkbench(options: UseApiWorkbenchOptions) {
  const initialEndpoint = options.endpoints[0]

  const [baseUrl, setBaseUrl] = createSignal(options.initialBaseUrl ?? import.meta.env.VITE_API_BASE_URL ?? '/api')
  const [search, setSearch] = createSignal('')
  const [selectedEndpointId, setSelectedEndpointId] = createSignal(initialEndpoint?.id ?? '')

  const [pathParamsText, setPathParamsText] = createSignal('{}')
  const [queryText, setQueryText] = createSignal('{}')
  const [headersText, setHeadersText] = createSignal('{}')
  const [bodyText, setBodyText] = createSignal('{}')
  const [uploadFile, setUploadFile] = createSignal<File | null>(null)

  const [requestUrl, setRequestUrl] = createSignal('')
  const [responseStatus, setResponseStatus] = createSignal<number | null>(null)
  const [responseDurationMs, setResponseDurationMs] = createSignal<number | null>(null)
  const [responseBody, setResponseBody] = createSignal('')
  const [responseHeaders, setResponseHeaders] = createSignal<Record<string, string>>({})

  const [streamEvents, setStreamEvents] = createSignal<StreamEvent[]>([])
  const [history, setHistory] = createSignal<HistoryItem[]>([])

  const [loading, setLoading] = createSignal(false)
  const [errorMessage, setErrorMessage] = createSignal('')
  const [activeController, setActiveController] = createSignal<AbortController | null>(null)

  const selectedEndpoint = createMemo<EndpointDef | undefined>(() => {
    return options.endpoints.find((endpoint) => endpoint.id === selectedEndpointId()) ?? options.endpoints[0]
  })

  const filteredBySearch = createMemo(() => {
    const needle = search().trim().toLowerCase()
    if (!needle) return options.endpoints

    return options.endpoints.filter((endpoint) => {
      return (
        endpoint.name.toLowerCase().includes(needle) ||
        endpoint.path.toLowerCase().includes(needle) ||
        endpoint.category.toLowerCase().includes(needle) ||
        endpoint.description.toLowerCase().includes(needle)
      )
    })
  })

  const groupedEndpoints = createMemo(() => {
    const groups = new Map<string, EndpointDef[]>()

    for (const endpoint of filteredBySearch()) {
      const existing = groups.get(endpoint.category) ?? []
      existing.push(endpoint)
      groups.set(endpoint.category, existing)
    }

    return [...groups.entries()]
  })

  createEffect(() => {
    if (!options.endpoints.length) return
    const activeId = selectedEndpointId()
    const stillExists = options.endpoints.some((endpoint) => endpoint.id === activeId)
    if (!stillExists) setSelectedEndpointId(options.endpoints[0].id)
  })

  createEffect(() => {
    const endpoint = selectedEndpoint()
    if (!endpoint) return

    const pathDefaults: Record<string, unknown> = {
      ...Object.fromEntries(extractPathTokens(endpoint.path).map((token) => [token, ''])),
      ...(endpoint.defaultPathParams ?? {}),
    }

    setPathParamsText(formatPretty(pathDefaults))
    setQueryText(formatPretty(endpoint.defaultQuery ?? {}))
    setHeadersText(formatPretty(endpoint.defaultHeaders ?? {}))

    if (endpoint.bodyMode === 'json') {
      setBodyText(formatPretty(endpoint.defaultBody ?? {}))
    } else {
      setBodyText('{}')
    }

    setUploadFile(null)
    setErrorMessage('')
    setResponseStatus(null)
    setResponseDurationMs(null)
    setResponseBody('')
    setResponseHeaders({})
    setStreamEvents([])
    setRequestUrl('')
  })

  const streamAnswerText = createMemo(() => {
    return streamEvents()
      .filter((entry) => entry.event === 'token')
      .map((entry) => entry.data)
      .join('')
  })

  const streamReasoningText = createMemo(() => {
    return streamEvents()
      .filter((entry) => entry.event === 'reasoning')
      .map((entry) => entry.data)
      .join('')
  })

  const curlPreview = createMemo(() => {
    const endpoint = selectedEndpoint()
    if (!endpoint) return '# No endpoint configured for this page'
    return buildCurlPreview({
      endpoint,
      baseUrl: baseUrl(),
      pathParamsText: pathParamsText(),
      queryText: queryText(),
      headersText: headersText(),
      bodyText: bodyText(),
      hasUploadFile: !!uploadFile(),
    })
  })

  const executeRequest = async () => {
    if (loading()) return
    const endpoint = selectedEndpoint()
    if (!endpoint) return

    const controller = new AbortController()
    setActiveController(controller)

    setLoading(true)
    setErrorMessage('')
    setResponseBody('')
    setResponseHeaders({})
    setResponseStatus(null)
    setResponseDurationMs(null)
    setStreamEvents([])

    let finalStatus: number | null = null
    let finalDuration: number | null = null
    let finalUrl = ''
    const started = performance.now()

    try {
      const pathParams = parseObjectJson(pathParamsText(), 'Path params')
      const queryParams = parseObjectJson(queryText(), 'Query params')
      const parsedHeaders = cleanHeaderValues(parseObjectJson(headersText(), 'Headers'))

      const base = baseUrl().trim().replace(/\/$/, '')
      const resolvedPath = resolvePath(endpoint.path, pathParams)
      finalUrl = `${base}${resolvedPath}${toQueryString(queryParams)}`
      setRequestUrl(finalUrl)

      const requestInit: RequestInit = {
        method: endpoint.method,
        headers: { ...parsedHeaders },
        signal: controller.signal,
      }

      if (endpoint.bodyMode === 'json' && endpoint.method !== 'GET' && endpoint.method !== 'DELETE') {
        const parsedBody = parseObjectJson(bodyText(), 'Request body')
        ;(requestInit.headers as Record<string, string>)['Content-Type'] = 'application/json'
        requestInit.body = JSON.stringify(parsedBody)
      }

      if (endpoint.bodyMode === 'multipart') {
        const file = uploadFile()
        if (!file) {
          throw new Error('Select a file before invoking a multipart endpoint')
        }

        const form = new FormData()
        form.set('file', file)
        requestInit.body = form

        if (requestInit.headers && typeof requestInit.headers === 'object') {
          delete (requestInit.headers as Record<string, string>)['Content-Type']
        }
      }

      if (endpoint.kind === 'sse') {
        await streamSse(finalUrl, requestInit, {
          onOpen: (response) => {
            finalStatus = response.status
            setResponseStatus(response.status)
            setResponseHeaders(readResponseHeaders(response.headers))
          },
          onEvent: (eventName, data, parsed) => {
            setStreamEvents((current) => {
              const next: StreamEvent = {
                id: current.length + 1,
                timestamp: new Date().toISOString(),
                event: eventName,
                data,
                parsed,
              }
              return [...current.slice(-799), next]
            })
          },
        })

        finalDuration = performance.now() - started
        setResponseDurationMs(finalDuration)
        setResponseBody(
          formatPretty({
            stream_event_count: streamEvents().length,
            answer_preview: streamAnswerText().slice(0, 1200),
            reasoning_preview: streamReasoningText().slice(0, 1200),
          }),
        )
      } else {
        const response = await fetch(finalUrl, requestInit)
        finalDuration = performance.now() - started
        finalStatus = response.status

        setResponseDurationMs(finalDuration)
        setResponseStatus(response.status)
        setResponseHeaders(readResponseHeaders(response.headers))

        const rawText = await response.text()
        if ((response.headers.get('content-type') ?? '').includes('application/json')) {
          const parsed = parseJsonSafe(rawText)
          setResponseBody(parsed === undefined ? rawText : formatPretty(parsed))
        } else {
          const parsed = parseJsonSafe(rawText)
          setResponseBody(parsed === undefined ? rawText : formatPretty(parsed))
        }
      }

      setHistory((current) => [
        {
          id: Date.now(),
          endpointId: endpoint.id,
          method: endpoint.method,
          url: finalUrl,
          status: finalStatus,
          durationMs: finalDuration,
          createdAt: new Date().toISOString(),
        },
        ...current,
      ].slice(0, 25))
    } catch (error) {
      const isAbort = error instanceof DOMException && error.name === 'AbortError'
      setErrorMessage(isAbort ? 'Request cancelled' : (error as Error).message)
    } finally {
      setLoading(false)
      setActiveController(null)
    }
  }

  const cancelRequest = () => {
    activeController()?.abort()
  }

  return {
    baseUrl,
    setBaseUrl,
    search,
    setSearch,
    selectedEndpointId,
    setSelectedEndpointId,
    selectedEndpoint,
    groupedEndpoints,
    pathParamsText,
    setPathParamsText,
    queryText,
    setQueryText,
    headersText,
    setHeadersText,
    bodyText,
    setBodyText,
    uploadFile,
    setUploadFile,
    requestUrl,
    responseStatus,
    responseDurationMs,
    responseBody,
    responseHeaders,
    streamEvents,
    history,
    loading,
    errorMessage,
    streamAnswerText,
    streamReasoningText,
    curlPreview,
    executeRequest,
    cancelRequest,
  }
}

function parseJsonSafe(text: string): unknown | undefined {
  try {
    return JSON.parse(text)
  } catch {
    return undefined
  }
}
