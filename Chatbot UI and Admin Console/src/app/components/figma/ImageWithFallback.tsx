import { useState } from 'react'

interface Props extends React.ImgHTMLAttributes<HTMLImageElement> {
  fallbackClassName?: string
}

export function ImageWithFallback({ src, alt, className, fallbackClassName, ...props }: Props) {
  const [failed, setFailed] = useState(false)

  if (failed || !src) {
    return (
      <div
        className={fallbackClassName ?? 'flex items-center justify-center rounded bg-muted text-muted-foreground text-xs'}
        aria-label={alt}
      />
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onError={() => setFailed(true)}
      {...props}
    />
  )
}
