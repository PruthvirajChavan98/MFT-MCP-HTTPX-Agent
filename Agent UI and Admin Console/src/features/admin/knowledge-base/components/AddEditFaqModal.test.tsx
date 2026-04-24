import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AddEditFaqModal } from './AddEditFaqModal'

const CATEGORIES = ['Technical', 'Billing', 'Account']

describe('AddEditFaqModal', () => {
  afterEach(() => {
    cleanup()
  })

  it('does not remount the question input while the user is typing', () => {
    const onSave = vi.fn()
    const onClose = vi.fn()

    render(
      <AddEditFaqModal
        initial={null}
        categories={CATEGORIES}
        saving={false}
        onSave={onSave}
        onClose={onClose}
      />,
    )

    const input = screen.getByPlaceholderText(
      'What does your customer need to know?',
    ) as HTMLInputElement
    const initialElement = input

    fireEvent.change(input, { target: { value: 'How do I reset my password?' } })

    const afterTyping = screen.getByPlaceholderText(
      'What does your customer need to know?',
    ) as HTMLInputElement

    // Same DOM node means React didn't unmount + remount EntryForm.
    // Prior bug: key={`${entry.question}:${index}`} forced remount on every keystroke.
    expect(afterTyping).toBe(initialElement)
    expect(afterTyping.value).toBe('How do I reset my password?')
  })

  it('submits normalized payload with trimmed tags', () => {
    const onSave = vi.fn()

    render(
      <AddEditFaqModal
        initial={null}
        categories={CATEGORIES}
        saving={false}
        onSave={onSave}
        onClose={() => {}}
      />,
    )

    fireEvent.change(
      screen.getByPlaceholderText('What does your customer need to know?'),
      { target: { value: '  How do I reset?  ' } },
    )
    fireEvent.change(
      screen.getByPlaceholderText('Provide a clear, concise answer.'),
      { target: { value: 'Go to settings.' } },
    )
    fireEvent.change(
      screen.getByPlaceholderText('e.g. billing, refund'),
      { target: { value: ' reset , password ,,  ' } },
    )

    fireEvent.click(screen.getByRole('button', { name: /Add FAQ/i }))

    expect(onSave).toHaveBeenCalledTimes(1)
    expect(onSave).toHaveBeenCalledWith([
      {
        question: 'How do I reset?',
        answer: 'Go to settings.',
        category: 'Technical',
        tags: ['reset', 'password'],
      },
    ])
  })

  it('uses token-based surfaces (no hardcoded light-mode colors)', () => {
    const { container } = render(
      <AddEditFaqModal
        initial={null}
        categories={CATEGORIES}
        saving={false}
        onSave={() => {}}
        onClose={() => {}}
      />,
    )

    const html = container.innerHTML

    expect(html).not.toMatch(/\bbg-white\b/)
    expect(html).not.toMatch(/\btext-gray-\d+/)
    expect(html).not.toMatch(/\bborder-gray-\d+/)
    expect(html).not.toMatch(/\bbg-teal-\d+/)
    expect(html).toMatch(/bg-card|bg-popover/)
    expect(html).toMatch(/border-border/)
  })

  it('shows validation errors when question or answer is empty', () => {
    const onSave = vi.fn()

    render(
      <AddEditFaqModal
        initial={null}
        categories={CATEGORIES}
        saving={false}
        onSave={onSave}
        onClose={() => {}}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Add FAQ/i }))

    expect(onSave).not.toHaveBeenCalled()
    expect(screen.getByText('Question is required')).toBeTruthy()
    expect(screen.getByText('Answer is required')).toBeTruthy()
  })
})
