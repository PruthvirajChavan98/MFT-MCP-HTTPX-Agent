import type { ReactNode } from "react"
import { cn } from "./utils"

type Breakpoint = "sm" | "md" | "lg" | "xl"

interface Column<T> {
  key: string
  label: string
  visibleFrom?: Breakpoint
  className?: string
  headerClassName?: string
}

interface ResponsiveTableProps<T> {
  columns: Column<T>[]
  data: T[]
  renderCell: (row: T, column: Column<T>, index: number) => ReactNode
  emptyMessage?: string
  onRowClick?: (row: T) => void
  className?: string
}

const breakpointVisibilityClass: Record<Breakpoint, string> = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
  xl: "hidden xl:table-cell",
}

function ResponsiveTable<T>({
  columns,
  data,
  renderCell,
  emptyMessage = "No data available.",
  onRowClick,
  className,
}: ResponsiveTableProps<T>) {
  return (
    <div className={cn("w-full overflow-x-auto", className)}>
      <table className="w-full caption-bottom text-sm">
        <thead className="[&_tr]:border-b">
          <tr className="border-b">
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn(
                  "px-4 py-3 text-left align-middle text-[10px] font-bold uppercase tracking-wide text-muted-foreground",
                  column.visibleFrom
                    ? breakpointVisibilityClass[column.visibleFrom]
                    : undefined,
                  column.headerClassName
                )}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&_tr:last-child]:border-0">
          {data.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-8 text-center text-sm text-muted-foreground"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className={cn(
                  "border-b transition-colors hover:bg-muted/50",
                  onRowClick ? "cursor-pointer" : undefined
                )}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cn(
                      "px-4 py-3 align-middle text-sm",
                      column.visibleFrom
                        ? breakpointVisibilityClass[column.visibleFrom]
                        : undefined,
                      column.className
                    )}
                  >
                    {renderCell(row, column, rowIndex)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

export { ResponsiveTable }
export type { Column, Breakpoint, ResponsiveTableProps }
