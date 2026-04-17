import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  CheckCircle,
  Database,
  Globe,
  Network,
  RefreshCw,
  Server,
  Shield,
  XCircle,
  type LucideProps,
} from 'lucide-react'
import type { ComponentType } from 'react'

import {
  fetchRateLimitConfig,
  fetchRateLimitMetrics,
  fetchSystemHealth,
} from '@features/admin/api/admin'
import { Alert, AlertDescription } from '@components/ui/alert'
import { Card } from '@components/ui/card'
import { MobileHeader } from '@components/ui/mobile-header'
import { ResponsiveGrid } from '@components/ui/responsive-grid'
import { Skeleton } from '@components/ui/skeleton'
import { cn } from '@components/ui/utils'

const DEPENDENCY_ICONS: Record<string, ComponentType<LucideProps>> = {
  redis: Database,
  postgres: Server,
  tor_exit_list: Network,
}

export function SystemHealth() {
  const {
    data: health,
    isLoading,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['system-health'],
    queryFn: fetchSystemHealth,
    refetchInterval: 15000,
  })

  const {
    data: rlMetrics,
    isLoading: rlmLoading,
    refetch: refetchMetrics,
  } = useQuery({
    queryKey: ['rate-limit-metrics'],
    queryFn: fetchRateLimitMetrics,
    refetchInterval: 15000,
  })

  const {
    data: rlConfig,
    isLoading: rlcLoading,
    refetch: refetchConfig,
  } = useQuery({
    queryKey: ['rate-limit-config'],
    queryFn: fetchRateLimitConfig,
    refetchInterval: 60000,
  })

  const handleRefetch = () => {
    refetch()
    refetchMetrics()
    refetchConfig()
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{(error as Error).message}</AlertDescription>
      </Alert>
    )
  }

  const healthy = health?.healthy ?? false

  return (
    <div className="space-y-8 max-w-[1200px] mx-auto">
      <MobileHeader
        title="System Health"
        description="Platform telemetry and dependency readiness"
        actions={
          <button
            onClick={handleRefetch}
            disabled={isFetching}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md border border-border bg-background text-foreground hover:bg-accent transition-colors text-xs font-medium disabled:opacity-50"
          >
            <RefreshCw
              className={cn('size-3.5', isFetching && 'animate-spin text-primary')}
            />
            Sync State
          </button>
        }
      />

      {isLoading || !health ? (
        <Skeleton className="w-full h-48 rounded-lg" />
      ) : (
        <>
          {/* Fleet Status — signature hero. Monochrome, dot-indicator, tabular timestamp. */}
          <Card variant="elevated" className="relative overflow-hidden p-6 sm:p-8">
            <div
              aria-hidden
              className="absolute inset-0 opacity-60"
              style={{ backgroundImage: 'var(--atmosphere-radial-1)' }}
            />
            <div className="relative flex flex-wrap items-center justify-between gap-6">
              <div className="flex items-center gap-4">
                <div
                  className={cn(
                    'size-12 rounded-md flex items-center justify-center ring-1',
                    healthy
                      ? 'bg-[var(--success-soft)] text-[var(--success)] ring-[var(--success)]/20'
                      : 'bg-destructive/10 text-destructive ring-destructive/20',
                  )}
                  aria-hidden
                >
                  {healthy ? <CheckCircle className="size-6" /> : <XCircle className="size-6" />}
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={cn(
                        'size-1.5 rounded-full',
                        healthy
                          ? 'bg-[var(--success)] animate-pulse'
                          : 'bg-destructive',
                      )}
                      aria-hidden
                    />
                    <span className="text-[10px] font-tabular uppercase tracking-[0.2em] text-muted-foreground">
                      fleet status · live
                    </span>
                  </div>
                  <div className="text-2xl sm:text-3xl font-light tracking-tight capitalize">
                    {health.status}
                  </div>
                </div>
              </div>

              <div className="text-right">
                <div className="text-[10px] font-tabular uppercase tracking-[0.2em] text-muted-foreground mb-1">
                  timestamp · utc
                </div>
                <div className="font-tabular text-sm text-foreground">
                  {new Date(health.timestamp * 1000).toUTCString()}
                </div>
              </div>
            </div>
          </Card>

          <div>
            <h3 className="text-sm font-medium tracking-tight mb-4">
              Infrastructure Dependencies
            </h3>
            <ResponsiveGrid cols={{ base: 1, sm: 2, lg: 3 }} gap={4}>
              {Object.entries(health.checks || {}).map(([name, dep]) => {
                const Icon = DEPENDENCY_ICONS[name] || Globe
                const isHealthy = dep.ok

                return (
                  <Card
                    key={name}
                    variant="bordered"
                    className="relative overflow-hidden p-5"
                  >
                    <div
                      aria-hidden
                      className={cn(
                        'absolute top-0 left-0 w-0.5 h-full',
                        isHealthy ? 'bg-[var(--success)]' : 'bg-destructive',
                      )}
                    />
                    <div className="flex items-start justify-between mb-4 pl-2">
                      <div className="flex items-center gap-3">
                        <div
                          className={cn(
                            'size-9 rounded-md flex items-center justify-center',
                            isHealthy
                              ? 'bg-[var(--success-soft)] text-[var(--success)]'
                              : 'bg-destructive/10 text-destructive',
                          )}
                        >
                          <Icon className="size-4" />
                        </div>
                        <div className="capitalize font-medium text-sm tracking-tight">
                          {name.replace(/_/g, ' ')}
                        </div>
                      </div>
                    </div>

                    <div className="space-y-2 pl-2 pt-2 border-t border-border">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">
                          Status
                        </span>
                        <span
                          className={cn(
                            'font-tabular rounded px-2 py-0.5 text-[10px] uppercase tracking-[0.15em]',
                            isHealthy
                              ? 'bg-[var(--success-soft)] text-[var(--success)]'
                              : 'bg-destructive/10 text-destructive',
                          )}
                        >
                          {isHealthy ? 'Operational' : 'Failing'}
                        </span>
                      </div>
                      {Object.entries(dep)
                        .filter(([k]) => k !== 'ok')
                        .map(([k, v]) => (
                          <div key={k} className="flex items-center justify-between">
                            <span className="text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">
                              {k.replace(/_/g, ' ')}
                            </span>
                            <span className="font-tabular text-xs text-foreground bg-muted px-2 py-0.5 rounded">
                              {String(v)}
                            </span>
                          </div>
                        ))}
                    </div>
                  </Card>
                )
              })}
            </ResponsiveGrid>
          </div>

          {/* Rate Limiting Section */}
          <div className="pt-6 border-t border-border">
            <div className="flex items-center gap-3 mb-6">
              <h3 className="text-sm font-medium tracking-tight">Traffic & Rate Limiting</h3>
              {rlConfig && (
                <span
                  className={cn(
                    'font-tabular rounded px-2 py-0.5 text-[10px] uppercase tracking-[0.15em]',
                    rlConfig.enabled
                      ? 'bg-[var(--success-soft)] text-[var(--success)]'
                      : 'bg-[var(--warning-soft)] text-[var(--warning)]',
                  )}
                >
                  {rlConfig.enabled ? 'Enforcing' : 'Disabled'}
                </span>
              )}
            </div>

            <div className="grid lg:grid-cols-2 gap-6">
              {/* Global Config Card */}
              <Card variant="bordered" className="relative overflow-hidden p-6">
                <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
                  <Shield className="size-32" />
                </div>
                <h4 className="text-xs font-tabular uppercase tracking-[0.15em] text-muted-foreground mb-4 flex items-center gap-2">
                  <Shield className="size-4 text-primary" />
                  Active Configuration
                </h4>
                {rlcLoading || !rlConfig ? (
                  <Skeleton className="w-full h-32" />
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      ['Algorithm', rlConfig.algorithm],
                      ['Failure Mode', rlConfig.failure_mode],
                      ['Max Burst', `${rlConfig.max_burst} reqs`],
                      [
                        'Per-IP Defense',
                        rlConfig.per_ip_enabled
                          ? `Active (${rlConfig.per_ip?.limit})`
                          : 'Inactive',
                      ],
                    ].map(([label, value]) => (
                      <div
                        key={label as string}
                        className="bg-muted p-3 rounded-md border border-border"
                      >
                        <div className="text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground mb-1">
                          {label}
                        </div>
                        <div className="font-tabular text-xs text-foreground">{value}</div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              {/* Endpoint Metrics */}
              <Card variant="bordered" className="p-6 flex flex-col items-start gap-4 h-full relative overflow-hidden">
                <h4 className="text-xs font-tabular uppercase tracking-[0.15em] text-muted-foreground flex items-center gap-2">
                  <Activity className="size-4 text-destructive" />
                  Endpoint Quotas
                </h4>
                {rlmLoading || !rlMetrics ? (
                  <Skeleton className="w-full h-32" />
                ) : (
                  <div className="w-full overflow-x-auto">
                    <table className="w-full text-xs text-left">
                      <thead>
                        <tr className="border-b border-border text-[10px] font-tabular uppercase tracking-[0.15em] text-muted-foreground">
                          <th className="pb-2">Endpoint</th>
                          <th className="pb-2 text-right">Allowed</th>
                          <th className="pb-2 text-right">Denied</th>
                          <th className="hidden md:table-cell pb-2 text-right">RPM</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {Object.entries(rlMetrics.metrics || {}).map(
                          ([ep, stats]: [string, Record<string, number | string>]) => {
                            const cleanName = ep.replace('endpoint:', '')
                            return (
                              <tr key={ep}>
                                <td className="py-2.5 font-tabular text-muted-foreground">
                                  /{cleanName}
                                </td>
                                <td className="py-2.5 text-right font-tabular text-[var(--success)]">
                                  {stats.requests_allowed}
                                </td>
                                <td className="py-2.5 text-right font-tabular text-destructive">
                                  {stats.requests_denied}
                                </td>
                                <td className="hidden md:table-cell py-2.5 text-right font-tabular text-muted-foreground">
                                  {stats.rate}
                                </td>
                              </tr>
                            )
                          },
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
