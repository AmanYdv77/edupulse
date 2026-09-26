import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { RouteGuard } from './RouteGuard';
import * as AuthContextModule from '../context/AuthContext';

describe('RouteGuard', () => {
  it('redirects to /login when user is not authenticated', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,
      hasCapability: () => false,
      login: vi.fn(),
      logout: vi.fn(),
      refetchUser: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/protected"
            element={
              <RouteGuard>
                <div>Protected Content</div>
              </RouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Login Page')).toBeInTheDocument();
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
  });

  it('redirects to /unauthorized when user lacks required capability', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: {
        id: 1,
        display_name: 'Student User',
        role: 'STUDENT',
        scope_label: 'Batch: 2024-CSE-A',
        capabilities: ['view_own_results'],
      },
      isAuthenticated: true,
      isLoading: false,
      error: null,
      hasCapability: (cap: string) => cap === 'view_own_results',
      login: vi.fn(),
      logout: vi.fn(),
      refetchUser: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/analytics']}>
        <Routes>
          <Route path="/unauthorized" element={<div>Unauthorized 403</div>} />
          <Route
            path="/analytics"
            element={
              <RouteGuard requiredCapability="view_analytics">
                <div>Analytics Content</div>
              </RouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Unauthorized 403')).toBeInTheDocument();
    expect(screen.queryByText('Analytics Content')).not.toBeInTheDocument();
  });

  it('renders children when user possesses required capability', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: {
        id: 2,
        display_name: 'Dean User',
        role: 'DEAN',
        scope_label: 'School of Engineering',
        capabilities: ['view_analytics', 'view_at_risk_roster'],
      },
      isAuthenticated: true,
      isLoading: false,
      error: null,
      hasCapability: (cap: string) => ['view_analytics', 'view_at_risk_roster'].includes(cap),
      login: vi.fn(),
      logout: vi.fn(),
      refetchUser: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/analytics']}>
        <Routes>
          <Route
            path="/analytics"
            element={
              <RouteGuard requiredCapability="view_analytics">
                <div>Analytics Content</div>
              </RouteGuard>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Analytics Content')).toBeInTheDocument();
  });
});
