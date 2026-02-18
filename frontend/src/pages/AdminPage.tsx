import { ApiWorkbench } from '../components/workbench/ApiWorkbench'
import { CATEGORY_GROUPS, ENDPOINTS } from '../config/endpoints'

const adminSet = new Set<string>(CATEGORY_GROUPS.admin)
const adminEndpoints = ENDPOINTS.filter((endpoint) => adminSet.has(endpoint.category))

export function AdminPage() {
  return (
    <ApiWorkbench
      title="Admin Surface"
      subtitle="FAQ management and privileged operations"
      endpoints={adminEndpoints}
      rightLabel="Admin Routes"
      rightValue={String(adminEndpoints.length)}
    />
  )
}
