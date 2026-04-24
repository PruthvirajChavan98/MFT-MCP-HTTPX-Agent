import { describe, expect, it } from 'vitest'
import { tableElementToMarkdown } from './clipboard'

describe('tableElementToMarkdown', () => {
  it('serializes an HTML table into markdown with a header divider', () => {
    document.body.innerHTML = `
      <table>
        <thead>
          <tr>
            <th>Product</th>
            <th>Rate</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Home Loan</td>
            <td>8.5%</td>
          </tr>
          <tr>
            <td>Business | Loan</td>
            <td>14%</td>
          </tr>
        </tbody>
      </table>
    `

    const table = document.querySelector('table')
    expect(table).toBeTruthy()

    const markdown = tableElementToMarkdown(table as HTMLTableElement)

    expect(markdown).toBe(
      [
        '| Product | Rate |',
        '| --- | --- |',
        '| Home Loan | 8.5% |',
        '| Business \\| Loan | 14% |',
      ].join('\n'),
    )
  })
})
