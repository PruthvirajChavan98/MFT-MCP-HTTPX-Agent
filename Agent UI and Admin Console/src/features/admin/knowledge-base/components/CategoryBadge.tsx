export function CategoryBadge({ category }: { category: string }) {
  const tones: Record<string, string> = {
    Billing: 'bg-[var(--info-soft)] text-[var(--info)] border-[var(--info)]/20',
    Account: 'bg-primary/10 text-primary border-primary/20',
    Data: 'bg-[var(--info-soft)] text-[var(--info)] border-[var(--info)]/20',
    Technical: 'bg-[var(--warning-soft)] text-[var(--warning)] border-[var(--warning)]/20',
    Sales: 'bg-[var(--success-soft)] text-[var(--success)] border-[var(--success)]/20',
  }

  return (
    <span
      className={[
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-tabular',
        tones[category] ?? 'bg-muted text-muted-foreground border-border',
      ].join(' ')}
    >
      {category}
    </span>
  )
}
