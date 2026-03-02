import { useState, useEffect } from 'react'
import { usePWAInstall } from '../hooks/usePWA'
import './PWAInstallBanner.css'

const DISMISSED_KEY = 'pwa_banner_dismissed_until'
const DISMISS_DURATION_MS = 7 * 24 * 60 * 60 * 1000 // 7 days

export function PWAInstallBanner() {
  const { canInstall, promptInstall } = usePWAInstall()
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!canInstall) return
    const dismissedUntil = localStorage.getItem(DISMISSED_KEY)
    if (dismissedUntil && Date.now() < Number(dismissedUntil)) return
    setVisible(true)
  }, [canInstall])

  if (!visible) return null

  const handleInstall = async () => {
    const accepted = await promptInstall()
    if (accepted) setVisible(false)
  }

  const handleDismiss = () => {
    localStorage.setItem(DISMISSED_KEY, String(Date.now() + DISMISS_DURATION_MS))
    setVisible(false)
  }

  return (
    <div className="pwa-install-banner" role="banner" aria-label="Install ClassBridge app">
      <div className="pwa-install-banner__content">
        <svg
          className="pwa-install-banner__icon"
          width="20"
          height="20"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        <span className="pwa-install-banner__text">
          Install ClassBridge for offline access to study guides and flashcards
        </span>
      </div>
      <div className="pwa-install-banner__actions">
        <button
          className="pwa-install-banner__btn pwa-install-banner__btn--install"
          onClick={handleInstall}
        >
          Install App
        </button>
        <button
          className="pwa-install-banner__btn pwa-install-banner__btn--dismiss"
          onClick={handleDismiss}
          aria-label="Dismiss install banner"
        >
          &times;
        </button>
      </div>
    </div>
  )
}
