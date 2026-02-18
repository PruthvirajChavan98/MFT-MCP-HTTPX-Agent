import { ApiWorkbench } from '../components/workbench/ApiWorkbench'
import { ENDPOINTS } from '../config/endpoints'

const streamingEndpoints = ENDPOINTS.filter((endpoint) => endpoint.kind === 'sse')

export function StreamsPage() {
  return (
    <ApiWorkbench
      title="Streaming Studio"
      subtitle="SSE-first workflows with live event telemetry"
      endpoints={streamingEndpoints}
      rightLabel="SSE Routes"
      rightValue={String(streamingEndpoints.length)}
    />
  )
}
