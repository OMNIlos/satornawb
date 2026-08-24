import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'

const frontendRoot = process.cwd()
const projectRoot = path.resolve(frontendRoot, '..')
const stamp = new Date().toISOString().replace(/[:.]/g, '-')
const outputRoot = path.resolve(projectRoot, 'outputs', `vella-baseline-${stamp}`)
const screenshotsDir = path.join(outputRoot, 'screenshots')
const tracesDir = path.join(outputRoot, 'traces')
const videosDir = path.join(outputRoot, 'videos')
const maskCssPath = path.join(frontendRoot, 'e2e', 'vella-baseline-mask.css')

const baseUrl = process.env.VELLA_BASE_URL || 'http://127.0.0.1:4175'
const shouldStartPreview = !process.env.VELLA_BASE_URL
const tooltipLimit = Number(process.env.VELLA_TOOLTIP_LIMIT || 9999)

const viewports = {
  desktop: { width: 1440, height: 900 },
  wide: { width: 1920, height: 1080 },
  mobile: { width: 390, height: 844 },
}

const tabs = [
  'products',
  'algo',
  'templates',
  'history',
  'liq',
  'promos',
  'monitor',
  'digest',
  'abc',
  'rnp',
  'pnl',
  'ads',
  'stock',
  'week',
  'report-rules',
  'notifications',
]

const manifest = {
  generatedAt: new Date().toISOString(),
  source: 'frontend/public/vella-production.html',
  baseUrl,
  tool: 'playwright',
  decisions: {
    firstMigrationModule: 'reports',
    router: 'react-router-dom for Phase 1-2',
    openApiGenerator: 'Orval',
    componentWorkbench: 'internal route first; Storybook later',
    htmlArchiveTarget: 'frontend/reference',
    coverageApproach: 'Playwright DOM inventory + manual checklist',
  },
  inventory: {},
  screenshots: [],
  failures: [],
}

function slug(input) {
  return String(input)
    .toLowerCase()
    .replace(/[^a-z0-9а-яё]+/giu, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 120)
}

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
  const distHtml = path.join(frontendRoot, 'dist', 'vella-production.html')
  if (!existsSync(distHtml)) {
    throw new Error('dist/vella-production.html is missing. Run npm run build first.')
  }

  const child = spawn(
    process.platform === 'win32' ? 'npx.cmd' : 'npx',
    ['vite', 'preview', '--host', '127.0.0.1', '--port', '4175', '--strictPort'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'] },
  )

  child.stdout.on('data', (chunk) => process.stdout.write(chunk))
  child.stderr.on('data', (chunk) => process.stderr.write(chunk))
  return child
}

async function gotoTab(page, tab, viewportName = 'desktop') {
  await page.setViewportSize(viewports[viewportName])
  await page.goto(`${baseUrl}/vella-production.html?tab=${encodeURIComponent(tab)}`, {
    waitUntil: 'domcontentloaded',
  })
  await page.addStyleTag({ path: maskCssPath })
  await page.waitForFunction(() => Boolean(document.querySelector('.tab-content.active')))
  await page.waitForTimeout(150)
}

async function collectInventory(page) {
  return page.evaluate(() => {
    const compact = (value) => String(value || '').replace(/\s+/g, ' ').trim().slice(0, 180)
    const elementRef = (el) => {
      const tag = el.tagName.toLowerCase()
      const id = el.id ? `#${el.id}` : ''
      const classes = [...el.classList].slice(0, 4).map((c) => `.${c}`).join('')
      const dataTab = el.dataset?.tab ? `[data-tab="${el.dataset.tab}"]` : ''
      const onclick = el.getAttribute('onclick') || ''
      return `${tag}${id}${classes}${dataTab}${onclick ? ` onclick="${onclick.slice(0, 80)}"` : ''}`
    }
    const visible = (el) => {
      const style = window.getComputedStyle(el)
      const rect = el.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
    }
    let helpKeys = []
    try {
      // HELP_CONTENT is declared in the static HTML script.
      helpKeys = Object.keys(HELP_CONTENT || {})
    } catch {
      helpKeys = []
    }

    return {
      tabs: [...document.querySelectorAll('.tab-content[id^="tab-"]')].map((el) => ({
        id: el.id,
        label: compact(document.querySelector(`.subtab[data-tab="${el.id.replace(/^tab-/, '')}"]`)?.textContent),
      })),
      subtabs: [...document.querySelectorAll('.subtab[data-tab]')].map((el) => ({
        tab: el.dataset.tab,
        text: compact(el.textContent),
        ref: elementRef(el),
      })),
      drawers: [...document.querySelectorAll('.drawer[id]')].map((el) => ({
        id: el.id,
        hidden: el.getAttribute('aria-hidden'),
        ref: elementRef(el),
      })),
      modals: [...document.querySelectorAll('.modal-overlay[id^="m-"]')].map((el) => ({
        id: el.id,
        name: el.id.replace(/^m-/, ''),
        title: compact(el.querySelector('.modal-title, h2, .modal-head')?.textContent),
        ref: elementRef(el),
      })),
      dropdowns: [...document.querySelectorAll('.dd[id]')].map((el) => ({
        id: el.id,
        text: compact(el.textContent),
        ref: elementRef(el),
      })),
      tooltips: [...document.querySelectorAll('[data-tip]')].map((el, index) => ({
        index,
        tip: el.getAttribute('data-tip'),
        text: compact(el.textContent),
        visible: visible(el),
        ref: elementRef(el),
      })),
      helpKeys,
      actionableControls: [
        ...document.querySelectorAll(
          'button, a[href], input, select, textarea, [role="button"], .chip, .view-btn, .nav-item, .subtab, .dd-item, .act, .help-btn, .calendar-preset, .seg-btn, .dt-tab, .misc-stab',
        ),
      ].map((el, index) => {
        const tag = el.tagName.toLowerCase()
        const type = el.getAttribute('type') || tag
        const disabled = Boolean(el.disabled) || el.getAttribute('aria-disabled') === 'true'
        const onclick = el.getAttribute('onclick') || ''
        const onchange = el.getAttribute('onchange') || ''
        const oninput = el.getAttribute('oninput') || ''
        const href = el.getAttribute('href') || ''
        const role = el.getAttribute('role') || ''
        const dataKeys = Object.keys(el.dataset || {})
        const hasBehavior =
          disabled ||
          Boolean(onclick || onchange || oninput || href) ||
          ['input', 'select', 'textarea'].includes(tag) ||
          role === 'button' ||
          dataKeys.some((key) =>
            ['tab', 'status', 'brand', 'calPreset', 'thresholdField', 'dtab', 'stab', 'reportFilter', 'columnId'].includes(
              key,
            ),
          )
        const needsMockBehavior = !disabled && visible(el)
        return {
          index,
          tag,
          type,
          text: compact(el.textContent || el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('placeholder')),
          disabled,
          visible: visible(el),
          needsMockBehavior,
          hasBehavior,
          behaviorEvidence: { onclick, onchange, oninput, href, role, dataKeys },
          ref: elementRef(el),
        }
      }),
      buttonsWithOnclick: [...document.querySelectorAll('[onclick]')].map((el) => ({
        ref: elementRef(el),
        text: compact(el.textContent || el.getAttribute('aria-label') || el.getAttribute('title')),
        onclick: el.getAttribute('onclick'),
      })),
      tables: [...document.querySelectorAll('table[id], .report-table-wrap, .table-wrap')].map((el) => ({
        ref: elementRef(el),
        rows: el.querySelectorAll('tbody tr').length,
        columns: el.querySelectorAll('thead th').length,
        visible: visible(el),
      })),
    }
  })
}

async function collectState(page) {
  return page.evaluate(() => {
    const activeTab = document.querySelector('.tab-content.active')?.id?.replace(/^tab-/, '') || null
    return {
      activeTab,
      activeSubtabs: [...document.querySelectorAll('.subtab.active')].map((el) => el.dataset.tab),
      openDropdowns: [...document.querySelectorAll('.dd.open[id]')].map((el) => el.id),
      openModals: [...document.querySelectorAll('.modal-overlay.open[id]')].map((el) => el.id),
      helpOpen: document.getElementById('helpModal')?.style.display === 'flex',
      helpTitle: document.getElementById('helpModalTitle')?.textContent?.trim() || null,
      calendarOpen: document.getElementById('calendarPopover')?.classList.contains('open') || false,
      drawerOpen: document.getElementById('dPanel')?.classList.contains('open') || false,
      drawerSku: document.getElementById('dSku')?.textContent?.trim() || null,
      drawerTab: document.querySelector('.dt-tab.active')?.dataset?.dtab || null,
      miscTab: document.querySelector('.misc-stab.active')?.dataset?.stab || null,
      reportCommentDrawerOpen: document.getElementById('reportCommentDrawer')?.classList.contains('open') || false,
      promoDetailOpen: document.getElementById('promoDetailOverlay')?.classList.contains('open') || false,
      toastCount: document.querySelectorAll('.toast.show').length,
      globalTipVisible: (() => {
        const tip = document.getElementById('g-tip')
        if (!tip) return false
        const style = window.getComputedStyle(tip)
        return style.opacity !== '0' && style.display !== 'none'
      })(),
      visibleRows: [...document.querySelectorAll('.tab-content.active tbody tr')].length,
    }
  })
}

async function capture(page, name, options = {}) {
  const fileName = `${slug(name)}.png`
  const screenshotPath = path.join(screenshotsDir, fileName)
  await page.waitForTimeout(options.waitMs ?? 120)
  await page.screenshot({ path: screenshotPath, fullPage: false })
  const state = await collectState(page)
  manifest.screenshots.push({
    name,
    file: `screenshots/${fileName}`,
    viewport: page.viewportSize(),
    state,
  })
}

async function runScenario(page, scenario) {
  try {
    await gotoTab(page, scenario.tab || 'products', scenario.viewport || 'desktop')
    if (scenario.setup) await scenario.setup(page)
    await capture(page, scenario.name, scenario)
  } catch (error) {
    manifest.failures.push({
      name: scenario.name,
      message: error instanceof Error ? error.message : String(error),
    })
  }
}

async function openModalByName(page, name, setup) {
  await page.evaluate((modalName) => {
    if (typeof closeAllModals === 'function') closeAllModals()
    const modal = document.getElementById(`m-${modalName}`)
    if (modal) {
      modal.classList.add('open')
      modal.setAttribute('aria-hidden', 'false')
    }
    if (modalName === 'applyProgress' && typeof runApplyProgress === 'function') runApplyProgress()
    if (modalName === 'thresholdPreview' && typeof openThresholdPreview === 'function') openThresholdPreview()
    if (modalName === 'bulkLiq' && typeof liqStep === 'function') liqStep(1)
  }, name)
  if (setup) await setup(page)
}

const baseScenarios = [
  ...tabs.map((tab) => ({ name: `tab-${tab}`, tab })),
  { name: 'mobile-fallback-products', tab: 'products', viewport: 'mobile' },
  { name: 'wide-products', tab: 'products', viewport: 'wide' },
  {
    name: 'topbar-calendar-popover',
    tab: 'products',
    setup: (page) => page.evaluate(() => openCalendarPopover(document.getElementById('globalPeriodRange'))),
  },
  {
    name: 'topbar-notifications-dropdown',
    tab: 'products',
    setup: (page) => page.evaluate(() => toggleDD('ddNotif')),
  },
  {
    name: 'topbar-export-dropdown',
    tab: 'products',
    setup: (page) => page.evaluate(() => toggleDD('ddExport')),
  },
  {
    name: 'products-advanced-filters',
    tab: 'products',
    setup: (page) => page.evaluate(() => toggleAdvanced()),
  },
  {
    name: 'products-sort-dropdown',
    tab: 'products',
    setup: (page) => page.evaluate(() => toggleDD('ddSort')),
  },
  {
    name: 'products-columns-dropdown',
    tab: 'products',
    setup: (page) => page.evaluate(() => toggleDD('ddCols')),
  },
  {
    name: 'products-bulk-bar-and-template-dropdown',
    tab: 'products',
    setup: (page) =>
      page.evaluate(() => {
        PRODUCTS.slice(0, 3).forEach((p) => {
          p.sel = true
        })
        renderTable()
        toggleDD('ddBulkTpl')
      }),
  },
  {
    name: 'products-empty-search-state',
    tab: 'products',
    setup: (page) =>
      page.evaluate(() => {
        document.getElementById('searchTable').value = 'zzzz-no-sku'
        onSearchInput()
      }),
  },
  {
    name: 'products-api-error-state',
    tab: 'products',
    setup: (page) =>
      page.evaluate(() => {
        document.getElementById('tableWrap').style.display = 'none'
        document.getElementById('apiErrorState').classList.add('show')
      }),
  },
  {
    name: 'products-status-cell-dropdown',
    tab: 'products',
    setup: async (page) => {
      await page.locator('.cell-drop-wrap').first().click()
    },
  },
  {
    name: 'products-apply-modal',
    tab: 'products',
    setup: (page) => openModalByName(page, 'apply'),
  },
  {
    name: 'products-apply-progress-modal',
    tab: 'products',
    setup: (page) => openModalByName(page, 'applyProgress'),
    waitMs: 450,
  },
  {
    name: 'products-night-median-modal',
    tab: 'products',
    setup: (page) => openModalByName(page, 'night'),
  },
  {
    name: 'products-bulk-pmin-modal',
    tab: 'products',
    setup: (page) => openModalByName(page, 'bulkPmin'),
  },
  {
    name: 'products-bulk-liquidation-step-1',
    tab: 'products',
    setup: (page) => openModalByName(page, 'bulkLiq'),
  },
  {
    name: 'products-bulk-liquidation-step-2',
    tab: 'products',
    setup: (page) => openModalByName(page, 'bulkLiq', (p) => p.evaluate(() => liqStep(2))),
  },
  {
    name: 'products-pmin-warning-modal',
    tab: 'products',
    setup: (page) => openModalByName(page, 'pminWarning'),
  },
  {
    name: 'templates-create-template-modal',
    tab: 'templates',
    setup: (page) => openModalByName(page, 'createTpl'),
  },
  {
    name: 'reports-problem-queue-modal',
    tab: 'monitor',
    setup: (page) => openModalByName(page, 'problemQueue'),
  },
  {
    name: 'reports-rules-threshold-preview-modal',
    tab: 'report-rules',
    setup: (page) => openModalByName(page, 'thresholdPreview'),
  },
  {
    name: 'promos-calculator-expanded',
    tab: 'promos',
    setup: (page) => page.evaluate(() => togglePromoCalcTable()),
  },
  {
    name: 'digest-brand-filter-popover',
    tab: 'digest',
    setup: (page) => page.evaluate(() => toggleDigestBrandMenu()),
  },
  {
    name: 'abc-report-comments-drawer',
    tab: 'abc',
    setup: (page) => page.evaluate(() => openReportCommentsDrawer('FBBT_42', 'ABC')),
  },
  {
    name: 'drawer-overview',
    tab: 'products',
    setup: (page) => page.evaluate(() => openDrawer('FBBT_42')),
  },
  {
    name: 'drawer-price-edit-focus',
    tab: 'products',
    setup: (page) =>
      page.evaluate(() => {
        openDrawer('FBBT_42')
        editPrice()
      }),
  },
  {
    name: 'drawer-rules-tab',
    tab: 'products',
    setup: (page) =>
      page.evaluate(() => {
        openDrawer('FBBT_42')
        goDrawerTab('algo')
      }),
  },
  {
    name: 'drawer-misc-orders-tab',
    tab: 'products',
    setup: (page) =>
      page.evaluate(() => {
        openDrawer('FBBT_42')
        goDrawerTab('misc')
        goMiscStab('orders')
      }),
  },
  {
    name: 'drawer-misc-logs-tab',
    tab: 'products',
    setup: (page) =>
      page.evaluate(() => {
        openDrawer('FBBT_42')
        goDrawerTab('misc')
        goMiscStab('logs')
      }),
  },
  {
    name: 'toast-success-info-warn-stack',
    tab: 'products',
    setup: (page) =>
      page.evaluate(() => {
        showToast('Baseline success toast', 'success', true)
        showToast('Baseline info toast', 'info')
        showToast('Baseline warning toast', 'warn')
      }),
  },
]

async function captureHelpStates(page) {
  const helpKeys = manifest.inventory.helpKeys || []
  for (const key of helpKeys) {
    await runScenario(page, {
      name: `help-${key}`,
      tab: key.startsWith('report-') || key.includes('abc') ? 'abc' : 'products',
      setup: (p) => p.evaluate((helpKey) => showHelp(helpKey), key),
    })
  }
}

async function captureVisibleTooltips(page) {
  let captured = 0
  for (const tab of tabs) {
    await gotoTab(page, tab)
    const count = await page.locator('[data-tip]:visible').count()
    for (let i = 0; i < count && captured < tooltipLimit; i += 1) {
      const locator = page.locator('[data-tip]:visible').nth(i)
      const tip = await locator.getAttribute('data-tip')
      if (!tip) continue
      try {
        await locator.scrollIntoViewIfNeeded()
        await locator.hover({ timeout: 1500 })
        await page.waitForTimeout(80)
        await capture(page, `tooltip-${tab}-${String(i + 1).padStart(3, '0')}-${tip.slice(0, 42)}`)
        captured += 1
      } catch (error) {
        manifest.failures.push({
          name: `tooltip-${tab}-${i}`,
          message: error instanceof Error ? error.message : String(error),
        })
      }
    }
  }
  manifest.inventory.tooltipScreenshotsCaptured = captured
}

async function main() {
  await mkdir(screenshotsDir, { recursive: true })
  await mkdir(tracesDir, { recursive: true })
  await mkdir(videosDir, { recursive: true })

  let preview
  if (shouldStartPreview) {
    preview = startPreviewServer()
    await waitForHttp(`${baseUrl}/vella-production.html`)
  }

  const browser = await chromium.launch()
  const context = await browser.newContext({
    viewport: viewports.desktop,
    deviceScaleFactor: 1,
    locale: 'ru-RU',
    timezoneId: 'Asia/Yekaterinburg',
    recordVideo: { dir: videosDir, size: viewports.desktop },
  })
  await context.tracing.start({ screenshots: true, snapshots: true, sources: true })
  const page = await context.newPage()

  await gotoTab(page, 'products')
  manifest.inventory = await collectInventory(page)

  for (const scenario of baseScenarios) {
    await runScenario(page, scenario)
  }

  await captureHelpStates(page)
  await captureVisibleTooltips(page)

  await context.tracing.stop({ path: path.join(tracesDir, 'vella-baseline-trace.zip') })
  await browser.close()

  await writeFile(path.join(outputRoot, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`)
  await writeFile(path.join(outputRoot, 'checklist.md'), renderChecklist(), 'utf8')

  if (preview) preview.kill('SIGTERM')

  console.log(`Baseline written to ${outputRoot}`)
  console.log(`Screenshots: ${manifest.screenshots.length}`)
  console.log(`Failures: ${manifest.failures.length}`)
}

function renderChecklist() {
  const inv = manifest.inventory
  const lines = [
    '# Vella Phase 0 Baseline Checklist',
    '',
    `Generated: ${manifest.generatedAt}`,
    `Source: \`${manifest.source}\``,
    '',
    '## Coverage Rule',
    '',
    '- A state is migration-blocking unless it appears in `manifest.json` and has a screenshot, or is explicitly marked not applicable.',
    '- A visible control is migration-blocking unless it has mock behavior, real behavior, or an explicit disabled/soon state with a visible reason.',
    '- "Clickable but no visible effect" is a failed migration state.',
    '- Tooltips are inventoried from every `[data-tip]`; visible tooltip screenshots are captured per tab until `VELLA_TOOLTIP_LIMIT`.',
    '- Manual QA may add notes, but Playwright artifacts are the source of truth.',
    '',
    '## Decisions',
    '',
    '- First module to migrate: reports.',
    '- Router for Phase 1-2: `react-router-dom`.',
    '- OpenAPI generator: Orval.',
    '- Component workbench: internal route first; Storybook later.',
    '- HTML reference target after migration: `frontend/reference`.',
    '- Exhaustive state strategy: Playwright DOM inventory + manual checklist.',
    '',
    '## Tabs',
    '',
    ...(inv.tabs || []).map((tab) => `- [ ] ${tab.id} ${tab.label ? `- ${tab.label}` : ''}`),
    '',
    '## Modals',
    '',
    ...(inv.modals || []).map((modal) => `- [ ] ${modal.id} - ${modal.title || modal.name}`),
    '',
    '## Drawers',
    '',
    ...(inv.drawers || []).map((drawer) => `- [ ] ${drawer.id}`),
    '',
    '## Dropdowns / Popovers',
    '',
    ...(inv.dropdowns || []).map((dropdown) => `- [ ] ${dropdown.id}`),
    '- [ ] calendarPopover',
    '- [ ] digestBrandFilter',
    '- [ ] reportColumnsPopover',
    '',
    '## Help Modal Keys',
    '',
    ...(inv.helpKeys || []).map((key) => `- [ ] ${key}`),
    '',
    '## Tooltips',
    '',
    `Total inventoried: ${(inv.tooltips || []).length}`,
    `Visible tooltip screenshots captured: ${inv.tooltipScreenshotsCaptured || 0}`,
    '',
    ...(inv.tooltips || []).map((tip) => `- [ ] #${tip.index} ${tip.tip} (${tip.ref})`),
    '',
    '## Actionable Controls',
    '',
    `Total inventoried: ${(inv.actionableControls || []).length}`,
    '',
    ...(inv.actionableControls || []).map((control) => {
      const status = control.disabled ? 'disabled-ok' : control.hasBehavior ? 'behavior-present' : 'needs-behavior'
      return `- [ ] #${control.index} ${status} · ${control.text || control.ref} (${control.ref})`
    }),
    '',
    '## Screenshots',
    '',
    ...manifest.screenshots.map((shot) => `- [ ] ${shot.name} -> \`${shot.file}\``),
    '',
    '## Failures To Triage',
    '',
    ...(manifest.failures.length
      ? manifest.failures.map((failure) => `- [ ] ${failure.name}: ${failure.message}`)
      : ['- none']),
    '',
  ]
  return `${lines.join('\n')}\n`
}

main().catch(async (error) => {
  manifest.failures.push({ name: 'fatal', message: error instanceof Error ? error.stack || error.message : String(error) })
  await mkdir(outputRoot, { recursive: true })
  await writeFile(path.join(outputRoot, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`)
  console.error(error)
  process.exit(1)
})
