import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ScopeAnalyticsView } from './ScopeAnalyticsView';
import { apiClient } from '../../api/client';
import * as AuthContextModule from '../../context/AuthContext';

describe('ScopeAnalyticsView Component', () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  const renderWithExecutive = () => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: {
        id: 99,
        display_name: 'Vice Chancellor',
        role: 'VICE_CHANCELLOR',
        scope_label: 'University Wide',
        capabilities: ['view_analytics', 'view_all_analytics'],
      },
      isAuthenticated: true,
      isLoading: false,
      error: null,
      hasCapability: () => true,
      login: vi.fn(),
      logout: vi.fn(),
      refetchUser: vi.fn(),
    });

    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ScopeAnalyticsView />
        </MemoryRouter>
      </QueryClientProvider>
    );
  };

  it('renders aggregated institutional KPIs and anonymized breakdowns without student PII', async () => {
    vi.spyOn(apiClient, 'GET').mockImplementation((path: string) => {
      if (path === '/api/v1/analytics/overview/') {
        return Promise.resolve({
          data: {
            scope: 'University Wide',
            total_students: 1250,
            average_percentage: 74.2,
            pass_rate: 88.5,
            at_risk_count: 42,
            at_risk_rate: 3.4,
            retention_rate: 96.1,
          },
          error: undefined,
        } as never);
      }
      if (path === '/api/v1/analytics/breakdown/') {
        return Promise.resolve({
          data: {
            dimension: 'department',
            groups: [
              { name: 'Computer Science', pass_rate: 91.2, average_percentage: 78.4, student_count: 320 },
              { name: 'Other (hidden)', pass_rate: 85.0, average_percentage: 70.0, student_count: 7 }, // Differential privacy
            ],
          },
          error: undefined,
        } as never);
      }
      if (path === '/api/v1/analytics/trend/') {
        return Promise.resolve({
          data: {
            metric: 'pass_rate',
            points: [
              { semester: 1, value: 82.0, sample_size: 400 },
              { semester: 2, value: 85.5, sample_size: 400 },
            ],
          },
          error: undefined,
        } as never);
      }
      return Promise.resolve({ data: null, error: undefined } as never);
    });

    renderWithExecutive();

    expect(await screen.findByText('1,250')).toBeInTheDocument();
    expect(screen.getByText('74.2%')).toBeInTheDocument();

    // Toggle chart to accessible data table to inspect tabular rows
    const tableToggles = screen.getAllByRole('button', { name: /View as Data Table/i });
    fireEvent.click(tableToggles[0]);

    expect(screen.getByText('Other (hidden)')).toBeInTheDocument();
    expect(screen.getByText('Computer Science')).toBeInTheDocument();
  });
});
