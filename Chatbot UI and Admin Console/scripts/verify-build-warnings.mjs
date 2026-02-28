import { spawnSync } from 'node:child_process'

const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm'

const result = spawnSync(npmCmd, ['run', 'build'], {
  encoding: 'utf8',
  env: process.env,
})

const stdout = result.stdout || ''
const stderr = result.stderr || ''
process.stdout.write(stdout)
process.stderr.write(stderr)

if (result.status && result.status !== 0) {
  process.exit(result.status)
}

const output = `${stdout}\n${stderr}`
const lines = output.split(/\r?\n/)

const warningLines = lines.filter((line) => {
  const normalized = line.toLowerCase()
  if (!normalized.trim()) return false
  return normalized.includes('(!)') || normalized.includes('warning')
})

if (warningLines.length) {
  console.error('\nBuild emitted warnings. Failing warning gate.')
  for (const line of warningLines) {
    console.error(`- ${line}`)
  }
  process.exit(1)
}
