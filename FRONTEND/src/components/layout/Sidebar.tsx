import React, { useEffect, useState, useRef, useCallback } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { MessageSquare, Network, BarChart3, LogOut, ChevronLeft, ChevronRight, Plus } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { useChatStore } from '../../store/chatStore';
import { authApi } from '../../api/authApi';
import { sessionApi } from '../../api/chatApi';
import styles from './Sidebar.module.css';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/chat',      icon: <MessageSquare size={18} />, label: 'Intelligence Studio' },
  { to: '/graph',     icon: <Network size={18} />,       label: 'Knowledge Graph' },
  { to: '/admin',     icon: <BarChart3 size={18} />,     label: 'Admin Panel', adminOnly: true },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { user, clearUser } = useAuthStore();
  const navigate = useNavigate();
  const sessions            = useChatStore((s) => s.sessions);
  const loadHistorySessions = useChatStore((s) => s.loadHistorySessions);
  const setActiveSession    = useChatStore((s) => s.setActiveSession);
  const activeSessionId     = useChatStore((s) => s.activeSessionId);

  const [width, setWidth] = useState(260);
  const isResizing = useRef(false);

  const startResizing = useCallback(() => {
    isResizing.current = true;
  }, []);

  const stopResizing = useCallback(() => {
    isResizing.current = false;
  }, []);

  const resize = useCallback((e: MouseEvent) => {
    if (isResizing.current) {
      setWidth(Math.min(Math.max(200, e.clientX), 500));
    }
  }, []);

  useEffect(() => {
    window.addEventListener('mousemove', resize);
    window.addEventListener('mouseup', stopResizing);
    return () => {
      window.removeEventListener('mousemove', resize);
      window.removeEventListener('mouseup', stopResizing);
    };
  }, [resize, stopResizing]);

  useEffect(() => {
    sessionApi.getSessions().then((data) => {
      loadHistorySessions(data.map((s) => ({
        id: s.id,
        category: s.category,
        createdAt: new Date(s.created_at || Date.now())
      })));
    }).catch(console.error);
  }, [loadHistorySessions]);

  const handleLogout = async () => {
    try { await authApi.logout(); } catch { /* ignore */ }
    clearUser();
    navigate('/login');
  };

  const handleNewChat = () => {
    setActiveSession(null);
    navigate('/chat');
  };

  const handleSelectSession = async (sessionId: string) => {
    setActiveSession(sessionId);
    navigate('/chat');
    try {
      const msgs = await sessionApi.getMessages(sessionId);
      useChatStore.getState().loadSessionMessages(
        sessionId, 
        msgs.map(m => ({
          id: m.id,
          role: m.role as 'user' | 'assistant',
          content: m.content,
          routeTaken: m.route_taken || undefined, // Fallback to undefined to prevent crash
          latencyMs: m.latency_ms || undefined,   // Fallback to undefined
          createdAt: new Date(m.created_at)
        }))
      );
    } catch (e) {
      console.error("Failed to load messages", e);
    }
  };

  const visibleItems = NAV_ITEMS.filter((i) => !i.adminOnly || user?.role === 'admin');

  return (
    <aside 
      className={[styles.sidebar, collapsed ? styles.collapsed : ''].join(' ')}
      style={!collapsed ? { width: `${width}px` } : undefined}
    >
      {!collapsed && <div className={styles.resizer} onMouseDown={startResizing} />}
      {/* Logo */}
      <div className={styles.logo}>
        <div className={styles.logoMark}>
          <Network size={20} />
        </div>
        {!collapsed && <span className={styles.logoText}>RAG Studio</span>}
      </div>

      {/* Navigation */}
      <nav className={styles.nav} style={{ flex: 'none' }}>
        {visibleItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              [styles.navItem, isActive ? styles.active : ''].join(' ')
            }
            title={collapsed ? item.label : undefined}
          >
            <span className={styles.navIcon}>{item.icon}</span>
            {!collapsed && <span className={styles.navLabel}>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {!collapsed && (
        <button className={styles.newChatBtn} onClick={handleNewChat}>
          <Plus size={16} />
          <span>New Chat</span>
        </button>
      )}

      {/* History */}
      {!collapsed && (
        <div className={styles.historySection}>
          <div className={styles.historyTitle}>Chat History</div>
          {sessions.filter(s => !s.isLocal).map(s => (
            <div 
              key={s.id} 
              className={[styles.historyItem, activeSessionId === s.id ? styles.active : ''].join(' ')}
              onClick={() => handleSelectSession(s.id)}
            >
              <div className={styles.historyCategory}>{s.category}</div>
              <div className={styles.historyDate}>{new Date(s.createdAt || Date.now()).toLocaleDateString()}</div>
            </div>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className={styles.footer}>
        <button onClick={handleLogout} className={styles.logoutBtn} title="Logout">
          <LogOut size={16} />
          {!collapsed && <span>Logout</span>}
        </button>
        <button onClick={onToggle} className={styles.collapseBtn} aria-label="Toggle sidebar">
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>
    </aside>
  );
}
