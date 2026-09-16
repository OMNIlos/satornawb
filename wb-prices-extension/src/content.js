(() => {
  'use strict'
  if (window.top !== window) return
  const C = WbPricesContract
  let blocked = false
  let checkTimer = null
  const send = (message) => { void chrome.runtime.sendMessage({ source: C.SOURCE, ...message }).catch(() => {}) }

  window.addEventListener('message', (event) => {
    if (event.source !== window || event.origin !== C.WB_ORIGIN) return
    const clean = C.sanitizePageMessage(event.data, location.href)
    if (clean) send(clean)
  })

  function checkChallenge() {
    checkTimer = null
    if (blocked) return
    const title = document.title.trim()
    const challenge = /^(access denied|captcha|доступ (ограничен|запрещен)|проверка (браузера|безопасности)|just a moment)/i.test(title)
      || (!document.querySelector('article[data-nm-id]') && /подтвердите,? что вы (не робот|человек)|проверяем.{0,40}(браузер|не робот)/i.test((document.body?.innerText || '').slice(0, 3000)))
    if (challenge) { blocked = true; send({ type: 'blocked', code: 'challenge' }) }
  }

  function watchChallenge() {
    checkChallenge()
    new MutationObserver(() => { if (!checkTimer && !blocked) checkTimer = setTimeout(checkChallenge, 250) })
      .observe(document.documentElement, { childList: true, subtree: true })
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', watchChallenge, { once: true })
  else watchChallenge()

  chrome.runtime.onMessage.addListener((message, sender, respond) => {
    if (sender.id !== chrome.runtime.id || message?.type !== 'scroll' || !C.sellerId(location.href) || blocked) return
    // Follow a control that the live page actually exposes; never invent page=N.
    const controls = document.querySelectorAll('[class*="pagination"] a, [class*="pagination"] button, [data-testid*="pagination"] a, [data-testid*="pagination"] button')
    const next = [...controls].find((element) => element.getClientRects().length && !element.disabled
      && element.getAttribute('aria-disabled') !== 'true'
      && /^(следующая(?: страница)?|далее|показать ещ[её]|загрузить ещ[её]|next)$/i.test(element.textContent.trim())
      && (!element.href || C.sellerId(element.href) === C.sellerId(location.href)))
    if (next) next.click()
    else window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' })
    respond({ ok: true })
  })
})()
