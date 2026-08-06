const COLOR_HINTS = [
  ['черн', 'черный'],
  ['бел', 'белый'],
  ['молоч', 'молочный'],
  ['сер', 'серый'],
  ['графит', 'графит'],
  ['красн', 'красный'],
  ['син', 'синий'],
  ['голуб', 'голубой'],
  ['зелен', 'зеленый'],
  ['розов', 'розовый'],
  ['беж', 'бежевый'],
  ['корич', 'коричневый'],
  ['фиолет', 'фиолетовый'],
]

const SIZE_VALUES = ['5XL', '4XL', '3XL', '2XL', 'XXL', 'XL', 'XS', 'S', 'M', 'L']
const DEFAULT_COLLECT_OPTIONS = {
  photoMode: 'one',
  colorFromDescription: true,
  sizeMode: 'description',
  articleFromDescription: true,
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[<>&"]/g, (char) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;' }[char]))
}

function logEvent(level, message, data = {}) {
  const method = level === 'error' ? 'error' : level === 'warn' ? 'warn' : 'info'
  console[method]('[Satorna Avito]', message, data)
  try {
    chrome.runtime.sendMessage({ type: 'AVITO_LOG', level, message, data })
  } catch (_error) {
    // Console logging still works if the background worker is unavailable.
  }
}

function textOf(node) {
  return String(node?.innerText || node?.textContent || '').replace(/\s+/g, ' ').trim()
}

function first(root, selectors) {
  for (const selector of selectors) {
    const found = root.querySelector(selector)
    if (found) return found
  }
  return null
}

function all(root, selectors) {
  const result = []
  selectors.forEach((selector) => root.querySelectorAll(selector).forEach((node) => result.push(node)))
  return Array.from(new Set(result))
}

function absoluteUrl(value) {
  if (!value) return null
  try {
    return new URL(value, location.href).toString()
  } catch {
    return null
  }
}

function isAvitoListingUrl(value) {
  const url = absoluteUrl(value)
  if (!url) return false
  try {
    const parsed = new URL(url)
    if (parsed.hostname !== 'www.avito.ru') return false
    if (/\/orders(?:\/|$)/i.test(parsed.pathname)) return false
    return /_[0-9]{5,}(?:\/)?$/i.test(parsed.pathname) || /\/items\/[0-9]+(?:\/)?$/i.test(parsed.pathname)
  } catch {
    return false
  }
}

function listingUrl(value) {
  return isAvitoListingUrl(value) ? absoluteUrl(value) : null
}

function decodedHtml(root) {
  return String(root.documentElement?.innerHTML || '')
    .replace(/\\u002F/g, '/')
    .replace(/\\\//g, '/')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
}

function srcsetUrl(value) {
  const text = String(value || '').trim()
  if (!text) return null
  const candidates = text.split(',').map((part) => part.trim().split(/\s+/)[0]).filter(Boolean)
  return candidates.length ? absoluteUrl(candidates[candidates.length - 1]) : null
}

function imageSource(image) {
  return absoluteUrl(
    image?.currentSrc
    || image?.src
    || image?.getAttribute?.('src')
    || image?.getAttribute?.('data-src')
    || image?.getAttribute?.('data-url')
  ) || srcsetUrl(image?.getAttribute?.('srcset') || image?.getAttribute?.('data-srcset'))
}

function metaContent(root, selector) {
  return root.querySelector(selector)?.getAttribute('content')?.trim() || null
}

function parseKopecks(text) {
  const match = String(text || '').replace(/\s+/g, '').match(/(\d+)(?:[,.](\d{1,2}))?\s*(?:₽|руб)/i)
  if (!match) return null
  const rub = Number(match[1])
  const kop = Number((match[2] || '0').padEnd(2, '0'))
  return Number.isFinite(rub) ? rub * 100 + (Number.isFinite(kop) ? kop : 0) : null
}

function parseArticle(text) {
  const value = String(text || '')
  const match = value.match(/(?:арт(?:икул)?|sku|id\s*товара)\s*[:#№-]?\s*([a-zа-яё0-9_-]{2,40})/iu)
  return match?.[1] || null
}

function parseColor(text) {
  const lower = String(text || '').toLocaleLowerCase('ru-RU')
  const explicit = lower.match(/цвет\s*[:—-]?\s*([а-яёa-z -]{3,24})/iu)
  if (explicit?.[1]) return explicit[1].trim().split(/[,.]/)[0]
  const found = COLOR_HINTS.find(([hint]) => lower.includes(hint))
  return found?.[1] || null
}

function parseSize(text) {
  const value = String(text || '')
  const explicit = Array.from(value.matchAll(/(?:размер|р-р|size)\s*[:—-]?\s*([0-9]{2}(?:-[0-9]{2})?(?:\s*\([^)]+\))?|[2-5]?XL|XXL|XS|[SML])/giu)).pop()
  if (explicit?.[1]) return explicit[1].toUpperCase()
  const numeric = Array.from(value.matchAll(/\b([3-6][0-9](?:-[3-6][0-9])?)\b/gu)).pop()
  if (numeric?.[1]) return numeric[1]
  const upper = ` ${value.toUpperCase()} `
  const found = SIZE_VALUES.find((size) => upper.includes(` ${size} `))
  return found || null
}

function normalizedTitle(value) {
  return String(value || '')
    .toLocaleLowerCase('ru-RU')
    .replace(/[^a-zа-яё0-9]+/giu, ' ')
    .trim()
}

function orderIdentity(text, root) {
  const attrId = root.getAttribute('data-order-id') || root.getAttribute('data-id')
  const href = first(root, ['a[href*="/orders/"]'])?.getAttribute('href') || ''
  const hrefId = href.match(/orders\/([a-zа-яё0-9_-]+)/i)?.[1]
  const textId = text.match(/(?:заказ|отправление|№)\s*[:#№-]?\s*([a-zа-яё0-9_-]{4,})/iu)?.[1]
  return attrId || hrefId || textId || null
}

function marketplaceIdentity(text) {
  return text.match(/\b([0-9]{5,})\b/u)?.[1] || null
}

function trackNumber(text) {
  const value = String(text || '')
  return (
    value.match(/\b(P\d{2}\s?\d{3}\s?\d{3}\s?\d{3}R?)\b/iu)?.[1]
    || value.match(/\b(103\s?\d{3}\s?\d{5})\b/u)?.[1]
    || value.match(/\b(\d{3}\s?\d{3}\s?\d{3}\s?\d{5})\b/u)?.[1]
    || value.match(/(?:трек|track|отслеживан(?:ие|ия))\s*[:#№-]?\s*([a-z0-9 -]{5,})/iu)?.[1]
    || null
  )
}

function deliveryService(text) {
  if (/яндекс\s+доставк/iu.test(text)) return 'Яндекс Доставка'
  if (/сдэк/iu.test(text)) return 'СДЭК'
  if (/почта\s+россии/iu.test(text)) return 'Почта России'
  if (/авито/iu.test(text)) return 'Авито'
  return null
}

function statusFromText(text) {
  const value = String(text || '').toLocaleLowerCase('ru-RU')
  if (value.includes('возврат')) return 'on_return'
  if (value.includes('отправьте заказ')) return 'ready_to_ship'
  if (value.includes('ждёт выдачи') || value.includes('ждет выдачи') || value.includes('едет к покупателю')) return 'in_transit'
  if (value.includes('напишите поддержке') || value.includes('спор')) return 'in_dispute'
  if (value.includes('заказ отмен')) return 'canceled'
  if (value.includes('заверш')) return 'closed'
  return null
}

function itemUrl(root) {
  const link = first(root, [
    'a[data-marker*="item"]',
    'a[href*="/items/"]',
    'a[href*="/avito.ru/"][href*="_"]',
  ])
  return absoluteUrl(link?.getAttribute('href'))
}

function itemIdFromUrl(url) {
  if (!url) return null
  return url.match(/_(\d{5,})(?:\?|$)/)?.[1] || url.match(/[?&]itemId=(\d+)/)?.[1] || null
}

function itemTitle(root, text) {
  const titleNode = first(root, [
    '[data-marker*="item-title"]',
    '[data-marker*="title"]',
    'a[href*="/items/"]',
    'h1',
    'h2',
    'h3',
  ])
  return textOf(titleNode) || text.split(/[.!?]/)[0]?.slice(0, 120) || 'Товар Авито'
}

function imageUrl(root) {
  return imageUrls(root, 1)[0] || null
}

function imageUrls(root, limit = 1) {
  const images = all(root, [
    '[data-marker="images-row"] img',
    'img[data-testid="image"]',
    'img[data-marker*="image"]',
    'img[src*="avito.st"]',
    'img[srcset*="avito.st"]',
    'img[src]',
  ])
  return images
    .map(imageSource)
    .filter(Boolean)
    .filter((value, index, array) => array.indexOf(value) === index)
    .slice(0, limit)
}

function chatText(root) {
  const nodes = all(root, [
    '[data-marker*="chat"]',
    '[data-marker*="message"]',
    '[class*="chat"]',
    '[class*="message"]',
  ])
  return nodes.map(textOf).filter((text) => text.length > 8).join('\n').slice(0, 4000) || null
}

function normalizeOptions(options) {
  const raw = { ...DEFAULT_COLLECT_OPTIONS, ...(options || {}) }
  return {
    photoMode: ['none', 'one', 'two'].includes(raw.photoMode) ? raw.photoMode : DEFAULT_COLLECT_OPTIONS.photoMode,
    colorFromDescription: Boolean(raw.colorFromDescription),
    sizeMode: ['none', 'description', 'chat_ai'].includes(raw.sizeMode) ? raw.sizeMode : DEFAULT_COLLECT_OPTIONS.sizeMode,
    articleFromDescription: Boolean(raw.articleFromDescription),
  }
}

function requestedMissing(item, options) {
  return {
    imageUrl: options.photoMode === 'none' ? false : !item.imageUrl,
    size: options.sizeMode === 'none' ? false : !item.size,
    color: !options.colorFromDescription ? false : !item.color,
    sellerArticle: !options.articleFromDescription ? false : !item.sellerArticle,
  }
}

function imageUrlOld(root) {
  const image = first(root, [
    'img[data-marker*="image"]',
    'img[src*="avito.st"]',
    'img[src]',
  ])
  return absoluteUrl(image?.currentSrc || image?.src || image?.getAttribute('src'))
}

function orderCandidates() {
  const orderRows = Array.from(document.querySelectorAll('[data-marker="order-row"]'))
  if (orderRows.length) return orderRows
  const nodes = all(document, [
    '[data-marker*="order"]',
    '[data-marker*="delivery"]',
    'article',
    'li',
    'section',
  ])
  return nodes
    .filter((node) => {
      const text = textOf(node)
      return text.length > 30 && /(заказ|отправлен|достав|трек|получател|покупател|авито доставка)/iu.test(text)
    })
    .slice(0, 80)
}

function orderDetailsLink(root) {
  return first(root, [
    'a[href^="/orders/"]',
    'a[href*="/orders/"]',
  ])
}

function orderIdFromLink(root) {
  const href = orderDetailsLink(root)?.getAttribute('href') || ''
  return href.match(/\/orders\/([^?/#]+)/i)?.[1] || null
}

function visibleProductImages(root, limit) {
  const images = all(root, [
    '[data-marker="images-row"] img',
    'img[data-testid="image"]',
    'img[alt][src*="avito.st"]',
    'img[alt][srcset*="avito.st"]',
    'img[alt]',
  ])
  return images
    .map((image) => ({
      title: String(image.getAttribute('alt') || '').trim(),
      url: imageSource(image),
    }))
    .filter((item) => item.title || item.url)
    .filter((item, index, array) => {
      const key = `${item.title}|${item.url || ''}`
      return array.findIndex((candidate) => `${candidate.title}|${candidate.url || ''}` === key) === index
    })
    .slice(0, limit)
}

async function fetchDocument(url) {
  const resolved = absoluteUrl(url)
  if (!resolved) return null
  const response = await fetch(resolved, {
    method: 'GET',
    credentials: 'include',
    cache: 'no-store',
    headers: { 'Accept': 'text/html,application/xhtml+xml' },
  })
  if (!response.ok) throw new Error(`Avito вернул ${response.status} для ${resolved}`)
  const html = await response.text()
  return new DOMParser().parseFromString(html, 'text/html')
}

function documentTitle(root) {
  return textOf(first(root, ['[data-marker="item-view/title-info"]', 'h1', 'meta[property="og:title"]']))
    || metaContent(root, 'meta[property="og:title"]')
    || metaContent(root, 'meta[name="title"]')
    || null
}

function documentDescription(root) {
  const selectors = [
    '[data-marker="item-view/item-description"]',
    '[itemprop="description"]',
    '[data-marker*="description"]',
    '[class*="description"]',
  ]
  const nodeText = textOf(first(root, selectors))
  return nodeText || metaContent(root, 'meta[property="og:description"]') || metaContent(root, 'meta[name="description"]') || ''
}

function documentImageUrls(root, limit) {
  const metaImages = [
    metaContent(root, 'meta[property="og:image"]'),
    metaContent(root, 'meta[name="twitter:image"]'),
  ].map(absoluteUrl).filter(Boolean)
  return [...metaImages, ...imageUrls(root, limit)]
    .filter((value, index, array) => value && array.indexOf(value) === index)
    .slice(0, limit)
}

function itemUrlsFromDocument(root) {
  const html = decodedHtml(root)
  const urls = all(root, ['a[href]', '[href]'])
    .map((link) => listingUrl(link.getAttribute('href')))
    .filter(Boolean)
  const attributeUrls = Array.from(root.querySelectorAll('*'))
    .flatMap((node) => Array.from(node.attributes || []).map((attr) => attr.value))
    .map((value) => String(value || '').replace(/\\u002F/g, '/').replace(/\\\//g, '/'))
    .flatMap((value) => {
      const matches = Array.from(value.matchAll(/(?:https:\/\/www\.avito\.ru)?(\/[^\s"'<>]+(?:_[0-9]{5,}|\/items\/[0-9]+)[^\s"'<>]*)/giu))
      return matches.map((match) => listingUrl(match[1]))
    })
    .filter(Boolean)
  const htmlUrls = Array.from(html.matchAll(/(?:https:\/\/www\.avito\.ru)?(\/[^\s"'<>]+(?:_[0-9]{5,}|\/items\/[0-9]+)[^\s"'<>]*)/giu))
    .map((match) => listingUrl(match[1]))
    .filter(Boolean)
  const canonical = root.querySelector('link[rel="canonical"]')?.getAttribute('href')
  const ogUrl = metaContent(root, 'meta[property="og:url"]')
  return [...urls, ...attributeUrls, ...htmlUrls, listingUrl(canonical), listingUrl(ogUrl)]
    .filter(Boolean)
    .filter((url, index, array) => array.indexOf(url) === index)
}

function linkSamples(root) {
  return all(root, ['a[href]'])
    .map((link) => ({
      text: textOf(link).slice(0, 100),
      href: absoluteUrl(link.getAttribute('href')),
    }))
    .filter((row) => row.href && row.text && !/\/orders(?:\/|$)/i.test(new URL(row.href).pathname))
    .slice(0, 12)
}

function extractCurrentPageDetails(optionsPayload) {
  const options = normalizeOptions(optionsPayload)
  const imageLimit = options.photoMode === 'two' ? 2 : 1
  const text = textOf(document)
  const title = documentTitle(document)
  const description = documentDescription(document)
  const images = options.photoMode === 'none' ? [] : documentImageUrls(document, imageLimit)
  const details = {
    ok: true,
    url: location.href,
    title,
    description,
    images,
    itemUrls: itemUrlsFromDocument(document),
    linkSamples: linkSamples(document),
    itemId: itemIdFromUrl(location.href),
    status: statusFromText(text),
    deliveryService: deliveryService(text),
    trackNumber: trackNumber(text),
    chatText: options.sizeMode === 'chat_ai' ? chatText(document) || text.slice(0, 4000) : null,
    textPreview: text.slice(0, 1000),
  }
  logEvent('info', 'page details extracted', {
    url: details.url,
    title: details.title,
    descriptionLength: details.description?.length || 0,
    images: details.images.length,
    itemUrls: details.itemUrls.length,
    linkSamples: details.linkSamples.slice(0, 5),
  })
  return details
}

function requestTabDetails(url, options) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: 'AVITO_EXTRACT_DETAILS_TAB', url, options }, (response) => {
      if (chrome.runtime.lastError || !response?.ok) {
        const error = chrome.runtime.lastError?.message || response?.error || 'Не удалось открыть деталку'
        logEvent('warn', 'tab details request failed', { url, error })
        resolve({ ok: false, error })
        return
      }
      resolve({ ok: true, details: response.details || null })
    })
  })
}

function mergeItemDetails(item, details, options) {
  const text = [details.title, details.description, item.description].filter(Boolean).join('\n')
  const photos = details.images?.length ? details.images : item.imageUrls || []
  if (details.itemUrl && !item.itemUrl) item.itemUrl = details.itemUrl
  if (details.itemId && !item.itemId) item.itemId = details.itemId
  if (details.title && (!item.title || item.title === 'Товар Авито' || item.title === 'Товар')) item.title = details.title
  if (photos.length && !item.imageUrl) item.imageUrl = photos[0]
  if (photos.length) item.imageUrls = photos
  if (details.description) item.description = details.description
  if (options.articleFromDescription && !item.sellerArticle) item.sellerArticle = parseArticle(text)
  if (options.colorFromDescription && !item.color) item.color = parseColor(text)
  if (options.sizeMode === 'description' && !item.size) item.size = parseSize(text)
}

async function enrichOrderFromDetails(order, options) {
  const detailUrls = [order.pageUrl].filter((url) => url && !url.includes('#'))
  const imageLimit = options.photoMode === 'two' ? 2 : 1
  let orderDetails = null
  const errors = []
  for (const url of detailUrls) {
    const response = await requestTabDetails(url, options)
    if (response?.ok && response.details) {
      orderDetails = response.details
      break
    }
    if (response?.error) errors.push(response.error)
  }
  if (!orderDetails) return { order, checked: false, itemPages: 0, errors }

  if (!order.status) order.status = orderDetails.status
  if (!order.deliveryService) order.deliveryService = orderDetails.deliveryService
  if (!order.trackNumber) order.trackNumber = orderDetails.trackNumber

  const itemUrls = orderDetails.itemUrls || []
  const orderImages = options.photoMode === 'none' ? [] : (orderDetails.images || []).slice(0, imageLimit)
  const orderDescription = orderDetails.description || ''
  const orderTitle = orderDetails.title || null
  const detailChatText = orderDetails.chatText || null
  let itemPages = 0

  if (!order.items.length) order.items = [{ title: orderTitle || 'Товар Авито', quantity: 1 }]

  for (let itemIndex = 0; itemIndex < order.items.length; itemIndex += 1) {
    const item = order.items[itemIndex]
    mergeItemDetails(item, {
      title: orderTitle,
      description: orderDescription,
      images: orderImages,
    }, options)
    if (detailChatText && !item.chatText) item.chatText = detailChatText

    const itemUrl = item.itemUrl || itemUrls[itemIndex] || itemUrls[0]
    const itemResponse = itemUrl ? await requestTabDetails(itemUrl, options) : null
    if (!itemUrl) {
      errors.push('В деталке заказа не найдена прямая ссылка на объявление')
      logEvent('warn', 'item url not found in order detail', {
        orderId: order.orderId,
        itemTitle: item.title,
        linkSamples: orderDetails.linkSamples || [],
      })
    }
    const itemDetails = itemResponse?.ok ? itemResponse.details : null
    if (itemDetails) {
      itemPages += 1
      mergeItemDetails(item, {
        itemUrl: itemDetails.url || itemUrl,
        itemId: itemDetails.itemId || itemIdFromUrl(itemDetails.url || itemUrl),
        title: itemDetails.title,
        description: itemDetails.description,
        images: options.photoMode === 'none' ? [] : (itemDetails.images || []).slice(0, imageLimit),
      }, options)
      if (itemDetails.chatText && !item.chatText) item.chatText = itemDetails.chatText
    } else {
      if (itemResponse?.error) errors.push(itemResponse.error)
      if (!item.itemUrl) item.itemUrl = itemUrl
      if (!item.itemId) item.itemId = itemIdFromUrl(itemUrl)
    }
  }
  return { order, checked: true, itemPages, errors }
}

function cleanFallbackTitle(text) {
  return String(text || '')
    .replace(/Отправьте заказ.*?(?=\d+\s*₽|$)/iu, '')
    .replace(/Возврат:.*?(?=\d+\s*₽|$)/iu, '')
    .replace(/Едет к покупателю.*?(?=\d+\s*₽|$)/iu, '')
    .replace(/Жд[её]т выдачи покупателю.*?(?=\d+\s*₽|$)/iu, '')
    .replace(/\bДо\s+\d{1,2}\s+[а-яё]+\s+включительно\b/giu, '')
    .replace(/\d[\d\s]*₽(?:\s*·\s*\d+\s*товар[а-я]*)?/giu, '')
    .replace(/\b(?:СДЭК|Яндекс Доставка|Почта России|Авито|Подробнее|Собрать)\b/giu, '')
    .replace(/\bP\d{2}\s?\d{3}\s?\d{3}\s?\d{3}R?\b/giu, '')
    .replace(/\b103\s?\d{3}\s?\d{5}\b/gu, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 120) || 'Товар Авито'
}

function ensureCollectorStyles() {
  const id = 'satorna-avito-orders-styles'
  if (document.getElementById(id)) return
  const style = document.createElement('style')
  style.id = id
  style.textContent = `
    #satorna-avito-orders-progress {
      position: fixed;
      top: 54px;
      right: 16px;
      bottom: 16px;
      z-index: 2147483647;
      width: min(424px, calc(100vw - 32px));
      border-radius: 18px;
      overflow: hidden;
      background: radial-gradient(circle at 10% 8%, rgba(249, 115, 22, .18), transparent 34%), linear-gradient(160deg, #17131a 0%, #0d0d12 62%, #171016 100%);
      box-shadow: 0 24px 70px rgba(0, 0, 0, .42);
      color: #f8fafc;
      font: 14px/1.45 Arial, sans-serif;
      display: grid;
      grid-template-rows: auto 1fr auto;
    }
    #satorna-avito-orders-progress.satorna-collapsed { display: none; }
    .satorna-panel-head {
      min-height: 78px;
      padding: 20px 22px;
      border-bottom: 1px solid rgba(255, 255, 255, .1);
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
    }
    .satorna-panel-title {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 18px;
      font-weight: 800;
      letter-spacing: 0;
    }
    .satorna-panel-dot {
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: #fb923c;
      box-shadow: 0 0 0 5px rgba(251, 146, 60, .12);
    }
    .satorna-panel-close {
      width: 36px;
      height: 36px;
      border-radius: 10px;
      border: 1px solid rgba(255,255,255,.12);
      background: rgba(255,255,255,.06);
      color: rgba(255,255,255,.72);
      cursor: pointer;
      font-size: 22px;
      line-height: 1;
    }
    .satorna-panel-body {
      padding: 22px;
      color: rgba(248,250,252,.78);
      overflow: auto;
    }
    .satorna-panel-hint {
      color: rgba(248,250,252,.36);
      text-align: center;
      margin-top: 4px;
    }
    .satorna-panel-progress {
      height: 8px;
      border-radius: 999px;
      background: rgba(255,255,255,.09);
      overflow: hidden;
      margin: 16px 0 18px;
    }
    .satorna-panel-progress span {
      display: block;
      height: 100%;
      width: var(--satorna-progress, 0%);
      border-radius: inherit;
      background: linear-gradient(90deg, #fb923c, #22c55e);
      transition: width .18s ease;
    }
    .satorna-panel-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 14px;
    }
    .satorna-panel-stat {
      border: 1px solid rgba(255,255,255,.09);
      border-radius: 12px;
      padding: 12px;
      background: rgba(255,255,255,.045);
    }
    .satorna-panel-stat span {
      display: block;
      color: rgba(248,250,252,.5);
      font-size: 12px;
    }
    .satorna-panel-stat b {
      display: block;
      margin-top: 4px;
      font-size: 20px;
      color: #fff;
    }
    .satorna-panel-list {
      display: grid;
      gap: 8px;
      margin-top: 14px;
    }
    .satorna-panel-row {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      border-bottom: 1px solid rgba(255,255,255,.08);
      padding-bottom: 8px;
      color: rgba(248,250,252,.68);
    }
    .satorna-panel-row b { color: #fff; }
    .satorna-panel-result {
      margin: 0 8px 8px;
      border-radius: 12px;
      padding: 14px;
      background: #ecfdf5;
      border: 1px solid #bbf7d0;
      color: #047857;
      font-size: 13px;
    }
    .satorna-panel-result.warn {
      background: #fff7ed;
      border-color: #fed7aa;
      color: #9a3412;
    }
    .satorna-panel-result.error {
      background: #fef2f2;
      border-color: #fecaca;
      color: #991b1b;
    }
    .satorna-order-highlight {
      outline: 1.5px solid #fb923c !important;
      outline-offset: 2px !important;
      border-radius: 14px !important;
    }
    @media (max-width: 700px) {
      #satorna-avito-orders-progress {
        top: 12px;
        left: 12px;
        right: 12px;
        bottom: 12px;
        width: auto;
      }
    }
  `
  document.documentElement.appendChild(style)
}

function showCollectorOverlay(lines, variant = 'info', stats = {}) {
  const id = 'satorna-avito-orders-progress'
  ensureCollectorStyles()
  let box = document.getElementById(id)
  if (!box) {
    box = document.createElement('div')
    box.id = id
    document.documentElement.appendChild(box)
  }
  box.classList.remove('satorna-collapsed')
  const processed = Number(stats.processed || 0)
  const total = Number(stats.total || 0)
  const progress = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0
  const missing = stats.missing || {}
  const resultClass = variant === 'error' ? 'error' : variant === 'ok' ? '' : 'warn'
  box.innerHTML = [
    '<div class="satorna-panel-head">',
    '<div class="satorna-panel-title"><span class="satorna-panel-dot"></span><span>Собранные заказы</span></div>',
    '<button class="satorna-panel-close" type="button" aria-label="Закрыть">×</button>',
    '</div>',
    '<div class="satorna-panel-body">',
    total ? `<div><b>${escapeHtml(stats.phase || 'Сбор заказов')}</b><div class="satorna-panel-progress" style="--satorna-progress:${progress}%"><span></span></div></div>` : '<div class="satorna-panel-hint">Нажмите “Собрать заказы”</div>',
    '<div class="satorna-panel-grid">',
    `<div class="satorna-panel-stat"><span>Найдено блоков</span><b>${escapeHtml(stats.candidates ?? total ?? 0)}</b></div>`,
    `<div class="satorna-panel-stat"><span>Обработано</span><b>${escapeHtml(processed)} / ${escapeHtml(total)}</b></div>`,
    `<div class="satorna-panel-stat"><span>Заказов</span><b>${escapeHtml(stats.orders ?? 0)}</b></div>`,
    `<div class="satorna-panel-stat"><span>Позиций</span><b>${escapeHtml(stats.items ?? 0)}</b></div>`,
    '</div>',
    '<div class="satorna-panel-list">',
    `<div class="satorna-panel-row"><span>Фото не найдено</span><b>${escapeHtml(missing.imageUrl ?? 0)}</b></div>`,
    `<div class="satorna-panel-row"><span>Размер не найден</span><b>${escapeHtml(missing.size ?? 0)}</b></div>`,
    `<div class="satorna-panel-row"><span>Цвет не найден</span><b>${escapeHtml(missing.color ?? 0)}</b></div>`,
    `<div class="satorna-panel-row"><span>Артикул не найден</span><b>${escapeHtml(missing.sellerArticle ?? 0)}</b></div>`,
    '</div>',
    '</div>',
    `<div class="satorna-panel-result ${resultClass}">${lines.map((line) => `<div>${escapeHtml(line)}</div>`).join('')}</div>`,
  ].join('')
  box.querySelector('.satorna-panel-close')?.addEventListener('click', () => box.classList.add('satorna-collapsed'))
}

function collectOrder(root, options) {
  const text = textOf(root)
  const url = itemUrl(root)
  const imageLimit = options.photoMode === 'two' ? 2 : 1
  const visibleImages = options.photoMode === 'none' ? [] : visibleProductImages(root, imageLimit)
  const fallbackPhotos = options.photoMode === 'none' ? [] : imageUrls(root, imageLimit)
  const fallbackTitle = itemTitle(root, text)
  const title = visibleImages[0]?.title || (fallbackTitle === text.split(/[.!?]/)[0]?.slice(0, 120) ? cleanFallbackTitle(text) : fallbackTitle) || cleanFallbackTitle(text)
  const combined = [title, text].join('\n')
  const parsedChatText = options.sizeMode === 'chat_ai' ? chatText(root) : null
  const orderId = orderIdFromLink(root) || orderIdentity(text, root)
  const marketplaceId = orderId || marketplaceIdentity(text)
  if (!orderId && !marketplaceId) return null
  const itemPhotos = visibleImages.map((image) => image.url).filter(Boolean)
  const photos = itemPhotos.length ? itemPhotos : fallbackPhotos
  return {
    orderId,
    marketplaceId,
    status: statusFromText(text),
    deliveryService: deliveryService(text),
    trackNumber: trackNumber(text),
    buyerName: text.match(/(?:покупатель|получатель)\s*[:—-]\s*([а-яёa-z .-]{2,40})/iu)?.[1]?.trim() || null,
    pageUrl: absoluteUrl(orderDetailsLink(root)?.getAttribute('href')) || location.href,
    items: [{
      itemId: itemIdFromUrl(url),
      title,
      itemUrl: url,
      quantity: Number(text.match(/(?:кол-во|количество)\s*[:—-]?\s*(\d+)/iu)?.[1] || 1),
      priceKopecks: parseKopecks(text),
      sellerArticle: options.articleFromDescription ? parseArticle(combined) : null,
      size: options.sizeMode === 'description' ? parseSize(combined) : null,
      color: options.colorFromDescription ? parseColor(combined) : null,
      imageUrl: photos[0] || null,
      imageUrls: photos,
      description: text,
      chatText: parsedChatText,
    }],
  }
}

function dedupeOrders(orders) {
  const byKey = new Map()
  orders.forEach((order) => {
    const key = order.orderId || order.marketplaceId
    if (!key || byKey.has(key)) return
    byKey.set(key, order)
  })
  return Array.from(byKey.values())
}

function missingSummary(orders, options) {
  const items = orders.flatMap((order) => order.items || [])
  const missingRows = items.map((item) => requestedMissing(item, options))
  return {
    items,
    missing: {
      imageUrl: missingRows.filter((item) => item.imageUrl).length,
      size: missingRows.filter((item) => item.size).length,
      color: missingRows.filter((item) => item.color).length,
      sellerArticle: missingRows.filter((item) => item.sellerArticle).length,
    },
  }
}

function highlightOrderRows(nodes) {
  nodes.forEach((node) => {
    if (node instanceof HTMLElement) node.classList.add('satorna-order-highlight')
  })
}

async function collectSnapshot(optionsPayload) {
  const options = normalizeOptions(optionsPayload)
  logEvent('info', 'collection started on orders page', { url: location.href, options })
  showCollectorOverlay(['Ищем строки заказов на странице Avito...'], 'info', { phase: 'Поиск заказов' })
  const candidates = orderCandidates()
  logEvent('info', 'order rows found', { count: candidates.length })
  highlightOrderRows(candidates)
  const collected = []
  let detailPages = 0
  let itemPages = 0
  const detailErrors = []
  for (let index = 0; index < candidates.length; index += 1) {
    const baseOrder = collectOrder(candidates[index], options)
    if (baseOrder) {
      logEvent('info', 'order row parsed', {
        index: index + 1,
        total: candidates.length,
        orderId: baseOrder.orderId,
        pageUrl: baseOrder.pageUrl,
        title: baseOrder.items?.[0]?.title,
        image: Boolean(baseOrder.items?.[0]?.imageUrl),
      })
      showCollectorOverlay([
        `Заказ ${index + 1} из ${candidates.length}: открываем детали`,
        baseOrder.orderId ? `ID: ${baseOrder.orderId}` : 'ID заказа не найден',
      ], 'info', {
        phase: 'Читаем детали заказов',
        candidates: candidates.length,
        total: candidates.length,
        processed: index,
        orders: dedupeOrders(collected).length,
        items: collected.flatMap((item) => item.items || []).length,
      })
      const enriched = await enrichOrderFromDetails(baseOrder, options)
      if (enriched.checked) detailPages += 1
      itemPages += enriched.itemPages || 0
      if (enriched.errors?.length) detailErrors.push(...enriched.errors)
      logEvent(enriched.checked ? 'info' : 'warn', 'order enrichment finished', {
        orderId: enriched.order.orderId,
        checked: enriched.checked,
        itemPages: enriched.itemPages || 0,
        errors: enriched.errors || [],
        item: {
          title: enriched.order.items?.[0]?.title,
          image: Boolean(enriched.order.items?.[0]?.imageUrl),
          size: enriched.order.items?.[0]?.size || null,
          color: enriched.order.items?.[0]?.color || null,
          article: enriched.order.items?.[0]?.sellerArticle || null,
        },
      })
      collected.push(enriched.order)
    }
    if (index === 0 || (index + 1) % 2 === 0 || index + 1 === candidates.length) {
      const partialOrders = dedupeOrders(collected)
      const { items: partialItems, missing: partialMissing } = missingSummary(partialOrders, options)
      showCollectorOverlay([
        `Обработано заказов: ${index + 1} из ${candidates.length}`,
        `Деталок заказа: ${detailPages}, объявлений: ${itemPages}`,
        detailErrors.length ? `Ошибок деталок: ${detailErrors.length} · ${detailErrors[detailErrors.length - 1]}` : 'Деталки читаются через вкладки расширения',
      ], 'info', {
        phase: 'Собираем описания и фото',
        candidates: candidates.length,
        total: candidates.length,
        processed: index + 1,
        orders: partialOrders.length,
        items: partialItems.length,
        missing: partialMissing,
      })
    }
    await sleep(120)
  }
  const orders = dedupeOrders(collected)
  const { items, missing } = missingSummary(orders, options)
  logEvent('info', 'collection completed on orders page', {
    candidates: candidates.length,
    orders: orders.length,
    items: items.length,
    detailPages,
    itemPages,
    missing,
    detailErrors: detailErrors.slice(-10),
  })
  showCollectorOverlay([
    `Найдено строк заказов Avito: ${candidates.length}`,
    `Собрано заказов: ${orders.length}`,
    `Позиций: ${items.length}`,
    `Проверено деталок: ${detailPages}, объявлений: ${itemPages}`,
    detailErrors.length ? `Ошибок деталок: ${detailErrors.length} · последняя: ${detailErrors[detailErrors.length - 1]}` : 'Ошибок деталок нет',
    `Не найдено: фото ${missing.imageUrl}, размер ${missing.size}, цвет ${missing.color}, артикул ${missing.sellerArticle}`,
  ], 'ok', {
    phase: 'Сбор завершен',
    candidates: candidates.length,
    total: candidates.length,
    processed: candidates.length,
    orders: orders.length,
    items: items.length,
    missing,
  })
  return {
    capturedAt: new Date().toISOString(),
    pageUrl: location.href,
    collector: {
      status: 'completed',
      candidates: candidates.length,
      orders: orders.length,
      items: items.length,
      missing,
      options,
      notes: [
        'Собраны данные со страницы заказов, деталей заказа и доступных страниц объявлений Avito.',
        `Проверено деталей заказа: ${detailPages}. Проверено объявлений: ${itemPages}.`,
        detailErrors.length ? `Ошибки деталей: ${detailErrors.slice(-3).join(' | ')}` : 'Ошибок деталей нет.',
        options.sizeMode === 'chat_ai'
          ? 'Размер будет дополнительно проверен backend AI-разбором по тексту чата.'
          : 'AI не используется, если размер выбран из описания или отключен.',
      ],
    },
    orders,
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === 'AVITO_PAGE_EXTRACT_DETAILS') {
    sendResponse(extractCurrentPageDetails(message.options))
    return false
  }
  if (message?.type !== 'AVITO_ORDERS_COLLECT_NOW') return false
  collectSnapshot(message.options)
    .then((payload) => sendResponse({ ok: true, payload }))
    .catch((error) => {
      const text = error instanceof Error ? error.message : String(error)
      showCollectorOverlay([text], 'error')
      sendResponse({ ok: false, error: text })
    })
  return true
})
