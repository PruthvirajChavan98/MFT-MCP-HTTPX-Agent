export function CategoryBadge({ category }: { category: string }) {
  const colors: Record<string, string> = {
    Billing: 'bg-blue-50 text-blue-700 border-blue-200',
    Account: 'bg-purple-50 text-purple-700 border-purple-200',
    Data: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    Technical: 'bg-orange-50 text-orange-700 border-orange-200',
    Sales: 'bg-green-50 text-green-700 border-green-200',
  }

  return (
    <span
      className={[
        'inline-flex items-center rounded-md border px-2 py-0.5 text-xs',
        colors[category] ?? 'bg-gray-50 text-gray-700 border-gray-200',
      ].join(' ')}
    >
      {category}
    </span>
  )
}
