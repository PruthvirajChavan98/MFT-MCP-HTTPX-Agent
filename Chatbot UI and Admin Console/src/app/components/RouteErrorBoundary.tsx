import { isRouteErrorResponse, useRouteError } from 'react-router'

function toMessage(error: unknown): string {
  if (isRouteErrorResponse(error)) {
    const detail =
      typeof error.data === 'string'
        ? error.data
        : (error.data as { message?: string; detail?: string } | undefined)?.message ||
          (error.data as { detail?: string } | undefined)?.detail
    return detail || error.statusText || `Request failed (${error.status})`
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message
  }

  return 'An unexpected error occurred while rendering this page.'
}

export function RouteErrorBoundary() {
  const error = useRouteError()
  const message = toMessage(error)

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <div className="w-full max-w-xl rounded-xl border border-red-200 bg-white p-6 shadow-sm">
        <h1 className="text-lg font-semibold text-slate-900">Something went wrong</h1>
        <p className="mt-2 text-sm text-slate-600">
          The page failed to load. Retry, and if the issue persists, check server logs for this request window.
        </p>
        <div className="mt-4 rounded-md border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">
          {message}
        </div>
        <div className="mt-5">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-md bg-cyan-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-cyan-700"
          >
            Retry
          </button>
        </div>
      </div>
    </div>
  )
}
