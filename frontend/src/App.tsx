import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { RouteErrorBoundary } from '@/components/RouteErrorBoundary'
import { ThemeProvider } from '@/components/ThemeProvider'
import { AppShell } from '@/layouts/AppShell'
import { ComingSoon } from '@/pages/stub/ComingSoon'
import { TemplatesPage } from './features/wb-repricer/TemplatesPage'
import { VellaFoundationWorkbench } from './components/vella/VellaFoundationWorkbench'
import { VellaSystemCatalog } from './components/vella-system/VellaSystemCatalog'
import { VellaStaticPage } from './features/vella-static/VellaStaticPage'
import { VellaHtmlParityPage } from './features/vella-parity/VellaHtmlParityPage'
import { VellaReactApp } from './features/vella-react/VellaReactApp'
import { VellaHtmlRepricer } from './components/vella-system/html/VellaHtmlRepricer'
import { WbRepricerPage } from './features/wb-repricer/WbRepricerPage'
import { WbRepricerChangelogPage } from './features/wb-repricer/WbRepricerChangelogPage'
import { WbRepricerSimulatorPage } from './features/wb-repricer/WbRepricerSimulatorPage'
import { WbRepricerStatsPage } from './features/wb-repricer/WbRepricerStatsPage'
import { WbReportsPage } from './features/wb-reports/WbReportsPage'
import { WbSourcesPage } from './features/wb-sources/WbSourcesPage'
import { WbRepricerWiki } from './wiki/pages/WbRepricerWiki'
import { LiquidationWiki } from './wiki/pages/LiquidationWiki'
import { PromotionsWiki } from './wiki/pages/PromotionsWiki'
import { AlgorithmWiki } from './wiki/pages/AlgorithmWiki'
import { TemplatesWiki } from './wiki/pages/TemplatesWiki'
import { OrdersPrintListPage } from './features/orders/OrdersPrintListPage'
import { AuthProvider } from './features/auth/AuthProvider'
import { LoginPage } from './features/auth/LoginPage'
import { RegisterPage } from './features/auth/RegisterPage'
import { PublicOnlyAuth, RequireAuth } from './features/auth/AuthRoutes'

function RoutedApp() {
  const location = useLocation()
  return (
    <RouteErrorBoundary resetKey={location.pathname}>
      <Routes>
            <Route element={<PublicOnlyAuth />}>
              <Route path="/auth/login" element={<LoginPage />} />
              <Route path="/auth/register" element={<RegisterPage />} />
            </Route>

            <Route element={<RequireAuth />}>
              <Route path="/internal/vella-system" element={<VellaSystemCatalog />} />
              <Route path="/internal/vella-components" element={<VellaFoundationWorkbench />} />
              <Route path="/internal/vella-parity/reports" element={<VellaHtmlParityPage />} />
              <Route path="/internal/vella-parity/*" element={<VellaHtmlParityPage />} />

              <Route path="/internal/vella-react/repricer" element={<VellaHtmlRepricer />} />
              <Route path="/internal/vella-react/repricer/sku/:articleId" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/repricer/stats" element={<WbRepricerStatsPage />} />
              <Route path="/internal/vella-react/repricer/changelog" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/repricer/liquidation" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/repricer/promos" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/promotions" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/liquidation" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/reports" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/reports/monitor" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/reports/rules" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/reports/abc" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/reports/rnp" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/reports/pnl" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/reports/expenses" element={<WbReportsPage />} />
              <Route path="/internal/vella-react/reports/ads" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/reports/sales" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/reports/stock" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/reports/week-over-week" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/reports/*" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/sources" element={<WbSourcesPage />} />
              <Route path="/internal/vella-react/notifications" element={<VellaReactApp />} />
              <Route path="/internal/vella-react/*" element={<VellaReactApp />} />

              <Route path="/internal/vella-preview/repricer" element={<WbRepricerPage />} />
              <Route path="/internal/vella-preview/repricer/sku/:articleId" element={<WbRepricerPage initialDrawerOpen />} />
              <Route path="/internal/vella-preview/templates" element={<TemplatesPage />} />
              <Route path="/internal/vella-preview/repricer/changelog" element={<WbRepricerChangelogPage />} />
              <Route path="/internal/vella-preview/repricer/stats" element={<WbRepricerStatsPage />} />
              <Route path="/internal/vella-preview/repricer/liquidation" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/repricer/promos" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/repricer/work-status" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/promotions" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/liquidation" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/reports" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/reports/monitor" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/reports/rules" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/reports/abc" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/reports/rnp" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/reports/pnl" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/reports/expenses" element={<WbReportsPage />} />
              <Route path="/internal/vella-preview/reports/ads" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/reports/sales" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/reports/stock" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/reports/week-over-week" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/reports/*" element={<VellaStaticPage />} />
              <Route path="/internal/vella-preview/sources" element={<WbSourcesPage />} />

              <Route path="/wb/repricer" element={<VellaHtmlParityPage />} />
              <Route path="/wb/repricer/stats" element={<VellaHtmlParityPage />} />
              <Route path="/wb/repricer/sku/:articleId" element={<VellaHtmlParityPage />} />
              <Route path="/wb/repricer/changelog" element={<VellaHtmlParityPage />} />
              <Route path="/wb/repricer/simulator" element={<WbRepricerSimulatorPage />} />
              <Route path="/wb/repricer/liquidation" element={<VellaHtmlParityPage />} />
              <Route path="/wb/repricer/promos" element={<VellaHtmlParityPage />} />
              <Route path="/wb/repricer/work-status" element={<VellaHtmlParityPage />} />
              <Route path="/wb/algorithm" element={<VellaHtmlParityPage />} />
              <Route path="/wb/templates" element={<VellaHtmlParityPage />} />
              <Route path="/wb/promotions" element={<VellaHtmlParityPage />} />
              <Route path="/wb/liquidation" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reports" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reports/monitor" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reports/rules" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reports/abc" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reports/rnp" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reports/pnl" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reports/expenses" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reports/ads" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reports/sales" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reports/stock" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reports/week-over-week" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reports/*" element={<VellaHtmlParityPage />} />
              <Route path="/wb/sources" element={<VellaHtmlParityPage />} />
              <Route path="/wb/reviews" element={<VellaHtmlParityPage />} />
              <Route path="/notifications" element={<VellaHtmlParityPage />} />
              <Route path="/avito" element={<VellaHtmlParityPage />} />
              <Route path="/avito/overview" element={<VellaHtmlParityPage />} />
              <Route path="/avito/chats" element={<VellaHtmlParityPage />} />
              <Route path="/avito/inbox" element={<VellaHtmlParityPage />} />
              <Route path="/avito/messages" element={<VellaHtmlParityPage />} />
              <Route path="/avito/orders" element={<VellaHtmlParityPage />} />
              <Route path="/avito/orders/archive" element={<VellaHtmlParityPage />} />
              <Route path="/avito/listings" element={<VellaHtmlParityPage />} />
              <Route path="/avito/repricer" element={<VellaHtmlParityPage />} />
              <Route path="/avito/reviews" element={<VellaHtmlParityPage />} />
              <Route path="/avito/stats" element={<VellaHtmlParityPage />} />
              <Route path="/avito/statistics" element={<VellaHtmlParityPage />} />
              <Route path="/avito/notifications" element={<VellaHtmlParityPage />} />
              <Route path="/orders/archive" element={<VellaHtmlParityPage />} />
              <Route path="/settings/profile" element={<VellaHtmlParityPage />} />
              <Route path="/settings/access" element={<VellaHtmlParityPage />} />
              <Route path="/settings/imports" element={<VellaHtmlParityPage />} />

              <Route path="/" element={<Navigate to="/wb/repricer" replace />} />
              <Route path="/dashboard" element={<Navigate to="/wb/repricer" replace />} />
              <Route path="/wb/repricer/dashboard" element={<Navigate to="/wb/repricer" replace />} />
              <Route path="/wb/repricer/algorithm" element={<Navigate to="/wb/algorithm" replace />} />
              <Route path="/settings" element={<Navigate to="/settings/profile" replace />} />
              <Route path="/settings/marketplaces" element={<Navigate to="/settings/profile" replace />} />
              <Route path="/settings/notifications" element={<Navigate to="/notifications" replace />} />
              <Route path="/settings/sessions" element={<Navigate to="/settings/profile" replace />} />
              <Route path="/settings/audit" element={<Navigate to="/settings/access" replace />} />

              <Route element={<AppShell />}>
                <Route path="/avito/accounts" element={<ComingSoon />} />
                <Route path="/avito/chat-bot" element={<ComingSoon />} />
                <Route path="/avito/listings/manage" element={<ComingSoon />} />
                <Route path="/avito/listings/photo-gen" element={<ComingSoon />} />
                <Route path="/avito/wallets" element={<ComingSoon />} />

                <Route path="/orders" element={<OrdersPrintListPage />} />
                <Route path="/orders/kiz" element={<ComingSoon />} />
                <Route path="/orders/returns" element={<ComingSoon />} />

                <Route path="/help" element={<Navigate to="/wiki/wb-repricer" replace />} />

                <Route path="/wiki" element={<Navigate to="/wiki/wb-repricer" replace />} />
                <Route path="/wiki/wb-repricer" element={<WbRepricerWiki />} />
                <Route path="/wiki/liquidation" element={<LiquidationWiki />} />
                <Route path="/wiki/promotions" element={<PromotionsWiki />} />
                <Route path="/wiki/algorithm" element={<AlgorithmWiki />} />
                <Route path="/wiki/templates" element={<TemplatesWiki />} />

                <Route path="*" element={<ComingSoon />} />
              </Route>
            </Route>
      </Routes>
    </RouteErrorBoundary>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <RoutedApp />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  )
}
