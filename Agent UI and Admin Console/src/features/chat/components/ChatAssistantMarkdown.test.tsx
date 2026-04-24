import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ChatAssistantMarkdown } from './ChatAssistantMarkdown'

describe('ChatAssistantMarkdown', () => {
  it('renders allowlisted raw HTML color styling', () => {
    const { container } = render(
      <ChatAssistantMarkdown
        content={'<span style="color:#83f287">Hi again! What can I help you with today?</span>'}
        status="done"
      />,
    )

    const span = screen.getByText('Hi again! What can I help you with today?')
    expect(span.tagName).toBe('SPAN')
    expect((span as HTMLElement).style.color).toBe('rgb(131, 242, 135)')
    expect(container.querySelector('script')).toBeNull()
  })

  it('strips unsafe html attributes and non-color inline styles', () => {
    render(
      <ChatAssistantMarkdown
        content={
          '<span style="background:red;color:#83f287" onclick="alert(1)">Safe text</span><script>alert(1)</script>'
        }
        status="done"
      />,
    )

    const span = screen.getByText('Safe text') as HTMLElement
    expect(span.tagName).toBe('SPAN')
    expect(span.style.color).toBe('rgb(131, 242, 135)')
    expect(span.style.backgroundColor).toBe('')
    expect(span.getAttribute('onclick')).toBeNull()
    expect(screen.queryByText('alert(1)')).not.toBeInTheDocument()
  })
})
