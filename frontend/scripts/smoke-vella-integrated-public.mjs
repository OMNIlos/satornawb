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
const outputRoot = path.resolve(projectRoot, 'outputs', `vella-integrated-public-smoke-${stamp}`)
const baseUrl = process.env.VELLA_BASE_URL || 'http://127.0.0.1:4186'
const shouldStartPreview = !process.env.VELLA_BASE_URL

const forbiddenText = [
  'mock',
  'parser',
  'парсер',
  'backend discovery',
  'apply blocked',
  'Guardrail regression',
  '1С · финансы и УУ',
  'финальный P&L',
  'Страница показывает',
  'Экран объясняет',
]

const routes = [
  {
    id: 'wb-sources',
    path: '/wb/sources',
    navTab: 'sources',
    contentTab: 'sources',
    requiredText: ['1С · Движение денежных средств', 'Правила статей ДДС', 'Подключение 1С', 'Шаблон Excel'],
  },
  {
    id: 'wb-expenses',
    path: '/wb/reports/expenses',
    navTab: 'expenses',
    contentTab: 'expenses',
    requiredText: ['Все расходы', 'P&L учтено', 'Чистая прибыль', 'Требует сверки', 'Добавить расход'],
  },
  {
    id: 'wb-repricer-stats',
    path: '/wb/repricer/stats',
    navTab: 'repricer-stats',
    contentTab: 'repricer-stats',
    requiredText: ['Все SKU', 'Можно пересчитать', 'Цена заблокирована', 'Корзины растут', 'Источник не готов'],
  },
  {
    id: 'avito-notifications',
    path: '/avito/notifications',
    navTab: 'avito-notifications',
    contentTab: 'notifications',
    requiredText: ['Новые Авито', 'Блокировки Авито', 'кошельки', 'чаты'],
  },
  {
    id: 'avito-reviews',
    path: '/avito/reviews',
    navTab: 'avito-reviews',
    contentTab: 'avito-reviews',
    requiredText: ['Неотвеченные', 'Требуют проверки', 'Автоответы сегодня', 'Заблокировано'],
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
      // retry
    }
    await sleep(250)
  }
  throw new Error(`Timed out waiting for ${url}`)
}

function startPreviewServer() {
  const distHtml = path.join(frontendRoot, 'dist', 'index.html')
  if (!existsSync(distHtml)) {
    throw new Error('frontend/dist is missing. Run npm run build first or set VELLA_BASE_URL.')
  }

  return spawn(
    process.platform === 'win32' ? 'npx.cmd' : 'npx',
    ['vite', 'preview', '--host', '127.0.0.1', '--port', '4186', '--strictPort'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'] },
  )
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
  await page.waitForTimeout(350)
}

async function goto(page, pathname) {
  await page.goto(`${baseUrl}${pathname}`, { waitUntil: 'domcontentloaded', timeout: 90_000 })
  await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => {})
  await stabilize(page)
}

function hasFailure(results) {
  return results.some((result) => result.status === 'fail' || result.checks.some((check) => check.pass === false))
}

async function checkRoute(browser, route) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 920 }, deviceScaleFactor: 1 })
  await goto(page, route.path)
  const routeDir = path.join(outputRoot, route.id)
  await mkdir(routeDir, { recursive: true })
  await page.screenshot({ path: path.join(routeDir, 'desktop.png'), fullPage: false })

  if (route.runtime === 'react-final') {
    const bodyText = await page.locator('body').innerText({ timeout: 10_000 }).catch(() => '')
    const checks = []
    const isSources = route.id === 'wb-sources'
    const isExpenses = route.id === 'wb-expenses'
    const isRepricerStats = route.id === 'wb-repricer-stats'
    checks.push({ name: 'React-final root', pass: await page.locator('.vella-final-root').count() === 1 })
    checks.push({ name: 'not HTML parity root', pass: await page.locator('[data-vella-parity-root]').count() === 0 })
    checks.push({ name: 'no login redirect', pass: !page.url().includes('/login'), value: page.url() })
    if (isSources) {
      checks.push({ name: 'sources is not inside report tabs', pass: await page.locator('.vella-final-subtab').count() === 0 })
      checks.push({ name: 'reports group collapsed on sources', pass: await page.locator('.vella-final-nav-sub').count() === 0 })
      checks.push({
        name: 'sources left nav active',
        pass: await page.locator('.vella-nav-button.active', { hasText: 'Источники и загрузки' }).count() === 1,
      })
    }
    if (isExpenses) {
      checks.push({ name: 'reports group open on expenses', pass: await page.locator('.vella-final-nav-sub').count() === 1 })
      checks.push({
        name: 'expenses report tab active',
        pass: await page.locator('.vella-final-subtab.active', { hasText: 'Расходы' }).count() === 1,
      })
    }
    if (isRepricerStats) {
      checks.push({ name: 'repricer group open on diagnostics', pass: await page.locator('.vella-final-nav-sub').count() === 1 })
      checks.push({
        name: 'repricer diagnostics tab active',
        pass: await page.locator('.vella-final-subtab.active', { hasText: 'Диагностика цен' }).count() === 1,
      })
      checks.push({
        name: 'repricer diagnostics left nav active',
        pass: await page.locator('.vella-nav-button.active', { hasText: 'Диагностика цен' }).count() === 1,
      })
    }

    for (const text of route.requiredText) {
      checks.push({ name: `required text ${text}`, pass: bodyText.includes(text) })
    }
    for (const text of forbiddenText) {
      checks.push({ name: `forbidden text ${text}`, pass: !bodyText.includes(text) })
    }
    checks.push({ name: 'no explanatory source copy', pass: !bodyText.includes('Страница показывает') && !bodyText.includes('Экран объясняет') && !bodyText.includes('Что откуда тянется') })
    if (isSources) {
      checks.push({ name: 'depends cells use non-button badges', pass: await page.locator('td:has-text("Расходы"):has-text("P&L") button').count() === 0 })
    }
    checks.push({
      name: 'table header sticky',
      pass: await page.locator('thead th').first().evaluate((node) => getComputedStyle(node).position) === 'sticky',
    })

    const tableRows = await page.locator('[data-report-row]').count()
    checks.push({ name: 'React table has rows', pass: tableRows > 0, value: tableRows })
    const status = checks.every((check) => check.pass) ? 'pass' : 'fail'
    await page.close()
    return { id: route.id, path: route.path, runtime: route.runtime, status, checks }
  }

  const activeTab = page.locator(`#tab-${route.contentTab}.tab-content.active`)
  const activeTabText = await activeTab.innerText({ timeout: 10_000 }).catch(() => '')
  const checks = []

  checks.push({ name: 'canonical parity root', pass: await page.locator('[data-vella-parity-root]').count() === 1 })
  checks.push({ name: 'no standalone React-final shell', pass: await page.locator('[data-vella-shell], .vella-final-root').count() === 0 })
  checks.push({ name: 'no login redirect', pass: !page.url().includes('/login'), value: page.url() })
  checks.push({ name: `active content tab ${route.contentTab}`, pass: await activeTab.count() === 1 })
  checks.push({
    name: `left nav active ${route.navTab}`,
    pass: await page.locator(`.nav-item[data-tab="${route.navTab}"].active, .nav-item[data-tab="${route.navTab}"].nav-sub-active`).count() > 0,
  })
  checks.push({
    name: `subtab active ${route.navTab}`,
    pass: await page.locator(`.subtab[data-tab="${route.navTab}"].active`).count() > 0,
  })

  for (const text of route.requiredText) {
    checks.push({ name: `required text ${text}`, pass: activeTabText.includes(text) })
  }
  for (const text of forbiddenText) {
    checks.push({ name: `forbidden text ${text}`, pass: !activeTabText.includes(text) })
  }

  const tableRows = await activeTab.locator('tbody tr, [data-report-row]').count()
  checks.push({ name: 'active tab has rows', pass: tableRows > 0, value: tableRows })

  const status = checks.every((check) => check.pass) ? 'pass' : 'fail'
  await page.close()
  return { id: route.id, path: route.path, navTab: route.navTab, contentTab: route.contentTab, status, checks }
}

async function main() {
  let server
  if (shouldStartPreview) {
    server = startPreviewServer()
    server.stdout.on('data', (chunk) => process.stdout.write(chunk))
    server.stderr.on('data', (chunk) => process.stderr.write(chunk))
    await waitForHttp(baseUrl)
  }

  await mkdir(outputRoot, { recursive: true })
  const browser = await chromium.launch()
  const results = []

  try {
    for (const route of routes) {
      const result = await checkRoute(browser, route)
      results.push(result)
      console.log(`${route.id}: ${result.status}`)
    }
  } finally {
    await browser.close()
    server?.kill('SIGTERM')
  }

  const report = { generatedAt: new Date().toISOString(), baseUrl, status: hasFailure(results) ? 'fail' : 'pass', results }
  await writeFile(path.join(outputRoot, 'integrated-public-smoke-report.json'), JSON.stringify(report, null, 2))

  if (report.status !== 'pass') {
    console.error(JSON.stringify(report.results.filter((result) => result.status !== 'pass'), null, 2))
    process.exit(1)
  }
  console.log(`Vella integrated public smoke passed: ${outputRoot}`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
