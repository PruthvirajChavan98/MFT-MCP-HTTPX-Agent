import * as React from "react"
import { cn } from "./utils"

interface SplitPaneProps {
  sidebar: React.ReactNode
  main: React.ReactNode
  sidebarWidth?: string
  showMain?: boolean
  onBack?: () => void
  className?: string
}

const SplitPane = React.forwardRef<HTMLDivElement, SplitPaneProps>(
  (
    {
      sidebar,
      main,
      sidebarWidth = "w-1/3",
      showMain = false,
      onBack,
      className,
    },
    ref
  ) => (
    <div ref={ref} className={cn("flex min-h-0 flex-1", className)}>
      {/* Desktop layout: side-by-side */}
      <div className={cn("hidden md:flex md:flex-row md:min-h-0 md:flex-1")}>
        <div className={cn("min-h-0 overflow-y-auto", sidebarWidth)}>
          {sidebar}
        </div>
        <div className="hidden md:block w-px bg-border" />
        <div className="min-h-0 flex-1 overflow-y-auto">{main}</div>
      </div>

      {/* Mobile layout: toggle between panels */}
      <div className="flex min-h-0 flex-1 flex-col md:hidden">
        {showMain ? (
          <div className="flex min-h-0 flex-1 flex-col">
            {onBack ? (
              <button
                type="button"
                onClick={onBack}
                className="flex items-center gap-1 px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="m15 18-6-6 6-6" />
                </svg>
                Back
              </button>
            ) : null}
            <div className="min-h-0 flex-1 overflow-y-auto">{main}</div>
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto">{sidebar}</div>
        )}
      </div>
    </div>
  )
)
SplitPane.displayName = "SplitPane"

export { SplitPane }
export type { SplitPaneProps }
