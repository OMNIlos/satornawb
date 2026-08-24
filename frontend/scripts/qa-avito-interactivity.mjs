import { chromium } from 'playwright';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import os from 'node:os';
import { mkdtemp, writeFile } from 'node:fs/promises';

const projectRoot = path.resolve(import.meta.dirname, '..');
const staticUrl = pathToFileURL(path.join(projectRoot, 'public', 'vella-production.html')).href;
const preferredBaseUrl = process.env.QA_BASE_URL || 'http://127.0.0.1:5173';
const htmlUrl = await fetch(`${preferredBaseUrl}/vella-production.html`, { method: 'HEAD' })
  .then(response => response.ok ? `${preferredBaseUrl}/vella-production.html` : staticUrl)
  .catch(() => staticUrl);
const tabs = [
  ['avito-overview', 'Обзор'],
  ['avito-inbox', 'Сообщения'],
  ['avito-listings', 'Объявления'],
  ['avito-stats', 'Статистика'],
  ['avito-notifications', 'Уведомления'],
];

const viewports = [
  { width: 1173, height: 696 },
  { width: 1440, height: 900 },
];
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: viewports[0] });
const errors = [];
const tmpDir = await mkdtemp(path.join(os.tmpdir(), 'vella-avito-qa-'));
const validImagePath = path.join(tmpDir, 'fit-photo.png');
const unsupportedFilePath = path.join(tmpDir, 'size-table.pdf');
await writeFile(validImagePath, Buffer.from('89504e470d0a1a0a0000000d49484452', 'hex'));
await writeFile(unsupportedFilePath, Buffer.from('%PDF-1.4\n% unsupported attachment fixture\n'));
const isIgnorableConsoleError = text => (
  htmlUrl.startsWith('file:') && text === 'Failed to load resource: net::ERR_FILE_NOT_FOUND'
);
page.on('console', msg => {
  if (msg.type() === 'error' && !isIgnorableConsoleError(msg.text())) errors.push(msg.text());
});
page.on('pageerror', error => errors.push(error.message));

async function assertNoNestedVerticalScroll(label) {
  const offenders = await page.evaluate(() => {
    const selectors = [
      '.report-shell',
      '.report-table-wrap',
      '.table-wrap',
      '.avito-overview-shell',
      '.avito-listings-shell',
      '.avito-listings-main',
      '.avito-stats-shell',
      '.avito-stats-main',
      '.avito-detail-panel',
      '.avito-detail-body',
      '.notif-page',
      '.notif-main',
      '.notif-side',
      '.notif-table-wrap',
    ];
    const active = document.querySelector('.tab-content.active');
    if (!active) return ['no active tab'];
    return [...active.querySelectorAll(selectors.join(','))]
      .map(el => {
        const cs = getComputedStyle(el);
        return {
          selector: el.id ? `#${el.id}` : '.' + [...el.classList].slice(0, 3).join('.'),
          overflowY: cs.overflowY,
          scrollHeight: Math.round(el.scrollHeight),
          clientHeight: Math.round(el.clientHeight),
        };
      })
      .filter(item => ['auto', 'scroll', 'hidden'].includes(item.overflowY) && item.scrollHeight > item.clientHeight + 2)
      .map(item => `${item.selector} overflow-y:${item.overflowY} ${item.scrollHeight}/${item.clientHeight}`);
  });
  if (offenders.length) throw new Error(`${label}: nested vertical scroll:\n${offenders.join('\n')}`);
}

async function assertAvitoInboxScrollLayout() {
  const layout = await page.evaluate(() => {
    const read = selector => {
      const el = document.querySelector(selector);
      if (!el) return null;
      const cs = getComputedStyle(el);
      const rect = el.getBoundingClientRect();
      return {
        selector,
        display: cs.display,
        flex: cs.flex,
        overflowY: cs.overflowY,
        height: Math.round(rect.height),
        top: Math.round(rect.top),
        bottom: Math.round(rect.bottom),
      };
    };
    return {
      viewportHeight: window.innerHeight,
      items: [
        read('#tab-avito-inbox'),
        read('#tab-avito-inbox .avito-inbox-shell'),
        read('#tab-avito-inbox .avito-conversation-list'),
        read('#tab-avito-inbox .avito-message-stream'),
        read('#tab-avito-inbox .avito-context'),
        read('#tab-avito-inbox .avito-composer'),
        read('#tab-avito-inbox .avito-suggestion'),
      ],
    };
  });
  const missing = layout.items.slice(0, 6).filter(item => !item).map((_, index) => index);
  if (missing.length) throw new Error(`Avito inbox layout missing required nodes: ${missing.join(', ')}`);
  const [tab, shell, list, stream, context, composer, suggestion] = layout.items;
  const failures = [];
  if (tab.overflowY !== 'hidden') failures.push(`#tab-avito-inbox overflow-y is ${tab.overflowY}`);
  if (shell.flex === '0 0 auto' || shell.overflowY !== 'hidden') failures.push(`shell flex/overflow is ${shell.flex}/${shell.overflowY}`);
  if (list.overflowY !== 'auto') failures.push(`conversation list overflow-y is ${list.overflowY}`);
  if (stream.overflowY !== 'auto') failures.push(`message stream overflow-y is ${stream.overflowY}`);
  if (context.overflowY !== 'auto') failures.push(`context overflow-y is ${context.overflowY}`);
  if (composer.bottom > layout.viewportHeight + 1) failures.push(`composer bottom ${composer.bottom} exceeds viewport ${layout.viewportHeight}`);
  if (composer.height < 60) failures.push(`composer height is too small: ${composer.height}`);
  if (suggestion) failures.push('suggestion block should not be rendered in Avito inbox');
  if (failures.length) throw new Error(`Avito inbox scroll layout failed:\n${failures.join('\n')}`);
}

for (const viewport of viewports) {
  await page.setViewportSize(viewport);
  for (const [tab, label] of tabs) {
    await page.goto(`${htmlUrl}?tab=${tab}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(900);
    await page.locator(`#tab-${tab === 'avito-notifications' ? 'notifications' : tab}`).waitFor({ state: 'visible' });
    await page.locator(`.subtab[data-tab="${tab}"].active`).waitFor({ state: 'visible' });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2);
    if (overflow) throw new Error(`${label} ${viewport.width}x${viewport.height}: horizontal overflow`);
    await assertNoNestedVerticalScroll(`${label} ${viewport.width}x${viewport.height}`);
  }
}

await page.goto(`${htmlUrl}?tab=avito-overview`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(900);
const overviewViewsBefore = await page.locator('#avitoOverviewViews').textContent();
const overviewTopBefore = await page.locator('#avitoTopYohjiMeta').textContent();
await page.locator('[data-avito-overview-period-control] .period-btn[data-period="30"]').click();
await page.locator('[data-avito-overview-period-control] .period-btn[data-period="30"].active').waitFor({ state: 'visible' });
const overviewViewsAfter = await page.locator('#avitoOverviewViews').textContent();
const overviewTopAfter = await page.locator('#avitoTopYohjiMeta').textContent();
if (overviewViewsBefore === overviewViewsAfter) throw new Error('Avito overview period did not update operational metrics');
if (overviewTopBefore === overviewTopAfter) throw new Error('Avito overview period did not update top positions');
await page.locator('[data-avito-overview-period-control] .period-btn[data-period="1"]').click();
await page.locator('[data-avito-overview-period-control] .period-btn[data-period="1"].active').waitFor({ state: 'visible' });
const overviewSummary = await page.locator('#avitoOverviewPeriodSummary').textContent();
if (!overviewSummary?.includes('1 день')) throw new Error(`Avito overview period summary did not update: ${overviewSummary}`);

await page.goto(`${htmlUrl}?tab=avito-stats`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(900);
const initialToastCount = await page.locator('#toastContainer .toast').count();
await page.locator('[data-avito-stats-mode="funnel"]').click();
await page.locator('[data-avito-stats-mode="funnel"].active').waitFor({ state: 'visible' });
await page.locator('[data-avito-stats-mode="sales"]').click();
await page.locator('[data-avito-stats-mode="sales"].active').waitFor({ state: 'visible' });
const afterModeToastCount = await page.locator('#toastContainer .toast').count();
if (afterModeToastCount !== initialToastCount) throw new Error('Avito stats mode switch created a toast');
await page.locator('#tab-avito-stats .avito-stats-row').first().click();
await page.locator('#avitoStatsDetailPanel.open').waitFor({ state: 'visible' });
await assertNoNestedVerticalScroll('Статистика detail-open');
const statsDetailChartText = await page.locator('#avitoStatsDetailMiniChart').textContent();
if (/max|mid|начало|середина|конец|Значение|Период/.test(statsDetailChartText || '')) {
  throw new Error(`Stats detail chart still has placeholder axis labels: ${statsDetailChartText}`);
}
if (!/Просмотры/.test(statsDetailChartText || '') || await page.locator('#avitoStatsDetailMiniChart .avito-mini-chart-point').count() < 6) {
  throw new Error(`Stats detail chart is not rendering concrete values: ${statsDetailChartText}`);
}
await page.keyboard.press('Escape');
await page.waitForTimeout(100);
if (await page.locator('#avitoStatsDetailPanel.open').count()) throw new Error('Stats popup did not close on Escape');
if (await page.locator('#avitoStatsPeriod').count()) throw new Error('Avito stats still duplicates period selector in local toolbar');
await page.locator('#globalPeriod .period-btn[data-period="30"]').click();
await page.locator('#globalPeriod .period-btn[data-period="30"].active').waitFor({ state: 'visible' });
const initialGlobalPeriod = await page.locator('#globalPeriod .period-btn.active').getAttribute('data-period');
if (initialGlobalPeriod !== '30') throw new Error(`Avito stats global period is not synced after explicit set: ${initialGlobalPeriod}`);
const statsViewsBefore = await page.locator('#avitoStatsKpiViews').textContent();
await page.locator('#globalPeriod .period-btn[data-period="7"]').click();
const globalPeriodAfterSelect = await page.locator('#globalPeriod .period-btn.active').getAttribute('data-period');
if (globalPeriodAfterSelect !== '7') throw new Error(`Avito stats period select did not sync global control: ${globalPeriodAfterSelect}`);
const statsViewsAfter = await page.locator('#avitoStatsKpiViews').textContent();
if (statsViewsBefore === statsViewsAfter) throw new Error('Avito stats period did not update KPI values');
await page.locator('#globalPeriod .period-btn[data-period="14"]').click();
const statsPeriodBadgeAfterGlobalClick = await page.locator('#avitoStatsPeriodBadge').textContent();
if (statsPeriodBadgeAfterGlobalClick !== '14 дней') throw new Error(`Avito stats period badge did not sync global control: ${statsPeriodBadgeAfterGlobalClick}`);
const statsAxisText = await page.locator('#tab-avito-stats').textContent();
if (/X: дата|Y: шт/.test(statsAxisText || '')) throw new Error('Avito stats still contains chart debug axis labels');
if (/Объявления по метрикам/.test(statsAxisText || '')) throw new Error('Avito stats still contains unclear listing block title');

await page.goto(`${htmlUrl}?tab=avito-listings`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(900);
await page.locator('#tab-avito-listings .avito-listing-row').first().click();
await page.locator('#avitoListingDetailPanel.open').waitFor({ state: 'visible' });
await assertNoNestedVerticalScroll('Объявления detail-open');
const listingViewsBefore = await page.locator('#avitoDetailViews').textContent();
await page.locator('[data-avito-detail-period-control] .period-btn[data-period="30"]').click();
await page.locator('[data-avito-detail-period-control] .period-btn[data-period="30"].active').waitFor({ state: 'visible' });
const listingViewsAfter = await page.locator('#avitoDetailViews').textContent();
if (listingViewsBefore === listingViewsAfter) throw new Error('Listings popup period did not update metric values');
const listingDeltaClasses = await page.evaluate(() => [...document.querySelectorAll('#avito-sec-metrics .avito-detail-delta')].map(el => el.className));
if (!listingDeltaClasses.some(className => className.includes('up')) || !listingDeltaClasses.some(className => className.includes('down'))) {
  throw new Error(`Listings popup deltas do not expose both positive and negative states: ${listingDeltaClasses.join(', ')}`);
}
await page.locator('[data-avito-detail-chart-mode="funnel"]').click();
await page.locator('[data-avito-detail-chart-mode="funnel"].active').waitFor({ state: 'visible' });
if (await page.locator('#avitoDetailChartSvg .avito-detail-chart-prev').count() === 0) throw new Error('Listings popup chart does not render previous-period line');
await page.locator('#avitoDetailChartSvg .avito-chart-hit').nth(2).hover();
await page.locator('#avitoDetailChartTooltip.active').waitFor({ state: 'visible' });
const listingChartTip = await page.locator('#avitoDetailChartTooltip').textContent();
if (!listingChartTip?.includes('сейчас / было')) throw new Error(`Listings chart tooltip is not comparative: ${listingChartTip}`);
if (await page.locator('#avitoListingDetailPanel .avito-section-nav button', { hasText: /^Фото$/ }).count()) {
  throw new Error('Listings popup still exposes standalone Photo section');
}
if (await page.locator('#avitoListingDetailPanel .avito-section-nav button', { hasText: /^Цена$/ }).count()) {
  throw new Error('Listings popup still exposes standalone Price section');
}
if (await page.locator('#avito-sec-photos, #avito-sec-repricer, #avitoPhotoGrid').count()) {
  throw new Error('Listings popup still contains removed Photo/Price sections');
}
const draftText = await page.locator('#avito-sec-draft').textContent();
if (!draftText?.includes('Статус черновика') || !draftText.includes('Проверка XML')) {
  throw new Error(`Listings changes section is not draft-focused: ${draftText}`);
}
await page.locator('#avitoListingDetailPanel .avito-section-nav button', { hasText: 'XML' }).click();
await page.waitForTimeout(150);
const activeListingSection = await page.locator('#avitoListingDetailPanel .avito-section-nav button.active').textContent();
if (activeListingSection !== 'XML') throw new Error(`Listings popup nav did not follow scroll: ${activeListingSection}`);
await page.locator('#avitoPopupBackdrop.open').click({ position: { x: 10, y: 10 } });
await page.waitForTimeout(100);
if (await page.locator('#avitoListingDetailPanel.open').count()) throw new Error('Listings popup did not close on backdrop click');
await page.locator('#avitoListingsChips .chip', { hasText: 'XML-проверка' }).click();
const visibleListingTitles = await page.evaluate(() => [...document.querySelectorAll('#tab-avito-listings .avito-listing-row')]
  .filter(row => !row.classList.contains('is-hidden-by-filter'))
  .map(row => row.querySelector('.avito-listing-title b')?.textContent?.trim() || ''));
if (visibleListingTitles.length !== 2 || !visibleListingTitles.some(title => title.includes('Devil')) || !visibleListingTitles.some(title => title.includes('Jaded'))) {
  throw new Error(`Listings XML filter failed: ${visibleListingTitles.join(', ')}`);
}
await page.locator('#avitoListingsSearch').fill('Everlast');
const searchedListingTitles = await page.evaluate(() => [...document.querySelectorAll('#tab-avito-listings .avito-listing-row')]
  .filter(row => !row.classList.contains('is-hidden-by-filter'))
  .map(row => row.querySelector('.avito-listing-title b')?.textContent?.trim() || ''));
if (searchedListingTitles.length !== 0) throw new Error(`Listings search should combine with XML filter and return empty: ${searchedListingTitles.join(', ')}`);

await page.locator('#bellBtn').click();
await page.locator('#ddNotif.open').waitFor({ state: 'visible' });
await page.mouse.click(20, 20);
await page.waitForTimeout(100);
if (await page.locator('#ddNotif.open').count()) throw new Error('Notification dropdown did not close on outside click');

await page.locator('#bellBtn').click();
await page.locator('#ddNotif.open').waitFor({ state: 'visible' });
await page.keyboard.press('Escape');
await page.waitForTimeout(100);
if (await page.locator('#ddNotif.open').count()) throw new Error('Notification dropdown did not close on Escape');

await page.goto(`${htmlUrl}?tab=avito-inbox`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(900);
const avitoForbiddenText = await page.evaluate(() => {
  const avitoTabs = ['tab-avito-overview', 'tab-avito-inbox', 'tab-avito-listings', 'tab-avito-stats']
    .map(id => document.getElementById(id))
    .filter(Boolean);
  return avitoTabs
    .map(tab => tab.textContent || '')
    .filter(text => text.includes('Сохранить вид'));
});
if (avitoForbiddenText.length) throw new Error('Avito still contains "Сохранить вид"');
const inboxText = await page.locator('#tab-avito-inbox').textContent();
if (/Остаток|остаток|остатки/.test(inboxText || '')) throw new Error('Avito inbox still contains stock wording');
const forbiddenInboxText = ['Шаблоны', 'Изменить шаблон', 'Черновик ответа', 'Доступы', 'Журнал', 'Тема и сроки'];
const foundForbiddenInboxText = forbiddenInboxText.filter(item => (inboxText || '').includes(item));
if (foundForbiddenInboxText.length) throw new Error(`Avito inbox contains removed text: ${foundForbiddenInboxText.join(', ')}`);
await assertAvitoInboxScrollLayout();
await page.locator('#avitoChatTitle', { hasText: 'Футболка белая' }).waitFor({ state: 'visible' });
await page.locator('#avitoAttachmentInput').setInputFiles(validImagePath);
await page.locator('#avitoAttachmentTray.active .avito-attachment-item:not(.blocked)', { hasText: 'fit-photo.png' }).waitFor({ state: 'visible' });
let attachmentHint = await page.locator('#avitoAttachmentHint').textContent();
if (!attachmentHint?.includes('добавлено')) throw new Error(`Valid image did not update attachment hint: ${attachmentHint}`);
await page.locator('#avitoAttachmentTray .avito-attachment-remove').click();
await page.waitForTimeout(100);
if (await page.locator('#avitoAttachmentTray.active').count()) throw new Error('Attachment tray stayed visible after removing the only attachment');
await page.locator('#avitoAttachmentInput').setInputFiles(validImagePath);
await page.locator('#avitoAttachmentTray.active .avito-attachment-item:not(.blocked)', { hasText: 'fit-photo.png' }).waitFor({ state: 'visible' });
await page.locator('#avitoSendButton').click();
await page.locator('#avitoMessageStream .avito-message-attachment', { hasText: 'fit-photo.png' }).last().waitFor({ state: 'visible' });
if (await page.locator('#avitoAttachmentTray.active').count()) throw new Error('Attachment tray did not reset after prepare-send preview');
await page.locator('#avitoAttachmentInput').setInputFiles(unsupportedFilePath);
await page.locator('#avitoAttachmentTray.active .avito-attachment-item.blocked', { hasText: 'size-table.pdf' }).waitFor({ state: 'visible' });
attachmentHint = await page.locator('#avitoAttachmentHint').textContent();
if (!attachmentHint?.includes('Авито API')) throw new Error(`Unsupported attachment did not show Avito API blocker: ${attachmentHint}`);
await page.locator('#avitoSendButton').click();
await page.locator('#avitoAttachmentTray.active .avito-attachment-item.blocked', { hasText: 'size-table.pdf' }).waitFor({ state: 'visible' });
await page.locator('#avitoAttachmentTray .avito-attachment-remove').click();
await page.waitForTimeout(100);
await page.locator('#avitoAttachmentInput').setInputFiles(validImagePath);
await page.locator('#avitoAttachmentTray.active .avito-attachment-item:not(.blocked)', { hasText: 'fit-photo.png' }).waitFor({ state: 'visible' });
await page.locator('#tab-avito-inbox [data-conversation-key="pavel"]').click();
await page.locator('#avitoChatTitle', { hasText: 'Худи чёрное' }).waitFor({ state: 'visible' });
if (await page.locator('#avitoAttachmentTray.active').count()) throw new Error('Attachment tray did not reset after switching conversations');

const expectedListings = [
  'Футболка белая · BT_42 · Anomie · Москва',
  'Худи чёрное oversize · Bless T · Подольск',
  'Лонгслив белый · Pearl · Bless T · Москва',
  'Футболка чёрная · Anime print · Anomie · Москва',
];
for (const listing of expectedListings) {
  await page.locator('#tab-avito-inbox .avito-conv-listing', { hasText: listing }).waitFor({ state: 'visible' });
}

const getVisibleInboxBuyers = () => page.evaluate(() => [...document.querySelectorAll('#tab-avito-inbox [data-avito-inbox-row]')]
  .filter(row => getComputedStyle(row).display !== 'none')
  .map(row => row.querySelector('.avito-conv-buyer')?.textContent?.trim() || ''));

await page.locator('#tab-avito-inbox .chips .chip', { hasText: 'Непрочитанные' }).click();
await page.locator('#tab-avito-inbox .chips .chip.active', { hasText: 'Непрочитанные' }).waitFor({ state: 'visible' });
let visibleInboxBuyers = await getVisibleInboxBuyers();
if (visibleInboxBuyers.length !== 2 || !visibleInboxBuyers.some(name => name.includes('Ирина')) || !visibleInboxBuyers.some(name => name.includes('Алексей'))) {
  throw new Error(`Unread inbox filter did not filter rows: ${visibleInboxBuyers.join(', ')}`);
}
await page.locator('#tab-avito-inbox .chips .chip', { hasText: 'На проверке' }).click();
await page.locator('#tab-avito-inbox .chips .chip.active', { hasText: 'На проверке' }).waitFor({ state: 'visible' });
visibleInboxBuyers = await getVisibleInboxBuyers();
if (visibleInboxBuyers.length !== 1 || !visibleInboxBuyers[0].includes('Ирина')) throw new Error(`Bot inbox filter failed: ${visibleInboxBuyers.join(', ')}`);
await page.locator('#tab-avito-inbox .chips .chip', { hasText: /^Все/ }).click();
await page.locator('#avitoInboxSort').selectOption('urgent');
visibleInboxBuyers = await getVisibleInboxBuyers();
if (!visibleInboxBuyers[0]?.includes('Павел')) throw new Error(`Urgent inbox sort failed: ${visibleInboxBuyers.join(', ')}`);
await page.locator('#avitoInboxSearch').fill('Pearl');
visibleInboxBuyers = await getVisibleInboxBuyers();
if (visibleInboxBuyers.length !== 1 || !visibleInboxBuyers[0].includes('Алексей')) throw new Error(`Inbox search failed: ${visibleInboxBuyers.join(', ')}`);
await page.locator('#tab-avito-inbox [data-conversation-key="alexey"]').click();
await page.locator('#avitoChatTitle', { hasText: 'Лонгслив белый' }).waitFor({ state: 'visible' });
await page.locator('#avitoContextBuyer', { hasText: 'Алексей' }).waitFor({ state: 'visible' });
if (!(await page.locator('#avitoSendButton').isDisabled())) throw new Error('Blocked inbox conversation should disable send button');
if (!(await page.locator('#avitoAttachButton').isDisabled())) throw new Error('Blocked inbox conversation should disable attachment button');
const blockedAttachmentHint = await page.locator('#avitoAttachmentHint').textContent();
if (!blockedAttachmentHint?.includes('messenger:write') && !blockedAttachmentHint?.includes('Нет тарифа')) {
  throw new Error(`Blocked inbox conversation did not show attachment capability reason: ${blockedAttachmentHint}`);
}
await page.locator('#avitoInboxSearch').fill('zzzz-no-match');
await page.locator('#avitoInboxEmpty.active').waitFor({ state: 'visible' });

await page.goto(`${htmlUrl}?tab=avito-notifications`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(900);
const avitoNotifText = await page.locator('#tab-notifications').textContent();
if (/AI|WB-дайджест|Сводный дайджест WB/.test(avitoNotifText || '')) throw new Error('Avito notifications contain generic WB/AI notification UI');
await page.locator('#notifCategoryChips .chip', { hasText: 'Блокировки' }).click();
await page.locator('#notifCategoryChips .chip.active', { hasText: 'Блокировки' }).waitFor({ state: 'visible' });

for (const [tab, label] of tabs) {
  await page.goto(`${htmlUrl}?tab=${tab}`, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(900);
  const activeText = await page.locator(`#tab-${tab === 'avito-notifications' ? 'notifications' : tab}`).textContent();
  const forbidden = ['прототип', 'открыть справа', 'REST-правка', 'X: дата', 'Y: шт', 'Фильтры открыты', 'частично', 'частичный', 'частичная', 'частичные', 'узкое место', 'лидер', 'дорогой контакт', 'дорогой трафик', 'хорошая видимость', 'низкая конверсия', 'просад', 'ниже нормы', 'блокер'];
  const found = forbidden.filter(item => (activeText || '').includes(item));
  if (found.length) throw new Error(`${label} contains forbidden visible text: ${found.join(', ')}`);
}

await browser.close();

if (errors.length) {
  throw new Error(`Console errors:\n${errors.join('\n')}`);
}

console.log('Avito HTML interactivity QA passed');
