import React, { useState, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { Sidebar } from './components/layout/Sidebar';
import { ThemeToggle } from './components/ui/ThemeToggle';
import { LoginPage } from './features/auth/LoginPage';
import { ChatPane } from './features/chat/ChatPane';
import { AnalyticsDashboard } from './features/admin/analytics/AnalyticsDashboard';
import { IngestionView } from './features/admin/ingestion/IngestionView';
const GlobalGraphView = lazy(() => import('./features/admin/graph/GlobalGraphView').then(m => ({ default: m.GlobalGraphView })));
import { UserManagement } from './features/admin/users/UserManagement';
import { ErrorBoundary } from './components/ErrorBoundary';

import { useChatStore } from './store/chatStore';
import { useAuthStore } from './store/authStore';
import './styles/index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 20_000, retry: 1 },
  },
});

// ─── App Shell (authenticated layout) ─────────────────────────────────────────
function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const user = useAuthStore((s) => s.user);

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Minimal top bar */}
        <header
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: '12px',
            height: 'var(--navbar-height)',
            padding: '0 16px',
            borderBottom: '1px solid var(--border)',
            background: 'var(--bg-surface)',
            backdropFilter: 'var(--glass-blur)',
            flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
            {user?.email}
          </span>
          <ThemeToggle />
        </header>
        <main style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          {children}
        </main>
      </div>
    </div>
  );
}

// ─── Chat view placeholder (uses active session) ────────────────────────────
function ChatView() {
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const addSession      = useChatStore((s) => s.addSession);
  const setActiveSession = useChatStore((s) => s.setActiveSession);

  // Create a local placeholder session on first visit or when starting a new chat.
  React.useEffect(() => {
    if (!activeSessionId) {
      const store = useChatStore.getState();
      const existingEmptyLocal = store.sessions.find(
        (s) => s.isLocal && (!store.messages[s.id] || store.messages[s.id].length === 0)
      );
      if (existingEmptyLocal) {
        setActiveSession(existingEmptyLocal.id);
      } else {
        const id = crypto.randomUUID();
        addSession({ id, category: 'general', createdAt: new Date(), isLocal: true });
        setActiveSession(id);
      }
    }
  }, [activeSessionId, addSession, setActiveSession]);

  if (!activeSessionId) return null;
  return (
    <ErrorBoundary>
      <ChatPane sessionId={activeSessionId} />
    </ErrorBoundary>
  );
}

// ─── Admin view ─────────────────────────────────────────────────────────────
function AdminView() {
  const [tab, setTab] = useState<'analytics' | 'ingestion' | 'users'>('analytics');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div
        style={{
          display: 'flex',
          gap: '4px',
          padding: '12px 24px 0',
          borderBottom: '1px solid var(--border)',
        }}
      >
        {(['analytics', 'ingestion', 'users'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: '6px 14px',
              borderRadius: '8px 8px 0 0',
              background: tab === t ? 'var(--bg-card)' : 'transparent',
              border: '1px solid var(--border)',
              borderBottom: tab === t ? '1px solid var(--bg-card)' : '1px solid var(--border)',
              color: tab === t ? 'var(--text-primary)' : 'var(--text-muted)',
              fontSize: 'var(--text-sm)',
              fontWeight: tab === t ? 600 : 400,
              cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
            }}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {tab === 'analytics' && <AnalyticsDashboard />}
        {tab === 'ingestion' && <IngestionView />}
        {tab === 'users' && <UserManagement />}
      </div>
    </div>
  );
}

// ─── Root ────────────────────────────────────────────────────────────────────
export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<Navigate to="/chat" replace />} />

          {/* Protected (all authenticated users) */}
          <Route element={<ProtectedRoute />}>
            <Route
              path="/chat"
              element={
                <AppShell>
                  <ChatView />
                </AppShell>
              }
            />
          </Route>

          {/* Protected (admin only) */}
          <Route element={<ProtectedRoute requireAdmin />}>
            <Route
              path="/admin"
              element={
                <AppShell>
                  <AdminView />
                </AppShell>
              }
            />
            <Route
              path="/graph"
              element={
                <AppShell>
                  <ErrorBoundary>
                    <Suspense fallback={<div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',color:'var(--text-muted)'}}>Loading graph…</div>}>
                      <GlobalGraphView />
                    </Suspense>
                  </ErrorBoundary>
                </AppShell>
              }
            />
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
