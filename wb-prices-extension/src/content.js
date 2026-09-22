(() => {
  'use strict'
  if (window.top !== window) return
  const C = WbPricesContract
  let blocked = false
  let checkTimer = null
  let challengeSince = null
  let scrollTimer = null
  const send = (message) => { void chrome.runtime.sendMessage({ source: C.SOURCE, ...message }).catch(() => {}) }

  window.addEventListener('message', (event) => {
    if (event.source !== window || event.origin !== C.WB_ORIGIN) return
    const clean = C.sanitizePageMessage(event.data, location.href)
    if (clean) {
      if (clean.catalogPage) clearTimeout(scrollTimer)
      send(clean)
    }
  })

  function checkChallenge() {
    checkTimer = null
    if (blocked) return
    const title = document.title.trim()
    const challenge = /^(access denied|captcha|доступ (ограничен|запрещен)|проверка (браузера|безопасности)|just a moment)/i.test(title)
      || (!document.querySelector('article[data-nm-id]') && /подтвердите,? что вы (не робот|человек)|проверяем.{0,40}(браузер|не робот)/i.test((document.body?.innerText || '').slice(0, 3000)))
    if (!challenge) { challengeSince = null; return }
    challengeSince ??= Date.now()
    // WB also shows a short automatic browser check which resolves unaided.
    // Never interact with a challenge; pause if it persists.
    if (Date.now() - challengeSince >= 10000) {
      blocked = true; clearTimeout(scrollTimer); send({ type: 'blocked', code: 'challenge' })
    } else checkTimer = setTimeout(checkChallenge, 500)
  }

  function watchChallenge() {
    checkChallenge()
    new MutationObserver(() => { if (!checkTimer && !blocked) checkTimer = setTimeout(checkChallenge, 250) })
      .observe(document.documentElement, { childList: true, subtree: true })
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watchChallenge, { once: true })
  else watchChallenge()

  chrome.runtime.onMessage.addListener((message, sender, respond) => {
    if (sender.id === chrome.runtime.id && message?.type === 'stop_scroll') {
      clearTimeout(scrollTimer); respond({ ok: true }); return
    }
    if (sender.id !== chrome.runtime.id || message?.type !== 'scroll' || !C.sellerId(location.href) || blocked) return
    // Follow a control that the live page actually exposes; never invent page=N.
    const controls = document.querySelectorAll('[class*="pagination"] a, [class*="pagination"] button, [data-testid*="pagination"] a, [data-testid*="pagination"] button')
    const next = [...controls].find((element) => element.getClientRects().length && !element.disabled
      && element.getAttribute('aria-disabled') !== 'true'
      && /^(следующая(?: страница)?|далее|показать ещ[её]|загрузить ещ[её]|next)$/i.test(element.textContent.trim())
      && (!element.href || C.sellerId(element.href) === C.sellerId(location.href)))
    if (next) next.click()
    else {
      clearTimeout(scrollTimer)
      const deadline = Date.now() + 18000
      const advance = () => {
        if (blocked || challengeSince || Date.now() >= deadline) return
        // The catalog lazily renders cards before requesting the next page.
        // Scrolling straight past its sentinel into the footer skips that load.
        const cards = [...document.querySelectorAll('.catalog-page__main article[data-nm-id]')].filter((item) => item.getClientRects().length)
        if (cards.length) cards.at(-1).scrollIntoView({ block: 'center', behavior: 'instant' })
        else window.scrollBy({ top: window.innerHeight * 0.8, behavior: 'instant' })
        scrollTimer = setTimeout(advance, 750)
      }
      advance()
    }
    respond({ ok: true })
  })
})()
