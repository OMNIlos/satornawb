/* Label generation uses the site's existing UI in the seller's session. No
 * private API contract, download UUID, cookies or transport code is invented. */
;(function (root) {
  function downloadUrl(value) {
    try {
      const url = new URL(value, 'https://www.avito.ru')
      return url.origin === 'https://www.avito.ru' && !url.username && !url.password &&
        /^\/web\/1\/orders\/labels\/[a-zA-Z0-9-]+\/download\/?$/.test(url.pathname) ? url.href : null
    } catch { return null }
  }

  // Runs in MAIN world; observes only label response URLs, never auth headers.
  function observeDownloads() {
    window.__satornaLabels?.restore?.()
    const originalFetch = window.fetch, originalOpen = window.open
    const originalXhrOpen = XMLHttpRequest.prototype.open
    const state = { urls: [], restore: null }
    const capture = value => {
      if (typeof value !== 'string') return
      try {
        const url = new URL(value, location.origin)
        if (url.origin === 'https://www.avito.ru' && /^\/web\/1\/orders\/labels\/[a-zA-Z0-9-]+\/download\/?$/.test(url.pathname) && !state.urls.includes(url.href)) state.urls.push(url.href)
      } catch { /* Not a URL. */ }
    }
    const inspect = (value, depth = 0) => {
      if (depth > 6) return
      if (typeof value === 'string') capture(value)
      else if (value && typeof value === 'object') Object.values(value).slice(0, 100).forEach(v => inspect(v, depth + 1))
    }
    window.fetch = async function (...args) {
      const response = await originalFetch.apply(this, args)
      const url = String(response.url || '')
      capture(url)
      if (url.includes('/orders/labels') && response.headers.get('content-type')?.includes('json')) {
        response.clone().json().then(inspect).catch(() => {})
      }
      return response
    }
    window.open = function (url, ...args) { capture(String(url || '')); return originalOpen.call(this, url, ...args) }
    XMLHttpRequest.prototype.open = function (...args) {
      if (String(args[1] || '').includes('/orders/labels')) this.addEventListener('load', () => {
        capture(this.responseURL)
        try { inspect(this.responseType === 'json' ? this.response : JSON.parse(this.responseText)) } catch { /* PDF body isn't logged/read as text. */ }
      }, { once: true })
      return originalXhrOpen.apply(this, args)
    }
    const wrappedFetch = window.fetch, wrappedOpen = window.open, wrappedXhrOpen = XMLHttpRequest.prototype.open
    state.restore = () => {
      if (window.fetch === wrappedFetch) window.fetch = originalFetch
      if (window.open === wrappedOpen) window.open = originalOpen
      if (XMLHttpRequest.prototype.open === wrappedXhrOpen) XMLHttpRequest.prototype.open = originalXhrOpen
    }
    window.__satornaLabels = state
    setTimeout(() => state.restore(), 60000)
    return true
  }

  // Runs in ISOLATED world. Only the print-labels route and exact label action.
  async function selectAndGenerate() {
    if (location.origin !== 'https://www.avito.ru' || location.pathname !== '/orders/print-labels') throw new Error('Откройте страницу печати этикеток Авито')
    const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
    let stable = 0, lastHeight = 0
    for (let i = 0; i < 40 && stable < 3; i++) {
      window.scrollTo(0, document.documentElement.scrollHeight)
      await pause(350)
      const height = document.documentElement.scrollHeight
      stable = height === lastHeight ? stable + 1 : 0
      lastHeight = height
    }
    for (const checkbox of document.querySelectorAll('input[type="checkbox"], [role="checkbox"]')) {
      const checked = checkbox.checked === true || checkbox.getAttribute('aria-checked') === 'true'
      if (!checked && !checkbox.disabled && checkbox.getAttribute('aria-disabled') !== 'true') { checkbox.click(); await pause(60) }
    }
    await pause(500)
    const buttons = [...document.querySelectorAll('button, [role="button"]')].filter(el =>
      /^Распечатать\s+\d+\s+этикет/iu.test((el.innerText || el.textContent || '').trim()) && !el.disabled)
    if (buttons.length !== 1) throw new Error('Не найдена однозначная кнопка «Распечатать … этикеток». Проверьте список Авито.')
    const count = Number(buttons[0].textContent.match(/\d+/)?.[0] || 0)
    if (!count || count > 100) throw new Error('За один сбор поддерживается от 1 до 100 этикеток')
    buttons[0].click() // Generates PDF only; never invokes window.print().
    return count
  }

  async function boundedPdf(response) {
    if (!response.ok || !response.body) throw new Error('Авито не отдало PDF этикеток')
    const chunks = [], reader = response.body.getReader()
    let size = 0
    try {
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        size += value.byteLength
        if (size > 12000000) throw new Error('PDF этикеток превышает 12 МБ')
        chunks.push(value)
      }
    } finally { await reader.cancel().catch(() => {}) }
    const data = new Uint8Array(size)
    let offset = 0
    for (const chunk of chunks) { data.set(chunk, offset); offset += chunk.length }
    if (new TextDecoder().decode(data.slice(0, 5)) !== '%PDF-') throw new Error('Вместо PDF Авито вернуло другую страницу')
    return data
  }
  root.SatornaLabels = { downloadUrl, observeDownloads, selectAndGenerate, boundedPdf }
})(typeof globalThis === 'object' ? globalThis : this)
