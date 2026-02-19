import { ResponsiveContainer } from "recharts"
import { cn } from "./utils"
interface ChartContainerProps extends React.HTMLAttributes<HTMLDivElement> { config?: Record<string, { label?: string; color?: string }>; children: React.ReactElement }
function ChartContainer({ className, children, config, ...props }: ChartContainerProps) {
  return (
    <div className={cn("flex aspect-video justify-center text-xs", className)} style={config ? Object.fromEntries(Object.entries(config).map(([k, v]) => [`--color-${k}`, v.color ?? "hsl(var(--chart-1))"])) : undefined} {...props}>
      <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
    </div>
  )
}
export { ChartContainer }
