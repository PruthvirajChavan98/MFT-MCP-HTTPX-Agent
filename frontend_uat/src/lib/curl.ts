import type { BodyMode, EndpointDef } from '../types/api'
import { cleanHeaderValues, parseObjectJson } from './json'
import { resolvePath, toQueryString } from './url'

export function asBodyPreview(bodyMode: BodyMode, bodyText: string, hasFile: boolean): string {
  if (bodyMode === 'none') return ''
  if (bodyMode === 'multipart') return hasFile ? '[multipart/form-data with file]' : '[multipart/form-data]'
  return bodyText.trim() || '{}'
}

export function buildCurlPreview(args: {
  endpoint: EndpointDef
  baseUrl: string
  pathParamsText: string
  queryText: string
  headersText: string
  bodyText: string
  hasUploadFile: boolean
}): string {
  const { endpoint, baseUrl, pathParamsText, queryText, headersText, bodyText, hasUploadFile } = args

  try {
    const pathParams = parseObjectJson(pathParamsText, 'Path params')
    const query = parseObjectJson(queryText, 'Query params')
    const headers = cleanHeaderValues(parseObjectJson(headersText, 'Headers'))

    const base = baseUrl.trim().replace(/\/$/, '')
    const resolvedPath = resolvePath(endpoint.path, pathParams)
    const fullUrl = `${base}${resolvedPath}${toQueryString(query)}`

    const segments = [`curl --request ${endpoint.method} '${fullUrl}'`]

    for (const [key, value] of Object.entries(headers)) {
      segments.push(`  --header '${key}: ${String(value).replace(/'/g, "'\\''")}'`)
    }

    if (endpoint.bodyMode === 'json' && endpoint.method !== 'GET' && endpoint.method !== 'DELETE') {
      const body = bodyText.trim() || '{}'
      segments.push(`  --header 'Content-Type: application/json'`)
      segments.push(`  --data '${body.replace(/'/g, "'\\''")}'`)
    }

    if (endpoint.bodyMode === 'multipart') {
      const filePart = hasUploadFile ? '--form file=@<selected_file>' : "--form 'file=@/path/to/file.pdf'"
      segments.push(`  ${filePart}`)
    }

    return segments.join(' \\\n')
  } catch (error) {
    return `# ${(error as Error).message}`
  }
}
