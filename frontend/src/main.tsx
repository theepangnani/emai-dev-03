import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './gradients.css'
import App from './App.tsx'
import { PWAInstallBanner } from './components/PWAInstallBanner'
import { OfflineIndicator } from './components/OfflineIndicator'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <PWAInstallBanner />
    <App />
    <OfflineIndicator />
  </StrictMode>,
)
