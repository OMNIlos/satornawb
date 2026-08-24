import pixelmatch from 'pixelmatch'
import { chromium } from 'playwright'
import { PNG } from 'pngjs'
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
const screenName = process.env.VELLA_PARITY_SCREEN || 'wb-reports-digest'
const outputRoot = path.resolve(projectRoot, 'outputs', `vella-page-parity-${screenName}-${stamp}`)
const baseUrl = process.env.VELLA_BASE_URL || 'http://127.0.0.1:4179'
const shouldStartPreview = !process.env.VELLA_BASE_URL
const strict = process.argv.includes('--strict')
const skipBuildServer = process.argv.includes('--no-server')
const maxMismatchRatio = Number(process.env.VELLA_PARITY_MAX_MISMATCH || (strict ? '0.01' : '0.06'))
const viewport = {
  width: Number(process.env.VELLA_PARITY_WIDTH || '1440'),
  height: Number(process.env.VELLA_PARITY_HEIGHT || '900'),
}

function genericReportScreen(tab, options = {}) {
  const root = `#tab-${tab}`
  return {
    referencePath: `/vella-production.html?tab=${tab}`,
    candidatePath: `/internal/vella-parity/reports?tab=${tab}`,
    waitFor: `${root}.active`,
    candidateWaitFor: `${root}.active`,
    requiredSelectors: [
      '.sidebar',
      '.topbar',
      '.subtabs',
      '.nav-sub[data-nav-group="reports"]',
      `${root}.active`,
      ...(options.hasStats === false ? [] : [`${root} .stats`, `${root} .stat`]),
      ...(options.hasSourceStrip ? [`${root} .report-source-strip`, `${root} .source-state-card`] : []),
      ...(options.extraRequiredSelectors || []),
      `${root} .toolbar`,
      `${root} .toolbar .search input`,
      `${root} .toolbar .chips .chip`,
      `${root} .toolbar-right`,
      `${root} .report-table-wrap`,
      `${root} table`,
      `${root} table thead`,
      `${root} table tbody`,
    ],
    candidateOnlySelectors: [
      '[data-vella-island="sidebar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="topbar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="subtabs"][data-vella-island-status="explicit-jsx"]',
      `[data-vella-island="${tab}"][data-vella-island-status="${options.islandStatus || 'explicit-jsx'}"]`,
      ...(options.candidateOnlySelectors || []),
    ],
    styleProbes: [
      { selector: '.sidebar', properties: ['width', 'backgroundColor', 'color'] },
      { selector: '.topbar', properties: ['height', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'] },
      { selector: '.subtabs', properties: ['minHeight', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'] },
      ...(options.hasStats === false ? [] : [
        { selector: `${root} .stats`, properties: ['display', 'gridTemplateColumns', 'backgroundColor', 'borderBottomColor'] },
        { selector: `${root} .stat`, properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'borderRightColor'] },
      ]),
      ...(options.hasSourceStrip ? [
        { selector: `${root} .report-source-strip`, properties: ['display', 'gridTemplateColumns', 'gap'] },
        { selector: `${root} .source-state-card`, properties: ['borderRadius', 'backgroundColor', 'borderTopColor', 'boxShadow'] },
      ] : []),
      { selector: `${root} .toolbar`, properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: `${root} .report-table-wrap`, properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'overflowX'] },
      { selector: `${root} table thead`, properties: ['backgroundColor'] },
      { selector: `${root} table thead th`, properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'color', 'fontWeight'] },
      { selector: `${root} table tbody tr`, properties: ['borderBottomColor'] },
      { selector: `${root} table`, properties: ['borderCollapse', 'fontSize'] },
    ],
  }
}

function genericTabScreen(tab, options = {}) {
  const rootTab = options.rootTab || tab
  const root = `#tab-${rootTab}`
  const islandName = options.islandName || rootTab
  const module = options.module || 'repricer'
  return {
    referencePath: `/vella-production.html?tab=${tab}`,
    candidatePath: `/internal/vella-parity/reports?tab=${tab}`,
    waitFor: `${root}.active`,
    candidateWaitFor: `${root}.active`,
    requiredSelectors: [
      '.sidebar',
      '.topbar',
      '.subtabs',
      ...(module === 'reports' ? ['.nav-sub[data-nav-group="reports"]'] : []),
      ...(module === 'repricer' ? ['.nav-sub[data-nav-group="repricer"]'] : []),
      `${root}.active`,
      ...(options.requiredSelectors || []),
    ],
    candidateOnlySelectors: [
      '[data-vella-island="sidebar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="topbar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="subtabs"][data-vella-island-status="explicit-jsx"]',
      `[data-vella-island="${islandName}"][data-vella-island-status="${options.islandStatus || 'explicit-jsx'}"]`,
      ...(options.candidateOnlySelectors || []),
    ],
    styleProbes: [
      { selector: '.sidebar', properties: ['width', 'backgroundColor', 'color'] },
      { selector: '.topbar', properties: ['height', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'] },
      { selector: '.subtabs', properties: ['minHeight', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'] },
      { selector: root, properties: ['display', 'overflowX', 'overflowY'] },
      ...(options.styleProbes || []),
    ],
  }
}

const productCandidateOnlySelectors = [
  '[data-vella-island="products-kpi-strip"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="products-saved-views-panel"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="products-saved-views-list"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
  '#savedViewsList .saved-view-btn[data-vella-react-handlers="onclick"]',
  '[data-vella-island="products-toolbar"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="products-active-filters"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="products-advanced-filters"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="products-table-shell"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="products-main-table"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="products-table-header"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="products-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
  '[data-vella-island="products-empty-state"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="products-api-error-state"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="products-pagination"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="products-bulk-bar"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="products-bulk-strategy-menu"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
  '#bulkStrategyMenuItems .dd-item[data-vella-react-handlers="onclick"]',
]

function productTabScreen(options = {}) {
  return genericTabScreen('products', {
    ...options,
    islandStatus: 'explicit-jsx',
    candidateOnlySelectors: [
      ...productCandidateOnlySelectors,
      ...(options.candidateOnlySelectors || []),
    ],
  })
}

async function openThresholdPreviewState(page) {
  await page.evaluate(() => {
    window.syncThresholdInputs?.()
    window.openThresholdPreview?.()
  })
  await page.waitForSelector('#m-thresholdPreview.open')
  await page.waitForTimeout(250)
}

async function openCalendarPopoverState(page) {
  await page.evaluate(() => {
    const anchor = document.getElementById('globalPeriodRange')
      || document.querySelector('.period-range')
    window.openCalendarPopover?.(anchor)
  })
  await page.waitForSelector('#calendarPopover.open')
  await page.waitForSelector('#calendarMonths .calendar-day')
  await page.waitForTimeout(250)
}

function openDropdownState(id) {
  return async (page) => {
    await page.evaluate((dropdownId) => {
      if (dropdownId === 'ddNotif') window.renderNotifPanel?.()
      window.toggleDD?.(dropdownId)
    }, id)
    await page.waitForSelector(`#${id}.open`)
    await page.waitForTimeout(250)
  }
}

async function selectProducts(page, count) {
  await page.evaluate((selectedCount) => {
    if (Array.isArray(window.PRODUCTS)) {
      window.PRODUCTS.forEach((product, index) => {
        product.sel = index < selectedCount
      })
    }
    window.renderTable?.()
  }, count)
  await page.waitForTimeout(100)
}

async function openProductsAdvancedFiltersState(page) {
  await page.evaluate(() => {
    const adv = document.getElementById('advBar')
    if (!adv?.classList.contains('open')) window.toggleAdvanced?.()
  })
  await page.waitForSelector('#tab-products #advBar.open')
  await page.waitForTimeout(250)
}

async function openProductsBulkStrategyState(page) {
  await selectProducts(page, 3)
  await page.evaluate(() => {
    window.toggleDD?.('ddBulkTpl')
  })
  await page.waitForSelector('#tab-products #bulkBar.show')
  await page.waitForSelector('#tab-products #ddBulkTpl.open')
  await page.waitForTimeout(250)
}

async function openProductsEmptySearchState(page) {
  await page.evaluate(() => {
    const search = document.getElementById('searchTable')
    if (search) search.value = 'zzzz-no-sku'
    window.onSearchInput?.()
  })
  await page.waitForSelector('#tab-products #emptyState.show')
  await page.waitForTimeout(250)
}

async function openProductsApiErrorState(page) {
  await page.evaluate(() => {
    const tableWrap = document.getElementById('tableWrap')
    const error = document.getElementById('apiErrorState')
    if (tableWrap) tableWrap.style.display = 'none'
    error?.classList.add('show')
  })
  await page.waitForSelector('#tab-products #apiErrorState.show')
  await page.waitForTimeout(250)
}

async function openProductsCellDropdownState(page) {
  await page.locator('#tab-products .cell-drop-wrap').first().click()
  await page.waitForSelector('#tab-products .cell-drop')
  await page.waitForTimeout(250)
}

function openModalState(name) {
  return async (page) => {
    await page.evaluate((modalName) => {
      window.openModal?.(modalName)
    }, name)
    await page.waitForSelector(`#m-${name}.open`)
    await page.waitForTimeout(250)
  }
}

function openSelectedProductsModalState(name, count = 3) {
  return async (page) => {
    await selectProducts(page, count)
    await page.evaluate((modalName) => {
      window.openModal?.(modalName)
    }, name)
    await page.waitForSelector(`#m-${name}.open`)
    await page.waitForTimeout(250)
  }
}

function openBulkLiquidationStepState(step) {
  return async (page) => {
    await page.evaluate((nextStep) => {
      window.openModal?.('bulkLiq')
      window.liqStep?.(nextStep)
    }, step)
    await page.waitForSelector(`#m-bulkLiq.open[data-step="${step}"]`)
    await page.waitForTimeout(250)
  }
}

async function openTemplatesCreateTemplateState(page) {
  await page.evaluate(() => {
    window.openModal?.('createTpl')
  })
  await page.waitForSelector('#m-createTpl.open')
  await page.waitForTimeout(250)
}

async function openPromosCalculatorExpandedState(page) {
  await page.evaluate(() => {
    window.recalcPromoCalc?.()
    const wrap = document.getElementById('promoCalcTableWrap')
    if (wrap?.style.display !== 'block') window.togglePromoCalcTable?.()
  })
  await page.waitForSelector('#tab-promos #promoCalcTableWrap')
  await page.waitForFunction(() => document.getElementById('promoCalcTableWrap')?.style.display === 'block')
  await page.waitForSelector('#tab-promos #promoCalcTbody tr')
  await page.waitForTimeout(250)
}

async function openDigestBrandFilterState(page) {
  await page.evaluate(() => {
    const filter = document.getElementById('digestBrandFilter')
    if (!filter?.classList.contains('open')) window.toggleDigestBrandMenu?.()
  })
  await page.waitForSelector('#digestBrandFilter.open')
  await page.waitForTimeout(250)
}

async function openAbcReportCommentsDrawerState(page) {
  await page.evaluate(() => {
    window.openReportCommentsDrawer?.('FBBT_42', 'ABC')
  })
  await page.waitForSelector('#reportCommentOverlay.open')
  await page.waitForSelector('#reportCommentDrawer.open')
  await page.waitForTimeout(250)
}

function openProductDrawerState(options = {}) {
  return async (page) => {
    await page.evaluate((stateOptions) => {
      window.openDrawer?.('FBBT_42')
      if (stateOptions.editPrice) window.editPrice?.()
      if (stateOptions.drawerTab) window.goDrawerTab?.(stateOptions.drawerTab)
      if (stateOptions.miscTab) {
        window.goDrawerTab?.('misc')
        window.goMiscStab?.(stateOptions.miscTab)
      }
    }, options)
    await page.waitForSelector('#dOverlay.open')
    await page.waitForSelector('#dPanel.open')
    if (options.editPrice) {
      await page.waitForSelector('#dCalcBlock.edit-focus')
      await page.waitForSelector('#toastContainer .toast.show.info')
      await page.evaluate(() => {
        const container = document.getElementById('toastContainer')
        const source = container?.querySelector('.toast.show.info') || container?.querySelector('.toast.info')
        if (!container || !source) return
        const pinned = source.cloneNode(true)
        pinned.setAttribute('data-vella-parity-pinned', 'drawer-price-edit')
        pinned.classList.add('show', 'info')
        pinned.style.transition = 'none'
        pinned.style.opacity = '1'
        pinned.style.transform = 'translateX(0)'
        container.querySelectorAll('.toast').forEach((toast) => toast.remove())
        container.appendChild(pinned)
      })
      await page.waitForSelector('#toastContainer .toast.show.info[data-vella-parity-pinned="drawer-price-edit"]')
    }
    if (options.drawerTab) await page.waitForSelector(`#dr-${options.drawerTab}.active`)
    if (options.miscTab) {
      await page.waitForSelector('#dr-misc.active')
      await page.waitForSelector(`#mst-${options.miscTab}.active`)
    }
    await page.waitForTimeout(250)
  }
}

async function openToastStackState(page) {
  await page.evaluate(() => {
    window.showToast?.('Baseline success toast', 'success', true)
    window.showToast?.('Baseline info toast', 'info')
    window.showToast?.('Baseline warning toast', 'warn')
  })
  await page.waitForSelector('#toastContainer .toast.show')
  await page.waitForFunction(() => document.querySelectorAll('#toastContainer .toast.show').length === 3)
  await page.waitForTimeout(250)
}

async function openSaveViewModalState(page) {
  await page.evaluate(() => {
    window.openModal?.('saveView')
  })
  await page.waitForSelector('#m-saveView.open')
  await page.waitForTimeout(250)
}

async function openSegmentDetailsModalState(page) {
  await page.evaluate(() => {
    window.openModal?.('segmentDetails')
  })
  await page.waitForSelector('#m-segmentDetails.open')
  await page.waitForSelector('#segmentDetailsBody')
  await page.waitForTimeout(250)
}

async function openBulkAssignManagerModalState(page) {
  await selectProducts(page, 3)
  await page.evaluate(() => {
    window.openBulkAssignManager?.()
  })
  await page.waitForSelector('#m-bulkAssignManager.open')
  await page.waitForSelector('#bulkAssignRows tr')
  await page.waitForTimeout(250)
}

async function openPromoDetailState(page) {
  await page.evaluate(() => {
    window.openPromoDetail?.(0)
  })
  await page.waitForSelector('#promoDetailOverlay.open')
  await page.waitForSelector('#pdCabinetRows tr')
  await page.waitForTimeout(250)
}

async function openSettingsAccessInviteState(page) {
  await page.locator('#tab-settings-access .access-head button').filter({ hasText: 'Пригласить' }).click()
  await page.waitForSelector('#settingsInviteModal.open .modal')
  await page.waitForSelector('#settingsInviteModules .access-invite-option')
  await page.waitForTimeout(250)
}

function openReviewDrawerState(tab = 'answer') {
  return async (page) => {
    await page.evaluate((drawerTab) => {
      window.openReviewDrawer?.('wb-review-002')
      if (drawerTab !== 'answer') window.switchReviewDrawerTab?.(drawerTab)
    }, tab)
    await page.waitForSelector('#reviewDrawerOverlay.open')
    await page.waitForSelector('#reviewDrawer.open')
    await page.waitForSelector(`#reviewDrawer [data-review-drawer-pane="${tab}"].active`)
    await page.waitForTimeout(250)
  }
}

async function openReviewSettingsModalState(page) {
  await page.evaluate(() => {
    window.openReviewsSettings?.()
  })
  await page.waitForSelector('#m-reviewSettings.open')
  await page.waitForSelector('#reviewStopTopicChips .review-rule-chip')
  await page.waitForTimeout(250)
}

async function openHelpModalState(page) {
  await page.evaluate(() => {
    window.showHelp?.('table-fields')
  })
  await page.waitForFunction(() => document.getElementById('helpModal')?.style.display === 'flex')
  await page.waitForSelector('#helpModal .help-modal')
  await page.waitForTimeout(250)
}

const screenContracts = {
  'wb-repricer-products': productTabScreen({
    requiredSelectors: [
      '#tab-products .stats.repricer-kpis',
      '#tab-products #savedViewsPanel',
      '#tab-products > .toolbar',
      '#tab-products #activeFilters',
      '#tab-products #advBar',
      '#tab-products #tableWrap',
      '#tab-products #mainTable',
      '#tab-products #mainTable thead',
      '#tab-products #tbody',
      '#tab-products .pagination',
      '#tab-products #bulkBar',
    ],
    styleProbes: [
      { selector: '#tab-products .stats.repricer-kpis', properties: ['display', 'gridTemplateColumns', 'backgroundColor', 'borderBottomColor'] },
      { selector: '#tab-products > .toolbar', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '#tab-products #tableWrap', properties: ['overflowX', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '#tab-products #mainTable thead', properties: ['backgroundColor'] },
    ],
  }),
  'mobile-fallback-products': {
    referencePath: '/vella-production.html?tab=products',
    candidatePath: '/internal/vella-parity/reports?tab=products',
    viewport: { width: 390, height: 844 },
    waitFor: '.desktop-only-fallback',
    candidateWaitFor: '.desktop-only-fallback',
    requiredSelectors: [
      '.sidebar',
      '.main-area',
      '.desktop-only-fallback',
      '.desktop-only-card',
      '#mobileFallbackTitle',
      '#mobileFallbackCopy',
      '#mobileFallbackLink',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="sidebar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="topbar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="subtabs"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="products"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="products-kpi-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="products-table-shell"][data-vella-island-status="explicit-jsx"]',
    ],
    styleProbes: [
      { selector: '.sidebar', properties: ['width', 'backgroundColor', 'color'] },
      { selector: '.desktop-only-fallback', properties: ['display', 'alignItems', 'justifyContent', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '.desktop-only-card', properties: ['borderRadius', 'backgroundColor', 'boxShadow'] },
      { selector: '#mobileFallbackTitle', properties: ['fontSize', 'fontWeight', 'color'] },
      { selector: '#mobileFallbackLink', properties: ['display', 'borderRadius', 'backgroundColor', 'color'] },
    ],
  },
  'wide-products': {
    ...productTabScreen({
      requiredSelectors: [
        '#tab-products .stats.repricer-kpis',
        '#tab-products #savedViewsPanel',
        '#tab-products > .toolbar',
        '#tab-products #tableWrap',
        '#tab-products #mainTable',
        '#tab-products #tbody',
        '#tab-products .pagination',
      ],
      styleProbes: [
        { selector: '#tab-products .stats.repricer-kpis', properties: ['display', 'gridTemplateColumns', 'backgroundColor', 'borderBottomColor'] },
        { selector: '#tab-products > .toolbar', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
        { selector: '#tab-products #tableWrap', properties: ['overflowX', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      ],
    }),
    viewport: { width: 1920, height: 1080 },
  },
  'wb-repricer-algo': genericTabScreen('algo', {
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-algo .settings-body',
      '#tab-algo .settings-nav',
      '#tab-algo .settings-nav-item.active',
      '#tab-algo .settings-cards',
      '#tab-algo .settings-card',
      '#tab-algo #alg-rules',
      '#tab-algo #alg-cart',
      '#tab-algo #alg-night',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="algo-settings-body"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="algo-settings-nav"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="algo-settings-cards"][data-vella-island-status="explicit-jsx"]',
    ],
    styleProbes: [
      { selector: '#tab-algo .settings-body', properties: ['display', 'gridTemplateColumns', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '#tab-algo .settings-card', properties: ['borderRadius', 'backgroundColor', 'borderTopColor', 'boxShadow'] },
    ],
  }),
  'wb-repricer-templates': genericTabScreen('templates', {
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-templates .tpl-body',
      '#tab-templates #strategyGrid',
      '#tab-templates .btn.btn-primary',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="templates-body"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="templates-header"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="templates-strategy-grid"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '#strategyGrid .tpl-card[data-strategy-card][data-vella-react-handlers="onclick"]',
    ],
    styleProbes: [
      { selector: '#tab-templates .tpl-body', properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '#tab-templates #strategyGrid', properties: ['display', 'gap'] },
    ],
  }),
  'wb-repricer-history': genericTabScreen('history', {
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-history .hist-body',
      '#tab-history .hist-filters',
      '#tab-history .hist-list',
      '#tab-history .hist-item',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="history-body"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="history-filters"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="history-list"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="history-entry"][data-vella-island-status="explicit-jsx"]',
    ],
    styleProbes: [
      { selector: '#tab-history .hist-body', properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '#tab-history .hist-item', properties: ['display', 'gap', 'borderBottomColor'] },
    ],
  }),
  'wb-repricer-liq': genericTabScreen('liq', {
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-liq .liq-stats',
      '#tab-liq .liq-stat',
      '#tab-liq > .toolbar',
      '#tab-liq .table-wrap',
      '#tab-liq table.liq-table',
      '#tab-liq table.liq-table thead',
      '#tab-liq table.liq-table tbody',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="liq-stats"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="liq-toolbar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="liq-table-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="liq-table-body"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="liq-table-row"][data-vella-island-status="explicit-jsx"]',
    ],
    styleProbes: [
      { selector: '#tab-liq .liq-stats', properties: ['display', 'gridTemplateColumns', 'gap'] },
      { selector: '#tab-liq > .toolbar', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '#tab-liq table.liq-table thead', properties: ['backgroundColor'] },
    ],
  }),
  'wb-repricer-promos': genericTabScreen('promos', {
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-promos .liq-stats',
      '#tab-promos #promoCalcCard',
      '#tab-promos .promo-body',
      '#tab-promos .promo-body > .toolbar',
      '#tab-promos .table-wrap',
      '#tab-promos table',
      '#tab-promos table thead',
      '#tab-promos table tbody',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="promos-stats"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="promos-calculator-card"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="promos-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="promos-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="promos-table-row"][data-vella-island-status="explicit-jsx"]',
    ],
    styleProbes: [
      { selector: '#tab-promos .liq-stats', properties: ['display', 'gridTemplateColumns', 'gap'] },
      { selector: '#tab-promos #promoCalcCard', properties: ['borderRadius', 'backgroundColor', 'boxShadow'] },
      { selector: '#tab-promos .promo-body > .toolbar', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
    ],
  }),
  'wb-reviews': genericTabScreen('reviews', {
    module: 'reviews',
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-reviews .stats',
      '#tab-reviews > .toolbar',
      '#tab-reviews .reviews-approval-strip',
      '#tab-reviews .reviews-shell',
      '#tab-reviews #reviewsQueueList',
      '#tab-reviews .reviews-table-wrap',
      '#tab-reviews #reviewsTableBody',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="reviews-kpi-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="reviews-kpi-strip"][data-vella-island-status="explicit-jsx"] .stat-tip[data-tip]',
      '[data-vella-island="reviews-toolbar"][data-vella-island-status="explicit-jsx"]',
      '#tab-reviews > .toolbar[data-vella-event-owner="react"]',
      '#tab-reviews #reviewsSearch[data-vella-react-handlers="oninput"]',
      '#tab-reviews [data-review-filter][data-vella-react-handlers="onclick"]',
      '#tab-reviews > .toolbar .toolbar-right button[data-vella-react-handlers="onclick"]',
      '[data-vella-island="reviews-approval-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="reviews-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="reviews-queue-list"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '#tab-reviews #reviewsQueueList .review-queue-item[data-vella-react-handlers="onclick"]',
      '[data-vella-island="reviews-table-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="reviews-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '#tab-reviews #reviewsTableBody tr[data-vella-react-handlers*="onclick"]',
      '[data-vella-island="reviews-empty-state"][data-vella-island-status="explicit-jsx"]',
    ],
    styleProbes: [
      { selector: '#tab-reviews .stats', properties: ['display', 'gridTemplateColumns', 'backgroundColor', 'borderBottomColor'] },
      { selector: '#tab-reviews > .toolbar', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '#tab-reviews .reviews-shell', properties: ['display', 'gap'] },
    ],
  }),
  'system-notifications': genericTabScreen('notifications', {
    module: 'system',
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-notifications #notifPage',
      '#tab-notifications .notif-main',
      '#tab-notifications .notif-kpis',
      '#tab-notifications .notif-mode-switch',
      '#tab-notifications .notif-toolbar',
      '#tab-notifications #notifCategoryChips',
      '#tab-notifications #notifTableBody',
      '#tab-notifications #notifDetail',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="notifications-page"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="notifications-kpi-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="notifications-mode-switch"][data-vella-island-status="explicit-jsx"]',
      '#tab-notifications [data-notif-mode][data-vella-react-handlers="onclick"]',
      '[data-vella-island="notifications-toolbar"][data-vella-island-status="explicit-jsx"]',
      '#tab-notifications .notif-toolbar[data-vella-event-owner="react"]',
      '#tab-notifications #notifSearch[data-vella-react-handlers="oninput"]',
      '#tab-notifications #notifPeriod[data-vella-react-handlers="onchange"]',
      '#tab-notifications #notifManager[data-vella-react-handlers="onchange"]',
      '#tab-notifications #notifRead[data-vella-react-handlers="onchange"]',
      '#tab-notifications .notif-toolbar button[data-vella-react-handlers="onclick"]',
      '[data-vella-island="notifications-category-chips"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="notifications-table-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="notifications-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="notifications-detail"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
    ],
    styleProbes: [
      { selector: '#tab-notifications #notifPage', properties: ['display', 'gridTemplateColumns', 'gap'] },
      { selector: '#tab-notifications .notif-kpis', properties: ['display', 'gridTemplateColumns'] },
      { selector: '#tab-notifications .notif-toolbar', properties: ['display', 'gap'] },
    ],
  }),
  'settings-profile': genericTabScreen('settings-profile', {
    module: 'system',
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-settings-profile .profile-shell',
      '#tab-settings-profile .profile-page-head',
      '#tab-settings-profile .profile-layout',
      '#tab-settings-profile .profile-card',
      '#tab-settings-profile #settingsProfileAccessRows',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="settings-profile-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="settings-profile-card"][data-vella-island-status="explicit-jsx"]',
      '#tab-settings-profile .profile-page-head button[data-vella-react-handlers="onclick"]',
      '#tab-settings-profile .profile-avatar-button[data-vella-react-handlers="onclick"]',
      '#tab-settings-profile #settingsProfileAvatarInput[data-vella-react-handlers="onchange"]',
      '#tab-settings-profile #settingsProfileName[data-vella-react-handlers="oninput"]',
      '#tab-settings-profile #settingsProfilePosition[data-vella-react-handlers="oninput"]',
      '[data-vella-island="settings-profile-access-card"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="settings-profile-access-rows"][data-vella-island-status="explicit-jsx"]',
      '#settingsProfileAccessRows:not([data-vella-runtime-owner])',
    ],
    styleProbes: [
      { selector: '#tab-settings-profile .profile-shell', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '#tab-settings-profile .profile-layout', properties: ['display', 'gridTemplateColumns', 'gap'] },
      { selector: '#tab-settings-profile .profile-card', properties: ['borderRadius', 'backgroundColor', 'boxShadow'] },
    ],
  }),
  'settings-access': genericTabScreen('settings-access', {
    module: 'system',
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-settings-access .access-shell',
      '#tab-settings-access .access-head',
      '#tab-settings-access .access-page',
      '#tab-settings-access .access-card',
      '#tab-settings-access #settingsAccessUsers',
      '#tab-settings-access .access-drawer',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="settings-access-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="settings-access-users-card"][data-vella-island-status="explicit-jsx"]',
      '#tab-settings-access .access-head button[data-vella-react-handlers="onclick"]',
      '[data-vella-island="settings-access-users"][data-vella-island-status="explicit-jsx"]',
      '#settingsAccessUsers:not([data-vella-runtime-owner])',
      '[data-vella-island="settings-access-drawer"][data-vella-island-status="explicit-jsx"]',
      '#tab-settings-access #settingsAccessRoleSelect[data-vella-react-handlers="onchange"]',
      '[data-vella-island="settings-access-drawer-scopes"][data-vella-island-status="explicit-jsx"]',
      '#settingsAccessDrawerScopes:not([data-vella-runtime-owner])',
      '[data-vella-island="settings-access-drawer-perms"][data-vella-island-status="explicit-jsx"]',
      '#settingsAccessDrawerPerms:not([data-vella-runtime-owner])',
      '[data-vella-island="settings-access-invite-modal"][data-vella-island-status="explicit-jsx"]',
      '#tab-settings-access #settingsInviteRole[data-vella-react-handlers="onchange"]',
      '[data-vella-island="settings-access-invite-modules"][data-vella-island-status="explicit-jsx"]',
      '#settingsInviteModules:not([data-vella-runtime-owner])',
    ],
    styleProbes: [
      { selector: '#tab-settings-access .access-shell', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '#tab-settings-access .access-card', properties: ['borderRadius', 'backgroundColor', 'boxShadow'] },
    ],
  }),
  'settings-access-invite-modal': {
    ...genericTabScreen('settings-access', {
      module: 'system',
      islandStatus: 'explicit-jsx',
      requiredSelectors: [
        '#settingsInviteModal.open',
        '#settingsInviteModal .modal',
        '#settingsInviteModal .modal-head',
        '#settingsInviteModal .modal-head h3',
        '#settingsInviteModal .modal-close',
        '#settingsInviteModal #settingsInviteEmail',
        '#settingsInviteModal #settingsInviteRole',
        '#settingsInviteModules .access-invite-option',
        '#settingsInviteModal .modal-foot',
      ],
      candidateOnlySelectors: [
        '#settingsInviteModal .settings-invite-modal',
        '[data-vella-island="settings-access-invite-modal"][data-vella-island-status="explicit-jsx"]',
        '#settingsInviteModal .modal-close[data-vella-react-handlers="onclick"]',
        '#settingsInviteModal #settingsInviteRole[data-vella-react-handlers="onchange"]',
        '[data-vella-island="settings-access-invite-modules"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
        '#settingsInviteModules .access-switch input[data-vella-react-handlers="onchange"]',
      ],
      styleProbes: [
        { selector: '#settingsInviteModal .modal', properties: ['maxWidth', 'borderRadius', 'backgroundColor', 'boxShadow'] },
        { selector: '#settingsInviteModal .modal-head', properties: ['paddingTop', 'paddingRight', 'paddingLeft'] },
        { selector: '#settingsInviteModal .modal-body', properties: ['paddingTop', 'paddingRight', 'paddingLeft'] },
        { selector: '#settingsInviteModal .access-invite-grid', properties: ['display', 'gridTemplateColumns', 'gap'] },
      ],
    }),
    setup: openSettingsAccessInviteState,
  },
  'avito-overview': genericTabScreen('avito-overview', {
    module: 'avito',
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-avito-overview .stats',
      '#tab-avito-overview > .toolbar',
      '#tab-avito-overview .saved-views-panel',
      '#tab-avito-overview .report-shell',
      '#tab-avito-overview .report-table-wrap',
      '#tab-avito-overview table.report-mid',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="avito-overview-kpi-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-overview-toolbar"][data-vella-island-status="explicit-jsx"]',
      '#tab-avito-overview > .toolbar[data-vella-event-owner="react"]',
      '#tab-avito-overview > .toolbar .chip[data-vella-react-handlers="onclick"]',
      '#tab-avito-overview > .toolbar .toolbar-right button[data-vella-react-handlers="onclick"]',
      '[data-vella-island="avito-overview-status-panel"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-overview-report-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-overview-period-control"][data-vella-island-status="explicit-jsx"]',
      '#tab-avito-overview [data-avito-overview-period-control] .period-btn[data-vella-react-handlers="onclick"]',
      '#tab-avito-overview table.report-mid tbody tr[data-vella-react-handlers="onclick"]',
    ],
    styleProbes: [
      { selector: '#tab-avito-overview .stats', properties: ['display', 'gridTemplateColumns', 'backgroundColor', 'borderBottomColor'] },
      { selector: '#tab-avito-overview > .toolbar', properties: ['display', 'gap'] },
      { selector: '#tab-avito-overview .report-shell', properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
    ],
  }),
  'avito-inbox': genericTabScreen('avito-inbox', {
    module: 'avito',
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-avito-inbox > .toolbar',
      '#tab-avito-inbox .avito-inbox-shell',
      '#tab-avito-inbox .avito-inbox-list',
      '#tab-avito-inbox .avito-conversation-list',
      '#tab-avito-inbox .avito-chat-pane',
      '#tab-avito-inbox .avito-context',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="avito-inbox-toolbar"][data-vella-island-status="explicit-jsx"]',
      '#tab-avito-inbox > .toolbar[data-vella-event-owner="react"]',
      '#tab-avito-inbox #avitoInboxSearch[data-vella-react-handlers="oninput"]',
      '#tab-avito-inbox [data-avito-inbox-filter][data-vella-react-handlers="onclick"]',
      '#tab-avito-inbox #avitoInboxAccount[data-vella-react-handlers="onchange"]',
      '#tab-avito-inbox #avitoInboxManager[data-vella-react-handlers="onchange"]',
      '[data-vella-island="avito-inbox-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-inbox-list"][data-vella-island-status="explicit-jsx"]',
      '#tab-avito-inbox #avitoInboxSort[data-vella-react-handlers="onchange"]',
      '[data-vella-island="avito-inbox-conversation-list"][data-vella-island-status="explicit-jsx"]',
      '#tab-avito-inbox [data-avito-inbox-row][data-vella-react-handlers="onclick"]',
      '[data-vella-island="avito-inbox-chat-pane"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-inbox-message-stream"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="avito-inbox-message"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="avito-inbox-composer"][data-vella-island-status="explicit-jsx"]',
      '#tab-avito-inbox #avitoAttachButton[data-vella-react-handlers="onclick"]',
      '#tab-avito-inbox #avitoAttachmentInput[data-vella-react-handlers="onchange"]',
      '#tab-avito-inbox #avitoSendButton[data-vella-react-handlers="onclick"]',
      '[data-vella-island="avito-inbox-context"][data-vella-island-status="explicit-jsx"]',
    ],
    styleProbes: [
      { selector: '#tab-avito-inbox > .toolbar', properties: ['display', 'gap'] },
      { selector: '#tab-avito-inbox .avito-inbox-shell', properties: ['display', 'gridTemplateColumns', 'backgroundColor'] },
    ],
  }),
  'avito-listings': genericTabScreen('avito-listings', {
    module: 'avito',
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-avito-listings .stats',
      '#tab-avito-listings > .toolbar',
      '#tab-avito-listings .avito-listings-shell',
      '#tab-avito-listings .avito-listings-main',
      '#tab-avito-listings table',
      '#tab-avito-listings #avitoListingDetailPanel',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="avito-listings-kpi-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-listings-kpi-strip"][data-vella-island-status="explicit-jsx"] .stat-tip[data-tip]',
      '[data-vella-island="avito-listings-toolbar"][data-vella-island-status="explicit-jsx"]',
      '#tab-avito-listings > .toolbar[data-vella-event-owner="react"]',
      '#tab-avito-listings #avitoListingsSearch[data-vella-react-handlers="oninput"]',
      '#tab-avito-listings [data-avito-listings-filter][data-vella-react-handlers="onclick"]',
      '#tab-avito-listings #avitoListingsPeriod[data-vella-react-handlers="onchange"]',
      '#tab-avito-listings #avitoListingsPageSize[data-vella-react-handlers="onchange"]',
      '#tab-avito-listings > .toolbar .toolbar-right button[data-vella-react-handlers="onclick"]',
      '[data-vella-island="avito-listings-status-panel"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-listings-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-listings-main"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-listings-table-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-listings-table"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-listings-table-header"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-listings-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="avito-listings-table-row"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="avito-listings-detail-panel"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-listings-detail-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
    ],
    styleProbes: [
      { selector: '#tab-avito-listings .stats', properties: ['display', 'gridTemplateColumns'] },
      { selector: '#tab-avito-listings .avito-listings-shell', properties: ['display', 'gridTemplateColumns', 'gap'] },
    ],
  }),
  'avito-stats': genericTabScreen('avito-stats', {
    module: 'avito',
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-avito-stats .stats',
      '#tab-avito-stats > .toolbar',
      '#tab-avito-stats .saved-views-panel',
      '#tab-avito-stats .avito-stats-shell',
      '#tab-avito-stats .avito-stats-main',
      '#tab-avito-stats table',
      '#tab-avito-stats #avitoStatsDetailPanel',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="avito-stats-kpi-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-stats-kpi-strip"][data-vella-island-status="explicit-jsx"] .stat-tip[data-tip]',
      '[data-vella-island="avito-stats-toolbar"][data-vella-island-status="explicit-jsx"]',
      '#tab-avito-stats > .toolbar[data-vella-event-owner="react"]',
      '#tab-avito-stats #avitoStatsSearch[data-vella-react-handlers="oninput"]',
      '#tab-avito-stats [data-avito-stats-filter][data-vella-react-handlers="onclick"]',
      '#tab-avito-stats #avitoStatsCategory[data-vella-react-handlers="onchange"]',
      '#tab-avito-stats > .toolbar .toolbar-right button[data-vella-react-handlers="onclick"]',
      '[data-vella-island="avito-stats-status-panel"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-stats-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-stats-main"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-stats-top-panels"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-stats-chart"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="avito-stats-table-shell-1"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-stats-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="avito-stats-table-row"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="avito-stats-detail-panel"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="avito-stats-detail-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
    ],
    styleProbes: [
      { selector: '#tab-avito-stats .stats', properties: ['display', 'gridTemplateColumns'] },
      { selector: '#tab-avito-stats .avito-stats-shell', properties: ['display', 'gridTemplateColumns', 'gap'] },
    ],
  }),
  'avito-notifications': genericTabScreen('avito-notifications', {
    module: 'avito',
    rootTab: 'notifications',
    islandName: 'notifications',
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-notifications #notifPage',
      '#tab-notifications .notif-main',
      '#tab-notifications .notif-kpis',
      '#tab-notifications .notif-context-banner',
      '#tab-notifications #avitoNotifTabs',
      '#tab-notifications #avitoNotifWorkspace',
      '#tab-notifications #notifTableBody',
      '#tab-notifications #notifDetail',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="notifications-page"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="notifications-kpi-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="notifications-toolbar"][data-vella-island-status="explicit-jsx"]',
      '#tab-notifications .notif-toolbar[data-vella-event-owner="react"]',
      '[data-vella-island="notifications-avito-context-banner"][data-vella-island-status="explicit-jsx"]',
      '#tab-notifications #notifContextBanner button[data-vella-react-handlers="onclick"]',
      '[data-vella-island="notifications-avito-tabs"][data-vella-island-status="explicit-jsx"]',
      '#tab-notifications #avitoNotifTabs .avito-notif-tab[data-vella-react-handlers="onclick"]',
      '[data-vella-island="notifications-avito-workspace"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="notifications-category-chips"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="notifications-table-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="notifications-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="notifications-detail"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
    ],
    styleProbes: [
      { selector: '#tab-notifications #notifPage', properties: ['display', 'gridTemplateColumns', 'gap'] },
      { selector: '#tab-notifications #avitoNotifTabs', properties: ['display', 'gap'] },
    ],
  }),
  'topbar-calendar-popover': {
    ...genericTabScreen('digest', {
      module: 'reports',
      islandStatus: 'explicit-jsx',
      requiredSelectors: [
        '#globalPeriod',
        '#globalPeriodRange',
        '#calendarPopover.open',
        '#calendarPopover .calendar-head',
        '#calendarPopover #calendarPresets',
        '#calendarPopover .calendar-preset.active',
        '#calendarPopover #calendarStartInput',
        '#calendarPopover #calendarEndInput',
        '#calendarPopover #calendarMonths',
        '#calendarPopover .calendar-day',
        '#calendarPopover .calendar-foot',
      ],
      styleProbes: [
        { selector: '#calendarPopover', properties: ['position', 'width', 'backgroundColor', 'borderRadius', 'boxShadow', 'opacity'] },
        { selector: '#calendarPopover .calendar-body', properties: ['display', 'gridTemplateColumns', 'minHeight'] },
        { selector: '#calendarPopover .calendar-presets', properties: ['display', 'gap', 'backgroundColor', 'borderRightColor'] },
        { selector: '#calendarPopover .calendar-months', properties: ['display', 'gridTemplateColumns', 'gap'] },
      ],
    }),
    setup: openCalendarPopoverState,
  },
  'topbar-notifications-dropdown': {
    ...productTabScreen({
      requiredSelectors: [
        '#ddNotif.open',
        '#ddNotif #bellBtn',
        '#ddNotif #notifPanel',
        '#ddNotif .notif-head',
        '#ddNotif #notifBody',
        '#ddNotif .notif-row',
        '#ddNotif .notif-foot',
      ],
      styleProbes: [
        { selector: '#ddNotif #notifPanel', properties: ['position', 'right', 'top', 'width', 'backgroundColor', 'borderRadius', 'boxShadow'] },
        { selector: '#ddNotif .notif-head', properties: ['display', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'borderBottomColor'] },
        { selector: '#ddNotif .notif-row', properties: ['borderBottomColor'] },
      ],
    }),
    setup: openDropdownState('ddNotif'),
  },
  'topbar-export-dropdown': {
    ...genericTabScreen('digest', {
      module: 'reports',
      islandStatus: 'explicit-jsx',
      requiredSelectors: [
        '#ddExport.open',
        '#ddExport .btn',
        '#ddExport .dd-menu',
        '#ddExport .dd-item',
        '#ddExport [data-export-action="price-import"]',
      ],
      styleProbes: [
        { selector: '#ddExport .dd-menu', properties: ['position', 'right', 'top', 'backgroundColor', 'borderRadius', 'boxShadow'] },
        { selector: '#ddExport .dd-item', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'color'] },
      ],
    }),
    setup: openDropdownState('ddExport'),
  },
  'products-advanced-filters': {
    ...productTabScreen({
      requiredSelectors: [
        '#tab-products #advBar.open',
        '#tab-products #advBar .adv-grid',
        '#tab-products #advBar .adv-field',
        '#tab-products #advBar .range-input',
        '#tab-products #advBar .adv-checks',
        '#tab-products #advBar .adv-actions',
      ],
      styleProbes: [
        { selector: '#tab-products #advBar', properties: ['display', 'gridTemplateRows', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'backgroundColor'] },
        { selector: '#tab-products #advBar .adv-grid', properties: ['display', 'gridTemplateColumns', 'gap'] },
        { selector: '#tab-products #advBar .adv-field', properties: ['display', 'gap'] },
      ],
    }),
    setup: openProductsAdvancedFiltersState,
  },
  'products-sort-dropdown': {
    ...productTabScreen({
      requiredSelectors: [
        '#tab-products #ddSort.open',
        '#tab-products #ddSort .dd-menu',
        '#tab-products #ddSort .dd-section',
        '#tab-products #ddSort .dd-item',
      ],
      styleProbes: [
        { selector: '#tab-products #ddSort .dd-menu', properties: ['position', 'right', 'top', 'backgroundColor', 'borderRadius', 'boxShadow'] },
        { selector: '#tab-products #ddSort .dd-item', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'color'] },
      ],
    }),
    setup: openDropdownState('ddSort'),
  },
  'products-columns-dropdown': {
    ...productTabScreen({
      requiredSelectors: [
        '#tab-products #ddCols.open',
        '#tab-products #ddCols .dd-menu',
        '#tab-products #ddCols .dd-section',
        '#tab-products #ddCols .dd-item',
        '#tab-products #ddCols input[type="checkbox"]',
      ],
      styleProbes: [
        { selector: '#tab-products #ddCols .dd-menu', properties: ['position', 'right', 'top', 'backgroundColor', 'borderRadius', 'boxShadow'] },
        { selector: '#tab-products #ddCols .dd-item', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'color'] },
      ],
    }),
    setup: openDropdownState('ddCols'),
  },
  'products-bulk-strategy-dropdown': {
    ...productTabScreen({
      requiredSelectors: [
        '#tab-products #bulkBar.show',
        '#tab-products #bulkN',
        '#tab-products #ddBulkTpl.open',
        '#tab-products #ddBulkTpl .dd-menu.dark',
        '#tab-products #bulkStrategyMenuItems',
        '#tab-products #bulkStrategyMenuItems .dd-item',
        '#tab-products #ddBulkTpl .tpl-color-dot',
      ],
      styleProbes: [
        { selector: '#tab-products #bulkBar', properties: ['position', 'bottom', 'left', 'backgroundColor', 'borderRadius', 'boxShadow', 'opacity'] },
        { selector: '#tab-products #ddBulkTpl .dd-menu', properties: ['position', 'backgroundColor', 'borderRadius', 'borderTopColor'] },
        { selector: '#tab-products #ddBulkTpl .dd-item', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'color'] },
      ],
    }),
    setup: openProductsBulkStrategyState,
  },
  'products-empty-search-state': {
    ...productTabScreen({
      requiredSelectors: [
        '#tab-products #searchTable',
        '#tab-products #emptyState.show',
        '#tab-products #emptyState .empty-icon',
        '#tab-products #emptyState .empty-title',
        '#tab-products #emptyState .empty-desc',
        '#tab-products #emptyState .btn',
      ],
      styleProbes: [
        { selector: '#tab-products #emptyState', properties: ['display', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'textAlign'] },
        { selector: '#tab-products #emptyState .empty-icon', properties: ['width', 'height', 'borderRadius', 'backgroundColor'] },
      ],
    }),
    setup: openProductsEmptySearchState,
  },
  'products-api-error-state': {
    ...productTabScreen({
      requiredSelectors: [
        '#tab-products #apiErrorState.show',
        '#tab-products #apiErrorState .api-error-icon',
        '#tab-products #apiErrorState .api-error-title',
        '#tab-products #apiErrorState .api-error-desc',
        '#tab-products #apiErrorState .api-error-meta',
        '#tab-products #apiErrorState .btn',
      ],
      styleProbes: [
        { selector: '#tab-products #apiErrorState', properties: ['display', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'backgroundColor', 'borderRadius'] },
        { selector: '#tab-products #apiErrorState .api-error-icon', properties: ['width', 'height', 'borderRadius', 'backgroundColor'] },
      ],
    }),
    setup: openProductsApiErrorState,
  },
  'products-status-cell-dropdown': {
    ...productTabScreen({
      requiredSelectors: [
        '#tab-products .cell-drop-wrap',
        '#tab-products .cell-drop',
        '#tab-products .cell-drop-item',
        '#tab-products .cell-drop-item.cur',
      ],
      styleProbes: [
        { selector: '#tab-products .cell-drop', properties: ['position', 'backgroundColor', 'borderRadius', 'boxShadow', 'zIndex'] },
        { selector: '#tab-products .cell-drop-item', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'color'] },
      ],
    }),
    setup: openProductsCellDropdownState,
  },
  'products-apply-modal': {
    ...productTabScreen({
      requiredSelectors: [
        '#m-apply.open',
        '#m-apply .modal.lg',
        '#m-apply .modal-head',
        '#m-apply .modal-summary',
        '#m-apply .bulk-preview-table',
        '#m-apply .bulk-preview-note',
        '#m-apply .modal-foot',
      ],
      styleProbes: [
        { selector: '#m-apply', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-apply .modal.lg', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-apply .modal-summary', properties: ['display', 'gridTemplateColumns', 'gap'] },
      ],
    }),
    setup: openModalState('apply'),
  },
  'products-apply-progress-modal': {
    ...productTabScreen({
      requiredSelectors: [
        '#m-applyProgress.open',
        '#m-applyProgress .modal.lg',
        '#m-applyProgress #applyProgressView',
        '#m-applyProgress #applyProgressTitle',
        '#m-applyProgress #applyProgressBar',
        '#m-applyProgress #applyLiveFeed',
        '#m-applyProgress .live-event',
        '#m-applyProgress .modal-foot',
      ],
      styleProbes: [
        { selector: '#m-applyProgress', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-applyProgress .modal.lg', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-applyProgress .progress-bar', properties: ['height', 'backgroundColor', 'borderRadius'] },
        { selector: '#m-applyProgress .live-feed', properties: ['display', 'gap'] },
      ],
    }),
    setup: openModalState('applyProgress'),
  },
  'products-night-median-modal': {
    ...productTabScreen({
      requiredSelectors: [
        '#m-night.open',
        '#m-night .modal.lg',
        '#m-night .modal-head',
        '#m-night .modal-icon.brand',
        '#m-night .modal-body',
        '#m-night .s-row',
        '#m-night .toggle',
        '#m-night .alg-pill',
        '#m-night .modal-foot',
      ],
      styleProbes: [
        { selector: '#m-night', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-night .modal.lg', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-night .s-row', properties: ['display', 'justifyContent', 'paddingTop', 'paddingBottom', 'borderBottomColor'] },
      ],
    }),
    setup: openModalState('night'),
  },
  'products-bulk-pmin-modal': {
    ...productTabScreen({
      requiredSelectors: [
        '#m-bulkPmin.open',
        '#m-bulkPmin .modal.lg',
        '#m-bulkPmin .modal-head',
        '#m-bulkPmin #bulkPminValue',
        '#m-bulkPmin .bulk-preview-table',
        '#m-bulkPmin #bulkPminRows tr',
        '#m-bulkPmin .bulk-preview-note',
        '#m-bulkPmin .modal-foot',
      ],
      styleProbes: [
        { selector: '#m-bulkPmin', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-bulkPmin .modal.lg', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-bulkPmin .bulk-preview-table', properties: ['width', 'borderCollapse', 'fontSize'] },
        { selector: '#m-bulkPmin .bulk-preview-note', properties: ['display', 'gap', 'backgroundColor', 'borderTopColor'] },
      ],
    }),
    setup: openSelectedProductsModalState('bulkPmin', 3),
  },
  'products-bulk-liquidation-step-1': {
    ...productTabScreen({
      requiredSelectors: [
        '#m-bulkLiq.open[data-step="1"]',
        '#m-bulkLiq .modal.lg',
        '#m-bulkLiq .lstep-1 .modal-head',
        '#m-bulkLiq .lstep-1 .modal-icon.danger',
        '#m-bulkLiq .lstep-1 .modal-summary',
        '#m-bulkLiq .lstep-1 .bulk-preview-table',
        '#m-bulkLiq .lstep-1 .modal-foot',
      ],
      styleProbes: [
        { selector: '#m-bulkLiq', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-bulkLiq .modal.lg', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-bulkLiq .lstep-1 .modal-summary', properties: ['display', 'gridTemplateColumns', 'gap'] },
      ],
    }),
    setup: openBulkLiquidationStepState(1),
  },
  'products-bulk-liquidation-step-2': {
    ...productTabScreen({
      requiredSelectors: [
        '#m-bulkLiq.open[data-step="2"]',
        '#m-bulkLiq .modal.lg',
        '#m-bulkLiq .lstep-2 .modal-head',
        '#m-bulkLiq .lstep-2 .modal-icon.danger',
        '#m-bulkLiq .lstep-2 .liq-sku-table',
        '#m-bulkLiq .lstep-2 .liq-sku-row',
        '#m-bulkLiq .lstep-2 .permission-check',
        '#m-bulkLiq .lstep-2 #liqConfirmBtn',
      ],
      styleProbes: [
        { selector: '#m-bulkLiq', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-bulkLiq .modal.lg', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-bulkLiq .lstep-2 .liq-sku-row', properties: ['display', 'gridTemplateColumns', 'gap', 'paddingTop', 'paddingBottom'] },
        { selector: '#m-bulkLiq .lstep-2 .permission-check', properties: ['display', 'gap', 'backgroundColor', 'borderTopColor'] },
      ],
    }),
    setup: openBulkLiquidationStepState(2),
  },
  'products-pmin-warning-modal': {
    ...productTabScreen({
      requiredSelectors: [
        '#m-pminWarning.open',
        '#m-pminWarning .modal',
        '#m-pminWarning .modal-head',
        '#m-pminWarning .modal-icon.warn',
        '#m-pminWarning .radio-opts',
        '#m-pminWarning .radio-opt',
        '#m-pminWarning input[name="pminAction"][checked]',
        '#m-pminWarning .modal-foot',
      ],
      styleProbes: [
        { selector: '#m-pminWarning', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-pminWarning .modal', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-pminWarning .radio-opts', properties: ['display', 'gap'] },
        { selector: '#m-pminWarning .radio-opt', properties: ['display', 'gap', 'backgroundColor', 'borderTopColor'] },
      ],
    }),
    setup: openModalState('pminWarning'),
  },
  'templates-create-template-modal': {
    ...genericTabScreen('templates', {
      islandStatus: 'explicit-jsx',
      candidateOnlySelectors: [
        '[data-vella-island="templates-body"][data-vella-island-status="explicit-jsx"]',
        '[data-vella-island="templates-header"][data-vella-island-status="explicit-jsx"]',
        '[data-vella-island="templates-strategy-grid"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
        '#strategyGrid .tpl-card[data-strategy-card][data-vella-react-handlers="onclick"]',
      ],
      requiredSelectors: [
        '#m-createTpl.open',
        '#m-createTpl .modal.lg',
        '#m-createTpl .modal-head',
        '#m-createTpl #strategyModalTitle',
        '#m-createTpl #strategyName',
        '#m-createTpl #strategyType',
        '#m-createTpl .strategy-form-field',
        '#m-createTpl #strategyFormError',
        '#m-createTpl .modal-foot',
      ],
      styleProbes: [
        { selector: '#m-createTpl', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-createTpl .modal.lg', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-createTpl .d-grid', properties: ['display', 'gridTemplateColumns', 'gap'] },
        { selector: '#m-createTpl .strategy-form-field', properties: ['display'] },
      ],
    }),
    setup: openTemplatesCreateTemplateState,
  },
  'promos-calculator-expanded': {
    ...genericTabScreen('promos', {
      islandStatus: 'explicit-jsx',
      candidateOnlySelectors: [
        '[data-vella-island="promos-stats"][data-vella-island-status="explicit-jsx"]',
        '[data-vella-island="promos-calculator-card"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
        '[data-vella-island="promos-calculator-rows"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
        '[data-vella-island="promos-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      ],
      requiredSelectors: [
        '#tab-promos #promoCalcCard',
        '#tab-promos #promoCalcExpandBtn',
        '#tab-promos #promoCalcTableWrap',
        '#tab-promos #promoCalcTableWrap .promo-calc-table',
        '#tab-promos #promoCalcTbody',
        '#tab-promos #promoCalcTbody tr',
        '#tab-promos .promo-calc-dec',
      ],
      styleProbes: [
        { selector: '#tab-promos #promoCalcCard', properties: ['borderRadius', 'backgroundColor', 'boxShadow'] },
        { selector: '#tab-promos #promoCalcTableWrap', properties: ['display', 'overflowX'] },
        { selector: '#tab-promos .promo-calc-table', properties: ['width', 'borderCollapse', 'fontSize'] },
        { selector: '#tab-promos .promo-calc-dec', properties: ['borderRadius', 'fontWeight', 'fontSize'] },
      ],
    }),
    setup: openPromosCalculatorExpandedState,
  },
  'digest-brand-filter-popover': {
    referencePath: '/vella-production.html?tab=digest',
    candidatePath: '/internal/vella-parity/reports?tab=digest',
    waitFor: '#tab-digest.active',
    candidateWaitFor: '#tab-digest.active',
    requiredSelectors: [
      '.sidebar',
      '.topbar',
      '.subtabs',
      '.nav-sub[data-nav-group="reports"]',
      '#tab-digest.active',
      '#digestBrandFilter.open',
      '#digestBrandFilter .brand-filter-btn',
      '#digestBrandFilter .brand-menu',
      '#digestBrandFilter .brand-option',
      '#digestBrandFilter .brand-scope-note',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="sidebar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="topbar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="subtabs"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="digest-brand-filter"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="digest"][data-vella-island-status="explicit-jsx"]',
    ],
    styleProbes: [
      { selector: '.sidebar', properties: ['width', 'backgroundColor', 'color'] },
      { selector: '.topbar', properties: ['height', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'] },
      { selector: '#digestBrandFilter', properties: ['position', 'display'] },
      { selector: '#digestBrandFilter .brand-menu', properties: ['position', 'backgroundColor', 'borderTopColor', 'boxShadow', 'borderRadius'] },
      { selector: '#digestBrandFilter .brand-option', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
    ],
    setup: openDigestBrandFilterState,
  },
  'abc-report-comments-drawer': {
    referencePath: '/vella-production.html?tab=abc',
    candidatePath: '/internal/vella-parity/reports?tab=abc',
    waitFor: '#tab-abc.active',
    candidateWaitFor: '#tab-abc.active',
    requiredSelectors: [
      '.sidebar',
      '.topbar',
      '.subtabs',
      '.nav-sub[data-nav-group="reports"]',
      '#tab-abc.active',
      '#reportCommentOverlay.open',
      '#reportCommentDrawer.open',
      '#reportCommentDrawer .drawer-header',
      '#reportCommentDrawer #reportCommentTitle',
      '#reportCommentDrawer #reportCommentSku',
      '#reportCommentDrawer #reportCommentList',
      '#reportCommentDrawer #reportCommentAudit',
      '#reportCommentDrawer #reportCommentInput',
      '#reportCommentDrawer .report-comment-form',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="sidebar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="topbar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="subtabs"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="abc"][data-vella-island-status="explicit-jsx"]',
    ],
    styleProbes: [
      { selector: '.sidebar', properties: ['width', 'backgroundColor', 'color'] },
      { selector: '.topbar', properties: ['height', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'] },
      { selector: '#reportCommentOverlay', properties: ['position', 'backgroundColor', 'opacity'] },
      { selector: '#reportCommentDrawer', properties: ['position', 'width', 'backgroundColor', 'boxShadow'] },
      { selector: '#reportCommentDrawer .drawer-header', properties: ['display', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '#reportCommentDrawer .report-comment-input', properties: ['minHeight', 'borderRadius', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
    ],
    setup: openAbcReportCommentsDrawerState,
  },
  'drawer-overview': {
    ...productTabScreen({
      requiredSelectors: [
        '#dOverlay.open',
        '#dPanel.open',
        '#dPanel .drawer-header',
        '#dPanel .drawer-tabs',
        '#dPanel .dt-tab.active[data-dtab="overview"]',
        '#dPanel #dr-overview.active',
        '#dPanel #dPrice',
        '#dPanel #dCalcBlock',
        '#dPanel #dHdrBrand',
        '#dPanel #dHdrAbc',
      ],
      styleProbes: [
        { selector: '#dOverlay', properties: ['position', 'backgroundColor', 'opacity'] },
        { selector: '#dPanel', properties: ['position', 'width', 'backgroundColor', 'boxShadow'] },
        { selector: '#dPanel .drawer-header', properties: ['display', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
        { selector: '#dPanel .drawer-tabs', properties: ['display', 'borderBottomColor'] },
        { selector: '#dPanel .d-price-block', properties: ['borderRadius', 'backgroundColor', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      ],
    }),
    setup: openProductDrawerState(),
  },
  'drawer-price-edit-focus': {
    ...productTabScreen({
      requiredSelectors: [
        '#dOverlay.open',
        '#dPanel.open',
        '#dPanel #dr-overview.active',
        '#dPanel #dCalcBlock',
        '#dPanel #dSlider',
        '#dPanel #dNewMargin',
        '#dPanel #dNewMarginRub',
        '#toastContainer .toast.show.info',
      ],
      styleProbes: [
        { selector: '#dPanel', properties: ['position', 'width', 'backgroundColor', 'boxShadow'] },
        { selector: '#dPanel #dCalcBlock', properties: ['borderRadius', 'backgroundColor', 'borderTopColor'] },
        { selector: '#dPanel #dSlider', properties: ['width'] },
        { selector: '#toastContainer', properties: ['position', 'bottom', 'right', 'display', 'gap'] },
        { selector: '#toastContainer .toast.show.info', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'opacity'] },
      ],
    }),
    setup: openProductDrawerState({ editPrice: true }),
  },
  'drawer-rules-tab': {
    ...productTabScreen({
      requiredSelectors: [
        '#dOverlay.open',
        '#dPanel.open',
        '#dPanel .dt-tab.active[data-dtab="algo"]',
        '#dPanel #dr-algo.active',
        '#dPanel .explain-card',
        '#dPanel .decision-list',
        '#dPanel #drawerPminBeforeInput',
        '#dPanel #dPromoBoost',
      ],
      styleProbes: [
        { selector: '#dPanel', properties: ['position', 'width', 'backgroundColor', 'boxShadow'] },
        { selector: '#dPanel .explain-card', properties: ['borderRadius', 'backgroundColor', 'borderTopColor'] },
        { selector: '#dPanel .decision-item', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
        { selector: '#dPanel .seg-ctl', properties: ['display', 'borderRadius', 'backgroundColor'] },
      ],
    }),
    setup: openProductDrawerState({ drawerTab: 'algo' }),
  },
  'drawer-misc-orders-tab': {
    ...productTabScreen({
      requiredSelectors: [
        '#dOverlay.open',
        '#dPanel.open',
        '#dPanel .dt-tab.active[data-dtab="misc"]',
        '#dPanel #dr-misc.active',
        '#dPanel .misc-stab.active[data-stab="orders"]',
        '#dPanel #mst-orders.active',
        '#dPanel #ordersDashboard',
      ],
      styleProbes: [
        { selector: '#dPanel', properties: ['position', 'width', 'backgroundColor', 'boxShadow'] },
        { selector: '#dPanel .misc-subtabs', properties: ['display', 'gap'] },
        { selector: '#dPanel .misc-stab', properties: ['borderRadius', 'fontWeight'] },
        { selector: '#dPanel #ordersDashboard', properties: ['display'] },
      ],
    }),
    setup: openProductDrawerState({ miscTab: 'orders' }),
  },
  'drawer-misc-logs-tab': {
    ...productTabScreen({
      requiredSelectors: [
        '#dOverlay.open',
        '#dPanel.open',
        '#dPanel .dt-tab.active[data-dtab="misc"]',
        '#dPanel #dr-misc.active',
        '#dPanel .misc-stab.active[data-stab="logs"]',
        '#dPanel #mst-logs.active',
        '#dPanel #auditLogDashboard',
      ],
      styleProbes: [
        { selector: '#dPanel', properties: ['position', 'width', 'backgroundColor', 'boxShadow'] },
        { selector: '#dPanel .misc-subtabs', properties: ['display', 'gap'] },
        { selector: '#dPanel .misc-stab', properties: ['borderRadius', 'fontWeight'] },
        { selector: '#dPanel #auditLogDashboard', properties: ['display'] },
      ],
    }),
    setup: openProductDrawerState({ miscTab: 'logs' }),
  },
  'toast-success-info-warn-stack': {
    ...productTabScreen({
      requiredSelectors: [
        '#toastContainer',
        '#toastContainer .toast.show.success',
        '#toastContainer .toast.show.info',
        '#toastContainer .toast.show.warn',
        '#toastContainer .toast-icon',
        '#toastContainer .toast-title',
        '#toastContainer .toast-undo',
      ],
      styleProbes: [
        { selector: '#toastContainer', properties: ['position', 'bottom', 'right', 'display', 'gap'] },
        { selector: '#toastContainer .toast', properties: ['display', 'alignItems', 'gap', 'borderRadius', 'backgroundColor', 'boxShadow'] },
        { selector: '#toastContainer .toast-icon', properties: ['width', 'height', 'borderRadius', 'display'] },
        { selector: '#toastContainer .toast-title', properties: ['fontWeight'] },
      ],
    }),
    setup: openToastStackState,
  },
  'products-save-view-modal': {
    ...productTabScreen({
      requiredSelectors: [
        '#m-saveView.open',
        '#m-saveView .modal',
        '#m-saveView .modal-head',
        '#m-saveView #saveViewName',
        '#m-saveView #saveViewAccess',
        '#m-saveView .modal-summary',
        '#m-saveView #saveViewOwner',
        '#m-saveView #saveViewFilterSummary',
        '#m-saveView .modal-foot',
      ],
      styleProbes: [
        { selector: '#m-saveView', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-saveView .modal', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-saveView .modal-summary', properties: ['display', 'gridTemplateColumns', 'gap'] },
        { selector: '#m-saveView .bulk-preview-note', properties: ['display', 'gap', 'backgroundColor', 'borderTopColor'] },
      ],
    }),
    setup: openSaveViewModalState,
  },
  'products-segment-details-modal': {
    ...productTabScreen({
      requiredSelectors: [
        '#m-segmentDetails.open',
        '#m-segmentDetails .modal',
        '#m-segmentDetails .modal-head',
        '#m-segmentDetails #segmentDetailsTitle',
        '#m-segmentDetails #segmentDetailsSubtitle',
        '#m-segmentDetails #segmentDetailsBody',
        '#m-segmentDetails .bulk-preview-note',
        '#m-segmentDetails #segmentDetailsUpdateBtn',
      ],
      styleProbes: [
        { selector: '#m-segmentDetails', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-segmentDetails .modal', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-segmentDetails .segment-criteria', properties: ['display', 'gap'] },
        { selector: '#m-segmentDetails .bulk-preview-note', properties: ['display', 'gap', 'backgroundColor', 'borderTopColor'] },
      ],
    }),
    setup: openSegmentDetailsModalState,
  },
  'products-bulk-assign-manager-modal': {
    ...productTabScreen({
      requiredSelectors: [
        '#m-bulkAssignManager.open',
        '#m-bulkAssignManager .modal.lg',
        '#m-bulkAssignManager .modal-head',
        '#m-bulkAssignManager #bulkAssignCount',
        '#m-bulkAssignManager #bulkAssignManagerSelect',
        '#m-bulkAssignManager #bulkAssignReason',
        '#m-bulkAssignManager .bulk-preview-table',
        '#m-bulkAssignManager #bulkAssignRows tr',
        '#m-bulkAssignManager .bulk-preview-note',
      ],
      styleProbes: [
        { selector: '#m-bulkAssignManager', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-bulkAssignManager .modal.lg', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-bulkAssignManager .bulk-preview-table', properties: ['width', 'borderCollapse', 'fontSize'] },
        { selector: '#m-bulkAssignManager .bulk-preview-note', properties: ['display', 'gap', 'backgroundColor', 'borderTopColor'] },
      ],
    }),
    setup: openBulkAssignManagerModalState,
  },
  'reports-problem-queue-modal': {
    ...productTabScreen({
      requiredSelectors: [
        '#m-problemQueue.open',
        '#m-problemQueue .modal.xl',
        '#m-problemQueue .modal-head',
        '#m-problemQueue .problem-modal-summary',
        '#m-problemQueue .problem-modal-toolbar',
        '#m-problemQueue .worklist-filter.active',
        '#m-problemQueue .problem-modal-grid',
        '#m-problemQueue .problem-card',
        '#m-problemQueue .modal-foot',
      ],
      styleProbes: [
        { selector: '#m-problemQueue', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-problemQueue .modal.xl', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-problemQueue .problem-modal-summary', properties: ['display', 'gridTemplateColumns', 'gap'] },
        { selector: '#m-problemQueue .problem-card', properties: ['borderRadius', 'backgroundColor', 'borderTopColor'] },
      ],
    }),
    setup: openModalState('problemQueue'),
  },
  'promos-detail-overlay': {
    ...genericTabScreen('promos', {
      islandStatus: 'explicit-jsx',
      candidateOnlySelectors: [
        '[data-vella-island="promos-stats"][data-vella-island-status="explicit-jsx"]',
        '[data-vella-island="promos-calculator-card"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
        '[data-vella-island="promos-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
        '[data-vella-island="promos-detail-overlay"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
        '[data-vella-island="promos-detail-cabinet-rows"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      ],
      requiredSelectors: [
        '#promoDetailOverlay.open',
        '#promoDetailPanel',
        '#promoDetailPanel .promo-detail-head',
        '#promoDetailPanel #pdTitle',
        '#promoDetailPanel #pdStatusBox',
        '#promoDetailPanel #pdParticipation',
        '#promoDetailPanel .promo-detail-table',
        '#promoDetailPanel #pdCabinetRows tr',
        '#promoDetailPanel .promo-detail-footer',
      ],
      styleProbes: [
        { selector: '#promoDetailOverlay', properties: ['position', 'backgroundColor', 'opacity', 'display', 'justifyContent'] },
        { selector: '#promoDetailPanel', properties: ['width', 'height', 'backgroundColor', 'boxShadow', 'display'] },
        { selector: '#promoDetailPanel .promo-detail-head', properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'borderBottomColor'] },
        { selector: '#promoDetailPanel .promo-detail-table', properties: ['width', 'borderCollapse', 'fontSize'] },
      ],
    }),
    setup: openPromoDetailState,
  },
  'reviews-drawer-answer': {
    ...genericTabScreen('reviews', {
      module: 'reviews',
      islandStatus: 'explicit-jsx',
      requiredSelectors: [
        '#reviewDrawerOverlay.open',
        '#reviewDrawer.open',
        '#reviewDrawer .drawer-header',
        '#reviewDrawer [data-review-drawer-tab="answer"].active',
        '#reviewDrawer [data-review-drawer-pane="answer"].active',
        '#reviewDrawer #reviewDrawerStars',
        '#reviewDrawer #reviewDrawerRisk',
        '#reviewDrawer #reviewDraftText',
        '#reviewDrawer #reviewApprovalGuard',
        '#reviewDrawer #reviewApproveBtn',
      ],
      styleProbes: [
        { selector: '#reviewDrawerOverlay', properties: ['position', 'backgroundColor', 'opacity'] },
        { selector: '#reviewDrawer', properties: ['position', 'width', 'backgroundColor', 'boxShadow'] },
        { selector: '#reviewDrawer .drawer-tabs', properties: ['display', 'borderBottomColor'] },
        { selector: '#reviewDrawer .review-drawer-textarea', properties: ['minHeight', 'borderRadius', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      ],
    }),
    setup: openReviewDrawerState('answer'),
  },
  'reviews-drawer-audit': {
    ...genericTabScreen('reviews', {
      module: 'reviews',
      islandStatus: 'explicit-jsx',
      requiredSelectors: [
        '#reviewDrawerOverlay.open',
        '#reviewDrawer.open',
        '#reviewDrawer [data-review-drawer-tab="audit"].active',
        '#reviewDrawer [data-review-drawer-pane="audit"].active',
        '#reviewDrawer #reviewAuditTrail',
        '#reviewDrawer .review-audit-item',
      ],
      styleProbes: [
        { selector: '#reviewDrawerOverlay', properties: ['position', 'backgroundColor', 'opacity'] },
        { selector: '#reviewDrawer', properties: ['position', 'width', 'backgroundColor', 'boxShadow'] },
        { selector: '#reviewDrawer .drawer-tabs', properties: ['display', 'borderBottomColor'] },
        { selector: '#reviewDrawer .review-audit-item', properties: ['borderRadius', 'backgroundColor', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      ],
    }),
    setup: openReviewDrawerState('audit'),
  },
  'reviews-settings-modal': {
    ...genericTabScreen('reviews', {
      module: 'reviews',
      islandStatus: 'explicit-jsx',
      requiredSelectors: [
        '#m-reviewSettings.open',
        '#m-reviewSettings .modal.xl',
        '#m-reviewSettings #reviewSettingsTitle',
        '#m-reviewSettings .review-settings-grid',
        '#m-reviewSettings #reviewSettingsMode',
        '#m-reviewSettings #reviewQuoteMode',
        '#m-reviewSettings #reviewStopTopicChips',
        '#m-reviewSettings .review-rule-chip',
        '#m-reviewSettings .modal-foot',
      ],
      styleProbes: [
        { selector: '#m-reviewSettings', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-reviewSettings .modal.xl', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-reviewSettings .review-settings-grid', properties: ['display', 'gridTemplateColumns', 'gap'] },
        { selector: '#m-reviewSettings .review-rule-chip', properties: ['borderRadius', 'fontWeight'] },
      ],
    }),
    setup: openReviewSettingsModalState,
  },
  'help-table-fields-modal': {
    ...productTabScreen({
      requiredSelectors: [
        '#helpModal',
        '#helpModal .help-modal',
        '#helpModal .help-modal-head',
        '#helpModal #helpModalTitle',
        '#helpModal #helpModalBody',
        '#helpModal .help-modal-close',
      ],
      styleProbes: [
        { selector: '#helpModal', properties: ['position', 'display', 'alignItems', 'justifyContent', 'backgroundColor'] },
        { selector: '#helpModal .help-modal', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#helpModal .help-modal-head', properties: ['display', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'borderBottomColor'] },
        { selector: '#helpModal .help-modal-body', properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'fontSize', 'lineHeight'] },
      ],
    }),
    setup: openHelpModalState,
  },
  'wb-reports-rules': genericTabScreen('report-rules', {
    module: 'reports',
    islandStatus: 'explicit-jsx',
    requiredSelectors: [
      '#tab-report-rules .settings-body',
      '#tab-report-rules .settings-nav',
      '#tab-report-rules .settings-nav-item.active',
      '#tab-report-rules .settings-cards.threshold-cards',
      '#tab-report-rules .settings-card',
      '#tab-report-rules #thr-profile',
      '#tab-report-rules #thr-abc',
      '#tab-report-rules #thr-funnel',
      '#tab-report-rules #thr-economy',
      '#tab-report-rules #thr-ads',
      '#tab-report-rules #thr-stock',
      '#tab-report-rules #thr-manager-plans',
      '#tab-report-rules #thr-automation',
      '#tab-report-rules #thr-history',
      '#tab-report-rules .threshold-preset-row',
      '#tab-report-rules .threshold-preset.active',
      '#tab-report-rules [data-threshold-field]',
      '#tab-report-rules #thresholdAuditList',
      '#tab-report-rules #thresholdSaveBtn',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="report-rules-settings-body"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="report-rules-settings-nav"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="report-rules-threshold-cards"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="report-rules-presets"][data-vella-island-status="explicit-jsx"]',
      '#tab-report-rules .threshold-preset[data-vella-react-handlers="onclick"]',
      '#tab-report-rules [data-threshold-field][data-vella-react-handlers="oninput"]',
      '[data-vella-island="report-rules-threshold-audit-list"][data-vella-island-status="explicit-jsx"]',
      '#tab-report-rules #thresholdAuditList:not([data-vella-runtime-owner])',
      '[data-vella-island="report-rules-actions"][data-vella-island-status="explicit-jsx"]',
      '#tab-report-rules #thresholdSaveBtn[data-vella-react-handlers="onclick"]',
    ],
    styleProbes: [
      { selector: '#tab-report-rules .settings-body', properties: ['display', 'gridTemplateColumns', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '#tab-report-rules .settings-card', properties: ['borderRadius', 'backgroundColor', 'borderTopColor', 'boxShadow'] },
      { selector: '#tab-report-rules .threshold-grid', properties: ['display', 'gridTemplateColumns', 'gap'] },
      { selector: '#tab-report-rules .threshold-table-wrap', properties: ['overflowX', 'borderRadius', 'borderTopColor'] },
      { selector: '#tab-report-rules .threshold-preset', properties: ['borderRadius', 'fontSize', 'fontWeight'] },
    ],
  }),
  'wb-reports-rules-preview': {
    ...genericTabScreen('report-rules', {
      module: 'reports',
      islandStatus: 'explicit-jsx',
      requiredSelectors: [
        '#tab-report-rules .settings-body',
        '#tab-report-rules .settings-cards.threshold-cards',
        '#tab-report-rules #thresholdSaveBtn',
        '#m-thresholdPreview.open',
        '#m-thresholdPreview .modal.xl',
        '#m-thresholdPreview .modal-head',
        '#m-thresholdPreview #thresholdPreviewStats',
        '#m-thresholdPreview .threshold-preview-stat',
        '#m-thresholdPreview .threshold-warning',
        '#m-thresholdPreview .threshold-preview-table',
        '#m-thresholdPreview #thresholdPreviewRows',
        '#m-thresholdPreview .modal-foot',
      ],
      candidateOnlySelectors: [
        '[data-vella-island="threshold-preview-modal"][data-vella-island-status="explicit-jsx"]',
        '#m-thresholdPreview[data-vella-react-handlers="onclick"]',
        '#m-thresholdPreview #thresholdPreviewStats[data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
        '#m-thresholdPreview #thresholdPreviewRows[data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
        '#m-thresholdPreview .modal-foot button[data-vella-react-handlers="onclick"]',
      ],
      styleProbes: [
        { selector: '#m-thresholdPreview', properties: ['display', 'alignItems', 'justifyContent', 'backgroundColor', 'opacity'] },
        { selector: '#m-thresholdPreview .modal.xl', properties: ['borderRadius', 'backgroundColor', 'boxShadow', 'maxWidth'] },
        { selector: '#m-thresholdPreview .threshold-preview-grid', properties: ['display', 'gridTemplateColumns', 'gap'] },
        { selector: '#m-thresholdPreview .threshold-preview-table', properties: ['borderCollapse', 'fontSize'] },
      ],
    }),
    setup: openThresholdPreviewState,
  },
  'wb-reports-digest': {
    referencePath: '/vella-production.html?tab=digest',
    candidatePath: '/internal/vella-parity/reports?tab=digest',
    waitFor: '#tab-digest.active, #tab-digest',
    candidateWaitFor: 'body',
    requiredSelectors: [
      '.sidebar',
      '.topbar',
      '.subtabs',
      '.nav-sub[data-nav-group="reports"]',
      '#tab-digest',
      '#tab-digest .report-shell',
      '#tab-digest .digest-mode-section[data-digest-mode="now"]',
      '#tab-digest .manager-signal-panel',
      '#tab-digest .digest-period-panel',
      '#tab-digest .balance-chart-card',
      '#tab-digest .monitor-critical-main',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="sidebar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="topbar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="subtabs"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="digest-brand-filter"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="global-period-control"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="export-dropdown"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="digest-balance-period-switch"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="manager-signal-panel"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="digest"][data-vella-island-status="explicit-jsx"]',
    ],
    styleProbes: [
      { selector: '.sidebar', properties: ['width', 'backgroundColor', 'color'] },
      { selector: '.topbar', properties: ['height', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'] },
      { selector: '.subtabs', properties: ['minHeight', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'] },
      { selector: '#tab-digest .report-shell', properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'gap'] },
      { selector: '#tab-digest .report-panel', properties: ['borderRadius', 'backgroundColor', 'borderTopColor', 'boxShadow'] },
      { selector: '#tab-digest .report-card-title', properties: ['fontSize', 'fontWeight', 'letterSpacing', 'color'] },
      { selector: '#tab-digest .report-tag', properties: ['borderRadius', 'fontSize', 'fontWeight'] },
    ],
  },
  'wb-reports-digest-period': {
    referencePath: '/vella-production.html?tab=digest&mode=period',
    candidatePath: '/internal/vella-parity/reports?tab=digest&mode=period',
    waitFor: '#tab-digest.active, #tab-digest',
    candidateWaitFor: 'body',
    requiredSelectors: [
      '.sidebar',
      '.topbar',
      '.subtabs',
      '.nav-sub[data-nav-group="reports"]',
      '#tab-digest',
      '#tab-digest .report-shell',
      '#tab-digest .digest-mode-section[data-digest-mode="period"]',
      '#tab-digest .digest-mode-section[data-digest-mode="period"].active',
      '#tab-digest .stats',
      '#tab-digest .stat',
      '#tab-digest .planfact-panel',
      '#tab-digest #digestPlanFactGrid',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="sidebar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="topbar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="subtabs"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="digest-brand-filter"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="global-period-control"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="export-dropdown"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="digest-balance-period-switch"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="manager-signal-panel"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="digest"][data-vella-island-status="explicit-jsx"]',
    ],
    styleProbes: [
      { selector: '.sidebar', properties: ['width', 'backgroundColor', 'color'] },
      { selector: '.topbar', properties: ['height', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'] },
      { selector: '.subtabs', properties: ['minHeight', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'] },
      { selector: '#tab-digest .report-shell', properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'gap'] },
      { selector: '#tab-digest .stats', properties: ['display', 'gridTemplateColumns', 'backgroundColor', 'borderBottomColor'] },
      { selector: '#tab-digest .stat', properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'borderRightColor'] },
      { selector: '#tab-digest .planfact-panel', properties: ['borderRadius', 'backgroundColor', 'borderTopColor', 'boxShadow'] },
      { selector: '#tab-digest .report-card-title', properties: ['fontSize', 'fontWeight', 'letterSpacing', 'color'] },
      { selector: '#tab-digest .report-tag', properties: ['borderRadius', 'fontSize', 'fontWeight'] },
    ],
  },
  'wb-reports-abc': {
    referencePath: '/vella-production.html?tab=abc',
    candidatePath: '/internal/vella-parity/reports?tab=abc',
    waitFor: '#tab-abc.active',
    candidateWaitFor: '#tab-abc.active',
    requiredSelectors: [
      '.sidebar',
      '.topbar',
      '.subtabs',
      '.nav-sub[data-nav-group="reports"]',
      '#tab-abc.active',
      '#tab-abc .stats',
      '#tab-abc .report-source-strip',
      '#tab-abc .source-state-card.partial',
      '#tab-abc .abc-filtered-summary',
      '#tab-abc .toolbar',
      '#tab-abc .abc-help-row',
      '#tab-abc .profit-status-grid',
      '#tab-abc .profit-status-card',
      '#tab-abc .report-table-wrap',
      '#tab-abc table.report-wide thead',
      '#tab-abc table.report-wide tbody',
      '#tab-abc table.report-wide',
    ],
    candidateOnlySelectors: [
      '[data-vella-island="sidebar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="topbar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="subtabs"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="global-period-control"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="export-dropdown"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="abc"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="abc-kpi-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="abc-source-state-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="abc-filtered-summary"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="abc-toolbar"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="abc-toolbar"][data-vella-event-owner="react"]',
      '#tab-abc .toolbar .search input[data-vella-react-handlers="oninput"]',
      '#tab-abc .toolbar .chips .chip[data-abc-bound="1"][data-vella-react-handlers="onclick"]',
      '#tab-abc .toolbar .toolbar-right button[data-vella-action-owner="react-columns"][data-vella-react-handlers="onclick"]',
      '#tab-abc .toolbar .toolbar-right button[data-vella-action-owner="react-export"][data-vella-react-handlers="onclick"]',
      '[data-vella-island="abc-help-row"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="abc-profit-status-panel"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="abc-table-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="abc-table-shell"][data-vella-island-status="explicit-jsx"] > table.report-wide',
      '[data-vella-island="abc-table-header"][data-vella-island-status="explicit-jsx"]',
      '#tab-abc table.report-wide thead[data-vella-sort-owner="react"]',
      '#tab-abc table.report-wide thead th[data-vella-column="abc-orders"][data-sort-key="orders"][data-vella-ux-delta="explicit-abc-sort-key"]',
      '[data-vella-island="abc-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
      '[data-vella-island="abc-table-row"][data-vella-island-status="react-row-renderer"]',
      '#tab-abc table.report-wide tbody tr[data-vella-filter-owner="react"][data-orders-count][data-orders-rub][data-profit-rub][data-ads-rub]',
      '[data-vella-cell="abc-product-cell"][data-vella-cell-status="react-row-cell"]',
      '[data-vella-cell="abc-status-cell"][data-vella-cell-status="react-row-cell"]',
      '[data-vella-cell="abc-action-cell"][data-vella-cell-status="react-row-cell"]',
      '[data-vella-cell="abc-manager-cell"][data-vella-cell-status="react-row-cell"]',
      '[data-vella-cell="abc-margin-cell"][data-vella-cell-status="react-row-cell"]',
      '[data-vella-cell="abc-orders-cell"][data-vella-cell-status="react-row-cell"]',
      '[data-vella-cell="abc-net-cell"][data-vella-cell-status="react-row-cell"]',
      '[data-vella-cell="abc-warehouse-cell"][data-vella-cell-status="react-row-cell"]',
      '[data-vella-cell="abc-comment-cell"][data-vella-cell-status="react-row-cell"]',
      '[data-vella-island="product-drawer-overlay"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-panel"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-header"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-tabs"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-body"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-tab-overview"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-tab-algo"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-tab-comments"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-tab-misc"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-overview-price"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-overview-identity"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-overview-margin"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-overview-demand"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-overview-stock"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-overview-calculator"][data-vella-island-status="explicit-jsx"]',
      '#dPanel #dPriceInput[data-vella-react-handlers="oninput"]',
      '#dPanel #dSlider[data-vella-react-handlers="oninput"]',
      '#dPanel #dApplyBtn[data-vella-react-handlers="onclick"]',
      '#dPanel #detailCalcToggle[data-vella-react-handlers="onclick"]',
      '[data-vella-island="product-drawer-overview-margin-analysis"][data-vella-island-status="explicit-jsx"]',
      '#dPanel #dMarginDiscInput[data-vella-react-handlers="oninput"]',
      '[data-vella-island="product-drawer-overview-basket-chart"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-overview-price-chart"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-overview-impact"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-overview-price-history"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-algo-decision"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-algo-strategy"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-algo-override"][data-vella-island-status="explicit-jsx"]',
      '#dPanel #priceBasisBeforeBtn[data-vella-react-handlers="onclick"]',
      '#dPanel #priceBasisAfterBtn[data-vella-react-handlers="onclick"]',
      '#dPanel #drawerPminBeforeInput[data-vella-react-handlers="oninput"]',
      '#dPanel #drawerPmaxBeforeInput[data-vella-react-handlers="oninput"]',
      '#dPanel #drawerPminAfterInput[data-vella-react-handlers="oninput"]',
      '#dPanel #drawerPmaxAfterInput[data-vella-react-handlers="oninput"]',
      '[data-vella-island="product-drawer-algo-cogs"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="product-drawer-algo-promo-boost"][data-vella-island-status="explicit-jsx"]',
      '#dPanel #dPromoBoost[data-vella-react-handlers="onchange"]',
      '[data-vella-island="product-drawer-comments"][data-vella-island-status="explicit-jsx"]',
      '#dPanel #dr-comments #drawerCommentInput',
      '#dPanel #dr-comments [data-vella-react-handlers="onclick"]',
      '[data-vella-island="product-drawer-misc"][data-vella-island-status="explicit-jsx"]',
      '#dPanel #miscSubtabs .misc-stab[data-vella-react-handlers="onclick"]',
      '#dPanel #ordersDashboard',
      '#dPanel #auditLogDashboard',
      '[data-vella-island="report-comment-overlay"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="report-comment-drawer"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="help-modal"][data-vella-island-status="explicit-jsx"]',
    ],
    styleProbes: [
      { selector: '.sidebar', properties: ['width', 'backgroundColor', 'color'] },
      { selector: '.topbar', properties: ['height', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'] },
      { selector: '.subtabs', properties: ['minHeight', 'paddingLeft', 'paddingRight', 'backgroundColor', 'borderBottomColor'] },
      { selector: '#tab-abc .stats', properties: ['display', 'gridTemplateColumns', 'backgroundColor', 'borderBottomColor'] },
      { selector: '#tab-abc .stat', properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'borderRightColor'] },
      { selector: '#tab-abc .report-source-strip', properties: ['display', 'gridTemplateColumns', 'gap'] },
      { selector: '#tab-abc .source-state-card', properties: ['borderRadius', 'backgroundColor', 'borderTopColor', 'boxShadow'] },
      { selector: '#tab-abc .abc-filtered-summary', properties: ['display', 'backgroundColor', 'borderTopColor', 'borderRadius'] },
      { selector: '#tab-abc > .toolbar', properties: ['display', 'gap', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'] },
      { selector: '#tab-abc > .report-panel.report-panel-pad', properties: ['marginTop', 'marginRight', 'marginBottom', 'marginLeft', 'backgroundColor', 'borderRadius'] },
      { selector: '#tab-abc .profit-status-grid', properties: ['display', 'gridTemplateColumns', 'gap'] },
      { selector: '#tab-abc .report-table-wrap', properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'overflowX'] },
      { selector: '#tab-abc table.report-wide thead', properties: ['backgroundColor'] },
      { selector: '#tab-abc table.report-wide thead th', properties: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'color', 'fontWeight'] },
      { selector: '#tab-abc table.report-wide tbody tr', properties: ['borderBottomColor'] },
      { selector: '#tab-abc table.report-wide', properties: ['borderCollapse', 'fontSize'] },
    ],
  },
  'wb-reports-rnp': genericReportScreen('rnp', {
    islandStatus: 'explicit-jsx',
    candidateOnlySelectors: [
      '[data-vella-island="rnp-kpi-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="rnp-source-state-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="rnp-toolbar"][data-vella-island-status="explicit-jsx"]',
      '#tab-rnp .toolbar[data-vella-event-owner="react"]',
      '#tab-rnp .toolbar .search input[data-vella-react-handlers="oninput"]',
      '#tab-rnp .toolbar .chips .chip[data-vella-react-handlers="onclick"]',
      '#tab-rnp .toolbar .toolbar-right select[data-vella-react-handlers="onchange"]',
      '#tab-rnp .toolbar .toolbar-right button[data-vella-action-owner="react-export"][data-vella-react-handlers="onclick"]',
      '[data-vella-island="rnp-table-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="rnp-table-shell"][data-vella-runtime-binding="renderSecondaryReports"] > table',
      '[data-vella-island="rnp-table-header"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="rnp-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
    ],
  }),
  'wb-reports-pnl': genericReportScreen('pnl', {
    islandStatus: 'explicit-jsx',
    hasStats: false,
    hasSourceStrip: true,
    extraRequiredSelectors: ['#tab-pnl .pnl-workbench', '#tab-pnl .mock-status-grid', '#tab-pnl .pnl-op-cost-panel'],
    candidateOnlySelectors: [
      '[data-vella-island="pnl-source-state-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="pnl-toolbar"][data-vella-island-status="explicit-jsx"]',
      '#tab-pnl .toolbar[data-vella-event-owner="react"]',
      '#tab-pnl .toolbar .search input[data-vella-react-handlers="oninput"]',
      '#tab-pnl .toolbar .chips .chip[data-vella-react-handlers="onclick"]',
      '#tab-pnl .toolbar .toolbar-right select[data-vella-react-handlers="onchange"]',
      '#tab-pnl .toolbar .toolbar-right button[data-vella-action-owner="react-export"][data-vella-react-handlers="onclick"]',
      '[data-vella-island="pnl-workbench"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="pnl-mock-status-grid"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="pnl-op-cost-panel"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="pnl-table-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="pnl-table-shell"][data-vella-runtime-binding="renderSecondaryReports"] > table.report-mid',
      '[data-vella-island="pnl-table-header"][data-vella-island-status="explicit-jsx"]',
      '#tab-pnl [data-vella-island="pnl-table-header"]:not([data-vella-runtime-owner])',
      '[data-vella-island="pnl-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
    ],
  }),
  'wb-reports-ads': genericReportScreen('ads', {
    islandStatus: 'explicit-jsx',
    hasSourceStrip: true,
    candidateOnlySelectors: [
      '[data-vella-island="ads-kpi-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="ads-source-state-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="ads-toolbar"][data-vella-island-status="explicit-jsx"]',
      '#tab-ads .toolbar[data-vella-event-owner="react"]',
      '#tab-ads .toolbar .search input[data-vella-react-handlers="oninput"]',
      '#tab-ads .toolbar .chips .chip[data-vella-react-handlers="onclick"]',
      '#tab-ads .toolbar .toolbar-right select[data-vella-react-handlers="onchange"]',
      '#tab-ads .toolbar .toolbar-right button[data-vella-action-owner="react-export"][data-vella-react-handlers="onclick"]',
      '[data-vella-island="ads-table-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="ads-table-shell"][data-vella-runtime-binding="renderSecondaryReports"] > table.report-mid',
      '[data-vella-island="ads-table-header"][data-vella-island-status="explicit-jsx"]',
      '#tab-ads [data-vella-island="ads-table-header"]:not([data-vella-runtime-owner])',
      '[data-vella-island="ads-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
    ],
  }),
  'wb-reports-stock': genericReportScreen('stock', {
    islandStatus: 'explicit-jsx',
    hasSourceStrip: true,
    candidateOnlySelectors: [
      '[data-vella-island="stock-kpi-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="stock-source-state-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="stock-kpi-strip"][data-vella-island-status="explicit-jsx"] .stat-tip[data-tip]',
      '[data-vella-island="stock-toolbar"][data-vella-island-status="explicit-jsx"]',
      '#tab-stock .toolbar[data-vella-event-owner="react"]',
      '#tab-stock .toolbar .search input[data-vella-react-handlers="oninput"]',
      '#tab-stock .toolbar .chips .chip[data-vella-react-handlers="onclick"]',
      '#tab-stock .toolbar .toolbar-right select[data-vella-react-handlers="onchange"]',
      '#tab-stock .toolbar .toolbar-right button[data-vella-action-owner="react-export"][data-vella-react-handlers="onclick"]',
      '[data-vella-island="stock-table-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="stock-table-shell"][data-vella-runtime-binding="renderSecondaryReports"] > table.report-mid',
      '[data-vella-island="stock-table-header"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="stock-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
    ],
  }),
  'wb-reports-week': genericReportScreen('week', {
    islandStatus: 'explicit-jsx',
    hasStats: false,
    hasSourceStrip: true,
    extraRequiredSelectors: ['#tab-week .week-workbench', '#tab-week .week-signal'],
    candidateOnlySelectors: [
      '[data-vella-island="week-source-state-strip"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="week-toolbar"][data-vella-island-status="explicit-jsx"]',
      '#tab-week .toolbar[data-vella-event-owner="react"]',
      '#tab-week .toolbar .search input[data-vella-react-handlers="oninput"]',
      '#tab-week .toolbar .chips .chip[data-vella-react-handlers="onclick"]',
      '#tab-week .toolbar .toolbar-right select[data-vella-react-handlers="onchange"]',
      '#tab-week .toolbar .toolbar-right button[data-vella-action-owner="react-export"][data-vella-react-handlers="onclick"]',
      '[data-vella-island="week-workbench"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="week-table-shell"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="week-table-shell"][data-vella-runtime-binding="renderSecondaryReports"] > table.report-mid',
      '[data-vella-island="week-table-header"][data-vella-island-status="explicit-jsx"]',
      '[data-vella-island="week-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
    ],
  }),
}

screenContracts['products-bulk-bar-and-template-dropdown'] = screenContracts['products-bulk-strategy-dropdown']
screenContracts['reports-rules-threshold-preview-modal'] = screenContracts['wb-reports-rules-preview']
screenContracts['wb-reports-sales'] = {
  ...screenContracts['wb-reports-digest-period'],
  candidatePath: '/internal/vella-parity/reports/sales',
}

const contract = screenContracts[screenName]
if (!contract) {
  throw new Error(`Unknown Vella parity screen "${screenName}". Known screens: ${Object.keys(screenContracts).join(', ')}`)
}

const referencePath = process.env.VELLA_REFERENCE_PATH || contract.referencePath
const candidatePath = process.env.VELLA_CANDIDATE_PATH || contract.candidatePath
const referenceUrl = `${baseUrl}${referencePath}`
const candidateUrl = `${baseUrl}${candidatePath}`
const pageViewport = contract.viewport || viewport

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
    ['vite', 'preview', '--host', '127.0.0.1', '--port', '4179', '--strictPort'],
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
  await page.waitForTimeout(800)
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

async function readComputed(page, selector, properties) {
  return page.evaluate(
    ({ selector: targetSelector, properties: targetProperties }) => {
      const element = document.querySelector(targetSelector)
      if (!element) return null
      const style = window.getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return {
        rect: {
          width: Math.round(rect.width * 100) / 100,
          height: Math.round(rect.height * 100) / 100,
          top: Math.round(rect.top * 100) / 100,
          left: Math.round(rect.left * 100) / 100,
        },
        styles: Object.fromEntries(targetProperties.map((property) => [property, style[property]])),
      }
    },
    { selector, properties },
  )
}

function normalize(value) {
  return String(value || '')
    .replace(/"/g, "'")
    .replace(/\s+/g, ' ')
    .trim()
}

function equivalent(property, reference, candidate) {
  if (property === 'fontFamily') {
    const left = normalize(reference).split(',')[0]?.trim()
    const right = normalize(candidate).split(',')[0]?.trim()
    return left === right
  }
  return normalize(reference) === normalize(candidate)
}

async function selectorExists(page, selector) {
  return page.locator(selector).count().then((count) => count > 0)
}

async function screenshotDiff(referenceBuffer, candidateBuffer) {
  const referencePng = PNG.sync.read(referenceBuffer)
  const candidatePng = PNG.sync.read(candidateBuffer)
  const width = Math.min(referencePng.width, candidatePng.width)
  const height = Math.min(referencePng.height, candidatePng.height)
  const referenceCrop = new PNG({ width, height })
  const candidateCrop = new PNG({ width, height })
  PNG.bitblt(referencePng, referenceCrop, 0, 0, width, height, 0, 0)
  PNG.bitblt(candidatePng, candidateCrop, 0, 0, width, height, 0, 0)
  const diff = new PNG({ width, height })
  const mismatchedPixels = pixelmatch(referenceCrop.data, candidateCrop.data, diff.data, width, height, {
    threshold: 0.1,
    includeAA: false,
  })
  return {
    diff,
    width,
    height,
    mismatchedPixels,
    mismatchRatio: mismatchedPixels / (width * height),
    dimensionMismatch: referencePng.width !== candidatePng.width || referencePng.height !== candidatePng.height,
    referenceSize: { width: referencePng.width, height: referencePng.height },
    candidateSize: { width: candidatePng.width, height: candidatePng.height },
  }
}

async function main() {
  let server = null
  if (shouldStartPreview && !skipBuildServer) {
    server = startPreviewServer()
    await waitForHttp(baseUrl)
  } else {
    await waitForHttp(baseUrl)
  }

  await mkdir(outputRoot, { recursive: true })
  const browser = await chromium.launch({ headless: true })
  const reference = await browser.newPage({ viewport: pageViewport, deviceScaleFactor: 1 })
  const candidate = await browser.newPage({ viewport: pageViewport, deviceScaleFactor: 1 })

  try {
    await gotoParityPage(reference, referenceUrl)
    await gotoParityPage(candidate, candidateUrl)
    await reference.waitForSelector(contract.waitFor)
    await candidate.waitForSelector(contract.candidateWaitFor)
    await stabilize(reference)
    await stabilize(candidate)
    if (contract.setup) {
      await contract.setup(reference)
      await contract.setup(candidate)
      await stabilize(reference)
      await stabilize(candidate)
    }

    const referencePathOut = path.join(outputRoot, 'reference.png')
    const candidatePathOut = path.join(outputRoot, 'candidate.png')
    const diffPathOut = path.join(outputRoot, 'diff.png')
    const referenceBuffer = await reference.screenshot({ path: referencePathOut, fullPage: false })
    const candidateBuffer = await candidate.screenshot({ path: candidatePathOut, fullPage: false })
    const imageDiff = await screenshotDiff(referenceBuffer, candidateBuffer)
    await writeFile(diffPathOut, PNG.sync.write(imageDiff.diff))

    const selectorChecks = []
    for (const selector of contract.requiredSelectors) {
      const referenceExists = await selectorExists(reference, selector)
      const candidateExists = await selectorExists(candidate, selector)
      selectorChecks.push({
        selector,
        scope: 'reference-and-candidate',
        pass: referenceExists && candidateExists,
        referenceExists,
        candidateExists,
      })
    }
    for (const selector of contract.candidateOnlySelectors || []) {
      const candidateExists = await selectorExists(candidate, selector)
      selectorChecks.push({
        selector,
        scope: 'candidate-only',
        pass: candidateExists,
        referenceExists: null,
        candidateExists,
      })
    }

    const styleChecks = []
    for (const probe of contract.styleProbes) {
      const referenceStyle = await readComputed(reference, probe.selector, probe.properties)
      const candidateStyle = await readComputed(candidate, probe.selector, probe.properties)
      const missing = !referenceStyle || !candidateStyle
      const diffs = missing
        ? [{ property: 'selector', reference: Boolean(referenceStyle), candidate: Boolean(candidateStyle) }]
        : probe.properties
          .filter((property) => !equivalent(property, referenceStyle.styles[property], candidateStyle.styles[property]))
          .map((property) => ({
            property,
            reference: referenceStyle.styles[property],
            candidate: candidateStyle.styles[property],
          }))
      styleChecks.push({
        selector: probe.selector,
        pass: !missing && diffs.length === 0,
        reference: referenceStyle,
        candidate: candidateStyle,
        diffs,
      })
    }

    const failedSelectors = selectorChecks.filter((check) => !check.pass)
    const failedStyles = styleChecks.filter((check) => !check.pass)
    const imagePass = imageDiff.mismatchRatio <= maxMismatchRatio && !imageDiff.dimensionMismatch
    const report = {
      generatedAt: new Date().toISOString(),
      strict,
      screenName,
      referenceUrl,
      candidateUrl,
      viewport: pageViewport,
      maxMismatchRatio,
      status: imagePass && failedSelectors.length === 0 && failedStyles.length === 0 ? 'pass' : 'fail',
      image: {
        pass: imagePass,
        mismatchRatio: Number(imageDiff.mismatchRatio.toFixed(6)),
        mismatchedPixels: imageDiff.mismatchedPixels,
        dimensionMismatch: imageDiff.dimensionMismatch,
        referenceSize: imageDiff.referenceSize,
        candidateSize: imageDiff.candidateSize,
      },
      selectorChecks,
      styleChecks,
      screenshots: ['reference.png', 'candidate.png', 'diff.png'],
    }

    await writeFile(path.join(outputRoot, 'parity-report.json'), JSON.stringify(report, null, 2))
    console.log(`Vella page parity (${screenName}): ${report.status}`)
    console.log(`Report: ${path.relative(projectRoot, path.join(outputRoot, 'parity-report.json'))}`)
    console.log(`Mismatch ratio: ${(report.image.mismatchRatio * 100).toFixed(2)}%`)
    for (const check of failedSelectors.slice(0, 12)) {
      console.log(`- Missing selector in candidate: ${check.selector}`)
    }
    for (const check of failedStyles.slice(0, 8)) {
      console.log(`- Style mismatch: ${check.selector}`)
      for (const diff of check.diffs.slice(0, 4)) {
        console.log(`  ${diff.property}: reference=${diff.reference} candidate=${diff.candidate}`)
      }
    }

    if (report.status !== 'pass') process.exitCode = 1
  } finally {
    await browser.close()
    if (server) server.kill('SIGTERM')
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
