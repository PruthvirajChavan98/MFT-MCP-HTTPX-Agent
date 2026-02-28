import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const files = [
  'src/app/components/admin/KnowledgeBaseEnterprise.tsx',
  'src/app/components/admin/viewmodels/knowledgeBase.ts',
  'src/app/components/admin/viewmodels/queryOptions.ts',
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
