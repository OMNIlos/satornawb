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

function normalizeAvitoUrl(value) {
  if (!value) return null
  const variants = [
    String(value),
    String(value).replace(/\\u002F/g, '/').replace(/\\\//g, '/').replace(/&amp;/g, '&').replace(/&quot;/g, '"'),
  ]
  for (const variant of variants) {
    try {
      const decoded = decodeURIComponent(variant)
      const url = new URL(decoded, location.origin)
      if (!/(\.|^)avito\.ru$/i.test(url.hostname)) continue
      url.hash = ''
      return url.toString()
    } catch (_error) {
      try {
        const url = new URL(variant, location.origin)
        if (!/(\.|^)avito\.ru$/i.test(url.hostname)) continue
        url.hash = ''
        return url.toString()
      } catch (_nestedError) {
        // Try the next representation.
      }
    }
  }
  return null
}

function isProbablyItemUrl(value) {
  const url = normalizeAvitoUrl(value)
  if (!url) return false
  try {
    const parsed = new URL(url)
    const badPrefixes = ['/orders', '/profile', '/messenger', '/favorites', '/cart', '/user', '/legal', '/help', '/brands', '/shops']
    if (badPrefixes.some((prefix) => parsed.pathname.startsWith(prefix))) return false
    if (/_[0-9]{6,12}(?:\/)?$/i.test(parsed.pathname)) return true
    if (/\/items\/[0-9]+(?:\/)?$/i.test(parsed.pathname)) return true
    if (/[?&]item(?:_|I)?d=\d{6,12}/i.test(parsed.search)) return true
    return false
  } catch {
    return false
  }
}

function listingUrl(value) {
  const url = normalizeAvitoUrl(value)
  return url && isProbablyItemUrl(url) ? url : null
}

function decodedHtml(root) {
  const scripts = Array.from(root.scripts || []).map((script) => script.textContent || '').join('\n')
  return [String(root.documentElement?.innerHTML || ''), scripts].join('\n')
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
  return null
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

function slugifyAvitoTitle(title) {
  const map = {
    а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e',
    ж: 'zh', з: 'z', и: 'i', й: 'y', к: 'k', л: 'l',
    м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's',
    т: 't', у: 'u', ф: 'f', х: 'h', ц: 'ts', ч: 'ch',
    ш: 'sh', щ: 'sch', ъ: '', ы: 'y', ь: '', э: 'e',
    ю: 'yu', я: 'ya',
  }
  return String(title || '')
    .toLocaleLowerCase('ru-RU')
    .replace(/[а-яё]/giu, (char) => map[char.toLocaleLowerCase('ru-RU')] ?? char)
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function extractAvitoItemIdFromText(text) {
  const ids = String(text || '').match(/\b\d{9,12}\b/g) || []
  return ids.find((id) => !id.startsWith('70000000') && !id.startsWith('103')) || null
}

function extractAvitoItemIdFromRow(root, text) {
  const direct = itemIdFromUrl(itemUrl(root)) || extractAvitoItemIdFromText(text)
  if (direct) return direct
  const html = String(root.innerHTML || '')
    .replace(/\\u002F/g, '/')
    .replace(/\\\//g, '/')
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, '&')
  const patterns = [
    /_[0-9]{6,12}(?=[/?#"'<\s]|$)/giu,
    /(?:itemId|item_id|avitoId|avito_id|adId|advertId)["':=\s]+([0-9]{6,12})/giu,
    /\/items\/([0-9]{6,12})/giu,
  ]
  for (const pattern of patterns) {
    for (const match of html.matchAll(pattern)) {
      const raw = match[1] || match[0].replace(/^_/, '')
      const found = extractAvitoItemIdFromText(raw)
      if (found) return found
    }
  }
  const attributeText = Array.from(root.querySelectorAll('*'))
    .flatMap((node) => Array.from(node.attributes || []).map((attr) => attr.value))
    .join('\n')
  return extractAvitoItemIdFromText(attributeText)
}

function buildAvitoItemUrl(title, itemId) {
  const slug = slugifyAvitoTitle(title)
  if (!slug || !itemId) return null
  return `https://www.avito.ru/voronezh/odezhda_obuv_aksessuary/${slug}_${itemId}`
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

function uniqueCandidates(items) {
  const map = new Map()
  items.forEach((item) => {
    if (!item?.url) return
    const prev = map.get(item.url)
    if (!prev || item.score > prev.score) map.set(item.url, item)
  })
  return Array.from(map.values()).sort((a, b) => b.score - a.score)
}

function titleWords(value) {
  return normalizedTitle(value).split(' ').filter((part) => part.length >= 4)
}

function itemUrlCandidatesFromAnchors(root, orderTitle) {
  const words = titleWords(orderTitle)
  return all(root, ['a[href]'])
    .map((link) => {
      const url = listingUrl(link.getAttribute('href'))
      if (!url) return null
      const text = normalizedTitle(textOf(link) || link.getAttribute('title') || '')
      let score = 50
      if (words.some((word) => text.includes(word))) score += 30
      if (link.closest('[data-marker*="order"]')) score += 20
      if (link.querySelector('img')) score += 10
      return { url, source: 'anchor', score, text: textOf(link).slice(0, 120) }
    })
    .filter(Boolean)
}

function itemUrlCandidatesFromMeta(root) {
  return [
    ['meta[property="og:url"]', metaContent(root, 'meta[property="og:url"]')],
    ['link[rel="canonical"]', root.querySelector('link[rel="canonical"]')?.getAttribute('href')],
  ]
    .map(([source, raw]) => {
      const url = listingUrl(raw)
      return url ? { url, source, score: 40 } : null
    })
    .filter(Boolean)
}

function itemUrlCandidatesFromScripts(root) {
  const html = decodedHtml(root)
  const patterns = [
    /https?:\/\/(?:www\.)?avito\.ru\/[^\s"'<>\\]+_[0-9]{6,12}/giu,
    /(?:https:\/\/www\.avito\.ru)?(\/[^\s"'<>]+_[0-9]{6,12})/giu,
    /"url"\s*:\s*"([^"]+_[0-9]{6,12})"/giu,
    /"itemUrl"\s*:\s*"([^"]+)"/giu,
    /"item_url"\s*:\s*"([^"]+)"/giu,
    /"canonicalUrl"\s*:\s*"([^"]+_[0-9]{6,12})"/giu,
  ]
  return patterns.flatMap((pattern) => Array.from(html.matchAll(pattern)).map((match) => {
    const raw = match[1] || match[0]
    const url = listingUrl(raw)
    return url ? { url, source: 'script/html', score: 35 } : null
  })).filter(Boolean)
}

function itemUrlCandidatesFromAttributes(root) {
  return Array.from(root.querySelectorAll('*'))
    .flatMap((node) => Array.from(node.attributes || []).map((attr) => ({ name: attr.name, value: attr.value })))
    .flatMap((attr) => {
      const text = String(attr.value || '').replace(/\\u002F/g, '/').replace(/\\\//g, '/')
      const matches = Array.from(text.matchAll(/(?:https:\/\/www\.avito\.ru)?(\/[^\s"'<>]+(?:_[0-9]{6,12}|\/items\/[0-9]+)[^\s"'<>]*)/giu))
      return matches.map((match) => {
        const url = listingUrl(match[1])
        return url ? { url, source: `attribute:${attr.name}`, score: 32 } : null
      })
    })
    .filter(Boolean)
}

function resolveItemUrlFromOrderPage(orderTitle) {
  const candidates = uniqueCandidates([
    ...itemUrlCandidatesFromAnchors(document, orderTitle),
    ...itemUrlCandidatesFromMeta(document),
    ...itemUrlCandidatesFromScripts(document),
    ...itemUrlCandidatesFromAttributes(document),
  ])
  return {
    itemUrl: candidates[0]?.url || null,
    candidates,
  }
}

function itemUrlsFromDocument(root, orderTitle) {
  if (root === document) return resolveItemUrlFromOrderPage(orderTitle).candidates.map((item) => item.url)
  return uniqueCandidates([
    ...itemUrlCandidatesFromAnchors(root, orderTitle),
    ...itemUrlCandidatesFromMeta(root),
    ...itemUrlCandidatesFromScripts(root),
    ...itemUrlCandidatesFromAttributes(root),
  ]).map((item) => item.url)
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

function isVisibleElement(node) {
  if (!(node instanceof HTMLElement)) return false
  const box = node.getBoundingClientRect()
  const style = window.getComputedStyle(node)
  return box.width > 0 && box.height > 0 && style.visibility !== 'hidden' && style.display !== 'none'
}

function clickableForNode(node) {
  if (!(node instanceof HTMLElement)) return null
  return node.closest('a, button, [role="link"], [role="button"], [tabindex]') || node
}

function findOrderListingClickTarget(title) {
  const titleNeedle = normalizedTitle(title)
  const titleParts = titleNeedle.split(' ').filter((part) => part.length > 2)
  const minScore = titleNeedle ? Math.min(25, Math.max(10, titleParts.length * 8)) : 8
  const rows = Array.from(document.querySelectorAll('a, button, [role="link"], [role="button"], [tabindex], h1, h2, h3, span, div'))
    .filter(isVisibleElement)
    .map((node) => {
      const rawText = textOf(node)
      const normalized = normalizedTitle(rawText)
      const matchedParts = titleParts.filter((part) => normalized.includes(part)).length
      const exactish = titleNeedle && (normalized === titleNeedle || normalized.includes(titleNeedle) || titleNeedle.includes(normalized))
      const context = textOf(node.closest('[data-marker*="order"], section, article, main') || document.body)
      return {
        node,
        rawText,
        score: (exactish ? 100 : 0) + matchedParts * 10 + (/заказ/iu.test(context) ? 5 : 0),
      }
    })
    .filter((row) => row.rawText.length >= 3 && row.rawText.length <= 140 && row.score >= minScore)
    .sort((a, b) => b.score - a.score)
  const candidate = rows[0]
  if (!candidate) return null
  return { target: clickableForNode(candidate.node), text: candidate.rawText, score: candidate.score }
}

function openListingFromOrderDetail(title) {
  const found = findOrderListingClickTarget(title)
  if (!found?.target) {
    logEvent('warn', 'order listing click target not found', { title, linkSamples: linkSamples(document) })
    return { ok: false, error: 'Не нашли кликабельное название товара в деталке заказа' }
  }
  found.target.scrollIntoView({ block: 'center', inline: 'center' })
  ;['pointerdown', 'mousedown', 'mouseup', 'click'].forEach((eventName) => {
    found.target.dispatchEvent(new MouseEvent(eventName, { bubbles: true, cancelable: true, view: window }))
  })
  logEvent('info', 'order listing click target clicked', { title, text: found.text, score: found.score })
  return { ok: true, text: found.text, score: found.score }
}

function metaDebug(root) {
  return {
    ogUrl: metaContent(root, 'meta[property="og:url"]'),
    ogImage: metaContent(root, 'meta[property="og:image"]'),
    canonical: root.querySelector('link[rel="canonical"]')?.getAttribute('href') || null,
    description: metaContent(root, 'meta[name="description"]'),
  }
}

function htmlItemIds(root) {
  const html = decodedHtml(root)
  return Array.from(html.matchAll(/(?:itemId|item_id|avitoId|avito_id)["':\s]+([0-9]{6,12})/giu))
    .map((match) => match[1])
    .filter((value, index, array) => array.indexOf(value) === index)
    .slice(0, 20)
}

async function waitForDomReady(timeoutMs = 8000) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    const bodyText = textOf(document.body)
    const hasOrderText = /заказ|доставка|трек|отправ|стоимость|итого/iu.test(bodyText)
    const hasItemText = /описание|характеристики|размер|цвет|артикул/iu.test(bodyText)
    const hasLinks = document.querySelectorAll('a[href]').length > 0
    const hasImages = document.querySelectorAll('img').length > 0
    if ((hasOrderText || hasItemText) && (hasLinks || hasImages || bodyText.length > 500)) return true
    await sleep(500)
  }
  return false
}

async function extractCurrentPageDetails(optionsPayload) {
  await waitForDomReady()
  const options = normalizeOptions(optionsPayload)
  const imageLimit = options.photoMode === 'two' ? 2 : 1
  const text = textOf(document)
  const rawText = String(document.body?.innerText || text)
  const title = documentTitle(document)
  const description = documentDescription(document)
  const images = options.photoMode === 'none' ? [] : documentImageUrls(document, imageLimit)
  const resolved = resolveItemUrlFromOrderPage(optionsPayload?.orderItemTitle || title || '')
  const details = {
    ok: true,
    url: location.href,
    title,
    description,
    pageText: rawText,
    images,
    itemUrls: resolved.candidates.map((item) => item.url),
    itemUrlCandidates: resolved.candidates.slice(0, 20),
    linkSamples: linkSamples(document),
    linksCount: document.querySelectorAll('a[href]').length,
    imagesCount: document.querySelectorAll('img').length,
    metas: metaDebug(document),
    htmlItemIds: htmlItemIds(document),
    itemId: itemIdFromUrl(location.href),
    status: statusFromText(text),
    deliveryService: deliveryService(text),
    trackNumber: trackNumber(text),
    chatText: options.sizeMode === 'chat_ai' ? chatText(document) || text.slice(0, 4000) : null,
    textPreview: rawText.slice(0, 1000),
  }
  logEvent('info', 'page details extracted', {
    url: details.url,
    title: details.title,
    descriptionLength: details.description?.length || 0,
    images: details.images.length,
    itemUrls: details.itemUrls.length,
    candidates: details.itemUrlCandidates.slice(0, 5),
    linksCount: details.linksCount,
    imagesCount: details.imagesCount,
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
  const text = [details.pageText, details.description, item.description].filter(Boolean).join('\n')
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
  const hasRowItemUrl = order.items?.some((item) => item.itemUrl)
  const detailUrls = hasRowItemUrl ? [] : [order.pageUrl].filter((url) => url && !url.includes('#'))
  const imageLimit = options.photoMode === 'two' ? 2 : 1
  let orderDetails = null
  const errors = []
  for (const url of detailUrls) {
    const response = await requestTabDetails(url, { ...options, orderItemTitle: order.items?.[0]?.title || '' })
    if (response?.ok && response.details) {
      orderDetails = response.details
      break
    }
    if (response?.error) errors.push(response.error)
  }
  if (!orderDetails && !hasRowItemUrl) return { order, checked: false, itemPages: 0, errors }
  if (!orderDetails) orderDetails = { itemUrls: [], images: [], description: '', title: null, chatText: null }

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
      pageText: orderDetails.pageText || orderDescription,
      images: orderImages,
    }, options)
    if (detailChatText && !item.chatText) item.chatText = detailChatText

    const itemUrl = item.itemUrl || itemUrls[itemIndex] || itemUrls[0]
    const itemResponse = itemUrl ? await requestTabDetails(itemUrl, options) : null
    if (!itemUrl) {
      const renderReason = orderDetails.detailNotRendered
        ? 'деталка Avito не отдала контент заказа'
        : 'URL объявления не найден'
      errors.push(`${renderReason}: ссылок ${orderDetails.linksCount || 0}, кандидатов ${orderDetails.itemUrlCandidates?.length || 0}, id в html ${orderDetails.htmlItemIds?.length || 0}`)
      logEvent('warn', 'item url not found in order detail', {
        orderId: order.orderId,
        itemTitle: item.title,
        detailNotRendered: Boolean(orderDetails.detailNotRendered),
        detailNotRenderedReason: orderDetails.detailNotRenderedReason || null,
        selectedFrame: orderDetails.selectedFrame || null,
        frameDebug: orderDetails.frameDebug || [],
        linksCount: orderDetails.linksCount || 0,
        imagesCount: orderDetails.imagesCount || 0,
        htmlItemIds: orderDetails.htmlItemIds || [],
        candidates: orderDetails.itemUrlCandidates || [],
        metas: orderDetails.metas || {},
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
        pageText: itemDetails.pageText || itemDetails.description,
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
  const imageLimit = options.photoMode === 'two' ? 2 : 1
  const visibleImages = options.photoMode === 'none' ? [] : visibleProductImages(root, imageLimit)
  const fallbackPhotos = options.photoMode === 'none' ? [] : imageUrls(root, imageLimit)
  const fallbackTitle = itemTitle(root, text)
  const title = visibleImages[0]?.title || (fallbackTitle === text.split(/[.!?]/)[0]?.slice(0, 120) ? cleanFallbackTitle(text) : fallbackTitle) || cleanFallbackTitle(text)
  const directUrl = itemUrl(root)
  const avitoItemId = extractAvitoItemIdFromRow(root, text)
  const url = directUrl || buildAvitoItemUrl(title, avitoItemId)
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
      itemId: itemIdFromUrl(url) || avitoItemId,
      title,
      itemUrl: url,
      quantity: Number(text.match(/(?:кол-во|количество)\s*[:—-]?\s*(\d+)/iu)?.[1] || 1),
      priceKopecks: parseKopecks(text),
      sellerArticle: options.articleFromDescription ? parseArticle(combined) : null,
      size: options.sizeMode === 'description' ? parseSize(combined) : null,
      color: null,
      imageUrl: photos[0] || null,
      imageUrls: photos,
      description: text,
      chatText: parsedChatText,
      sources: {
        itemUrl: directUrl ? 'row_link' : url ? 'row_item_id_slug' : null,
        itemId: avitoItemId ? 'row_dom' : null,
        imageUrl: photos[0] ? 'order_row' : null,
      },
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
        itemId: baseOrder.items?.[0]?.itemId || null,
        itemUrl: baseOrder.items?.[0]?.itemUrl || null,
        sources: baseOrder.items?.[0]?.sources || {},
        image: Boolean(baseOrder.items?.[0]?.imageUrl),
      })
      const previewOrders = dedupeOrders([...collected, baseOrder])
      const { items: previewItems, missing: previewMissing } = missingSummary(previewOrders, options)
      showCollectorOverlay([
        `Заказ ${index + 1} из ${candidates.length}: ищем карточку товара`,
        baseOrder.orderId ? `ID: ${baseOrder.orderId}` : 'ID заказа не найден',
        baseOrder.items?.[0]?.itemId ? `ID объявления: ${baseOrder.items[0].itemId}` : 'ID объявления: не найден',
        baseOrder.items?.[0]?.itemUrl ? 'Карточка товара: ссылка собрана' : 'Карточка товара: ссылки пока нет',
      ], 'info', {
        phase: 'Ищем карточки и поля',
        candidates: candidates.length,
        total: candidates.length,
        processed: index,
        orders: previewOrders.length,
        items: previewItems.length,
        missing: previewMissing,
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
          itemId: enriched.order.items?.[0]?.itemId || null,
          itemUrl: enriched.order.items?.[0]?.itemUrl || null,
          sources: enriched.order.items?.[0]?.sources || {},
          image: Boolean(enriched.order.items?.[0]?.imageUrl),
          size: enriched.order.items?.[0]?.size || null,
          color: enriched.order.items?.[0]?.color || null,
          article: enriched.order.items?.[0]?.sellerArticle || null,
        },
      })
      collected.push(enriched.order)
      const liveItem = enriched.order.items?.[0] || {}
      const liveMissing = requestedMissing(liveItem, options)
      showCollectorOverlay([
        `Заказ ${index + 1} из ${candidates.length}: ${liveItem.title || 'товар'}`,
        liveItem.itemUrl ? 'Карточка товара: проверена или поставлена в очередь' : 'Карточка товара: ссылка не найдена',
        `Найдено: фото ${liveItem.imageUrl ? 'да' : 'нет'}, размер ${liveItem.size ? 'да' : 'нет'}, цвет ${liveItem.color ? 'да' : 'нет'}, артикул ${liveItem.sellerArticle ? 'да' : 'нет'}`,
        (liveMissing.size || liveMissing.color || liveMissing.sellerArticle) ? 'Часть данных ещё не найдена' : 'Данные товара собраны',
      ], liveItem.itemUrl ? 'info' : 'warn', {
        phase: 'Проверяем товар',
        candidates: candidates.length,
        total: candidates.length,
        processed: index + 1,
        orders: dedupeOrders(collected).length,
        items: collected.flatMap((item) => item.items || []).length,
        missing: missingSummary(dedupeOrders(collected), options).missing,
      })
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
    extractCurrentPageDetails(message.options)
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) }))
    return true
  }
  if (message?.type === 'AVITO_OPEN_LISTING_FROM_ORDER') {
    sendResponse(openListingFromOrderDetail(message.title || message.options?.orderItemTitle || ''))
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
