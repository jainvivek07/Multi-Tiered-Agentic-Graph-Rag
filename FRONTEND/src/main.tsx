import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { ErrorBoundary } from './components/ErrorBoundary';

// Apply persisted theme before first render to prevent FOUC.
// Wrapped in try/catch so corrupt localStorage never causes a black screen.
try {
  const saved = localStorage.getItem('rag-theme');
  const theme = saved
    ? (JSON.parse(saved) as { state?: { theme?: string } }).state?.theme ?? 'dark'
    : 'dark';
  document.documentElement.setAttribute('data-theme', theme);
} catch {
  document.documentElement.setAttribute('data-theme', 'dark');
}

const root = document.getElementById('root');
if (!root) throw new Error('Root element not found');

createRoot(root).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
);
