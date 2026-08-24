import { useState } from 'react'
import { WikiLayout, WikiSection } from '../WikiLayout'
import { ROUTES } from '@/lib/routes'

const SECTIONS = [
  { id: 'how-it-works', title: 'Как работает' },
  { id: 'instructions', title: 'Пошаговые инструкции' },
  { id: 'faq', title: 'Частые вопросы' },
  { id: 'glossary', title: 'Термины' },
]

export function PromotionsWiki() {
  return (
    <WikiLayout
      title="Акции WB"
      subtitle="Защита минимальной цены в акциях Wildberries"
      sections={SECTIONS}
      activeModule={ROUTES.wiki.promotions}
    >
      <HowItWorks />
      <Instructions />
      <Faq />
      <Glossary />
    </WikiLayout>
  )
}

function HowItWorks() {
  return (
    <WikiSection id="how-it-works" title="Как работает">
      <p className="text-sm text-foreground leading-relaxed mb-5">
        WB регулярно проводит акции, в которые автоматически затягивает товары продавцов. Основная защита —
        <strong> min_price</strong>: параметр в WB API, который не даёт акционной цене опуститься ниже вашего
        P_min. Наш модуль управляет этой защитой: следит за акциями, показывает затронутые товары и даёт
        инструменты реагирования.
      </p>

      <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 mb-6">
        <div className="flex gap-3">
          <span className="text-lg leading-none mt-0.5">🚫</span>
          <div>
            <div className="text-sm font-semibold text-red-800 dark:text-red-200 mb-1">Нет API для управления акциями</div>
            <div className="text-sm text-red-700 dark:text-red-300 leading-relaxed">
              WB не предоставляет API для включения/выключения участия в акциях (апрель 2026, дорожной карты нет).
              Единственная защита — корректно установленный <code className="bg-red-500/20 px-1 rounded">min_price</code>.
            </div>
          </div>
        </div>
      </div>

      <h3 className="text-sm font-semibold text-foreground mb-3">Как работает защита через min_price</h3>
      <div className="space-y-3">
        {PROTECTION_STEPS.map((s, i) => (
          <div key={s.num} className="flex gap-4">
            <div className="flex-shrink-0 w-7 h-7 rounded-full bg-purple-100 text-purple-600 dark:text-purple-400 text-xs font-bold flex items-center justify-center">
              {s.num}
            </div>
            <div className="flex-1 pt-0.5">
              <div className="text-sm font-semibold text-foreground">{s.title}</div>
              <div className="text-sm text-muted-foreground mt-0.5">{s.body}</div>
              {i < PROTECTION_STEPS.length - 1 && <div className="mt-3 w-px h-3 bg-muted ml-3" />}
            </div>
          </div>
        ))}
      </div>

      <h3 className="text-sm font-semibold text-foreground mt-6 mb-3">Что показывает раздел «Акции»</h3>
      <div className="space-y-3 text-sm">
        {FEATURES.map((f) => (
          <div key={f.label} className="flex gap-3">
            <span className="text-muted-foreground/60 font-mono w-4 flex-shrink-0 mt-0.5">→</span>
            <div>
              <span className="font-semibold text-foreground">{f.label}:</span>{' '}
              <span className="text-muted-foreground">{f.desc}</span>
            </div>
          </div>
        ))}
      </div>
    </WikiSection>
  )
}

function Instructions() {
  return (
    <WikiSection id="instructions" title="Пошаговые инструкции">
      <h3 className="text-sm font-semibold text-foreground mb-3">Проверить защиту P_min для акции</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside mb-6">
        <li>Откройте раздел <strong>Акции WB</strong>.</li>
        <li>Просмотрите список активных акций WB и затронутых SKU.</li>
        <li>Проверьте колонку «min_price» — она должна равняться P_min из карточки SKU.</li>
        <li>Если значение не совпадает — нажмите <strong>Синхронизировать min_price</strong>.</li>
      </ol>

      <h3 className="text-sm font-semibold text-foreground mb-3">Обновить P_min перед началом акции</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside mb-6">
        <li>Перейдите в <strong>Репрайсер → Товары</strong>.</li>
        <li>Откройте карточку SKU, который участвует в акции.</li>
        <li>Пересчитайте себестоимость (изменились материалы? логистика?).</li>
        <li>Сохраните — P_min и min_price обновятся автоматически.</li>
      </ol>

      <h3 className="text-sm font-semibold text-foreground mb-3">Загрузить Excel с акционными товарами</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside">
        <li>Скачайте Excel-файл акции из личного кабинета WB.</li>
        <li>В разделе «Акции» нажмите <strong>Загрузить файл акции</strong>.</li>
        <li>Система сопоставит артикулы с вашими SKU и покажет, где min_price не защищает.</li>
        <li>Подтвердите массовое обновление min_price для всех затронутых товаров.</li>
      </ol>
    </WikiSection>
  )
}

function Faq() {
  const items = [
    {
      q: 'Почему нельзя просто отказаться от участия в акции через систему?',
      a: 'WB не предоставляет публичный API для управления участием в акциях (апрель 2026). Отказаться можно только вручную в личном кабинете WB. Наша защита — установка min_price, которая не даёт опуститься ниже точки безубыточности.',
    },
    {
      q: 'Что произойдёт, если min_price ниже P_min?',
      a: 'WB может опустить вашу цену до акционного уровня, что приведёт к убыткам. Система предупреждает, когда min_price ниже текущего P_min.',
    },
    {
      q: 'Как часто нужно проверять раздел «Акции»?',
      a: 'WB объявляет акции заблаговременно (обычно за 3-7 дней). Рекомендуем проверять раздел еженедельно и перед каждой крупной акцией (11.11, Новый год, распродажи). Система пришлёт уведомление при появлении новой акции.',
    },
    {
      q: 'Можно ли установить min_price выше P_min?',
      a: 'Да, min_price может быть выше P_min — тогда в акциях ваша цена не опустится ниже этого значения, даже если формально безубыточность позволяла бы продавать дешевле. Используйте для товаров с высокой маркой.',
    },
    {
      q: 'СПП учитывается при расчёте P_min?',
      a: 'СПП (скидка постоянного покупателя) — это скидка покупателю от WB, которую WB оплачивает сам. Она не влияет на вашу выручку напрямую и не учитывается в расчёте P_min. Влияет только официальная цена и комиссия WB.',
    },
  ]

  return (
    <WikiSection id="faq" title="Частые вопросы">
      <div className="space-y-1">
        {items.map((item) => <FaqItem key={item.q} q={item.q} a={item.a} />)}
      </div>
    </WikiSection>
  )
}

function Glossary() {
  const terms = [
    { term: 'min_price', def: 'Параметр WB API: минимальная цена участия в акции. WB не может снизить цену ниже этого значения. Устанавливается равным P_min через API при каждом сохранении настроек SKU.' },
    { term: 'P_min', def: 'Минимальная цена продажи без убытка, рассчитанная репрайсером. Синхронизируется с min_price.' },
    { term: 'СПП', def: 'Скидка Постоянного Покупателя — скидка от WB покупателю за лояльность. Оплачивается WB, не влияет на выручку продавца.' },
    { term: 'Акция WB', def: 'Периодическая скидочная кампания Wildberries, в которую могут принудительно включаться товары продавцов.' },
    { term: 'Excel акции', def: 'Файл из личного кабинета WB со списком товаров, участвующих в акции, и условиями скидок.' },
  ]

  return (
    <WikiSection id="glossary" title="Термины">
      <div className="space-y-3">
        {terms.map((t) => (
          <div key={t.term} className="flex gap-3 text-sm">
            <span className="font-semibold text-foreground w-36 flex-shrink-0">{t.term}</span>
            <span className="text-muted-foreground leading-relaxed">{t.def}</span>
          </div>
        ))}
      </div>
    </WikiSection>
  )
}

function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/40 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="text-sm font-medium text-foreground">{q}</span>
        <svg className={`w-4 h-4 flex-shrink-0 text-muted-foreground/70 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && <div className="px-4 pb-4 text-sm text-muted-foreground leading-relaxed border-t border-border/60 pt-3">{a}</div>}
    </div>
  )
}

const PROTECTION_STEPS = [
  { num: '1', title: 'WB анонсирует акцию', body: 'Wildberries создаёт акцию и включает в неё товары продавцов по своим критериям.' },
  { num: '2', title: 'Система читает список', body: 'Модуль получает список акций и затронутых SKU через WB API.' },
  { num: '3', title: 'Проверяет min_price', body: 'Для каждого SKU проверяется: установлен ли min_price равным P_min в WB API.' },
  { num: '4', title: 'Предупреждает о рисках', body: 'Если min_price отсутствует или ниже P_min — система подсвечивает SKU как рискованный.' },
  { num: '5', title: 'Обновляет защиту', body: 'По команде или автоматически устанавливает min_price = P_min для всех затронутых товаров.' },
]

const FEATURES = [
  { label: 'Список акций', desc: 'Текущие и предстоящие акции WB с датами и условиями.' },
  { label: 'Затронутые SKU', desc: 'Какие ваши товары включены в каждую акцию.' },
  { label: 'Статус защиты', desc: 'Для каждого SKU: защищён / требует обновления / без защиты.' },
  { label: 'Загрузка Excel', desc: 'Импорт файла акции из WB для массового сопоставления и обновления.' },
]
