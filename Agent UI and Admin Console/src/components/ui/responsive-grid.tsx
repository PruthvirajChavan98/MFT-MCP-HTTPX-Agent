import * as React from "react"
import { cn } from "./utils"

interface ResponsiveGridProps {
  children: React.ReactNode
  cols?: {
    base?: number
    sm?: number
    md?: number
    lg?: number
    xl?: number
  }
  gap?: number
  className?: string
}

const gridColsMap: Record<number, string> = {
  1: "grid-cols-1",
  2: "grid-cols-2",
  3: "grid-cols-3",
  4: "grid-cols-4",
  5: "grid-cols-5",
  6: "grid-cols-6",
  7: "grid-cols-7",
  8: "grid-cols-8",
  9: "grid-cols-9",
  10: "grid-cols-10",
  11: "grid-cols-11",
  12: "grid-cols-12",
}

const smGridColsMap: Record<number, string> = {
  1: "sm:grid-cols-1",
  2: "sm:grid-cols-2",
  3: "sm:grid-cols-3",
  4: "sm:grid-cols-4",
  5: "sm:grid-cols-5",
  6: "sm:grid-cols-6",
  7: "sm:grid-cols-7",
  8: "sm:grid-cols-8",
  9: "sm:grid-cols-9",
  10: "sm:grid-cols-10",
  11: "sm:grid-cols-11",
  12: "sm:grid-cols-12",
}

const mdGridColsMap: Record<number, string> = {
  1: "md:grid-cols-1",
  2: "md:grid-cols-2",
  3: "md:grid-cols-3",
  4: "md:grid-cols-4",
  5: "md:grid-cols-5",
  6: "md:grid-cols-6",
  7: "md:grid-cols-7",
  8: "md:grid-cols-8",
  9: "md:grid-cols-9",
  10: "md:grid-cols-10",
  11: "md:grid-cols-11",
  12: "md:grid-cols-12",
}

const lgGridColsMap: Record<number, string> = {
  1: "lg:grid-cols-1",
  2: "lg:grid-cols-2",
  3: "lg:grid-cols-3",
  4: "lg:grid-cols-4",
  5: "lg:grid-cols-5",
  6: "lg:grid-cols-6",
  7: "lg:grid-cols-7",
  8: "lg:grid-cols-8",
  9: "lg:grid-cols-9",
  10: "lg:grid-cols-10",
  11: "lg:grid-cols-11",
  12: "lg:grid-cols-12",
}

const xlGridColsMap: Record<number, string> = {
  1: "xl:grid-cols-1",
  2: "xl:grid-cols-2",
  3: "xl:grid-cols-3",
  4: "xl:grid-cols-4",
  5: "xl:grid-cols-5",
  6: "xl:grid-cols-6",
  7: "xl:grid-cols-7",
  8: "xl:grid-cols-8",
  9: "xl:grid-cols-9",
  10: "xl:grid-cols-10",
  11: "xl:grid-cols-11",
  12: "xl:grid-cols-12",
}

const gapMap: Record<number, string> = {
  0: "gap-0",
  1: "gap-1",
  2: "gap-2",
  3: "gap-3",
  4: "gap-4",
  5: "gap-5",
  6: "gap-6",
  8: "gap-8",
  10: "gap-10",
  12: "gap-12",
}

function buildGridClasses(
  cols: ResponsiveGridProps["cols"],
  gap: number
): string {
  const classes: string[] = ["grid"]

  const base = cols?.base ?? 1
  const baseClass = gridColsMap[base]
  if (baseClass) classes.push(baseClass)

  if (cols?.sm !== undefined) {
    const smClass = smGridColsMap[cols.sm]
    if (smClass) classes.push(smClass)
  }

  if (cols?.md !== undefined) {
    const mdClass = mdGridColsMap[cols.md]
    if (mdClass) classes.push(mdClass)
  }

  if (cols?.lg !== undefined) {
    const lgClass = lgGridColsMap[cols.lg]
    if (lgClass) classes.push(lgClass)
  }

  if (cols?.xl !== undefined) {
    const xlClass = xlGridColsMap[cols.xl]
    if (xlClass) classes.push(xlClass)
  }

  const gapClass = gapMap[gap]
  if (gapClass) classes.push(gapClass)

  return classes.join(" ")
}

const ResponsiveGrid = React.forwardRef<HTMLDivElement, ResponsiveGridProps>(
  ({ children, cols, gap = 4, className }, ref) => (
    <div ref={ref} className={cn(buildGridClasses(cols, gap), className)}>
      {children}
    </div>
  )
)
ResponsiveGrid.displayName = "ResponsiveGrid"

export { ResponsiveGrid }
export type { ResponsiveGridProps }
