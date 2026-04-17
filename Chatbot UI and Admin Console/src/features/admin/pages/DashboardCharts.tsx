import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

export interface ActivityTrendPoint {
  date: string
  requests: number
}

export interface CategoryPoint {
  reason: string
  count: number
  pct: number
}

export interface DashboardChartsProps {
  activityTrend: ActivityTrendPoint[]
  categories: CategoryPoint[]
}

// Token-bound palette — pulls the four accent hues from :root/.dark via CSS vars.
// Order: info (cyan), success, warning, destructive, then muted neutrals.
const PIE_COLORS = [
  'var(--info)',
  'var(--success)',
  'var(--warning)',
  'var(--destructive)',
  'var(--primary)',
  'color-mix(in srgb, var(--muted-foreground) 80%, transparent)',
]

/**
 * Charts partition for the Dashboard page — extracted into its own module so
 * the parent `Dashboard.tsx` can `lazy()`-load it. Recharts is ~370 KB gz;
 * keeping it out of the initial admin bundle is worth a deferred load here.
 */
export function DashboardCharts({ activityTrend, categories }: DashboardChartsProps) {
  return (
    <>
      <div className="xl:col-span-2 rounded-lg border border-border bg-card p-6 flex flex-col min-h-[360px]">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-sm font-medium tracking-tight">Request Volume</h3>
          <span className="text-[10px] font-tabular uppercase tracking-[0.2em] text-muted-foreground">
            trailing window
          </span>
        </div>
        <div className="flex-1 min-h-0">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={activityTrend}>
              <defs>
                <linearGradient id="dashboard-volume-fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.24} />
                  <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="2 4"
                stroke="var(--border)"
                vertical={false}
              />
              <XAxis
                dataKey="date"
                tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
                axisLine={{ stroke: 'var(--border)' }}
                tickLine={false}
                dy={6}
              />
              <YAxis
                tick={{ fill: 'var(--muted-foreground)', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                dx={-6}
              />
              <Tooltip
                cursor={{ stroke: 'var(--border)', strokeDasharray: '2 2' }}
                contentStyle={{
                  borderRadius: 6,
                  border: '1px solid var(--border)',
                  backgroundColor: 'var(--card)',
                  color: 'var(--foreground)',
                  fontSize: 12,
                }}
                labelStyle={{ color: 'var(--muted-foreground)' }}
              />
              <Area
                type="monotone"
                dataKey="requests"
                stroke="var(--primary)"
                strokeWidth={1.5}
                fill="url(#dashboard-volume-fill)"
                name="Requests"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-6 flex flex-col min-h-[360px]">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-sm font-medium tracking-tight">Topic Distribution</h3>
          <span className="text-[10px] font-tabular uppercase tracking-[0.2em] text-muted-foreground">
            top 6
          </span>
        </div>
        <div className="flex-1 min-h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={categories.slice(0, 6)}
                dataKey="count"
                nameKey="reason"
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={2}
                stroke="var(--card)"
                strokeWidth={2}
              >
                {categories.slice(0, 6).map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  borderRadius: 6,
                  border: '1px solid var(--border)',
                  backgroundColor: 'var(--card)',
                  color: 'var(--foreground)',
                  fontSize: 12,
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="space-y-2 mt-4 pt-4 border-t border-border">
          {categories.slice(0, 4).map((cat, i) => (
            <div key={cat.reason} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2.5 min-w-0">
                <span
                  className="size-2 rounded-full shrink-0"
                  style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                />
                <span className="text-muted-foreground truncate">
                  {cat.reason.replace(/_/g, ' ')}
                </span>
              </div>
              <span className="font-tabular text-foreground">
                {(cat.pct * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

// Default export for React.lazy() interop
export default DashboardCharts
