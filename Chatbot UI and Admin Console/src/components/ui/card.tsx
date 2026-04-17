import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "./utils"

/**
 * Card variants — default is byte-identical to the pre-variant implementation
 * so every existing consumer renders the same markup. New variants unlock the
 * Terminal-grade Fintech surface language (elevated, bordered, ghost, hairline).
 *
 * Variant semantics:
 * - default:   standard shadcn card (rounded-lg, border, bg-card, shadow-sm)
 * - elevated:  layered gradient + inset hairline — use for hero / signature cards
 * - bordered:  stronger border, no shadow — use for stat-tile grids
 * - ghost:     no bg, no border — use for content scoped inside another card
 * - hairline:  single hairline, no shadow — restrained / secondary surfaces
 */
const cardVariants = cva("rounded-lg text-card-foreground", {
  variants: {
    variant: {
      default: "border bg-card shadow-sm",
      elevated:
        "border border-border/60 bg-gradient-to-b from-card to-[color-mix(in_srgb,var(--card)_92%,var(--background))] shadow-[0_1px_0_0_rgba(255,255,255,0.04)_inset,0_20px_40px_-24px_rgba(0,0,0,0.35)]",
      bordered: "border border-border bg-card",
      ghost: "bg-transparent",
      hairline: "border border-hairline bg-card",
    },
  },
  defaultVariants: {
    variant: "default",
  },
})

export interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {}

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(cardVariants({ variant, className }))}
      {...props}
    />
  ),
)
Card.displayName = "Card"

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />
  ),
)
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("text-2xl font-semibold leading-none tracking-tight", className)} {...props} />
  ),
)
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
  ),
)
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
  ),
)
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex items-center p-6 pt-0", className)} {...props} />
  ),
)
CardFooter.displayName = "CardFooter"

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardDescription,
  CardContent,
  cardVariants,
}
