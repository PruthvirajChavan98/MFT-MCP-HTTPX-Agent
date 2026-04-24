import * as React from "react"
import { cn } from "./utils"

interface MobileHeaderProps {
  title: string
  description?: string
  actions?: React.ReactNode
  className?: string
}

const MobileHeader = React.forwardRef<HTMLDivElement, MobileHeaderProps>(
  ({ title, description, actions, className }, ref) => (
    <div
      ref={ref}
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between",
        className
      )}
    >
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description ? (
          <p className="text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
          {actions}
        </div>
      ) : null}
    </div>
  )
)
MobileHeader.displayName = "MobileHeader"

export { MobileHeader }
export type { MobileHeaderProps }
