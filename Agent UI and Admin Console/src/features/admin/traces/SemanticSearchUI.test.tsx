import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SemanticSearchUI } from './SemanticSearchUI'

/**
 * TanStack Query caches results by `queryKey`. In the original
 * implementation, a same-text resubmit of the "Search Vectors" button
 * was a no-op because `setActiveQuery(sameValue)` didn't change the key.
 * The fix explicitly calls `refetch()` in that branch. These tests lock
 * that behaviour:
 *
 * 1. First submit fires one network call.
 * 2. Second submit with IDENTICAL text fires another network call.
 * 3. Submit with DIFFERENT text fires another network call (and keys
 *    the in-flight query under the new text).
 */

const fetchVectorSearch = vi.fn()
vi.mock('@features/admin/api/admin', () => ({
    fetchVectorSearch: (args: unknown) => fetchVectorSearch(args),
}))

function renderUI() {
    // Fresh QueryClient per test so queryKey caches can't leak between
    // test runs. `retry: false` makes mock errors propagate immediately.
    const qc = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
    })
    return render(
        <QueryClientProvider client={qc}>
            <SemanticSearchUI />
        </QueryClientProvider>,
    )
}

beforeEach(() => {
    fetchVectorSearch.mockReset()
    fetchVectorSearch.mockResolvedValue({ kind: 'trace', k: 5, items: [] })
})

afterEach(() => {
    cleanup()
})

async function submitSearch(text: string) {
    const input = screen.getByPlaceholderText(/search traces semantically/i)
    fireEvent.change(input, { target: { value: text } })
    const button = screen.getByRole('button', { name: /search vectors/i })
    fireEvent.click(button)
}

describe('SemanticSearchUI — "Search Vectors" re-submit', () => {
    it('fires fetchVectorSearch on the first submit', async () => {
        renderUI()
        await submitSearch('angry user')
        await waitFor(() => expect(fetchVectorSearch).toHaveBeenCalledTimes(1))
        expect(fetchVectorSearch).toHaveBeenLastCalledWith({
            kind: 'trace',
            text: 'angry user',
            k: 5,
        })
    })

    it('fires a second network call when the same text is submitted again', async () => {
        renderUI()
        await submitSearch('angry user')
        await waitFor(() => expect(fetchVectorSearch).toHaveBeenCalledTimes(1))

        // Click "Search Vectors" a second time with identical text.
        const button = screen.getByRole('button', { name: /search vectors/i })
        fireEvent.click(button)

        await waitFor(() => expect(fetchVectorSearch).toHaveBeenCalledTimes(2))
    })

    it('fires a new network call when the text changes', async () => {
        renderUI()
        await submitSearch('angry user')
        await waitFor(() => expect(fetchVectorSearch).toHaveBeenCalledTimes(1))

        await submitSearch('loan foreclosure')
        await waitFor(() => expect(fetchVectorSearch).toHaveBeenCalledTimes(2))
        expect(fetchVectorSearch).toHaveBeenLastCalledWith({
            kind: 'trace',
            text: 'loan foreclosure',
            k: 5,
        })
    })
})
