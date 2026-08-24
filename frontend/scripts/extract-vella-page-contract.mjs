import { chromium } from 'playwright'
import { spawn } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync } from 'node:fs'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'

const cwd = process.cwd()
const frontendRoot = existsSync(path.join(cwd, 'package.json')) && existsSync(path.join(cwd, 'src'))
  ? cwd
  : path.join(cwd, 'frontend')
const projectRoot = path.resolve(frontendRoot, '..')
const stamp = new Date().toISOString().replace(/[:.]/g, '-')
const screenName = process.env.VELLA_CONTRACT_SCREEN || 'wb-reports-digest'
const outputRoot = path.resolve(projectRoot, 'outputs', `vella-page-contract-${screenName}-${stamp}`)
const baseUrl = process.env.VELLA_BASE_URL || 'http://127.0.0.1:4179'
const shouldStartPreview = !process.env.VELLA_BASE_URL
const isAbcScreen = screenName === 'wb-reports-abc'
const isSalesScreen = screenName === 'wb-reports-sales'
const genericReportTabs = {
  'wb-reports-rnp': 'rnp',
  'wb-reports-pnl': 'pnl',
  'wb-reports-ads': 'ads',
  'wb-reports-stock': 'stock',
  'wb-reports-week': 'week',
}
const genericPageTabs = {
  'wb-repricer-products': { tab: 'products' },
  'wb-repricer-algo': { tab: 'algo' },
  'wb-repricer-templates': { tab: 'templates' },
  'wb-repricer-history': { tab: 'history' },
  'wb-repricer-liq': { tab: 'liq' },
  'wb-repricer-promos': { tab: 'promos' },
  'wb-reviews': { tab: 'reviews' },
  'system-notifications': { tab: 'notifications' },
  'settings-profile': { tab: 'settings-profile' },
  'settings-access': { tab: 'settings-access' },
  'avito-overview': { tab: 'avito-overview' },
  'avito-inbox': { tab: 'avito-inbox' },
  'avito-listings': { tab: 'avito-listings' },
  'avito-stats': { tab: 'avito-stats' },
  'avito-notifications': { tab: 'avito-notifications', rootTab: 'notifications', island: 'notifications' },
  'wb-reports-rules': { tab: 'report-rules' },
}
const genericReportTab = genericReportTabs[screenName]
const genericPageConfig = genericPageTabs[screenName]
const genericPageTab = genericPageConfig?.tab
const genericPageRootTab = genericPageConfig?.rootTab || genericPageTab
const genericPageIsland = genericPageConfig?.island || genericPageRootTab
const isGenericReportScreen = Boolean(genericReportTab)
const isGenericPageScreen = Boolean(genericPageTab)
const screensWithReactOwnedHandlerGrowth = new Set([
  'wb-repricer-products',
  'wb-repricer-promos',
  'wb-reviews',
  'system-notifications',
  'avito-notifications',
  'settings-profile',
  'settings-access',
  'avito-inbox',
])
const screensWithReactOwnedHandlerRebalance = new Set([
  'avito-stats',
])

const states = isSalesScreen ? [
  {
    name: 'period',
    referencePath: '/vella-production.html?tab=digest&mode=period',
    candidatePath: '/internal/vella-parity/reports/sales',
  },
] : isAbcScreen || isGenericReportScreen || isGenericPageScreen ? [
  {
    name: 'default',
    referencePath: `/vella-production.html?tab=${isAbcScreen ? 'abc' : genericReportTab || genericPageTab}`,
    candidatePath: `/internal/vella-parity/reports?tab=${isAbcScreen ? 'abc' : genericReportTab || genericPageTab}`,
  },
] : [
  {
    name: 'now',
    referencePath: '/vella-production.html?tab=digest',
    candidatePath: '/internal/vella-parity/reports?tab=digest',
  },
  {
    name: 'period',
    referencePath: '/vella-production.html?tab=digest&mode=period',
    candidatePath: '/internal/vella-parity/reports?tab=digest&mode=period',
  },
]

const genericReportRoot = `#tab-${genericReportTab}`
const genericPageRoot = `#tab-${genericPageRootTab}`

const selectorProbes = isAbcScreen ? [
  '#sidebar',
  '.topbar',
  '.subtabs',
  '#subtabsContext',
  '#tab-abc',
  '#tab-abc .stats',
  '#tab-abc .report-source-strip',
  '#tab-abc .abc-filtered-summary',
  '#tab-abc > .toolbar',
  '#tab-abc > .abc-help-row',
  '#tab-abc .profit-status-grid',
  '#tab-abc > .report-table-wrap',
  '#tab-abc table.report-wide',
  '#tab-abc table.report-wide > thead',
  '#tab-abc table.report-wide > tbody',
  '#helpModal',
  '#dOverlay',
  '#dPanel',
  '#dPanel #dThumb',
  '#dPanel #dName',
  '#dPanel #dSku',
  '#dPanel .drawer-tabs',
  '#dPanel #dr-overview',
  '#dPanel #dr-algo',
  '#dPanel #dr-comments',
  '#dPanel #dr-misc',
  '#dPanel #miscSubtabs',
  '#dPanel #ordersDashboard',
  '#dPanel #auditLogDashboard',
  '#reportCommentOverlay',
  '#reportCommentDrawer',
] : isGenericReportScreen ? [
  '#sidebar',
  '.topbar',
  '.subtabs',
  '#subtabsContext',
  genericReportRoot,
  `${genericReportRoot}.active`,
  `${genericReportRoot} .toolbar`,
  `${genericReportRoot} .toolbar .search input`,
  `${genericReportRoot} .toolbar .chips .chip`,
  `${genericReportRoot} .toolbar-right`,
  ...(['rnp', 'pnl', 'ads', 'stock', 'week'].includes(genericReportTab) ? [`${genericReportRoot} .report-source-strip`, `${genericReportRoot} .source-state-card`] : []),
  `${genericReportRoot} .report-table-wrap`,
  `${genericReportRoot} table`,
  `${genericReportRoot} table thead`,
  `${genericReportRoot} table tbody`,
  ...(genericReportTab === 'pnl' ? [`${genericReportRoot} .pnl-workbench`, `${genericReportRoot} .pnl-op-cost-panel`] : []),
  ...(genericReportTab === 'week' ? [`${genericReportRoot} .week-workbench`, `${genericReportRoot} .week-signal`] : []),
] : isGenericPageScreen ? [
  '#sidebar',
  '.topbar',
  '.subtabs',
  '#subtabsContext',
  genericPageRoot,
  `${genericPageRoot}.active`,
  ...(genericPageTab === 'products' ? [
    `${genericPageRoot} .stats.repricer-kpis`,
    `${genericPageRoot} #savedViewsPanel`,
    `${genericPageRoot} > .toolbar`,
    `${genericPageRoot} #tableWrap`,
    `${genericPageRoot} #mainTable`,
    `${genericPageRoot} #mainTable thead`,
    `${genericPageRoot} #tbody`,
    `${genericPageRoot} .pagination`,
    `${genericPageRoot} #bulkBar`,
  ] : []),
  ...(genericPageTab === 'algo' ? [
    `${genericPageRoot} .settings-body`,
    `${genericPageRoot} .settings-nav`,
    `${genericPageRoot} .settings-cards`,
    `${genericPageRoot} .settings-card`,
    `${genericPageRoot} #alg-rules`,
  ] : []),
  ...(genericPageTab === 'templates' ? [
    `${genericPageRoot} .tpl-body`,
    `${genericPageRoot} #strategyGrid`,
  ] : []),
  ...(genericPageTab === 'history' ? [
    `${genericPageRoot} .hist-body`,
    `${genericPageRoot} .hist-filters`,
    `${genericPageRoot} .hist-list`,
    `${genericPageRoot} .hist-item`,
  ] : []),
  ...(genericPageTab === 'liq' ? [
    `${genericPageRoot} .liq-stats`,
    `${genericPageRoot} > .toolbar`,
    `${genericPageRoot} .table-wrap`,
    `${genericPageRoot} table.liq-table`,
    `${genericPageRoot} table.liq-table tbody`,
  ] : []),
  ...(genericPageTab === 'promos' ? [
    `${genericPageRoot} .liq-stats`,
    `${genericPageRoot} #promoCalcCard`,
    `${genericPageRoot} .promo-body`,
    `${genericPageRoot} .promo-body > .toolbar`,
    `${genericPageRoot} .table-wrap`,
    `${genericPageRoot} table tbody`,
  ] : []),
  ...(genericPageTab === 'reviews' ? [
    `${genericPageRoot} .stats`,
    `${genericPageRoot} > .toolbar`,
    `${genericPageRoot} .reviews-approval-strip`,
    `${genericPageRoot} .reviews-shell`,
    `${genericPageRoot} #reviewsQueueList`,
    `${genericPageRoot} #reviewsTableBody`,
  ] : []),
  ...(genericPageTab === 'notifications' || genericPageTab === 'avito-notifications' ? [
    `${genericPageRoot} #notifPage`,
    `${genericPageRoot} .notif-main`,
    `${genericPageRoot} .notif-kpis`,
    `${genericPageRoot} .notif-toolbar`,
    `${genericPageRoot} #notifTableBody`,
    `${genericPageRoot} #notifDetail`,
  ] : []),
  ...(genericPageTab === 'avito-notifications' ? [
    `${genericPageRoot} #avitoNotifTabs`,
    `${genericPageRoot} #avitoNotifWorkspace`,
  ] : []),
  ...(genericPageTab === 'settings-profile' ? [
    `${genericPageRoot} .profile-shell`,
    `${genericPageRoot} .profile-layout`,
    `${genericPageRoot} .profile-card`,
    `${genericPageRoot} #settingsProfileAccessRows`,
  ] : []),
  ...(genericPageTab === 'settings-access' ? [
    `${genericPageRoot} .access-shell`,
    `${genericPageRoot} .access-page`,
    `${genericPageRoot} .access-card`,
    `${genericPageRoot} #settingsAccessUsers`,
    `${genericPageRoot} .access-drawer`,
  ] : []),
  ...(genericPageTab === 'avito-overview' ? [
    `${genericPageRoot} .stats`,
    `${genericPageRoot} > .toolbar`,
    `${genericPageRoot} .saved-views-panel`,
    `${genericPageRoot} .report-shell`,
    `${genericPageRoot} .report-table-wrap`,
    `${genericPageRoot} table.report-mid`,
  ] : []),
  ...(genericPageTab === 'avito-inbox' ? [
    `${genericPageRoot} > .toolbar`,
    `${genericPageRoot} .avito-inbox-shell`,
    `${genericPageRoot} .avito-inbox-list`,
    `${genericPageRoot} .avito-conversation-list`,
    `${genericPageRoot} .avito-chat-pane`,
    `${genericPageRoot} .avito-message-stream`,
    `${genericPageRoot} .avito-context`,
  ] : []),
  ...(genericPageTab === 'avito-listings' ? [
    `${genericPageRoot} .stats`,
    `${genericPageRoot} > .toolbar`,
    `${genericPageRoot} .avito-listings-shell`,
    `${genericPageRoot} .avito-listings-main`,
    `${genericPageRoot} table`,
    `${genericPageRoot} #avitoListingDetailPanel`,
  ] : []),
  ...(genericPageTab === 'avito-stats' ? [
    `${genericPageRoot} .stats`,
    `${genericPageRoot} > .toolbar`,
    `${genericPageRoot} .saved-views-panel`,
    `${genericPageRoot} .avito-stats-shell`,
    `${genericPageRoot} .avito-stats-main`,
    `${genericPageRoot} table`,
    `${genericPageRoot} #avitoStatsDetailPanel`,
  ] : []),
  ...(genericPageTab === 'report-rules' ? [
    `${genericPageRoot} .settings-body`,
    `${genericPageRoot} .settings-nav`,
    `${genericPageRoot} .settings-nav-item.active`,
    `${genericPageRoot} .settings-cards.threshold-cards`,
    `${genericPageRoot} .settings-card`,
    `${genericPageRoot} #thr-profile`,
    `${genericPageRoot} #thr-abc`,
    `${genericPageRoot} #thr-funnel`,
    `${genericPageRoot} #thr-economy`,
    `${genericPageRoot} #thr-ads`,
    `${genericPageRoot} #thr-stock`,
    `${genericPageRoot} #thr-manager-plans`,
    `${genericPageRoot} #thr-automation`,
    `${genericPageRoot} #thr-history`,
    `${genericPageRoot} .threshold-preset-row`,
    `${genericPageRoot} .threshold-preset.active`,
    `${genericPageRoot} [data-threshold-field]`,
    `${genericPageRoot} #thresholdAuditList`,
    `${genericPageRoot} #thresholdSaveBtn`,
  ] : []),
] : [
  '#sidebar',
  '.topbar',
  '.subtabs',
  '#subtabsContext',
  '#digestBrandFilter',
  '#globalPeriod',
  '#ddExport',
  '.balance-period-switch',
  '#tab-digest',
  '#tab-digest .report-shell',
  '#tab-digest .digest-mode-section[data-digest-mode="now"]',
  '#tab-digest .digest-mode-section[data-digest-mode="period"]',
  '#tab-digest .manager-signal-panel',
  '#tab-digest .digest-period-panel',
  '#tab-digest .balance-chart-card',
  '#digestBalanceChart',
  '#digestPlanFactGrid',
]

const candidateOnlySelectorProbes = isAbcScreen ? [
  '[data-vella-island="sidebar"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="topbar"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="subtabs"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="abc"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="abc-kpi-strip"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="abc-source-state-strip"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="abc-filtered-summary"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="abc-toolbar"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="abc-help-row"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="abc-profit-status-panel"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="abc-table-shell"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="abc-table-header"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="abc-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
  '[data-vella-island="product-drawer-overlay"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="product-drawer-panel"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="product-drawer-header"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="product-drawer-tabs"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="product-drawer-body"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="product-drawer-comments"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="product-drawer-misc"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="report-comment-overlay"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="report-comment-drawer"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="help-modal"][data-vella-island-status="explicit-jsx"]',
] : isGenericReportScreen ? [
  '[data-vella-island="sidebar"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="topbar"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="subtabs"][data-vella-island-status="explicit-jsx"]',
  `[data-vella-island="${genericReportTab}"][data-vella-island-status="explicit-jsx"]`,
] : isGenericPageScreen ? [
  '[data-vella-island="sidebar"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="topbar"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="subtabs"][data-vella-island-status="explicit-jsx"]',
  `[data-vella-island="${genericPageIsland}"][data-vella-island-status="explicit-jsx"]`,
  ...(genericPageTab === 'promos' ? [
    '[data-vella-island="promos-calculator-card"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
    '[data-vella-island="promos-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
    '[data-vella-island="promos-table-body"][data-vella-island-status="explicit-jsx"]:not([data-vella-runtime-owner])',
  ] : []),
] : [
  '[data-vella-island="sidebar"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="topbar"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="subtabs"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="digest-brand-filter"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="global-period-control"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="export-dropdown"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="digest-balance-period-switch"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="manager-signal-panel"][data-vella-island-status="explicit-jsx"]',
  '[data-vella-island="digest"][data-vella-island-status="explicit-jsx"]',
]

const runtimeFunctionNames = isAbcScreen ? [
  '_goSubtabSilent',
  'goSubtab',
  'enhanceReportsDemo',
  'renderAbcDemoRows',
  'applyAbcFilter',
  'enhanceReportTableSorting',
  'showHelp',
  'closeHelp',
  'closeDrawer',
  'goDrawerTab',
  'goMiscStab',
  'openSkuRnpFromDrawer',
  'syncDrawerPriceInput',
  'recalcDrawerPricing',
  'resetDrawerSlider',
  'applyDrawerPrice',
  'toggleDetailCalc',
  'recalcMarginAnalysis',
  'setPriceBoundsBasis',
  'updatePriceBoundInput',
  'togglePromoBoost',
  'addDrawerComment',
  'openReportCommentsDrawer',
  'closeReportCommentsDrawer',
  'addReportComment',
] : isGenericReportScreen ? [
  '_goSubtabSilent',
  'goSubtab',
  'enhanceReportsDemo',
  'enhanceReportTableSorting',
  'applyGenericReportFilter',
  'showHelp',
  'openReportCommentsDrawer',
  'closeReportCommentsDrawer',
  'addReportComment',
] : isGenericPageScreen ? [
  '_goSubtabSilent',
  'goSubtab',
  'toggleDD',
  'showHelp',
  'showToast',
  'setGlobalPeriod',
  'openCalendarPopover',
  ...(genericPageTab === 'report-rules' ? [
    'syncThresholdInputs',
    'setThresholdPreset',
    'onThresholdInput',
    'resetThresholdDraft',
    'openThresholdPreview',
    'applyThresholdProfile',
    'closeModal',
  ] : []),
] : [
  '_goSubtabSilent',
  'goSubtab',
  'setDigestMode',
  'enhanceReportsDemo',
  'renderDigestBalance',
  'initDigestBalancePeriodControls',
  'setDigestBalanceScenario',
  'renderDigestPlanFact',
  'renderDigestManagerSignals',
  'toggleDigestBrandMenu',
  'setDigestBrandSelection',
  'setGlobalPeriod',
  'toggleDD',
  'openCalendarPopover',
]

const eventAttributes = [
  'onclick',
  'oninput',
  'onchange',
  'onkeydown',
  'onkeyup',
  'onmouseover',
  'onmouseenter',
  'onmouseleave',
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
    ['vite', 'preview', '--host', '127.0.0.1', '--port', '4179', '--strictPort'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'] },
  )
  child.stdout.on('data', (chunk) => process.stdout.write(chunk))
  child.stderr.on('data', (chunk) => process.stderr.write(chunk))
  return child
}

function sha256(value) {
  return createHash('sha256').update(value).digest('hex')
}

function countRegex(source, pattern) {
  return Array.from(source.matchAll(pattern)).length
}

function extractStaticRuntimeHints(html) {
  return {
    htmlHash: sha256(html),
    scriptCount: countRegex(html, /<script\b/gi),
    inlineHandlerCount: countRegex(html, /\son[a-z]+="/gi),
    localStorageReferences: Array.from(new Set(Array.from(html.matchAll(/localStorage\.(?:getItem|setItem|removeItem)\(['"]([^'"]+)['"]/g)).map((match) => match[1]))).sort(),
    functionDefinitions: runtimeFunctionNames
      .filter((name) => new RegExp(`function\\s+${name}\\s*\\(`).test(html) || new RegExp(`(?:const|let|var)\\s+${name}\\s*=`).test(html)),
    functionReferences: runtimeFunctionNames
      .filter((name) => new RegExp(`\\b${name}\\b`).test(html)),
  }
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

async function extractDomContract(page) {
  const screenRootSelector = isAbcScreen
    ? '#tab-abc'
    : isGenericReportScreen
      ? genericReportRoot
      : isGenericPageScreen
        ? genericPageRoot
        : '#tab-digest'
  return page.evaluate(({ selectorProbes, candidateOnlySelectorProbes, runtimeFunctionNames, eventAttributes, screenRootSelector }) => {
    function normalizeText(value) {
      return String(value || '').replace(/\s+/g, ' ').trim()
    }

    function elementPath(element) {
      const parts = []
      let current = element
      while (current && current.nodeType === Node.ELEMENT_NODE && current !== document.body) {
        const tag = current.tagName.toLowerCase()
        const id = current.id ? `#${current.id}` : ''
        const classes = Array.from(current.classList).slice(0, 3).map((item) => `.${item}`).join('')
        const sameTagSiblings = Array.from(current.parentElement?.children || []).filter((child) => child.tagName === current.tagName)
        const nth = sameTagSiblings.length > 1 ? `:nth-of-type(${sameTagSiblings.indexOf(current) + 1})` : ''
        parts.unshift(`${tag}${id}${id ? '' : classes}${nth}`)
        current = current.parentElement
      }
      return parts.join(' > ')
    }

    function classHistogram(root) {
      const histogram = {}
      for (const element of Array.from(root.querySelectorAll('*'))) {
        for (const className of Array.from(element.classList)) {
          histogram[className] = (histogram[className] || 0) + 1
        }
      }
      return Object.fromEntries(Object.entries(histogram).sort(([left], [right]) => left.localeCompare(right)))
    }

    function dataAttributes(element) {
      return Object.fromEntries(
        Array.from(element.attributes)
          .filter((attribute) => attribute.name.startsWith('data-'))
          .map((attribute) => [attribute.name, attribute.value]),
      )
    }

    function selectorSnapshot(selector) {
      const element = document.querySelector(selector)
      if (!element) return { selector, exists: false }
      const rect = element.getBoundingClientRect()
      return {
        selector,
        exists: true,
        tag: element.tagName.toLowerCase(),
        id: element.id || null,
        className: element.className || null,
        dataAttributes: dataAttributes(element),
        childElementCount: element.childElementCount,
        descendantElementCount: element.querySelectorAll('*').length,
        textHash: normalizeText(element.textContent).length ? undefined : null,
        rect: {
          width: Math.round(rect.width * 100) / 100,
          height: Math.round(rect.height * 100) / 100,
          top: Math.round(rect.top * 100) / 100,
          left: Math.round(rect.left * 100) / 100,
        },
      }
    }

    function handlerSnapshot(rootSelector) {
      const root = document.querySelector(rootSelector)
      if (!root) return []
      const handlerSelector = [...eventAttributes.map((attribute) => `[${attribute}]`), '[data-vella-react-handlers]'].join(',')
      return Array.from(root.querySelectorAll(handlerSelector)).map((element) => ({
        path: elementPath(element),
        tag: element.tagName.toLowerCase(),
        id: element.id || null,
        className: element.className || null,
        text: normalizeText(element.textContent).slice(0, 80),
        convertedReactHandlers: element.getAttribute('data-vella-react-handlers'),
        handlers: Object.fromEntries(eventAttributes
          .filter((attribute) => element.hasAttribute(attribute))
          .map((attribute) => [attribute, element.getAttribute(attribute)])),
      }))
    }

    function controlsSnapshot(rootSelector) {
      const root = document.querySelector(rootSelector)
      if (!root) return []
      return Array.from(root.querySelectorAll('button,input,select,textarea,[role="button"],[role="menuitem"]')).map((element) => ({
        path: elementPath(element),
        tag: element.tagName.toLowerCase(),
        id: element.id || null,
        className: element.className || null,
        type: element.getAttribute('type'),
        role: element.getAttribute('role'),
        ariaLabel: element.getAttribute('aria-label'),
        text: normalizeText(element.textContent).slice(0, 80),
        value: 'value' in element ? element.value : null,
        checked: 'checked' in element ? element.checked : null,
        disabled: element.hasAttribute('disabled'),
      }))
    }

    function activeStateSnapshot(rootSelector) {
      const root = document.querySelector(rootSelector)
      if (!root) return []
      return Array.from(root.querySelectorAll('.active,.open,[aria-hidden],[aria-selected],[data-digest-mode],[data-vella-island]')).map((element) => ({
        path: elementPath(element),
        tag: element.tagName.toLowerCase(),
        id: element.id || null,
        className: element.className || null,
        dataAttributes: dataAttributes(element),
        ariaHidden: element.getAttribute('aria-hidden'),
        ariaSelected: element.getAttribute('aria-selected'),
      }))
    }

    function rootVars() {
      const style = window.getComputedStyle(document.documentElement)
      return Array.from(document.styleSheets)
        .flatMap((sheet) => {
          try {
            return Array.from(sheet.cssRules || [])
          } catch {
            return []
          }
        })
        .filter((rule) => rule.selectorText === ':root')
        .flatMap((rule) => Array.from(rule.style).filter((name) => name.startsWith('--')))
        .sort()
        .reduce((acc, name) => {
          acc[name] = style.getPropertyValue(name).trim()
          return acc
        }, {})
    }

    const screenRoot = document.querySelector(screenRootSelector) || document.body
    return {
      url: location.href,
      title: document.title,
      totalElements: document.querySelectorAll('*').length,
      selectorProbes: selectorProbes.map(selectorSnapshot),
      candidateOnlySelectorProbes: candidateOnlySelectorProbes.map(selectorSnapshot),
      classHistogramScreen: classHistogram(screenRoot),
      eventHandlers: {
        shellAndScreen: handlerSnapshot('body'),
        screenOnly: handlerSnapshot(screenRootSelector),
      },
      controls: {
        screenOnly: controlsSnapshot(screenRootSelector),
        subtabsContext: controlsSnapshot('#subtabsContext'),
      },
      activeStates: activeStateSnapshot('body'),
      cssVariables: rootVars(),
      runtimeFunctions: Object.fromEntries(runtimeFunctionNames.map((name) => [name, typeof window[name]])),
      localStorageKeys: Object.keys(localStorage).sort(),
    }
  }, { selectorProbes, candidateOnlySelectorProbes, runtimeFunctionNames, eventAttributes, screenRootSelector })
}

async function extractPage(page, url) {
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 90_000 })
  } catch (error) {
    if (error?.name !== 'TimeoutError') throw error
    await page.goto(url, { waitUntil: 'commit', timeout: 90_000 })
    await page.waitForLoadState('domcontentloaded', { timeout: 15_000 }).catch(() => {})
  }
  await page.waitForSelector(isAbcScreen ? '#tab-abc, body' : isGenericReportScreen ? `${genericReportRoot}, body` : isGenericPageScreen ? `${genericPageRoot}, body` : '#tab-digest, body')
  await stabilize(page)
  return extractDomContract(page)
}

function collectGateFailures(report) {
  const failures = []

  const missingDefinitions = runtimeFunctionNames
    .filter((name) => !report.source.staticRuntimeHints.functionDefinitions.includes(name))
  if (missingDefinitions.length) {
    failures.push({
      scope: 'source',
      check: 'runtime-function-definitions',
      message: `Missing baseline function definitions: ${missingDefinitions.join(', ')}`,
    })
  }

  for (const state of report.states) {
    for (const sideName of ['reference', 'candidate']) {
      const side = state[sideName]
      const missingCommonSelectors = side.selectorProbes.filter((probe) => !probe.exists).map((probe) => probe.selector)
      if (missingCommonSelectors.length) {
        failures.push({
          state: state.name,
          side: sideName,
          check: 'common-selectors',
          message: `Missing common selectors: ${missingCommonSelectors.join(', ')}`,
        })
      }

      const missingRuntimeFunctions = Object.entries(side.runtimeFunctions)
        .filter(([, value]) => value === 'undefined')
        .map(([name]) => name)
      if (missingRuntimeFunctions.length) {
        failures.push({
          state: state.name,
          side: sideName,
          check: 'runtime-functions',
          message: `Missing runtime functions: ${missingRuntimeFunctions.join(', ')}`,
        })
      }
    }

    const missingCandidateOnlySelectors = state.candidate.candidateOnlySelectorProbes
      .filter((probe) => !probe.exists)
      .map((probe) => probe.selector)
    if (missingCandidateOnlySelectors.length) {
      failures.push({
        state: state.name,
        side: 'candidate',
        check: 'candidate-only-selectors',
        message: `Missing candidate island selectors: ${missingCandidateOnlySelectors.join(', ')}`,
      })
    }

    const referenceScreenHandlers = state.reference.eventHandlers.screenOnly.length
    const candidateScreenHandlers = state.candidate.eventHandlers.screenOnly.length
    const handlerCountIsInvalid = screensWithReactOwnedHandlerRebalance.has(screenName)
      ? false
      : isAbcScreen || isGenericReportScreen || screensWithReactOwnedHandlerGrowth.has(screenName)
      ? candidateScreenHandlers < referenceScreenHandlers
      : candidateScreenHandlers !== referenceScreenHandlers
    if (handlerCountIsInvalid) {
      failures.push({
        state: state.name,
        side: 'candidate',
        check: 'screen-handler-count',
        message: `Screen handler count invalid: reference=${referenceScreenHandlers}, candidate=${candidateScreenHandlers}`,
      })
    }

    const convertedScreenHandlers = state.candidate.eventHandlers.screenOnly
      .filter((handler) => handler.convertedReactHandlers).length
    if (!isGenericReportScreen && !isGenericPageScreen && convertedScreenHandlers === 0) {
      failures.push({
        state: state.name,
        side: 'candidate',
        check: 'react-converted-screen-handlers',
        message: 'No converted React handlers found in screen island.',
      })
    }
  }

  return failures
}

function summarizeGate(report, failures) {
  return {
    status: failures.length ? 'fail' : 'pass',
    failures,
    states: report.states.map((state) => ({
      name: state.name,
      commonSelectorFailures: {
        reference: state.reference.selectorProbes.filter((probe) => !probe.exists).length,
        candidate: state.candidate.selectorProbes.filter((probe) => !probe.exists).length,
      },
      candidateOnlySelectorFailures: state.candidate.candidateOnlySelectorProbes.filter((probe) => !probe.exists).length,
      screenHandlerReferenceCount: state.reference.eventHandlers.screenOnly.length,
      screenHandlerCandidateCount: state.candidate.eventHandlers.screenOnly.length,
      screenReactConvertedHandlerCount: state.candidate.eventHandlers.screenOnly.filter((handler) => handler.convertedReactHandlers).length,
      digestHandlerReferenceCount: state.reference.eventHandlers.screenOnly.length,
      digestHandlerCandidateCount: state.candidate.eventHandlers.screenOnly.length,
      digestReactConvertedHandlerCount: state.candidate.eventHandlers.screenOnly.filter((handler) => handler.convertedReactHandlers).length,
      runtimeFunctionFailures: {
        reference: Object.values(state.reference.runtimeFunctions).filter((value) => value === 'undefined').length,
        candidate: Object.values(state.candidate.runtimeFunctions).filter((value) => value === 'undefined').length,
      },
      screenControlCount: {
        reference: state.reference.controls.screenOnly.length,
        candidate: state.candidate.controls.screenOnly.length,
      },
      digestControlCount: {
        reference: state.reference.controls.screenOnly.length,
        candidate: state.candidate.controls.screenOnly.length,
      },
    })),
  }
}

async function main() {
  await mkdir(outputRoot, { recursive: true })
  const sourceHtml = await readFile(path.join(frontendRoot, 'public', 'vella-production.html'), 'utf8')
  const preview = shouldStartPreview ? startPreviewServer() : null
  if (preview) await waitForHttp(baseUrl)

  const browser = await chromium.launch()
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
    const stateContracts = []
    for (const state of states) {
      const reference = await extractPage(page, `${baseUrl}${state.referencePath}`)
      const candidate = await extractPage(page, `${baseUrl}${state.candidatePath}`)
      stateContracts.push({
        name: state.name,
        referencePath: state.referencePath,
        candidatePath: state.candidatePath,
        reference,
        candidate,
      })
    }

    const report = {
      screen: screenName,
      generatedAt: new Date().toISOString(),
      source: {
        htmlBaseline: 'frontend/public/vella-production.html',
        staticRuntimeHints: extractStaticRuntimeHints(sourceHtml),
      },
      states: stateContracts,
    }
    const failures = collectGateFailures(report)
    report.gate = summarizeGate(report, failures)

    await writeFile(path.join(outputRoot, 'page-contract.json'), `${JSON.stringify(report, null, 2)}\n`)
    console.log(`Vella page contract: ${report.gate.status}`)
    console.log(`Report: ${path.relative(projectRoot, path.join(outputRoot, 'page-contract.json'))}`)
    if (failures.length) {
      for (const failure of failures) {
        console.error(`- ${failure.state || failure.scope}/${failure.side || 'n/a'} ${failure.check}: ${failure.message}`)
      }
      process.exitCode = 1
    }
  } finally {
    await browser.close()
    if (preview) preview.kill()
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
