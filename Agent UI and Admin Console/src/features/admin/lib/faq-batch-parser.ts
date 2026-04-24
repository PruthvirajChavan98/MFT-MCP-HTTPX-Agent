export interface ParsedFaqRow {
  line: number
  question: string
  answer: string
}

export interface ParsedFaqError {
  line: number
  message: string
  source: string
}

export interface ParsedFaqBatch {
  rows: ParsedFaqRow[]
  errors: ParsedFaqError[]
  delimiter: string
}

const DELIMITERS = ['|', '\t', ';', ',']

function normalize(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function guessDelimiter(lines: string[]): string {
  let winner = '|'
  let score = -1
  for (const delimiter of DELIMITERS) {
    const current = lines.reduce((sum, line) => sum + (line.includes(delimiter) ? 1 : 0), 0)
    if (current > score) {
      score = current
      winner = delimiter
    }
  }
  return winner
}

export function parseFaqBatchInput(source: string): ParsedFaqBatch {
  const lines = source
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  const delimiter = guessDelimiter(lines)
  const rows: ParsedFaqRow[] = []
  const errors: ParsedFaqError[] = []

  for (const [index, rawLine] of lines.entries()) {
    const lineNumber = index + 1
    if (!rawLine.includes(delimiter)) {
      errors.push({
        line: lineNumber,
        source: rawLine,
        message: `Missing delimiter "${delimiter}"`,
      })
      continue
    }

    const parts = rawLine.split(delimiter)
    const question = normalize(parts[0] || '')
    const answer = normalize(parts.slice(1).join(delimiter))
    if (!question || !answer) {
      errors.push({
        line: lineNumber,
        source: rawLine,
        message: 'Both question and answer are required',
      })
      continue
    }

    rows.push({
      line: lineNumber,
      question,
      answer,
    })
  }

  return { rows, errors, delimiter }
}
