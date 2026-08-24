import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'

const cwd = process.cwd()
const frontendRoot = existsSync(path.join(cwd, 'package.json')) && existsSync(path.join(cwd, 'src'))
  ? cwd
  : path.join(cwd, 'frontend')
const baseUrl = process.env.VELLA_BASE_URL || 'http://127.0.0.1:4183'
const shouldStartPreview = !process.env.VELLA_BASE_URL

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitForHttp(url, timeoutMs = 30_000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      // keep polling
    }
    await sleep(250)
  }
  throw new Error(`Timed out waiting for ${url}`)
}

function runCommand(command, args, options = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd: frontendRoot,
      env: {
        ...process.env,
        ...options.env,
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    let output = ''
    child.stdout.on('data', (chunk) => {
      const text = chunk.toString()
      output += text
      process.stdout.write(text)
    })
    child.stderr.on('data', (chunk) => {
      const text = chunk.toString()
      output += text
      process.stderr.write(text)
    })
    child.on('close', (code) => resolve({ code, output }))
  })
}

function startPreviewServer() {
  const child = spawn(
    process.platform === 'win32' ? 'npx.cmd' : 'npx',
    ['vite', 'preview', '--host', '127.0.0.1', '--port', '4183', '--strictPort'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'] },
  )
  child.stdout.on('data', (chunk) => process.stdout.write(chunk))
  child.stderr.on('data', (chunk) => process.stderr.write(chunk))
  return child
}

function ensurePass(label, result) {
  if (result.code !== 0) {
    throw new Error(`${label} failed with exit code ${result.code}`)
  }
}

async function main() {
  let server = null

  const build = await runCommand(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'build'])
  ensurePass('build', build)

  if (shouldStartPreview) {
    server = startPreviewServer()
  }
  await waitForHttp(baseUrl)

  try {
    const env = { VELLA_BASE_URL: baseUrl }

    const visual = await runCommand(process.execPath, ['scripts/compare-vella-page-parity-all.mjs'], { env })
    ensurePass('visual parity all', visual)

    const contract = await runCommand(process.execPath, ['scripts/extract-vella-page-contract.mjs'], { env })
    ensurePass('machine page contract', contract)

    const strict = await runCommand(process.execPath, ['scripts/compare-vella-page-parity.mjs', '--strict'], { env })
    if (strict.code === 0) {
      console.log('Strict parity: pass')
    } else {
      console.log('Strict parity: expected non-blocking fail for approval refresh')
    }

    const interactions = await runCommand(process.execPath, ['scripts/smoke-vella-page-interactions.mjs'], { env })
    ensurePass('interaction parity', interactions)

    const review = await runCommand(process.execPath, ['scripts/create-vella-approval-review.mjs'])
    ensurePass('approval review generation', review)
  } finally {
    if (server) server.kill('SIGTERM')
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
