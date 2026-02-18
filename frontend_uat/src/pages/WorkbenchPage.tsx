import { ApiWorkbench } from '../components/workbench/ApiWorkbench'
import { ENDPOINTS } from '../config/endpoints'

export function WorkbenchPage() {
  return (
    <ApiWorkbench
      title="Unified API Workbench"
      subtitle="Complete Endpoint Matrix"
      endpoints={ENDPOINTS}
      rightLabel="Total Routes"
      rightValue={String(ENDPOINTS.length)}
    />
  )
}
