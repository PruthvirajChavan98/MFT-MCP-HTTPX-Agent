export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
export type EndpointKind = 'http' | 'sse'
export type BodyMode = 'none' | 'json' | 'multipart'

export interface EndpointDef {
  id: string
  category: string
  name: string
  description: string
  method: HttpMethod
  path: string
  kind: EndpointKind
  bodyMode: BodyMode
  defaultPathParams?: Record<string, unknown>
  defaultQuery?: Record<string, unknown>
  defaultHeaders?: Record<string, unknown>
  defaultBody?: Record<string, unknown>
}

export interface StreamEvent {
  id: number
  timestamp: string
  event: string
  data: string
  parsed?: unknown
}

export interface HistoryItem {
  id: number
  endpointId: string
  method: HttpMethod
  url: string
  status: number | null
  durationMs: number | null
  createdAt: string
}
