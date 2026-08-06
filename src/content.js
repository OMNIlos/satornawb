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
  const explicit = lower.match(/цвет\s*[:—-]\s*([а-яёa-z -]{3,24})/iu)
  if (explicit?.[1]) return explicit[1].trim().split(/[,.]/)[0]
  const found = COLOR_HINTS.find(([hint]) => lower.includes(hint))
  return found?.[1] || null
}

function parseSize(text) {
  const value = String(text || '')
  const explicit = Array.from(value.matchAll(/(?:размер|р-р|size)\s*[:—-]?\s*([0-9]{2}(?:-[0-9]{2})?|[2-5]?XL|XXL|XS|[SML])/giu)).pop()
  if (explicit?.[1]) return explicit[1].toUpperCase()
  const numeric = Array.from(value.matchAll(/\b([3-6][0-9](?:-[3-6][0-9])?)\b/gu)).pop()
  if (numeric?.[1]) return numeric[1]
  const upper = ` ${value.toUpperCase()} `
  const found = SIZE_VALUES.find((size) => upper.includes(` ${size} `))
  return found || null
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
    'img[src]',
  ])
  return images
    .map((image) => absoluteUrl(image.currentSrc || image.src || image.getAttribute('src')))
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
    'img[alt]',
  ])
  return images
    .map((image) => ({
      title: String(image.getAttribute('alt') || '').trim(),
      url: absoluteUrl(image.currentSrc || image.src || image.getAttribute('src') || image.getAttribute('data-src')),
    }))
    .filter((item) => item.title || item.url)
    .filter((item, index, array) => {
      const key = `${item.title}|${item.url || ''}`
      return array.findIndex((candidate) => `${candidate.title}|${candidate.url || ''}` === key) === index
    })
    .slice(0, limit)
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

function showCollectorOverlay(lines, variant = 'info') {
  const id = 'satorna-avito-orders-progress'
  let box = document.getElementById(id)
  if (!box) {
    box = document.createElement('div')
    box.id = id
    box.style.position = 'fixed'
    box.style.right = '18px'
    box.style.bottom = '18px'
    box.style.zIndex = '2147483647'
    box.style.width = '320px'
    box.style.padding = '14px'
    box.style.borderRadius = '12px'
    box.style.boxShadow = '0 18px 45px rgba(15,23,42,.22)'
    box.style.font = '13px/1.35 Arial, sans-serif'
    document.documentElement.appendChild(box)
  }
  box.style.background = variant === 'error' ? '#FEF2F2' : variant === 'ok' ? '#ECFDF5' : '#EFF6FF'
  box.style.border = variant === 'error' ? '1px solid #FECACA' : variant === 'ok' ? '1px solid #BBF7D0' : '1px solid #BFDBFE'
  box.style.color = variant === 'error' ? '#991B1B' : variant === 'ok' ? '#065F46' : '#1E3A8A'
  box.innerHTML = [
    '<b style="display:block;margin-bottom:7px">Satorna собирает заказы Avito</b>',
    ...lines.map((line) => `<div style="margin-top:3px">${String(line).replace(/[<>&]/g, (char) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[char]))}</div>`),
  ].join('')
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

function collectSnapshot(optionsPayload) {
  const options = normalizeOptions(optionsPayload)
  showCollectorOverlay(['Ищем блоки заказов на странице...'])
  const candidates = orderCandidates()
  const orders = dedupeOrders(candidates.map((node) => collectOrder(node, options)).filter(Boolean))
  const items = orders.flatMap((order) => order.items || [])
  const missingRows = items.map((item) => requestedMissing(item, options))
  const missing = {
    imageUrl: missingRows.filter((item) => item.imageUrl).length,
    size: missingRows.filter((item) => item.size).length,
    color: missingRows.filter((item) => item.color).length,
    sellerArticle: missingRows.filter((item) => item.sellerArticle).length,
  }
  showCollectorOverlay([
    `Найдено строк заказов Avito: ${candidates.length}`,
    `Собрано заказов: ${orders.length}`,
    `Позиций: ${items.length}`,
    `Не найдено: фото ${missing.imageUrl}, размер ${missing.size}, цвет ${missing.color}, артикул ${missing.sellerArticle}`,
  ], 'ok')
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
        'Собраны данные, которые были видны в DOM страницы Avito.',
        options.sizeMode === 'chat_ai'
          ? 'Размер будет дополнительно проверен backend AI-разбором по тексту чата.'
          : 'AI не используется, если размер выбран из описания или отключен.',
      ],
    },
    orders,
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type !== 'AVITO_ORDERS_COLLECT_NOW') return false
  sendResponse({ ok: true, payload: collectSnapshot(message.options) })
  return false
})
