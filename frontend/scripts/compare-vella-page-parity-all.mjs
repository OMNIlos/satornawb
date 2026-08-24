import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'

const frontendRoot = process.cwd()
const baseUrl = process.env.VELLA_BASE_URL || 'http://127.0.0.1:4181'
const shouldStartPreview = !process.env.VELLA_BASE_URL
const screens = [
  'wb-repricer-products',
  'mobile-fallback-products',
  'wide-products',
  'wb-repricer-algo',
  'wb-repricer-templates',
  'wb-repricer-history',
  'wb-repricer-liq',
  'wb-repricer-promos',
  'products-advanced-filters',
  'products-sort-dropdown',
  'products-columns-dropdown',
  'products-bulk-strategy-dropdown',
  'products-bulk-bar-and-template-dropdown',
  'products-empty-search-state',
  'products-api-error-state',
  'products-status-cell-dropdown',
  'products-apply-modal',
  'products-apply-progress-modal',
  'products-night-median-modal',
  'products-bulk-pmin-modal',
  'products-bulk-liquidation-step-1',
  'products-bulk-liquidation-step-2',
  'products-pmin-warning-modal',
  'wb-reviews',
  'system-notifications',
  'settings-profile',
  'settings-access',
  'avito-overview',
  'avito-inbox',
  'avito-listings',
  'avito-stats',
  'avito-notifications',
  'topbar-calendar-popover',
  'topbar-notifications-dropdown',
  'topbar-export-dropdown',
  'templates-create-template-modal',
  'promos-calculator-expanded',
  'digest-brand-filter-popover',
  'abc-report-comments-drawer',
  'drawer-overview',
  'drawer-price-edit-focus',
  'drawer-rules-tab',
  'drawer-misc-orders-tab',
  'drawer-misc-logs-tab',
  'toast-success-info-warn-stack',
  'products-save-view-modal',
  'products-segment-details-modal',
  'products-bulk-assign-manager-modal',
  'reports-problem-queue-modal',
  'promos-detail-overlay',
  'reviews-drawer-answer',
  'reviews-drawer-audit',
  'reviews-settings-modal',
  'help-table-fields-modal',
  'wb-reports-digest',
  'wb-reports-digest-period',
  'wb-reports-rules',
  'wb-reports-rules-preview',
  'reports-rules-threshold-preview-modal',
  'wb-reports-abc',
  'wb-reports-rnp',
  'wb-reports-pnl',
  'wb-reports-ads',
  'wb-reports-stock',
  'wb-reports-week',
]

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

function startPreviewServer() {
  const distHtml = path.join(frontendRoot, 'dist', 'index.html')
  if (!existsSync(distHtml)) {
    throw new Error('frontend/dist is missing. Run npm run build first.')
  }

  const child = spawn(
    process.platform === 'win32' ? 'npx.cmd' : 'npx',
    ['vite', 'preview', '--host', '127.0.0.1', '--port', '4181', '--strictPort'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'] },
  )
  child.stdout.on('data', (chunk) => process.stdout.write(chunk))
  child.stderr.on('data', (chunk) => process.stderr.write(chunk))
  return child
}

function runScreen(screen) {
  return new Promise((resolve) => {
    const child = spawn(
      process.execPath,
      ['scripts/compare-vella-page-parity.mjs', '--no-server'],
      {
        cwd: frontendRoot,
        env: {
          ...process.env,
          VELLA_BASE_URL: baseUrl,
          VELLA_PARITY_SCREEN: screen,
        },
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    )
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
    child.on('close', (code) => resolve({ screen, code, output }))
  })
}

async function main() {
  let server = null
  if (shouldStartPreview) {
    server = startPreviewServer()
  }
  await waitForHttp(baseUrl)

  try {
    const results = []
    for (const screen of screens) {
      results.push(await runScreen(screen))
    }
    const failed = results.filter((result) => result.code !== 0)
    if (failed.length) {
      console.error(`Vella page parity all: fail (${failed.map((result) => result.screen).join(', ')})`)
      process.exitCode = 1
    } else {
      console.log(`Vella page parity all: pass (${screens.join(', ')})`)
    }
  } finally {
    if (server) server.kill('SIGTERM')
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
