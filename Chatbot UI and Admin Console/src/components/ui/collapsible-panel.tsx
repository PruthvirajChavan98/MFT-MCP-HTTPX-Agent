import * as React from "react"
import { cn } from "./utils"

type Breakpoint = "sm" | "md" | "lg" | "xl"

interface CollapsiblePanelProps {
  title: string
  children: React.ReactNode
  collapseBelow?: Breakpoint
  defaultOpen?: boolean
  className?: string
}

/**
 * Tailwind responsive-hide class for the desktop (always-visible) section.
 * Example: collapseBelow="md" -> desktop section uses "hidden md:block".
 */
const desktopVisibleClass: Record<Breakpoint, string> = {
  sm: "hidden sm:block",
  md: "hidden md:block",
  lg: "hidden lg:block",
  xl: "hidden xl:block",
}

/**
 * Tailwind responsive-hide class for the mobile (collapsible) section.
 * Example: collapseBelow="md" -> mobile section uses "md:hidden".
 */
const mobileVisibleClass: Record<Breakpoint, string> = {
  sm: "sm:hidden",
  md: "md:hidden",
  lg: "lg:hidden",
  xl: "xl:hidden",
}

function CollapsiblePanel({
  title,
  children,
  collapseBelow = "md",
  defaultOpen = false,
  className,
}: CollapsiblePanelProps) {
  const [open, setOpen] = React.useState(defaultOpen)

  return (
    <div className={cn(className)}>
      {/* Desktop: always visible, no toggle */}
      <div className={desktopVisibleClass[collapseBelow]}>{children}</div>

      {/* Mobile: collapsible toggle */}
      <div className={mobileVisibleClass[collapseBelow]}>
        <button
          type="button"
          onClick={() => setOpen((prev) => !prev)}
          className="flex w-full items-center justify-between rounded-md px-4 py-3 text-sm font-medium text-foreground hover:bg-muted/50"
          aria-expanded={open}
        >
          {title}
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
            className={cn(
              "transition-transform duration-200",
              open ? "rotate-180" : "rotate-0"
            )}
          >
            <path d="m6 9 6 6 6-6" />
          </svg>
        </button>
        {open ? <div className="px-4 pb-4">{children}</div> : null}
      </div>
    </div>
  )
}

export { CollapsiblePanel }
export type { CollapsiblePanelProps }
