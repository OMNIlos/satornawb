import { Settings, Star } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Badge, DataTable, Drawer, FilterSummary, FilterToolbar, SourceStrip, VellaFinalMetrics, type DataColumn } from '../components/VellaFinalPrimitives'
import { requiresHumanApproval, type AvitoReviewRow } from '../contracts/avitoReviews'
import { avitoReviewBrandSettings, avitoReviewRows } from '../data/demoAvitoReviews'
import { VellaProductionShell } from '../shell/VellaProductionShell'

const filters = ['Все статусы', 'Требуют проверки', 'Запланировано', 'Заблокировано', 'Bless T', 'Anomie studio']

function stars(rating: AvitoReviewRow['rating']) {
  return '★★★★★'.slice(0, rating) + '☆☆☆☆☆'.slice(0, 5 - rating)
}

export function AvitoReviewsPage() {
  const [filter, setFilter] = useState('Все статусы')
  const [query, setQuery] = useState('')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const stopTopics = avitoReviewBrandSettings.flatMap((settings) => settings.stopTopics)
  const rows = useMemo(() => {
    const q = query.trim().toLowerCase()
    return avitoReviewRows
      .filter((row) => {
        if (filter === 'Все статусы') return true
        if (filter === 'Требуют проверки') return row.status === 'pending'
        if (filter === 'Запланировано') return row.status === 'scheduled'
        if (filter === 'Заблокировано') return row.status === 'blocked'
        return row.brandLabel === filter
      })
      .filter((row) => !q || `${row.author} ${row.brandLabel} ${row.accountLabel} ${row.listingTitle} ${row.reviewText}`.toLowerCase().includes(q))
  }, [filter, query])

  const columns: Array<DataColumn<AvitoReviewRow>> = [
    { key: 'review', label: 'Отзыв', sticky: true, render: (row) => <><b>{row.author} · {stars(row.rating)}</b><span className="sub">{row.reviewText}</span><span className="review-muted">{row.ageLabel}</span></> },
    { key: 'brand', label: 'Аккаунт / бренд', render: (row) => <><b>{row.brandLabel}</b><span className="sub">{row.accountLabel}</span></> },
    { key: 'listing', label: 'Товар / объявление', render: (row) => row.listingTitle },
    { key: 'risk', label: 'Риск', render: (row) => row.risk === 'high' ? <Badge tone="bad">высокий</Badge> : row.risk === 'medium' ? <Badge tone="warn">средний</Badge> : <Badge tone="ok">низкий</Badge> },
    { key: 'ai', label: 'AI-статус', render: (row) => <>{row.aiStatus}<span className="sub">{requiresHumanApproval(row, stopTopics) ? 'нужен человек' : 'можно по правилам'}</span></> },
    { key: 'answer', label: 'Ответ', render: (row) => row.answerPreview },
    { key: 'action', label: 'Действие', render: () => <button className="btn btn-default btn-sm" type="button">Открыть</button> },
  ]

  return (
    <VellaProductionShell
      title="Отзывы Авито"
      subtitle="Avito review queue and AI draft controls. Рейтинги 1-3★ и stop topics всегда требуют человека."
      mobileTitle="Отзывы Авито доступны в desktop-версии"
      mobileCopy="Очередь отзывов, AI-черновики и правила рейтингов/ключевых слов требуют широкого рабочего экрана."
      topbarActions={<><button className="vella-button" type="button" onClick={() => setSettingsOpen(true)}><Settings size={16} /> Настройки</button><button className="vella-button" type="button"><Star size={16} /> Обновить</button></>}
    >
      <VellaFinalMetrics items={[
        { label: 'Неотвеченные', value: 14, delta: '3 с рейтингом ≤3', tone: 'down', tip: 'Отзывы Авито без опубликованного ответа.' },
        { label: 'Требуют проверки', value: 7, delta: 'рейтинг, ключевые слова или спор', tone: 'neutral', tip: 'AI подготовил черновик, но нужен человек.' },
        { label: 'Автоответы сегодня', value: 31, delta: 'через тон бренда', tone: 'up' },
        { label: 'Заблокировано', value: 4, delta: 'до ручного решения', tone: 'down' },
      ]} />
      <SourceStrip
        kicker="Авито отзывы"
        chips={['2 бренда', 'AI draft', 'approval']}
        title="Ответы публикуются только после проверки правил рейтинга и ключевых слов"
        meta="Джейсон Стейтем-мем · только Авито. WB остаётся в нормальном маркетплейс-тоне без мемных цитат."
      />
      <FilterToolbar
        searchPlaceholder="Поиск по аккаунту, бренду, объявлению или тексту"
        query={query}
        onQueryChange={setQuery}
        filters={filters}
        activeFilter={filter}
        onFilterChange={setFilter}
        right={<button className="btn btn-default btn-sm" type="button" onClick={() => setSettingsOpen(true)}>Настройки</button>}
      />
      <FilterSummary shown={rows.length} total={avitoReviewRows.length} label={filter} onReset={() => { setFilter('Все статусы'); setQuery('') }} />
      <DataTable rows={rows} columns={columns} className="vella-final-avito-reviews-table" />
      <Drawer open={settingsOpen} title="Настройки отзывов Авито" meta="бренды · тон · правила отправки" tag="Авито" onClose={() => setSettingsOpen(false)}>
        {avitoReviewBrandSettings.map((settings) => (
          <div className="vella-final-settings-row" key={settings.brandId}>
            <b>{settings.brandLabel}</b>
            <span>{settings.voicePreset === 'jason_statham_meme' ? 'Джейсон Стейтем-мем · только Авито' : settings.voicePreset}</span>
            <span>Задержка публикации: {settings.publishDelayMinutes} мин</span>
            <span>Stop topics: {settings.stopTopics.join(', ')}</span>
          </div>
        ))}
      </Drawer>
    </VellaProductionShell>
  )
}
