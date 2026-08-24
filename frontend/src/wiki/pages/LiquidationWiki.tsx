import { useState } from 'react'
import { WikiLayout, WikiSection } from '../WikiLayout'
import { ROUTES } from '@/lib/routes'

const SECTIONS = [
  { id: 'how-it-works', title: 'Как работает' },
  { id: 'instructions', title: 'Пошаговые инструкции' },
  { id: 'faq', title: 'Частые вопросы' },
  { id: 'glossary', title: 'Термины' },
]

export function LiquidationWiki() {
  return (
    <WikiLayout
      title="Ликвидация"
      subtitle="Плановое снижение цены для освобождения склада"
      sections={SECTIONS}
      activeModule={ROUTES.wiki.liquidation}
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
        Ликвидация — режим осознанной распродажи остатков с постепенным снижением цены. Алгоритм ежедневно
        проверяет кандидатов по трём сигналам: оборачиваемость, активность корзин и расходы на рекламу.
        Вы сами решаете, кого отправить в ликвидацию — система только предлагает и исполняет.
      </p>

      <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 mb-6">
        <div className="flex gap-3">
          <span className="text-lg leading-none mt-0.5">⚠️</span>
          <div>
            <div className="text-sm font-semibold text-amber-800 dark:text-amber-200 mb-1">Продажа ниже P_min</div>
            <div className="text-sm text-amber-700 dark:text-amber-300 leading-relaxed">
              В режиме ликвидации алгоритм может снижать цену <strong>ниже P_min</strong> — продавать с убытком.
              Это осознанное решение: освобождение склада важнее маржи.
            </div>
          </div>
        </div>
      </div>

      <h3 className="text-sm font-semibold text-foreground mb-3">Критерии попадания в список кандидатов</h3>
      <div className="space-y-3 text-sm mb-6">
        {CRITERIA.map((c) => (
          <div key={c.label} className="flex gap-3">
            <span className="text-muted-foreground/60 font-mono w-4 flex-shrink-0 mt-0.5">→</span>
            <div>
              <span className="font-semibold text-foreground">{c.label}:</span>{' '}
              <span className="text-muted-foreground">{c.desc}</span>
            </div>
          </div>
        ))}
      </div>

      <h3 className="text-sm font-semibold text-foreground mb-3">Механика снижения цены</h3>
      <div className="space-y-3">
        {STEPS.map((s, i) => (
          <div key={s.num} className="flex gap-4">
            <div className="flex-shrink-0 w-7 h-7 rounded-full bg-amber-100 text-amber-700 dark:text-amber-400 text-xs font-bold flex items-center justify-center">
              {s.num}
            </div>
            <div className="flex-1 pt-0.5">
              <div className="text-sm font-semibold text-foreground">{s.title}</div>
              <div className="text-sm text-muted-foreground mt-0.5">{s.body}</div>
              {i < STEPS.length - 1 && <div className="mt-3 w-px h-3 bg-muted ml-3" />}
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
      <h3 className="text-sm font-semibold text-foreground mb-3">Запустить ликвидацию для SKU</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside mb-6">
        <li>Откройте раздел <strong>Репрайсер → Ликвидация</strong>.</li>
        <li>Система показывает кандидатов — SKU с низкой оборачиваемостью или корзинами.</li>
        <li>Поставьте галочку рядом с нужными артикулами.</li>
        <li>Нажмите <strong>Запустить ликвидацию</strong> и подтвердите.</li>
        <li>Алгоритм начнёт снижать цену каждые 24 часа на заданный шаг.</li>
      </ol>

      <h3 className="text-sm font-semibold text-foreground mb-3">Остановить ликвидацию</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside mb-6">
        <li>Откройте карточку SKU или раздел Ликвидация.</li>
        <li>Нажмите <strong>Остановить</strong> рядом с нужным артикулом.</li>
        <li>Алгоритм вернётся в обычный режим с текущей ценой.</li>
        <li>P_min восстановится — алгоритм больше не будет опускать цену ниже него.</li>
      </ol>

      <h3 className="text-sm font-semibold text-foreground mb-3">Подтвердить продолжение ликвидации</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside">
        <li>Каждые 24 часа система запрашивает подтверждение продолжения.</li>
        <li>Найдите уведомление в разделе Ликвидация или в хедере приложения.</li>
        <li>Нажмите <strong>Продолжить</strong> — снижение продолжится.</li>
        <li>Если не подтвердить — ликвидация остановится автоматически.</li>
      </ol>
    </WikiSection>
  )
}

function Faq() {
  const items = [
    {
      q: 'Когда стоит запускать ликвидацию?',
      a: 'Смена коллекции, залежавшиеся остатки (оборачиваемость > 90 дней), товары с нулевыми корзинами несмотря на рекламу, плановая ротация ассортимента в конце сезона.',
    },
    {
      q: 'Какой шаг снижения цены?',
      a: 'Шаг задаётся в настройках алгоритма. По умолчанию снижение идёт ежедневно. Минимальная цена — 1 ₽ (ограничение WB), но продажа ниже себестоимости уже считается убытком.',
    },
    {
      q: 'Что будет с SKU после распродажи?',
      a: 'Когда остатки обнуляются, SKU автоматически выходит из режима ликвидации. Если добавить новую партию того же артикула — ликвидация не включится автоматически, нужно выбрать снова.',
    },
    {
      q: 'Можно ли задать нижнюю границу ниже которой не снижать?',
      a: 'Да, можно указать минимальную цену ликвидации в карточке SKU — алгоритм не опустится ниже неё, даже в режиме ликвидации. Это полезно если хотите продать с убытком, но не совсем в ноль.',
    },
    {
      q: 'Почему система не предлагает некоторые SKU как кандидатов?',
      a: 'SKU попадает в кандидаты при: оборачиваемость > 60 дней ИЛИ корзины = 0 за 14 дней при ненулевых рекламных расходах. Если товар продаётся медленно, но стабильно — он не кандидат.',
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
    { term: 'Оборачиваемость', def: 'Число дней, за которые распродаётся текущий остаток товара при текущем темпе продаж. Высокая оборачиваемость (>60–90 дн.) — сигнал к ликвидации.' },
    { term: 'Кандидат', def: 'SKU, который система предлагает для ликвидации по критериям оборачиваемости, корзин и расходов на рекламу.' },
    { term: 'Шаг снижения', def: 'Абсолютная или процентная величина, на которую цена снижается каждые 24 часа в режиме ликвидации.' },
    { term: 'Подтверждение 24ч', def: 'Ежедневный запрос системы: продолжать ли ликвидацию. Без подтверждения режим останавливается автоматически.' },
    { term: 'P_min в ликвидации', def: 'В режиме ликвидации P_min игнорируется — алгоритм может опустить цену ниже точки безубыточности.' },
  ]

  return (
    <WikiSection id="glossary" title="Термины">
      <div className="space-y-3">
        {terms.map((t) => (
          <div key={t.term} className="flex gap-3 text-sm">
            <span className="font-semibold text-foreground w-40 flex-shrink-0">{t.term}</span>
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

const CRITERIA = [
  { label: 'Низкая оборачиваемость', desc: 'Текущие остатки распродадутся дольше 60 дней при текущем темпе.' },
  { label: 'Нулевые корзины', desc: 'Покупатели не добавляли товар в корзину 14+ дней, при этом реклама работала.' },
  { label: 'Высокий ДРР', desc: 'Расходы на рекламу непропорционально высоки относительно выручки.' },
]

const STEPS = [
  { num: '1', title: 'Отбор кандидатов', body: 'Ежедневно алгоритм анализирует SKU по трём критериям и составляет список кандидатов.' },
  { num: '2', title: 'Ваш выбор', body: 'Вы просматриваете список, ставите галочки и подтверждаете запуск ликвидации.' },
  { num: '3', title: 'Снижение раз в 24ч', body: 'Каждые сутки цена снижается на заданный шаг. P_min в расчётах игнорируется.' },
  { num: '4', title: 'Ежедневное подтверждение', body: 'Система запрашивает подтверждение продолжения — защита от случайной затяжной распродажи.' },
  { num: '5', title: 'Завершение', body: 'Остатки проданы — ликвидация завершается автоматически. Или вы останавливаете вручную.' },
]
