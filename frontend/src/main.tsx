import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './gradients.css'
import App from './App.tsx'

// Global handler for Vite chunk preload failures (CSS chunks, async deps).
// Vite fires this event when a preloaded module fails to load (e.g., 404 after
// a deploy with new hashed filenames). Auto-reload the page once to pick up
// the fresh asset manifest.
window.addEventListener('vite:preloadError', (event) => {
  const reloaded = sessionStorage.getItem('chunk_reload');
  if (!reloaded) {
    sessionStorage.setItem('chunk_reload', '1');
    event.preventDefault();
    window.location.reload();
  }
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
