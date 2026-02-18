export function PageHeader(props: {
  title: string
  subtitle: string
  rightLabel?: string
  rightValue?: string
}) {
  return (
    <header class="page-header card">
      <div>
        <p class="eyebrow">{props.subtitle}</p>
        <h2>{props.title}</h2>
      </div>
      <div class="header-metric">
        <span>{props.rightLabel ?? 'Status'}</span>
        <strong>{props.rightValue ?? 'Active'}</strong>
      </div>
    </header>
  )
}
