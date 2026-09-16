(() => {
  'use strict'
  const contract = globalThis.WbPricesContract
  const post = globalThis.postMessage.bind(globalThis)
  const emit = (message) => post({ source: contract.SOURCE, ...message }, contract.WB_ORIGIN)

  function report(status, payload, requestUrl) {
    if (!contract.isDetailRequest(requestUrl, location.href)) return
    if (status === 403 || status === 429) return emit({ type: 'blocked', code: `http_${status}` })
    if (status !== 200) return
    const items = contract.parseDetail(payload, location.href, requestUrl)
    const catalogPage = contract.catalogPage(requestUrl, location.href)
    if (catalogPage && Array.isArray(payload?.products) && payload.products.length <= 1000) {
      emit({ type: 'observations', items, catalogPage, productCount: payload.products.length })
    } else if (items.length) emit({ type: 'observations', items })
  }

  const originalFetch = globalThis.fetch
  globalThis.fetch = function (...args) {
    const result = Reflect.apply(originalFetch, this, args)
    const requestUrl = typeof args[0] === 'string' || args[0] instanceof URL ? String(args[0]) : args[0]?.url
    const method = String(args[1]?.method || args[0]?.method || 'GET').toUpperCase()
    if (method === 'GET' && contract.isDetailRequest(requestUrl, location.href)) {
      void result.then(async (response) => {
        if (response.url && !contract.isDetailRequest(response.url, location.href)) return
        if (response.status === 403 || response.status === 429) return report(response.status, null, requestUrl)
        if (response.status === 200) report(200, await response.clone().json(), requestUrl)
      }).catch(() => {})
    }
    return result
  }

  const originalOpen = XMLHttpRequest.prototype.open
  XMLHttpRequest.prototype.open = function (method, url, ...args) {
    if (String(method).toUpperCase() === 'GET' && contract.isDetailRequest(String(url), location.href)) {
      this.addEventListener('load', () => {
        if (!contract.isDetailRequest(this.responseURL, location.href)) return
        try {
          const payload = this.status === 200
            ? (this.responseType === 'json' ? this.response : JSON.parse(this.responseText)) : null
          report(this.status, payload, this.responseURL)
        } catch { /* A non-JSON response is not a price observation. */ }
      }, { once: true })
    }
    return Reflect.apply(originalOpen, this, [method, url, ...args])
  }
})()
