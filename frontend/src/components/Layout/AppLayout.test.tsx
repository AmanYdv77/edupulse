import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AppLayout } from './AppLayout';
import * as AuthContextModule from '../../context/AuthContext';

describe('AppLayout Capability-Based Navigation', () => {
  it('renders student navigation matching student capabilities only', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: {
        id: 10,
        display_name: 'Aarav Sharma',
        role: 'STUDENT',
        scope_label: 'Batch: 2024-CSE-A',
        capabilities: ['view_own_results', 'log_habits'],
      },
      isAuthenticated: true,
      isLoading: false,
      error: null,
      hasCapability: (cap: string) => ['view_own_results', 'log_habits'].includes(cap),
      login: vi.fn(),
      logout: vi.fn(),
      refetchUser: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AppLayout />
      </MemoryRouter>
    );

    // Should render allowed items
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('My Results')).toBeInTheDocument();
    expect(screen.getByText('Habit Check-In')).toBeInTheDocument();

    // Must NOT render forbidden items
    expect(screen.queryByText('Institutional Analytics')).not.toBeInTheDocument();
    expect(screen.queryByText('At-Risk Roster')).not.toBeInTheDocument();
    expect(screen.queryByText('Internal Marks Entry')).not.toBeInTheDocument();
    expect(screen.queryByText('Model Registry')).not.toBeInTheDocument();

    // Verify scope badge
    expect(screen.getByText('Batch: 2024-CSE-A')).toBeInTheDocument();
  });

  it('renders executive navigation matching executive capabilities without student rosters', () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: {
        id: 1,
        display_name: 'Vice Chancellor',
        role: 'VICE_CHANCELLOR',
        scope_label: 'University-wide (VC)',
        capabilities: ['view_analytics'],
      },
      isAuthenticated: true,
      isLoading: false,
      error: null,
      hasCapability: (cap: string) => cap === 'view_analytics',
      login: vi.fn(),
      logout: vi.fn(),
      refetchUser: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AppLayout />
      </MemoryRouter>
    );

    expect(screen.getByText('Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Institutional Analytics')).toBeInTheDocument();

    // Executives must never see student level screens
    expect(screen.queryByText('My Results')).not.toBeInTheDocument();
    expect(screen.queryByText('Habit Check-In')).not.toBeInTheDocument();
    expect(screen.queryByText('At-Risk Roster')).not.toBeInTheDocument();
    expect(screen.queryByText('Internal Marks Entry')).not.toBeInTheDocument();
  });
});
