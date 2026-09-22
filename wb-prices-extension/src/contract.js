(() => {
  'use strict'
  const WB_ORIGIN = 'https://www.wildberries.ru'
  const SOURCE = 'satorna-wb-prices-v1'
  const integer = (value) => Number.isSafeInteger(value) && value > 0
  const key = (item) => `${item.nmId}:${item.sizeId}`

  function cardNmId(value) {
    try {
      const url = new URL(value)
      const match = url.pathname.match(/^\/catalog\/(\d+)\/detail\.aspx$/)
      const id = Number(match?.[1])
      return url.origin === WB_ORIGIN && !url.username && !url.password && integer(id) ? id : null
    } catch { return null }
  }

  function sellerId(value) {
    try {
      const url = new URL(value)
      const id = Number(url.pathname.match(/^\/seller\/(\d+)\/?$/)?.[1])
      return url.origin === WB_ORIGIN && !url.username && !url.password && integer(id) ? id : null
    } catch { return null }
  }

  function pageIdentity(value) {
    if (integer(value)) return `card:${value}`
    const nmId = cardNmId(value)
    if (nmId) return `card:${nmId}`
    const supplier = sellerId(value)
    return supplier ? `seller:${supplier}` : null
  }

  function catalogPage(value, pageUrl) {
    try {
      const url = new URL(value, pageUrl)
      const supplier = sellerId(pageUrl)
      const page = Number(url.searchParams.get('page'))
      return supplier && url.origin === WB_ORIGIN && !url.username && !url.password
        && url.pathname === '/__internal/u-catalog/sellers/v4/catalog' && url.searchParams.get('curr') === 'rub'
        && url.searchParams.get('supplier') === String(supplier) && integer(page) ? page : null
    } catch { return null }
  }

  function isDetailRequest(value, pageUrl) {
    try {
      const url = new URL(value, pageUrl)
      if (catalogPage(value, pageUrl)) return true
      if (!pageIdentity(pageUrl) || url.origin !== WB_ORIGIN || url.username || url.password || url.searchParams.get('curr') !== 'rub') return false
      const ids = url.searchParams.get('nm') || ''
      return ['/__internal/u-card/cards/v4/detail', '/__internal/u-card/cards/v4/list'].includes(url.pathname)
        && /^\d+(;\d+)*$/.test(ids) && ids.split(';').length <= 1000 && ids.split(';').every((id) => integer(Number(id)))
    } catch { return false }
  }

  function parseDetail(payload, pageUrl, requestUrl) {
    if (!isDetailRequest(requestUrl, pageUrl) || !Array.isArray(payload?.products) || payload.products.length > 1000) return []
    const requested = catalogPage(requestUrl, pageUrl) ? null : new Set(new URL(requestUrl, pageUrl).searchParams.get('nm').split(';').map(Number))
    const seen = new Set()
    const items = []
    for (const product of payload.products) {
      if (!integer(product?.id) || (requested && !requested.has(product.id)) || !Array.isArray(product.sizes) || product.sizes.length > 100) continue
      for (const size of product.sizes) {
        const offer = `${product.id}:${size?.optionId}`
        if (!integer(size?.optionId) || !integer(size?.price?.product) || seen.has(offer)) continue
        seen.add(offer)
        // price.wallet is not a final wallet price; product is already kopecks.
        const item = { nmId: product.id, sizeId: size.optionId, buyerPriceNoWalletKopecks: size.price.product }
        if (integer(product.supplierId)) item.supplierId = product.supplierId
        items.push(item)
        if (items.length > 10000) return []
      }
    }
    return items
  }

  function sanitizePageMessage(value, page) {
    if (!pageIdentity(page) || value?.source !== SOURCE) return null
    if (value.type === 'blocked' && ['http_403', 'http_429', 'challenge'].includes(value.code)) {
      return { type: 'blocked', code: value.code }
    }
    const isCatalog = Boolean(sellerId(page) && integer(value.catalogPage) && Number.isSafeInteger(value.productCount) && value.productCount >= 0 && value.productCount <= 1000)
    const loadedNmId = integer(value.loadedNmId) && value.loadedNmId === cardNmId(page) ? value.loadedNmId : null
    if (value.type !== 'observations' || !Array.isArray(value.items) || (!value.items.length && !isCatalog && !loadedNmId) || value.items.length > 10000) return null
    const seen = new Set()
    const items = []
    for (const item of value.items) {
      if (!integer(item?.nmId) || !integer(item.sizeId) || !integer(item.buyerPriceNoWalletKopecks) || seen.has(key(item))) return null
      seen.add(key(item))
      const clean = { nmId: item.nmId, sizeId: item.sizeId, buyerPriceNoWalletKopecks: item.buyerPriceNoWalletKopecks }
      if (integer(item.supplierId)) clean.supplierId = item.supplierId
      items.push(clean)
    }
    return { type: 'observations', items, ...(isCatalog ? { catalogPage: value.catalogPage, productCount: value.productCount } : {}), ...(loadedNmId ? { loadedNmId } : {}) }
  }

  function validateCatalogPage(value, page, expected = null, now = Date.now()) {
    if (!value || !integer(value.marketplaceAccountId) || typeof value.goodsRevision !== 'string'
      || !value.goodsRevision || value.goodsRevision.length > 256 || value.page !== page || value.pageSize !== 100
      || !Number.isSafeInteger(value.total) || value.total < 0 || value.total > 100000 || !integer(value.maxAgeSeconds)
      || value.maxAgeSeconds > 1800 || !Array.isArray(value.items)
      || value.items.length !== Math.min(100, Math.max(0, value.total - (page - 1) * 100))) throw new Error('catalog_invalid')
    if (expected && ['marketplaceAccountId', 'goodsRevision', 'total', 'maxAgeSeconds'].some((field) => expected[field] !== value[field])) throw new Error('catalog_changed')
    const seen = new Set()
    const items = value.items.map((item) => {
      if (!integer(item?.nmId) || !integer(item.sizeId) || !integer(item.sellerPriceKopecks) || seen.has(key(item))) throw new Error('catalog_invalid')
      seen.add(key(item))
      const observed = Date.parse(item.sellerPriceObservedAt)
      if (!Number.isFinite(observed) || now - observed > value.maxAgeSeconds * 1000 || observed > now + 30000) throw new Error('catalog_stale')
      return { nmId: item.nmId, sizeId: item.sizeId, sellerPriceKopecks: item.sellerPriceKopecks, sellerPriceObservedAt: item.sellerPriceObservedAt }
    })
    return { marketplaceAccountId: value.marketplaceAccountId, goodsRevision: value.goodsRevision, page, pageSize: 100, total: value.total, maxAgeSeconds: value.maxAgeSeconds, items }
  }

  function snapshotItems(observations, catalog, observedAt) {
    const offers = new Map(catalog.map((item) => [key(item), item]))
    const seen = new Set()
    const items = []
    for (const observation of observations) {
      const offer = offers.get(key(observation))
      if (!offer || !integer(observation.buyerPriceNoWalletKopecks)
        || observation.buyerPriceNoWalletKopecks > offer.sellerPriceKopecks || seen.has(key(observation))) continue
      seen.add(key(observation))
      items.push({ nmId: offer.nmId, sizeId: offer.sizeId, sellerPriceKopecks: offer.sellerPriceKopecks,
        buyerPriceNoWalletKopecks: observation.buyerPriceNoWalletKopecks, buyerPriceWithWalletKopecks: null, observedAt })
    }
    return { items, ignored: observations.length - items.length }
  }

  function isTrustedPopupSender(sender, extensionId) {
    const url = `chrome-extension://${extensionId}/src/popup.html`
    return sender?.id === extensionId && sender.url === url
      && (!sender.tab || (sender.frameId === 0 && sender.tab.url === url))
  }

  function isTrustedPageSender(sender, extensionId, tabId, page) {
    const expected = pageIdentity(page)
    return sender?.id === extensionId && sender.frameId === 0 && expected !== null
      && sender.tab?.id === tabId && pageIdentity(sender.url) === expected && pageIdentity(sender.tab.url) === expected
  }

  globalThis.WbPricesContract = Object.freeze({ SOURCE, WB_ORIGIN, integer, key, cardNmId, sellerId, pageIdentity, catalogPage, isDetailRequest,
    parseDetail, sanitizePageMessage, validateCatalogPage, snapshotItems, isTrustedPopupSender, isTrustedPageSender })
})()
