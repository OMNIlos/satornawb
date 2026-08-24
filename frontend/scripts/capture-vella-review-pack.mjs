import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const frontendRoot = process.cwd()
const projectRoot = path.resolve(frontendRoot, '..')
const stamp = new Date().toISOString().replace(/[:.]/g, '-')
const outputRoot = path.resolve(projectRoot, 'outputs', `vella-review-pack-${stamp}`)
const baseUrl = process.env.VELLA_BASE_URL || 'http://127.0.0.1:4176'
const shouldStartPreview = !process.env.VELLA_BASE_URL

const referenceUrl = `${baseUrl}/vella-production.html?tab=products`
const previewUrl = `${baseUrl}/internal/vella-preview/repricer`

const states = [
  {
    name: '01-default-1920',
    title: 'Default, desktop 1920',
    viewport: { width: 1920, height: 1080 },
  },
  {
    name: '02-default-1440',
    title: 'Default, desktop 1440',
    viewport: { width: 1440, height: 900 },
  },
  {
    name: '03-topbar-calendar',
    title: 'Topbar period calendar popover',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('#globalPeriodRange').click(),
    preview: async (page) => page.locator('#globalPeriodRange').click(),
  },
  {
    name: '04-topbar-notifications',
    title: 'Topbar notifications popover',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('#bellBtn').click(),
    preview: async (page) => page.locator('#bellBtn').click(),
  },
  {
    name: '05-topbar-export',
    title: 'Topbar export dropdown',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('#ddExport button').first().click(),
    preview: async (page) => page.locator('#ddExport button').first().click(),
  },
  {
    name: '06-toolbar-sort',
    title: 'Toolbar sort dropdown',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('#ddSort button').first().click(),
    preview: async (page) => page.locator('#ddSort button').first().click(),
  },
  {
    name: '07-toolbar-columns',
    title: 'Toolbar columns dropdown',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('#ddCols button').first().click(),
    preview: async (page) => page.locator('#ddCols button').first().click(),
  },
  {
    name: '08-table-tooltip',
    title: 'Table header tooltip',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('#mainTable thead .th-tip').first().hover(),
    preview: async (page) => page.locator('#mainTable thead .th-tip').first().hover(),
  },
  {
    name: '09-search-empty',
    title: 'Search empty state',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => {
      await page.locator('#searchTable').fill('ZZZ_EMPTY_STATE')
      await page.waitForTimeout(250)
    },
    preview: async (page) => {
      await page.locator('.search input').fill('ZZZ_EMPTY_STATE')
      await page.waitForTimeout(250)
    },
  },
  {
    name: '10-sku-drawer',
    title: 'SKU drawer',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('#mainTable tbody .sku').first().click(),
    preview: async (page) => page.locator('#mainTable tbody .sku').first().click(),
  },
  {
    name: '11-night-modal',
    title: 'Night median modal',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('.topbar .icon-btn').first().click(),
    preview: async (page) => page.locator('.topbar .icon-btn').first().click(),
  },
  {
    name: '12-apply-modal',
    title: 'Apply prices modal',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.getByRole('button', { name: /Применить цены/ }).click(),
    preview: async (page) => page.getByRole('button', { name: /Применить цены/ }).click(),
  },
  {
    name: '13-problem-modal',
    title: 'Problem SKU modal',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.getByRole('button', { name: /Проблемные SKU/ }).click(),
    preview: async (page) => page.getByRole('button', { name: /Проблемные SKU/ }).click(),
  },
  {
    name: '14-bulk-strategy-dropdown',
    title: 'Bulk strategy dropdown',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('#ddBulkTpl button').first().click(),
    preview: async (page) => page.locator('#ddBulkTpl button').first().click(),
  },
  {
    name: '15-bulk-pmin-modal',
    title: 'Bulk P_min modal',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.getByRole('button', { name: /Задать P_min/ }).click(),
    preview: async (page) => page.getByRole('button', { name: /Задать P_min/ }).click(),
  },
  {
    name: '16-bulk-liquidation-modal',
    title: 'Bulk liquidation modal',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.getByRole('button', { name: /Ликвидировать/ }).click(),
    preview: async (page) => page.getByRole('button', { name: /Ликвидировать/ }).click(),
  },
  {
    name: '17-advanced-filters',
    title: 'Advanced filters panel',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('.view-btn-wide').click(),
    preview: async (page) => page.locator('.view-btn-wide').click(),
  },
  {
    name: '18-sidebar-collapsed',
    title: 'Collapsed sidebar',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('#sidebarEdge').click(),
    preview: async (page) => page.locator('#sidebarEdge').click(),
  },
  {
    name: '19-drawer-rules',
    title: 'SKU drawer rules tab',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => {
      await page.locator('#mainTable tbody .sku').first().click()
      await page.locator('.dt-tab').filter({ hasText: 'Правила' }).click()
    },
    preview: async (page) => {
      await page.locator('#mainTable tbody .sku').first().click()
      await page.locator('.drawer .drawer-tab').filter({ hasText: 'Правила' }).click()
    },
  },
  {
    name: '20-drawer-misc',
    title: 'SKU drawer misc tab',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => {
      await page.locator('#mainTable tbody .sku').first().click()
      await page.locator('.dt-tab').filter({ hasText: 'Прочее' }).click()
    },
    preview: async (page) => {
      await page.locator('#mainTable tbody .sku').first().click()
      await page.locator('.drawer .drawer-tab').filter({ hasText: 'Прочее' }).click()
    },
  },
  {
    name: '21-apply-progress',
    title: 'Apply prices progress modal',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => {
      await page.evaluate(() => {
        if (typeof window.openModal === 'function') window.openModal('applyProgress')
      })
    },
    previewUrl: `${previewUrl}?reviewState=apply-progress`,
  },
  {
    name: '22-toast-undo',
    title: 'Toast with undo action',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => {
      await page.evaluate(() => {
        if (typeof window.showToast === 'function') window.showToast('XLSX будет сформирован по текущим фильтрам', 'info', true)
      })
    },
    previewUrl: `${previewUrl}?reviewState=toast`,
  },
  {
    name: '23-api-error',
    title: 'WB API error state',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => {
      await page.evaluate(() => {
        document.getElementById('mainTable')?.classList.add('is-hidden')
        document.getElementById('apiErrorState')?.classList.add('show')
      })
    },
    previewUrl: `${previewUrl}?reviewState=api-error`,
  },
  {
    name: '24-loading-skeleton',
    title: 'WB API loading state',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => {
      await page.evaluate(() => {
        const tableWrap = document.querySelector('.table-wrap')
        const html = typeof window.dataLoadingStateHTML === 'function'
          ? window.dataLoadingStateHTML({ skeleton: true })
          : '<div class="data-loading-state"><div class="vella-loader"></div><div class="data-loading-copy"><div class="data-loading-title">Загружаем данные WB</div><div class="data-loading-text">Подтягиваем данные из API. Экран обновится автоматически, когда источник ответит.</div></div></div>'
        tableWrap?.insertAdjacentHTML('afterbegin', html)
      })
    },
    previewUrl: `${previewUrl}?reviewState=loading`,
  },
  {
    name: '25-tab-strategies',
    title: 'Strategies tab',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('.subtab').filter({ hasText: 'Стратегии' }).click(),
    preview: async (page) => page.locator('.subtab').filter({ hasText: 'Стратегии' }).click(),
  },
  {
    name: '26-tab-history',
    title: 'History tab',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('.subtab').filter({ hasText: 'История' }).click(),
    preview: async (page) => page.locator('.subtab').filter({ hasText: 'История' }).click(),
  },
  {
    name: '27-tab-liquidation',
    title: 'Liquidation tab',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('.subtab').filter({ hasText: 'Ликвидация' }).click(),
    preview: async (page) => page.locator('.subtab').filter({ hasText: 'Ликвидация' }).click(),
  },
  {
    name: '28-tab-promos',
    title: 'WB promos tab',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('.subtab').filter({ hasText: 'Акции WB' }).click(),
    preview: async (page) => page.locator('.subtab').filter({ hasText: 'Акции WB' }).click(),
  },
  {
    name: '29-tab-rules',
    title: 'Rules tab',
    viewport: { width: 1920, height: 1080 },
    reference: async (page) => page.locator('.subtab').filter({ hasText: 'Правила' }).first().click(),
    preview: async (page) => page.locator('.subtab').filter({ hasText: 'Правила' }).first().click(),
  },
]

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitForHttp(url, timeoutMs = 20_000) {
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
    throw new Error('dist/index.html is missing. Run npm run build first.')
  }

  const child = spawn(
    process.platform === 'win32' ? 'npx.cmd' : 'npx',
    ['vite', 'preview', '--host', '127.0.0.1', '--port', '4176', '--strictPort'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'] },
  )
  child.stdout.on('data', (chunk) => process.stdout.write(chunk))
  child.stderr.on('data', (chunk) => process.stderr.write(chunk))
  return child
}

async function captureState(browser, state) {
  const reference = await browser.newPage({ viewport: state.viewport })
  const preview = await browser.newPage({ viewport: state.viewport })
  const referencePath = path.join(outputRoot, `${state.name}-reference.png`)
  const previewPath = path.join(outputRoot, `${state.name}-preview.png`)

  try {
    await reference.goto(state.referenceUrl || referenceUrl, { waitUntil: 'domcontentloaded' })
    await preview.goto(state.previewUrl || previewUrl, { waitUntil: 'domcontentloaded' })
    await reference.waitForTimeout(700)
    await preview.waitForTimeout(700)

    if (state.reference) await state.reference(reference)
    if (state.preview) await state.preview(preview)
    await reference.waitForTimeout(450)
    await preview.waitForTimeout(450)

    await reference.screenshot({ path: referencePath, fullPage: false })
    await preview.screenshot({ path: previewPath, fullPage: false })

    return {
      ...state,
      referenceFile: path.basename(referencePath),
      previewFile: path.basename(previewPath),
      status: 'captured',
    }
  } catch (error) {
    await reference.screenshot({ path: referencePath, fullPage: false }).catch(() => {})
    await preview.screenshot({ path: previewPath, fullPage: false }).catch(() => {})
    return {
      ...state,
      referenceFile: existsSync(referencePath) ? path.basename(referencePath) : null,
      previewFile: existsSync(previewPath) ? path.basename(previewPath) : null,
      status: 'failed',
      error: error instanceof Error ? error.message : String(error),
    }
  } finally {
    await reference.close()
    await preview.close()
  }
}

function renderIndex(results) {
  const rows = results.map((result) => `
    <section class="state ${result.status === 'failed' ? 'failed' : ''}">
      <header>
        <div>
          <h2>${result.title}</h2>
          <p>${result.name} · ${result.viewport.width}x${result.viewport.height}${result.error ? ` · ERROR: ${result.error}` : ''}</p>
        </div>
      </header>
      <div class="pair">
        <figure>
          <figcaption>HTML source-of-truth</figcaption>
          ${result.referenceFile ? `<img src="./${result.referenceFile}" alt="${result.name} reference">` : '<div class="missing">missing</div>'}
        </figure>
        <figure>
          <figcaption>React preview</figcaption>
          ${result.previewFile ? `<img src="./${result.previewFile}" alt="${result.name} preview">` : '<div class="missing">missing</div>'}
        </figure>
      </div>
    </section>
  `).join('\n')

  return `<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Vella React Review Pack</title>
  <style>
    body { margin: 0; font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f172a; color: #e5e7eb; }
    main { padding: 24px; }
    h1 { margin: 0 0 6px; font-size: 24px; }
    .meta { margin: 0 0 24px; color: #94a3b8; }
    .state { margin-bottom: 28px; border: 1px solid rgba(255,255,255,.12); border-radius: 14px; overflow: hidden; background: rgba(15,23,42,.92); }
    .state.failed { border-color: #ef4444; }
    header { display: flex; justify-content: space-between; gap: 16px; padding: 14px 16px; border-bottom: 1px solid rgba(255,255,255,.12); }
    h2 { margin: 0; font-size: 16px; }
    p { margin: 4px 0 0; color: #94a3b8; font-size: 13px; }
    .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: rgba(255,255,255,.10); }
    figure { margin: 0; background: #111827; min-width: 0; }
    figcaption { padding: 10px 12px; font-size: 12px; color: #cbd5e1; background: rgba(255,255,255,.06); }
    img { display: block; width: 100%; height: auto; }
    .missing { padding: 80px 20px; color: #ef4444; text-align: center; }
  </style>
</head>
<body>
  <main>
    <h1>Vella 1:1 review pack</h1>
    <p class="meta">Reference: ${referenceUrl} · Preview: ${previewUrl} · ${new Date().toISOString()}</p>
    ${rows}
  </main>
</body>
</html>`
}

async function main() {
  let server = null
  if (shouldStartPreview) {
    server = startPreviewServer()
    await waitForHttp(baseUrl)
  }

  await mkdir(outputRoot, { recursive: true })
  const browser = await chromium.launch({ headless: true })

  try {
    const results = []
    for (const state of states) {
      results.push(await captureState(browser, state))
    }

    await writeFile(path.join(outputRoot, 'index.html'), renderIndex(results))
    await writeFile(path.join(outputRoot, 'review-pack.json'), JSON.stringify({ referenceUrl, previewUrl, generatedAt: new Date().toISOString(), results }, null, 2))

    const failed = results.filter((result) => result.status === 'failed')
    console.log(`Review pack: ${outputRoot}`)
    if (failed.length > 0) {
      console.error(`Failed states: ${failed.map((result) => result.name).join(', ')}`)
      process.exitCode = 1
    }
  } finally {
    await browser.close()
    if (server) server.kill()
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
