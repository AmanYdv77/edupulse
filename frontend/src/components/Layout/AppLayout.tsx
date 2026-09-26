import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/Button';
import './AppLayout.css';

interface NavItem {
  label: string;
  to: string;
  capability?: string | string[];
  icon?: string;
}

const ALL_NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', to: '/', icon: '📊' },
  { label: 'My Results', to: '/student/results', capability: 'view_own_results', icon: '📝' },
  { label: 'Habit Check-In', to: '/student/habits', capability: ['submit_habit_checkin', 'view_own_habits', 'log_habits'], icon: '⏱️' },
  { label: 'My Classes', to: '/classes', capability: ['view_teaching_assignments', 'enter_internal_marks'], icon: '🏫' },
  {
    label: 'Institutional Analytics',
    to: '/analytics',
    capability: ['view_analytics', 'view_department_analytics', 'view_school_analytics', 'view_executive_analytics', 'view_class_analytics'],
    icon: '📈',
  },
  { label: 'At-Risk Roster', to: '/roster', capability: ['view_at_risk_roster', 'view_class_analytics'], icon: '⚠️' },
  { label: 'Internal Marks Entry', to: '/marks', capability: 'enter_internal_marks', icon: '✏️' },
  { label: 'Model Registry', to: '/models', capability: ['manage_models', 'manage_model_registry'], icon: '🤖' },
];

export const AppLayout: React.FC = () => {
  const { user, hasCapability, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();

  const authorizedNavItems = ALL_NAV_ITEMS.filter((item) => {
    if (!item.capability) return true;
    return Array.isArray(item.capability)
      ? item.capability.some((c) => hasCapability(c))
      : hasCapability(item.capability);
  });

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="app-shell">
      {/* Mobile Drawer Backdrop */}
      {mobileOpen && (
        <div
          className="sidebar-backdrop"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside className={`app-sidebar ${mobileOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <NavLink to="/" className="app-brand" onClick={() => setMobileOpen(false)}>
            <span className="app-brand-pulse">●</span>
            <span>EduPulse</span>
          </NavLink>
        </div>

        <nav className="sidebar-nav" aria-label="Main Navigation">
          {authorizedNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMobileOpen(false)}
            >
              <span aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <Button variant="ghost" size="sm" onClick={handleLogout} style={{ width: '100%' }}>
            Sign Out
          </Button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="app-main">
        <header className="app-header">
          <div className="header-left">
            <button
              className="mobile-toggle"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-label="Toggle navigation menu"
            >
              ☰
            </button>
            {user?.scope_label && (
              <div className="scope-badge" title="Active Academic Scope">
                <span className="scope-badge-dot" aria-hidden="true" />
                <span>{user.scope_label}</span>
              </div>
            )}
          </div>

          <div className="header-right">
            {user && (
              <div className="user-profile-info">
                <span className="user-name">{user.display_name}</span>
                <span className="user-role">{user.role}</span>
              </div>
            )}
            <Button variant="outline" size="sm" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </header>

        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
