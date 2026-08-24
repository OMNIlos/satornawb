import { useState } from 'react'
import { WikiLayout, WikiSection } from '../WikiLayout'
import { ROUTES } from '@/lib/routes'

const SECTIONS = [
  { id: 'how-it-works', title: 'Как работает' },
  { id: 'instructions', title: 'Пошаговые инструкции' },
  { id: 'faq', title: 'Частые вопросы' },
  { id: 'glossary', title: 'Термины' },
]

export function WbRepricerWiki() {
  return (
    <WikiLayout
      title="WB Репрайсер"
      subtitle="Автоматическое управление ценами на Wildberries"
      sections={SECTIONS}
      activeModule={ROUTES.wiki.wbRepricer}
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
        Репрайсер следит за корзинами по каждому артикулу и автоматически корректирует цену, не выходя за
        установленные вами границы P_min и максимальной цены. Всё происходит без вашего участия.
      </p>

      <div className="grid grid-cols-3 gap-4 mb-6">
        <BenefitCard icon="⏱" title="Экономит время" body="Не нужно вручную менять цены — система делает это по расписанию." />
        <BenefitCard icon="📈" title="Максимизирует выручку" body="Поднимает цену при высоком спросе без потери позиций в поиске." />
        <BenefitCard icon="🛡" title="Защищает от убытков" body="Никогда не опустит цену ниже P_min — точки безубыточности." />
      </div>

      <h3 className="text-sm font-semibold text-foreground mb-3">Цикл работы алгоритма</h3>
      <div className="space-y-3">
        {ALGORITHM_STEPS.map((s, i) => (
          <div key={s.num} className="flex gap-4">
            <div className="flex-shrink-0 w-7 h-7 rounded-full bg-indigo-100 text-indigo-600 dark:text-indigo-400 text-xs font-bold flex items-center justify-center">
              {s.num}
            </div>
            <div className="flex-1 pt-0.5">
              <div className="text-sm font-semibold text-foreground">{s.title}</div>
              <div className="text-sm text-muted-foreground mt-0.5">{s.body}</div>
              {i < ALGORITHM_STEPS.length - 1 && <div className="mt-3 w-px h-3 bg-muted ml-3" />}
            </div>
          </div>
        ))}
      </div>

      <h3 className="text-sm font-semibold text-foreground mt-6 mb-3">Статусы SKU</h3>
      <div className="grid grid-cols-2 gap-3">
        {STATUSES.map((s) => (
          <div key={s.badge} className="bg-card border border-border rounded-lg p-3">
            <span className={`inline-flex items-center px-2 py-0.5 text-xs font-medium uppercase rounded border mb-2 ${s.className}`}>
              {s.badge}
            </span>
            <div className="text-sm font-semibold text-foreground mb-1">{s.title}</div>
            <div className="text-xs text-muted-foreground leading-relaxed">{s.body}</div>
          </div>
        ))}
      </div>

      <h3 className="text-sm font-semibold text-foreground mt-6 mb-3">Ночная медиана</h3>
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 text-sm text-foreground">
        <p className="leading-relaxed">
          С <strong>23:00 до 04:00 МСК</strong> алгоритм переключается в режим ночной медианы: поднимает цену на
          заданный процент (консервативный +5% или агрессивный +10%), улучшая позицию в ночном ранжировании WB.
          В 04:00 цена автоматически возвращается к дневной базовой.
        </p>
      </div>
    </WikiSection>
  )
}

function Instructions() {
  return (
    <WikiSection id="instructions" title="Пошаговые инструкции">
      <h3 className="text-sm font-semibold text-foreground mb-3">Добавить новый SKU</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside mb-6">
        <li>Откройте раздел <strong>Репрайсер → Товары</strong>.</li>
        <li>Найдите артикул в таблице (поиск по артикулу или названию).</li>
        <li>Нажмите на строку — откроется карточка SKU.</li>
        <li>Заполните: Себестоимость, Комиссия WB, Логистика WB, Целевая маржа, Максимальная цена.</li>
        <li>P_min рассчитается автоматически — проверьте, что он ниже Максимальной цены.</li>
        <li>Нажмите <strong>Сохранить</strong>. Алгоритм начнёт работу сразу.</li>
      </ol>

      <h3 className="text-sm font-semibold text-foreground mb-3">Настроить ночную медиану</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside mb-6">
        <li>Откройте <strong>Репрайсер → Алгоритм</strong>.</li>
        <li>В блоке «Ночная медиана» установите режим: <em>Консервативный (+5%)</em> или <em>Агрессивный (+10%)</em>.</li>
        <li>Сохраните. Изменения применятся с ближайшего цикла в 23:00.</li>
      </ol>

      <h3 className="text-sm font-semibold text-foreground mb-3">Перевести SKU на ручное управление</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside mb-6">
        <li>Откройте карточку SKU.</li>
        <li>В блоке «Режим управления» выберите <strong>Ручной</strong>.</li>
        <li>Введите новую цену и сохраните.</li>
        <li>Алгоритм не будет трогать цену, пока вы не вернёте статус «Авто».</li>
      </ol>

      <h3 className="text-sm font-semibold text-foreground mb-3">Посмотреть журнал изменений</h3>
      <ol className="space-y-2 text-sm text-foreground list-decimal list-inside">
        <li>Откройте <strong>Репрайсер → Журнал</strong>.</li>
        <li>Используйте фильтры по триггеру (алгоритм / ночная медиана / ручное / ликвидация).</li>
        <li>Кликните на строку — откроется карточка SKU в соответствующем состоянии.</li>
      </ol>
    </WikiSection>
  )
}

function Faq() {
  const items = [
    {
      q: 'Что такое «норма корзин» и откуда она берётся?',
      a: 'Норма — ориентир: сколько раз товар должен добавляться в корзину за 7 дней при нормальном спросе. Порядок: (1) ручной ввод руководителя — приоритет; (2) авторасчёт по данным WB Analytics; (3) fallback по типу товара на период прогрева. Ручной ввод нужен, если автоматика дала заниженную норму из-за плохого прошлого (завышенная цена, слабые фото).',
    },
    {
      q: 'Почему цена не меняется при включённой автоматике?',
      a: 'Возможные причины: SKU в периоде warmup (менее 30 дней), корзин столько же, сколько норма — изменение не нужно, цена уже на границе P_min или Максимальной цены.',
    },
    {
      q: 'Что произойдёт, если Максимальная цена окажется ниже P_min?',
      a: 'Система покажет ошибку валидации и не позволит сохранить настройки. Максимальная цена всегда должна быть выше P_min — иначе алгоритму негде работать.',
    },
    {
      q: 'Что такое режим ликвидации?',
      a: 'Специальный режим, при котором алгоритм может снижать цену ниже P_min — продавать с убытком, чтобы быстро освободить склад. Требует подтверждения каждые 24 часа.',
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
    { term: 'P_min', def: 'Минимальная цена продажи без убытка. Рассчитывается автоматически: (Себестоимость + Логистика) / (1 − Комиссия − Целевая маржа). WB не может опустить цену ниже в акциях.' },
    { term: 'Корзины', def: 'Добавления товара в корзину покупателями. Основной сигнал алгоритма: больше корзин → выше спрос → можно поднять цену.' },
    { term: 'Норма корзин', def: 'Целевой уровень корзин за 7 дней при нормальном спросе. Используется как точка сравнения для решений алгоритма.' },
    { term: 'Прогрев (warmup)', def: 'Период накопления данных для нового SKU (30 дней). В это время алгоритм не работает — нет достаточной статистики.' },
    { term: 'Ночная медиана', def: 'Механизм повышения цены с 23:00 до 04:00 для улучшения медианной позиции в ночном ранжировании WB.' },
    { term: 'min_price', def: 'Параметр в WB API: защита от принудительного снижения цены в акциях WB. Устанавливается равным P_min.' },
    { term: 'Ликвидация', def: 'Режим осознанной продажи с убытком для быстрого освобождения склада. Алгоритм игнорирует P_min.' },
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

function BenefitCard({ icon, title, body }: { icon: string; title: string; body: string }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="text-2xl mb-2">{icon}</div>
      <div className="text-sm font-semibold text-foreground mb-1">{title}</div>
      <div className="text-xs text-muted-foreground leading-relaxed">{body}</div>
    </div>
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

const ALGORITHM_STEPS = [
  { num: '1', title: 'Мониторим корзины', body: 'Каждый цикл система смотрит, сколько раз покупатели добавили товар в корзину за последние 7 дней.' },
  { num: '2', title: 'Сравниваем с нормой', body: 'Корзин больше нормы — спрос высокий, цену поднять. Меньше нормы — снизить, чтобы привлечь покупателей.' },
  { num: '3', title: 'Двигаем цену на шаг', body: 'Изменение постепенное — на заданный шаг с дневным лимитом.' },
  { num: '4', title: 'Проверяем границы', body: 'Новая цена не ниже P_min и не выше Максимальной цены.' },
  { num: '5', title: 'Синхронизируем с WB', body: 'Финальная цена отправляется в WB через API. Обновляется min_price — защита от принудительного снижения на акциях.' },
]

const STATUSES = [
  {
    badge: 'auto',
    className: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30',
    title: 'Автоматика активна',
    body: 'Репрайсер управляет ценой по алгоритму корзин. SKU проработал 30+ дней.',
  },
  {
    badge: 'manual',
    className: 'bg-muted text-foreground border-border',
    title: 'Ручное управление',
    body: 'Автоматика отключена. Цена меняется только вручную.',
  },
  {
    badge: 'warmup',
    className: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30',
    title: 'Накопление данных',
    body: 'SKU добавлен менее 30 дней назад. Автоматика включится сама после накопления статистики.',
  },
]
