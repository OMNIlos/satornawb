import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const cwd = process.cwd()
const frontendRoot = existsSync(path.join(cwd, 'package.json')) && existsSync(path.join(cwd, 'src'))
  ? cwd
  : path.join(cwd, 'frontend')
const projectRoot = path.resolve(frontendRoot, '..')
const stamp = new Date().toISOString().replace(/[:.]/g, '-')
const outputRoot = path.resolve(projectRoot, 'outputs', `vella-interaction-parity-${stamp}`)
const baseUrl = process.env.VELLA_BASE_URL || 'http://127.0.0.1:4182'
const shouldStartPreview = !process.env.VELLA_BASE_URL
const viewport = {
  width: Number(process.env.VELLA_PARITY_WIDTH || '1440'),
  height: Number(process.env.VELLA_PARITY_HEIGHT || '900'),
}

const targets = [
  {
    name: 'reference',
    nowPath: '/vella-production.html?tab=digest',
    periodPath: '/vella-production.html?tab=digest&mode=period',
    abcPath: '/vella-production.html?tab=abc',
  },
  {
    name: 'public',
    nowPath: '/wb/reports?tab=digest',
    periodPath: '/wb/reports?tab=digest&mode=period',
    abcPath: '/wb/reports/abc',
  },
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
    throw new Error('frontend/dist is missing. Run npm --prefix frontend run build first.')
  }

  const child = spawn(
    process.platform === 'win32' ? 'npx.cmd' : 'npx',
    ['vite', 'preview', '--host', '127.0.0.1', '--port', '4182', '--strictPort'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'] },
  )
  child.stdout.on('data', (chunk) => process.stdout.write(chunk))
  child.stderr.on('data', (chunk) => process.stderr.write(chunk))
  return child
}

async function stabilize(page) {
  await page.evaluate(() => document.fonts?.ready ?? Promise.resolve()).catch(() => {})
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
        caret-color: transparent !important;
      }
    `,
  })
  await page.waitForTimeout(500)
}

async function gotoParityPage(page, url) {
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 90_000 })
  } catch (error) {
    if (error?.name !== 'TimeoutError') throw error
    await page.goto(url, { waitUntil: 'commit', timeout: 90_000 })
    await page.waitForLoadState('domcontentloaded', { timeout: 15_000 }).catch(() => {})
  }
}

async function expectStep(page, description, assertion) {
  try {
    await assertion()
    return { description, pass: true }
  } catch (error) {
    await page.screenshot({
      path: path.join(outputRoot, `${description.toLowerCase().replace(/[^a-z0-9]+/g, '-')}.png`),
      fullPage: false,
    }).catch(() => {})
    return {
      description,
      pass: false,
      error: error instanceof Error ? error.message : String(error),
    }
  }
}

async function isVisible(page, selector) {
  return page.locator(selector).first().isVisible()
}

async function runNowChecks(page, target) {
  const steps = []
  await gotoParityPage(page, `${baseUrl}${target.nowPath}`)
  await page.waitForSelector('#tab-digest.active')
  await stabilize(page)

  steps.push(await expectStep(page, `${target.name} digest starts in now mode`, async () => {
    const active = await isVisible(page, '.digest-mode-section[data-digest-mode="now"].active')
    if (!active) throw new Error('Expected active now digest section')
  }))

  steps.push(await expectStep(page, `${target.name} opens brand filter`, async () => {
    await page.locator('#digestBrandBtn').click()
    await page.waitForSelector('#digestBrandFilter.open')
  }))

  steps.push(await expectStep(page, `${target.name} selects Anomie brand`, async () => {
    await page.locator('[data-brand-option="anomie"]').click()
    await page.waitForFunction(() => document.getElementById('digestBrandBtn')?.textContent?.includes('Anomie'))
    const label = await page.locator('#digestBrandBtn').innerText()
    if (!label.includes('Anomie')) throw new Error(`Expected Anomie label, got "${label}"`)
  }))

  steps.push(await expectStep(page, `${target.name} renders manager signal cards`, async () => {
    await page.waitForFunction(() => document.querySelectorAll('#digestManagerSignalGrid .manager-signal-card').length >= 4)
    const count = await page.locator('#digestManagerSignalGrid .manager-signal-card').count()
    if (count < 4) throw new Error(`Expected at least 4 manager signal cards, got ${count}`)
  }))

  steps.push(await expectStep(page, `${target.name} opens export dropdown and triggers XLSX toast`, async () => {
    await page.locator('#ddExport > button').click()
    await page.waitForSelector('#ddExport.open')
    await page.locator('#ddExport .dd-item').filter({ hasText: 'Экспорт XLSX' }).click()
    await page.waitForFunction(() => [...document.querySelectorAll('#toastContainer .toast-title')]
      .some((node) => node.textContent?.includes('XLSX будет сформирован')))
  }))

  steps.push(await expectStep(page, `${target.name} switches balance period to 30 days`, async () => {
    await page.locator('[data-digest-balance-period="thirty"]').click()
    await page.waitForFunction(() => document.querySelector('[data-digest-balance-period="thirty"]')?.classList.contains('active'))
    const ariaSelected = await page.locator('[data-digest-balance-period="thirty"]').getAttribute('aria-selected')
    if (ariaSelected !== 'true') throw new Error(`Expected aria-selected=true, got "${ariaSelected}"`)
  }))

  steps.push(await expectStep(page, `${target.name} critical action opens ABC tab`, async () => {
    await page.locator('.monitor-rec-link').filter({ hasText: 'Открыть ABC' }).click()
    await page.waitForSelector('#tab-abc.active')
    const activeTabExists = await page.locator('.subtab.active[data-tab="abc"], .nav-sub.active[data-tab="abc"]').count()
    if (!activeTabExists) throw new Error('Expected ABC tab navigation to become active')
  }))

  return steps
}

async function runPeriodChecks(page, target) {
  const steps = []
  await gotoParityPage(page, `${baseUrl}${target.periodPath}`)
  await page.waitForSelector('#tab-digest.active')
  await stabilize(page)

  steps.push(await expectStep(page, `${target.name} digest starts in period mode`, async () => {
    const active = await isVisible(page, '.digest-mode-section[data-digest-mode="period"].active')
    if (!active) throw new Error('Expected active period digest section')
  }))

  steps.push(await expectStep(page, `${target.name} renders plan fact rows`, async () => {
    await page.waitForFunction(() => document.querySelectorAll('#digestPlanFactGrid .planfact-card').length > 0)
    const count = await page.locator('#digestPlanFactGrid .planfact-card').count()
    if (count < 4) throw new Error(`Expected at least 4 plan-fact cards, got ${count}`)
  }))

  steps.push(await expectStep(page, `${target.name} switches global period to 14 days`, async () => {
    await page.locator('#globalPeriod .period-btn[data-period="14"]').click()
    await page.waitForFunction(() => document.querySelector('#globalPeriod .period-btn[data-period="14"]')?.classList.contains('active'))
  }))

  return steps
}

async function runAbcChecks(page, target) {
  const steps = []
  await gotoParityPage(page, `${baseUrl}${target.abcPath}`)
  await page.waitForSelector('#tab-abc.active')
  await stabilize(page)

  steps.push(await expectStep(page, `${target.name} abc opens from route`, async () => {
    const active = await isVisible(page, '#tab-abc.active')
    if (!active) throw new Error('Expected active ABC tab')
  }))

  steps.push(await expectStep(page, `${target.name} abc filtered summary is populated`, async () => {
    await page.waitForFunction(() => document.getElementById('abcFilteredSkuCount')?.textContent?.trim() !== '—')
    const skuCount = await page.locator('#abcFilteredSkuCount').innerText()
    const orders = await page.locator('#abcFilteredOrders').innerText()
    const profit = await page.locator('#abcFilteredProfit').innerText()
    if (!skuCount || skuCount === '—') throw new Error(`Expected SKU count, got "${skuCount}"`)
    if (!orders.includes('/')) throw new Error(`Expected order count and rub summary, got "${orders}"`)
    if (!profit.includes('₽')) throw new Error(`Expected profit rub summary, got "${profit}"`)
  }))

  steps.push(await expectStep(page, `${target.name} abc source states render`, async () => {
    if (target.name === 'candidate') {
      const kpiStrip = await page.locator('#tab-abc > .stats[data-vella-island="abc-kpi-strip"][data-vella-island-status="explicit-jsx"]').count()
      if (kpiStrip !== 1) throw new Error(`Expected one explicit React ABC KPI strip, got ${kpiStrip}`)
    }
    const statCount = await page.locator('#tab-abc > .stats .stat').count()
    if (statCount !== 4) throw new Error(`Expected 4 ABC KPI stats, got ${statCount}`)
    const statsText = await page.locator('#tab-abc > .stats').innerText()
    for (const label of ['Продажи / чистая', 'Чистая прибыль', 'Корзины / заказы', 'SKU ниже порогов']) {
      if (!statsText.includes(label)) throw new Error(`Expected KPI label "${label}" in ABC stats`)
    }
    const cards = page.locator('#tab-abc .report-source-strip .source-state-card')
    const cardCount = await cards.count()
    if (cardCount !== 1) throw new Error(`Expected one compact ABC source-state card, got ${cardCount}`)
    const stripText = (await page.locator('#tab-abc .report-source-strip').innerText()).toLowerCase()
    for (const label of ['ABC-данные', 'WB-02', 'WB-23']) {
      if (!stripText.includes(label.toLowerCase())) throw new Error(`Expected source label "${label}" in ABC source strip`)
    }
  }))

  steps.push(await expectStep(page, `${target.name} abc chip filter updates summary`, async () => {
    if (target.name === 'candidate') {
      const reactToolbar = await page.locator('#tab-abc .toolbar[data-vella-event-owner="react"]').count()
      if (reactToolbar !== 1) throw new Error(`Expected React-owned ABC toolbar events, got ${reactToolbar}`)
      const reactChips = await page.locator('#tab-abc .toolbar .chips .chip[data-abc-bound="1"][data-vella-react-handlers="onclick"]').count()
      if (reactChips !== 6) throw new Error(`Expected 6 React-bound ABC chips, got ${reactChips}`)
      const reactSearch = await page.locator('#tab-abc .toolbar .search input[data-vella-react-handlers="oninput"]').count()
      if (reactSearch !== 1) throw new Error(`Expected React-bound ABC search input, got ${reactSearch}`)
      const reactActions = await page.locator('#tab-abc .toolbar .toolbar-right button[data-vella-react-handlers="onclick"][data-vella-action-owner^="react-"]').count()
      if (reactActions !== 2) throw new Error(`Expected 2 React-owned ABC toolbar actions, got ${reactActions}`)
    }
    await page.locator('#tab-abc .chips .chip', { hasText: 'Новинки' }).click()
    await page.waitForFunction(() => document.getElementById('abcFilteredTitle')?.textContent?.includes('Новинки'))
    const activeChip = await page.locator('#tab-abc .chips .chip.active').innerText()
    const title = await page.locator('#abcFilteredTitle').innerText()
    if (activeChip.trim() !== 'Новинки') throw new Error(`Expected active Новинки chip, got "${activeChip}"`)
    if (!title.includes('Новинки')) throw new Error(`Expected Новинки summary title, got "${title}"`)
    if (target.name === 'candidate') {
      const visibleRows = await page.locator('#tab-abc table.report-wide tbody tr').evaluateAll((rows) => rows
        .filter((row) => getComputedStyle(row).display !== 'none').length)
      const summarySkuCount = Number((await page.locator('#abcFilteredSkuCount').innerText()).replace(/\D/g, ''))
      if (summarySkuCount !== visibleRows) throw new Error(`Expected React ABC summary SKU count ${visibleRows}, got ${summarySkuCount}`)
    }
  }))

  steps.push(await expectStep(page, `${target.name} abc search updates summary`, async () => {
    await page.locator('#tab-abc .chips .chip', { hasText: 'Все SKU' }).click()
    await page.locator('#tab-abc .search input').fill('HCBT_17')
    await page.waitForFunction(() => document.getElementById('abcFilteredTitle')?.textContent?.toLowerCase().includes('hcbt_17'))
    const visibleRows = await page.locator('#tab-abc table.report-wide tbody tr').evaluateAll((rows) => rows
      .filter((row) => getComputedStyle(row).display !== 'none').length)
    const summarySkuCount = Number((await page.locator('#abcFilteredSkuCount').innerText()).replace(/\D/g, ''))
    if (visibleRows !== 1) throw new Error(`Expected search to leave 1 visible row, got ${visibleRows}`)
    if (summarySkuCount !== visibleRows) throw new Error(`Expected search summary SKU count ${visibleRows}, got ${summarySkuCount}`)
    await page.locator('#tab-abc .search input').fill('')
    await page.waitForFunction(() => document.getElementById('abcFilteredTitle')?.textContent?.includes('все SKU'))
  }))

  steps.push(await expectStep(page, `${target.name} abc toolbar right actions work`, async () => {
    const columnsButton = page.locator('#tab-abc .toolbar .toolbar-right button', { hasText: 'Колонки' })
    const exportButton = page.locator('#tab-abc .toolbar .toolbar-right button', { hasText: 'Экспорт XLSX' })
    if (target.name === 'candidate') {
      const columnsOwner = await columnsButton.getAttribute('data-vella-action-owner')
      const exportOwner = await exportButton.getAttribute('data-vella-action-owner')
      if (columnsOwner !== 'react-columns') throw new Error(`Expected React columns owner, got "${columnsOwner}"`)
      if (exportOwner !== 'react-export') throw new Error(`Expected React export owner, got "${exportOwner}"`)
    }
    await columnsButton.click()
    await page.waitForSelector('#reportColumnsPopover.open')
    const columnRows = await page.locator('#reportColumnsPopover .report-columns-row').count()
    if (columnRows < 5) throw new Error(`Expected ABC columns popover rows, got ${columnRows}`)
    await columnsButton.click()
    await page.waitForFunction(() => !document.getElementById('reportColumnsPopover')?.classList.contains('open'))
    const toastCountBefore = await page.locator('#toastContainer .toast-title', { hasText: 'XLSX будет сформирован' }).count()
    await exportButton.click()
    await page.waitForFunction((countBefore) => [...document.querySelectorAll('#toastContainer .toast-title')]
      .filter((node) => node.textContent?.includes('XLSX будет сформирован')).length > countBefore, toastCountBefore)
  }))

  steps.push(await expectStep(page, `${target.name} abc help opens`, async () => {
    if (target.name === 'candidate') {
      const helpMarker = await page.locator('#helpModal[data-vella-island="help-modal"][data-vella-island-status="explicit-jsx"]').count()
      if (helpMarker !== 1) throw new Error(`Expected one React-owned help modal, got ${helpMarker}`)
    }
    await page.locator('#tab-abc .abc-help-row > button', { hasText: 'Как читать?' }).click()
    await page.waitForSelector('#helpModal', { state: 'visible' })
    const title = await page.locator('#helpModalTitle').innerText()
    if (!title.includes('ABC')) throw new Error(`Expected ABC help title, got "${title}"`)
    await page.keyboard.press('Escape')
    await page.waitForSelector('#helpModal', { state: 'hidden' })
  }))

  steps.push(await expectStep(page, `${target.name} abc profit status panel renders`, async () => {
    const cards = page.locator('#tab-abc .profit-status-card')
    const cardCount = await cards.count()
    if (cardCount !== 5) throw new Error(`Expected 5 profit status cards, got ${cardCount}`)
    const panelText = await page.locator('#tab-abc .profit-status-grid').innerText()
    for (const label of ['Локомотивы', 'Новинки', 'Средний', 'Неликвид', 'Ликвидация']) {
      if (!panelText.includes(label)) throw new Error(`Expected status "${label}" in profit panel`)
    }
  }))

  steps.push(await expectStep(page, `${target.name} abc table header is sortable`, async () => {
    const headers = page.locator('#tab-abc table.report-wide thead th')
    const headerCount = await headers.count()
    if (headerCount !== 24) throw new Error(`Expected 24 ABC table headers, got ${headerCount}`)
    const firstHeader = await headers.first().innerText()
    const lastHeader = await headers.last().innerText()
    if (!firstHeader.toLowerCase().includes('позиция')) throw new Error(`Expected first header Позиция, got "${firstHeader}"`)
    if (!lastHeader.toLowerCase().includes('комментарий')) throw new Error(`Expected last header Комментарий, got "${lastHeader}"`)
    if (target.name === 'candidate') {
      const hiddenSortArrows = await page.locator('#tab-abc table.report-wide thead .sort-arrow[aria-hidden="true"]').count()
      if (hiddenSortArrows !== 24) throw new Error(`Expected 24 aria-hidden sort arrows, got ${hiddenSortArrows}`)
      const explicitSortKeys = await page.locator('#tab-abc table.report-wide thead th[data-sort-key][data-vella-ux-delta~="explicit-abc-sort-key"]').count()
      if (explicitSortKeys !== 24) throw new Error(`Expected 24 explicit ABC sort keys, got ${explicitSortKeys}`)
      const ordersSortKey = await page.locator('#tab-abc table.report-wide thead th', { hasText: 'Заказы' }).getAttribute('data-sort-key')
      if (ordersSortKey !== 'orders') throw new Error(`Expected Заказы data-sort-key=orders, got "${ordersSortKey}"`)
    }
    await page.locator('#tab-abc table.report-wide thead th', { hasText: 'Заказы' }).click()
    await page.waitForFunction(() => document.querySelector('#tab-abc table.report-wide thead th.sorted')?.textContent?.includes('Заказы'))
    const sortedHeader = await page.locator('#tab-abc table.report-wide thead th.sorted').innerText()
    if (!sortedHeader.toLowerCase().includes('заказы')) throw new Error(`Expected sorted Заказы header, got "${sortedHeader}"`)
    if (target.name === 'candidate') {
      const visibleOrderValues = await page.locator('#tab-abc table.report-wide tbody tr').evaluateAll((rows) => rows
        .filter((row) => getComputedStyle(row).display !== 'none')
        .map((row) => Number((row.children[14]?.textContent || '').split('/')[0].replace(/[^\d,.\-−]/g, '').replace('−', '-').replace(',', '.')))
        .filter((value) => Number.isFinite(value)))
      const sortedDescending = visibleOrderValues.every((value, index, values) => index === 0 || values[index - 1] >= value)
      if (!sortedDescending) throw new Error(`Expected candidate Заказы sort to order visible rows descending, got ${visibleOrderValues.join(', ')}`)
    }
  }))

  steps.push(await expectStep(page, `${target.name} abc table renders rows`, async () => {
    if (target.name === 'candidate') {
      const tableShell = await page.locator('#tab-abc > .report-table-wrap[data-vella-island="abc-table-shell"][data-vella-island-status="explicit-jsx"] > table.report-wide').count()
      if (tableShell !== 1) throw new Error(`Expected one explicit React ABC table shell, got ${tableShell}`)
      const tbodyMarker = await page.locator('#tab-abc table.report-wide tbody[data-vella-island="abc-table-body"][data-vella-island-status="explicit-jsx"]').count()
      if (tbodyMarker !== 1) throw new Error(`Expected one React-owned ABC tbody boundary, got ${tbodyMarker}`)
      const rowMarkerCount = await page.locator('#tab-abc table.report-wide tbody tr[data-vella-island="abc-table-row"][data-vella-island-status="react-row-renderer"]').count()
      if (rowMarkerCount < 3) throw new Error(`Expected React-rendered ABC row markers, got ${rowMarkerCount}`)
      const filterOwnerRows = await page.locator('#tab-abc table.report-wide tbody tr[data-vella-filter-owner="react"][data-orders-count][data-orders-rub][data-profit-rub][data-ads-rub]').count()
      if (filterOwnerRows < 3) throw new Error(`Expected React filter-owner ABC row metrics, got ${filterOwnerRows}`)
      const productCells = await page.locator('#tab-abc table.report-wide tbody [data-vella-cell="abc-product-cell"][data-vella-cell-status="react-row-cell"]').count()
      const commentCells = await page.locator('#tab-abc table.report-wide tbody [data-vella-cell="abc-comment-cell"][data-vella-cell-status="react-row-cell"]').count()
      if (productCells < 3) throw new Error(`Expected React product cell markers, got ${productCells}`)
      if (commentCells < 3) throw new Error(`Expected React comment cell markers, got ${commentCells}`)
      for (const cellName of ['abc-status-cell', 'abc-action-cell', 'abc-manager-cell', 'abc-margin-cell', 'abc-orders-cell', 'abc-net-cell', 'abc-warehouse-cell']) {
        const markerCount = await page.locator(`#tab-abc table.report-wide tbody [data-vella-cell="${cellName}"][data-vella-cell-status="react-row-cell"]`).count()
        if (markerCount < 3) throw new Error(`Expected React ${cellName} markers, got ${markerCount}`)
      }
    }
    const rowCount = await page.locator('#tab-abc table.report-wide tbody tr').count()
    if (rowCount < 3) throw new Error(`Expected ABC table rows, got ${rowCount}`)
    const firstRowText = await page.locator('#tab-abc table.report-wide tbody tr').first().innerText()
    if (!firstRowText.includes('₽')) throw new Error(`Expected populated ABC row with rub values, got "${firstRowText}"`)
  }))

  steps.push(await expectStep(page, `${target.name} abc visible row opens sku drawer`, async () => {
    if (target.name === 'candidate') {
      const overlayMarker = await page.locator('#dOverlay[data-vella-island="product-drawer-overlay"][data-vella-island-status="explicit-jsx"]').count()
      if (overlayMarker !== 1) throw new Error(`Expected one React-owned SKU drawer overlay, got ${overlayMarker}`)
      const panelMarker = await page.locator('#dPanel[data-vella-island="product-drawer-panel"][data-vella-island-status="explicit-jsx"]').count()
      if (panelMarker !== 1) throw new Error(`Expected one React-owned SKU drawer panel, got ${panelMarker}`)
      const headerMarker = await page.locator('#dPanel [data-vella-island="product-drawer-header"][data-vella-island-status="explicit-jsx"]').count()
      if (headerMarker !== 1) throw new Error(`Expected one React-owned SKU drawer header, got ${headerMarker}`)
      const tabsMarker = await page.locator('#dPanel [data-vella-island="product-drawer-tabs"][data-vella-island-status="explicit-jsx"]').count()
      if (tabsMarker !== 1) throw new Error(`Expected one React-owned SKU drawer tabs block, got ${tabsMarker}`)
      const bodyMarker = await page.locator('#dPanel [data-vella-island="product-drawer-body"][data-vella-island-status="explicit-jsx"]').count()
      if (bodyMarker !== 1) throw new Error(`Expected one React-owned SKU drawer body, got ${bodyMarker}`)
      for (const tabName of ['overview', 'algo', 'comments', 'misc']) {
        const tabMarker = await page.locator(`#dPanel [data-vella-island="product-drawer-tab-${tabName}"][data-vella-island-status="explicit-jsx"]`).count()
        if (tabMarker !== 1) throw new Error(`Expected one React-owned SKU drawer ${tabName} tab content, got ${tabMarker}`)
      }
      const overviewPriceMarker = await page.locator('#dPanel [data-vella-island="product-drawer-overview-price"][data-vella-island-status="explicit-jsx"]').count()
      if (overviewPriceMarker !== 1) throw new Error(`Expected one explicit React SKU drawer overview price block, got ${overviewPriceMarker}`)
      const overviewIdentityMarker = await page.locator('#dPanel [data-vella-island="product-drawer-overview-identity"][data-vella-island-status="explicit-jsx"]').count()
      if (overviewIdentityMarker !== 1) throw new Error(`Expected one explicit React SKU drawer overview identity row, got ${overviewIdentityMarker}`)
      const overviewMarginMarker = await page.locator('#dPanel [data-vella-island="product-drawer-overview-margin"][data-vella-island-status="explicit-jsx"]').count()
      if (overviewMarginMarker !== 1) throw new Error(`Expected one explicit React SKU drawer overview margin section, got ${overviewMarginMarker}`)
      const overviewDemandMarker = await page.locator('#dPanel [data-vella-island="product-drawer-overview-demand"][data-vella-island-status="explicit-jsx"]').count()
      if (overviewDemandMarker !== 1) throw new Error(`Expected one explicit React SKU drawer overview demand section, got ${overviewDemandMarker}`)
      const overviewStockMarker = await page.locator('#dPanel [data-vella-island="product-drawer-overview-stock"][data-vella-island-status="explicit-jsx"]').count()
      if (overviewStockMarker !== 1) throw new Error(`Expected one explicit React SKU drawer overview stock section, got ${overviewStockMarker}`)
      const overviewCalculatorMarker = await page.locator('#dPanel [data-vella-island="product-drawer-overview-calculator"][data-vella-island-status="explicit-jsx"]').count()
      if (overviewCalculatorMarker !== 1) throw new Error(`Expected one explicit React SKU drawer overview calculator section, got ${overviewCalculatorMarker}`)
      const overviewMarginAnalysisMarker = await page.locator('#dPanel [data-vella-island="product-drawer-overview-margin-analysis"][data-vella-island-status="explicit-jsx"]').count()
      if (overviewMarginAnalysisMarker !== 1) throw new Error(`Expected one explicit React SKU drawer overview margin analysis section, got ${overviewMarginAnalysisMarker}`)
      const overviewBasketChartMarker = await page.locator('#dPanel [data-vella-island="product-drawer-overview-basket-chart"][data-vella-island-status="explicit-jsx"]').count()
      if (overviewBasketChartMarker !== 1) throw new Error(`Expected one explicit React SKU drawer basket chart, got ${overviewBasketChartMarker}`)
      const overviewPriceChartMarker = await page.locator('#dPanel [data-vella-island="product-drawer-overview-price-chart"][data-vella-island-status="explicit-jsx"]').count()
      if (overviewPriceChartMarker !== 1) throw new Error(`Expected one explicit React SKU drawer price chart, got ${overviewPriceChartMarker}`)
      const overviewImpactMarker = await page.locator('#dPanel [data-vella-island="product-drawer-overview-impact"][data-vella-island-status="explicit-jsx"]').count()
      if (overviewImpactMarker !== 1) throw new Error(`Expected one explicit React SKU drawer impact section, got ${overviewImpactMarker}`)
      const overviewPriceHistoryMarker = await page.locator('#dPanel [data-vella-island="product-drawer-overview-price-history"][data-vella-island-status="explicit-jsx"]').count()
      if (overviewPriceHistoryMarker !== 1) throw new Error(`Expected one explicit React SKU drawer price history section, got ${overviewPriceHistoryMarker}`)
      const algoDecisionMarker = await page.locator('#dPanel [data-vella-island="product-drawer-algo-decision"][data-vella-island-status="explicit-jsx"]').count()
      if (algoDecisionMarker !== 1) throw new Error(`Expected one explicit React SKU drawer algo decision section, got ${algoDecisionMarker}`)
      const algoStrategyMarker = await page.locator('#dPanel [data-vella-island="product-drawer-algo-strategy"][data-vella-island-status="explicit-jsx"]').count()
      if (algoStrategyMarker !== 1) throw new Error(`Expected one explicit React SKU drawer algo strategy section, got ${algoStrategyMarker}`)
      const algoOverrideMarker = await page.locator('#dPanel [data-vella-island="product-drawer-algo-override"][data-vella-island-status="explicit-jsx"]').count()
      if (algoOverrideMarker !== 1) throw new Error(`Expected one explicit React SKU drawer algo override section, got ${algoOverrideMarker}`)
      const algoCogsMarker = await page.locator('#dPanel [data-vella-island="product-drawer-algo-cogs"][data-vella-island-status="explicit-jsx"]').count()
      if (algoCogsMarker !== 1) throw new Error(`Expected one explicit React SKU drawer algo cogs section, got ${algoCogsMarker}`)
      const algoPromoMarker = await page.locator('#dPanel [data-vella-island="product-drawer-algo-promo-boost"][data-vella-island-status="explicit-jsx"]').count()
      if (algoPromoMarker !== 1) throw new Error(`Expected one explicit React SKU drawer promo boost section, got ${algoPromoMarker}`)
      const commentsMarker = await page.locator('#dPanel [data-vella-island="product-drawer-comments"][data-vella-island-status="explicit-jsx"]').count()
      if (commentsMarker !== 1) throw new Error(`Expected one explicit React SKU drawer comments section, got ${commentsMarker}`)
      const miscMarker = await page.locator('#dPanel [data-vella-island="product-drawer-misc"][data-vella-island-status="explicit-jsx"]').count()
      if (miscMarker !== 1) throw new Error(`Expected one explicit React SKU drawer misc section, got ${miscMarker}`)
    }
    await page.evaluate(() => {
      const visibleRow = [...document.querySelectorAll('#tab-abc table.report-wide tbody tr')]
        .find((row) => getComputedStyle(row).display !== 'none')
      visibleRow?.querySelector('[data-report-open-sku]')?.click()
    })
    await page.waitForSelector('#dPanel.open')
    const drawerSku = await page.locator('#dPanel .drawer-sku').innerText()
    if (!drawerSku.trim()) throw new Error('Expected drawer SKU after opening visible ABC row')
    const drawerPrice = await page.locator('#dPanel #dPrice').innerText()
    if (!drawerPrice.includes('₽')) throw new Error(`Expected drawer price after opening visible ABC row, got "${drawerPrice}"`)
    const drawerNmId = await page.locator('#dPanel #dHdrNmId').innerText()
    if (!drawerNmId.trim()) throw new Error('Expected drawer NM id in overview identity row')
    const drawerMargin = await page.locator('#dPanel #dMg').innerText()
    if (!drawerMargin.trim()) throw new Error('Expected drawer margin in overview margin section')
    const drawerStrategy = await page.locator('#dPanel #dTplCell').innerText()
    if (!drawerStrategy.trim()) throw new Error('Expected drawer strategy in overview margin section')
    const drawerBaskets = await page.locator('#dPanel #dBsk').innerText()
    if (!drawerBaskets.trim()) throw new Error('Expected drawer baskets in overview demand section')
    const drawerStock = await page.locator('#dPanel #dStock').innerText()
    if (!drawerStock.trim()) throw new Error('Expected drawer stock in overview stock section')
    const drawerPriceInput = await page.locator('#dPanel #dPriceInput').inputValue()
    if (!drawerPriceInput.trim()) throw new Error('Expected drawer calculator price input value')
    const drawerFinalPrice = await page.locator('#dPanel #dPriceFinal').innerText()
    if (!drawerFinalPrice.includes('₽')) throw new Error(`Expected drawer final price in calculator section, got "${drawerFinalPrice}"`)
    await page.locator('#dPanel #detailCalcToggle').click()
    await page.waitForSelector('#dPanel #detailCalcBody.open')
    const detailRows = await page.locator('#dPanel #detailCalcTbody tr').count()
    if (detailRows < 1) throw new Error(`Expected detail calculator rows after toggle, got ${detailRows}`)
    const marginDiscount = await page.locator('#dPanel #dMarginDiscInput').inputValue()
    if (!marginDiscount.trim()) throw new Error('Expected margin analysis discount input value')
    const marginAnalysisText = await page.locator('#dPanel #dMarginAnalysisCard').innerText()
    if (!marginAnalysisText.trim()) throw new Error('Expected margin analysis card text after opening drawer')
    const chartTitles = await page.locator('#dPanel .chart-card .chart-title').evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim()))
    for (const expectedTitle of ['Корзины за период', 'Цена за 30 дней']) {
      if (!chartTitles.includes(expectedTitle)) throw new Error(`Expected drawer chart title "${expectedTitle}", got ${chartTitles.join(', ')}`)
    }
    const impactLabels = await page.locator('#dPanel .impact-grid .impact-label').evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim()))
    for (const expectedLabel of ['Корзины, 24 ч', 'Заказы, 48 ч', 'Маржа, 72 ч']) {
      if (!impactLabels.includes(expectedLabel)) throw new Error(`Expected impact label "${expectedLabel}", got ${impactLabels.join(', ')}`)
    }
    const historyTitle = await page.locator('#dPanel .d-section:has(.history-list) .d-section-title').evaluate((node) => node.textContent?.trim() || '')
    if (historyTitle.trim() !== 'История цены (14 дней)') throw new Error(`Expected drawer price history title, got "${historyTitle}"`)
    const historyRows = await page.locator('#dPanel .history-list .history-row').count()
    if (historyRows !== 8) throw new Error(`Expected 8 drawer price history rows, got ${historyRows}`)
    const pMinRows = await page.locator('#dPanel .d-section:has(.history-list) > div:last-child .history-row').count()
    if (pMinRows !== 2) throw new Error(`Expected 2 drawer P_MIN history rows, got ${pMinRows}`)
    await page.locator('#dPanel .dt-tab[data-dtab="algo"]').click()
    await page.waitForSelector('#dPanel #dr-algo.active')
    const algoDecisionTitle = await page.locator('#dPanel #dr-algo .d-section:has(.explain-card) .d-section-title').evaluate((node) => node.textContent?.trim() || '')
    if (algoDecisionTitle !== 'Почему алгоритм принял решение') throw new Error(`Expected drawer algo decision title, got "${algoDecisionTitle}"`)
    const explainCells = await page.locator('#dPanel #dr-algo .explain-grid > div').count()
    if (explainCells !== 4) throw new Error(`Expected 4 drawer algo explain cells, got ${explainCells}`)
    const decisionRows = await page.locator('#dPanel #dr-algo .decision-list .decision-item').count()
    if (decisionRows !== 4) throw new Error(`Expected 4 drawer algo decision rows, got ${decisionRows}`)
    const strategyTitle = await page.locator('#dPanel #dr-algo .d-section:has(.tpl-color-dot) .d-section-title').evaluate((node) => node.textContent?.trim() || '')
    if (strategyTitle !== 'Применённая стратегия') throw new Error(`Expected drawer algo strategy title, got "${strategyTitle}"`)
    const strategyText = await page.locator('#dPanel #dr-algo .d-section:has(.tpl-color-dot)').innerText()
    for (const expectedText of ['Агрессивный', 'Маржа 20%', 'Сменить']) {
      if (!strategyText.includes(expectedText)) throw new Error(`Expected drawer algo strategy text "${expectedText}", got "${strategyText}"`)
    }
    const overrideTitle = await page.locator('#dPanel #dr-algo .d-section:has(#drawerPminBeforeInput) .d-section-title').evaluate((node) => node.textContent?.trim() || '')
    if (!overrideTitle.startsWith('Override для этого SKU')) throw new Error(`Expected drawer algo override title, got "${overrideTitle}"`)
    const pminBefore = await page.locator('#dPanel #drawerPminBeforeInput').inputValue()
    const pmaxBefore = await page.locator('#dPanel #drawerPmaxBeforeInput').inputValue()
    const pminAfter = await page.locator('#dPanel #drawerPminAfterInput').inputValue()
    if (!pminBefore.trim() || !pmaxBefore.trim() || !pminAfter.trim()) throw new Error('Expected drawer price bound inputs to be populated')
    const inheritedStepDisabled = await page.locator('#dPanel #dr-algo .d-section:has(#drawerPminBeforeInput) .s-row:has-text("Шаг изменения") input.s-input').isDisabled()
    if (!inheritedStepDisabled) throw new Error('Expected inherited step input to stay disabled')
    const stepSelectDisabled = await page.locator('#dPanel #dr-algo .d-section:has(#drawerPminBeforeInput) select.s-select').isDisabled()
    if (!stepSelectDisabled) throw new Error('Expected step time select to stay disabled')
    const nightMedianChecked = await page.locator('#dPanel #dr-algo .d-section:has(#drawerPminBeforeInput) .s-row:has-text("Ночная медиана") input[type="checkbox"]').isChecked()
    if (!nightMedianChecked) throw new Error('Expected night median override toggle to stay checked')
    await page.locator('#dPanel #priceBasisAfterBtn').click()
    const afterBasisActive = await page.locator('#dPanel #priceBasisAfterBtn.active').count()
    if (afterBasisActive !== 1) throw new Error('Expected after-SPP price basis button to become active')
    const afterInputReadonly = await page.locator('#dPanel #drawerPminAfterInput').evaluate((node) => node.readOnly)
    if (afterInputReadonly) throw new Error('Expected after-SPP P_min input to become editable after switching basis')
    await page.locator('#dPanel #priceBasisBeforeBtn').click()
    const beforeBasisActive = await page.locator('#dPanel #priceBasisBeforeBtn.active').count()
    if (beforeBasisActive !== 1) throw new Error('Expected before-SPP price basis button to become active again')
    const cogsRows = await page.locator('#dPanel #dr-algo .d-section:has(.d-row .mg-high) .d-row').count()
    if (cogsRows !== 7) throw new Error(`Expected 7 drawer cogs rows, got ${cogsRows}`)
    const cogsText = await page.locator('#dPanel #dr-algo .d-section:has(.d-row .mg-high)').innerText()
    for (const expectedText of ['Итого себестоимость', '467 ₽', 'Маржа в ₽', '+255 ₽']) {
      if (!cogsText.includes(expectedText)) throw new Error(`Expected drawer cogs text "${expectedText}", got "${cogsText}"`)
    }
    const promoTitle = await page.locator('#dPanel #dr-algo .d-section:has(#dPromoBoost) .d-section-title').evaluate((node) => node.textContent?.trim() || '')
    if (!promoTitle.startsWith('Стратегия акций WB')) throw new Error(`Expected drawer promo boost title, got "${promoTitle}"`)
    const promoFieldsInitial = await page.locator('#dPanel #dPromoBoostFields').evaluate((node) => getComputedStyle(node).display)
    await page.locator('#dPanel .d-section:has(#dPromoBoost) label.toggle').click()
    const promoFieldsAfterToggle = await page.locator('#dPanel #dPromoBoostFields').evaluate((node) => getComputedStyle(node).display)
    if (promoFieldsInitial === promoFieldsAfterToggle) throw new Error(`Expected promo boost fields display to change after toggle, stayed "${promoFieldsAfterToggle}"`)
    const promoPct = await page.locator('#dPanel #dPromoBoostPct').inputValue()
    const promoHours = await page.locator('#dPanel #dPromoBoostHours').inputValue()
    if (!promoPct.trim() || !promoHours.trim()) throw new Error('Expected promo boost fields to stay populated')
    await page.locator('#dPanel .dt-tab[data-dtab="comments"]').click()
    await page.waitForSelector('#dPanel #dr-comments.active')
    const commentsTitle = await page.locator('#dPanel #dr-comments .d-section:has(#drawerCommentList) .d-section-title').evaluate((node) => node.textContent?.trim() || '')
    if (commentsTitle !== 'История комментариев') throw new Error(`Expected drawer comments title, got "${commentsTitle}"`)
    const drawerCommentInput = page.locator('#dPanel #drawerCommentInput')
    const drawerCommentPlaceholder = await drawerCommentInput.getAttribute('placeholder')
    if (drawerCommentPlaceholder !== 'Добавить комментарий менеджера...') throw new Error(`Expected drawer comment placeholder, got "${drawerCommentPlaceholder}"`)
    await drawerCommentInput.fill('Smoke drawer comment')
    await page.locator('#dPanel #dr-comments .report-comment-form .btn-primary').click()
    await page.waitForFunction(() => document.querySelector('#dPanel #drawerCommentList')?.textContent?.includes('Smoke drawer comment'))
    const drawerCommentValue = await drawerCommentInput.inputValue()
    if (drawerCommentValue.trim()) throw new Error('Expected drawer comment input to clear after add')
    await page.locator('#dPanel .dt-tab[data-dtab="misc"]').click()
    await page.waitForSelector('#dPanel #dr-misc.active')
    const miscButtons = await page.locator('#dPanel #miscSubtabs .misc-stab').evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim()))
    for (const expectedButton of ['Заказы', 'Логи']) {
      if (!miscButtons.includes(expectedButton)) throw new Error(`Expected drawer misc button "${expectedButton}", got ${miscButtons.join(', ')}`)
    }
    const ordersDashboardText = await page.locator('#dPanel #ordersDashboard').innerText()
    if (!ordersDashboardText.trim()) throw new Error('Expected orders dashboard content in drawer misc tab')
    await page.locator('#dPanel #miscSubtabs .misc-stab[data-stab="logs"]').click()
    await page.waitForSelector('#dPanel #mst-logs.active')
    const logsButtonActive = await page.locator('#dPanel #miscSubtabs .misc-stab.active[data-stab="logs"]').count()
    if (logsButtonActive !== 1) throw new Error('Expected drawer misc logs subtab to become active')
    const auditDashboardText = await page.locator('#dPanel #auditLogDashboard').innerText()
    if (!auditDashboardText.trim()) throw new Error('Expected audit log dashboard content in drawer misc tab')
    await page.locator('#dPanel #miscSubtabs .misc-stab[data-stab="orders"]').click()
    await page.waitForSelector('#dPanel #mst-orders.active')
    await page.locator('#dPanel .dt-tab[data-dtab="overview"]').click()
    await page.waitForSelector('#dPanel #dr-overview.active')
    await page.evaluate(() => window.closeDrawer?.())
    await page.waitForSelector('#dPanel.open', { state: 'detached', timeout: 500 }).catch(async () => {
      const stillOpen = await page.locator('#dPanel.open').count()
      if (stillOpen) throw new Error('Expected SKU drawer to close')
    })
  }))

  steps.push(await expectStep(page, `${target.name} abc visible row opens comment drawer`, async () => {
    if (target.name === 'candidate') {
      const overlayMarker = await page.locator('#reportCommentOverlay[data-vella-island="report-comment-overlay"][data-vella-island-status="explicit-jsx"]').count()
      const drawerMarker = await page.locator('#reportCommentDrawer[data-vella-island="report-comment-drawer"][data-vella-island-status="explicit-jsx"]').count()
      if (overlayMarker !== 1) throw new Error(`Expected one React-owned comment overlay, got ${overlayMarker}`)
      if (drawerMarker !== 1) throw new Error(`Expected one React-owned comment drawer, got ${drawerMarker}`)
    }
    await page.evaluate(() => {
      const visibleRow = [...document.querySelectorAll('#tab-abc table.report-wide tbody tr')]
        .find((row) => getComputedStyle(row).display !== 'none')
      visibleRow?.querySelector('.report-comment-btn')?.click()
    })
    await page.waitForSelector('#reportCommentDrawer.open')
    const commentSku = await page.locator('#reportCommentSku').innerText()
    const commentSource = await page.locator('#reportCommentSource').innerText()
    if (!commentSku.trim()) throw new Error('Expected comment drawer SKU after opening ABC comment cell')
    if (!commentSource.includes('ABC')) throw new Error(`Expected ABC comment source, got "${commentSource}"`)
    await page.evaluate(() => window.closeReportCommentsDrawer?.())
    await page.waitForSelector('#reportCommentDrawer.open', { state: 'detached', timeout: 500 }).catch(async () => {
      const stillOpen = await page.locator('#reportCommentDrawer.open').count()
      if (stillOpen) throw new Error('Expected comment drawer to close')
    })
  }))

  return steps
}

async function runTarget(browser, target) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 })
  try {
    const now = await runNowChecks(page, target)
    const period = await runPeriodChecks(page, target)
    const abc = await runAbcChecks(page, target)
    return { target: target.name, steps: [...now, ...period, ...abc] }
  } finally {
    await page.close()
  }
}

async function main() {
  let server = null
  if (shouldStartPreview) {
    server = startPreviewServer()
  }
  await waitForHttp(baseUrl)
  await mkdir(outputRoot, { recursive: true })

  const browser = await chromium.launch({ headless: true })
  try {
    const results = []
    for (const target of targets) {
      results.push(await runTarget(browser, target))
    }

    const failedSteps = results.flatMap((result) => result.steps.filter((step) => !step.pass).map((step) => ({ target: result.target, ...step })))
    const report = {
      status: failedSteps.length ? 'fail' : 'pass',
      baseUrl,
      viewport,
      outputRoot,
      results,
      failedSteps,
    }
    await writeFile(path.join(outputRoot, 'interaction-report.json'), `${JSON.stringify(report, null, 2)}\n`)

    if (failedSteps.length) {
      console.error(`Vella interaction parity: fail (${failedSteps.length} failed step(s))`)
      console.error(`Report: ${path.join(outputRoot, 'interaction-report.json')}`)
      process.exitCode = 1
    } else {
      console.log('Vella interaction parity: pass')
      console.log(`Report: ${path.join(outputRoot, 'interaction-report.json')}`)
    }
  } finally {
    await browser.close()
    if (server) server.kill('SIGTERM')
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
