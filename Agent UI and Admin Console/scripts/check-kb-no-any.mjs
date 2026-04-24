import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Paths updated after Phase-5 frontend restructure moved admin/*
// into feature-sliced `src/features/admin/…`.
const files = [
  'src/features/admin/knowledge-base/KnowledgeBasePage.tsx',
  'src/features/admin/knowledge-base/viewmodel.ts',
  'src/features/admin/query/queryOptions.ts',
]

const anyPattern = /\bany\b/
const violations = []

for (const file of files) {
  const absolute = resolve(process.cwd(), file)
  const source = readFileSync(absolute, 'utf8')
  const lines = source.split(/\r?\n/)

  lines.forEach((line, index) => {
    if (line.trimStart().startsWith('//')) return
    if (anyPattern.test(line)) {
      violations.push(`${file}:${index + 1}: ${line.trim()}`)
    }
  })
}

if (violations.length > 0) {
  console.error('KB no-any gate failed:')
  for (const violation of violations) {
    console.error(`- ${violation}`)
  }
  process.exit(1)
}
