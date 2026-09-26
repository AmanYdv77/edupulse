import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { StudentDashboard } from './StudentDashboard';
import { apiClient } from '../../api/client';
import * as AuthContextModule from '../../context/AuthContext';

describe('StudentDashboard Component', () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  const renderWithProviders = (ui: React.ReactElement) => {
    vi.spyOn(AuthContextModule, 'useAuth').mockReturnValue({
      user: {
        id: 1,
        display_name: 'Aarav Sharma',
        role: 'STUDENT',
        scope_label: 'Batch: 2024-CSE-A',
        capabilities: ['view_own_results', 'view_predictions', 'submit_habits'],
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
        <MemoryRouter>{ui}</MemoryRouter>
      </QueryClientProvider>
    );
  };

  it('renders student predictions with model labels and key driver factors', async () => {
    vi.spyOn(apiClient, 'GET').mockImplementation((path: string) => {
      if (path.includes('predictions')) {
        return Promise.resolve({
          data: {
            predictions: [
              {
                subject_code: 'CS101',
                subject_name: 'Computer Networks',
                semester: 3,
                predicted_score: 78.5,
                confidence_score: 0.88,
                risk_band: 'low',
                model_slot: 'baseline',
                model_version: 1,
                model_label: 'Ridge (α=1.0)',
                insufficient_data: false,
                factors: [
                  { feature: 'study_hours', name: 'Study Hours', impact: '+4.2 pts', direction: 'positive', description: 'Consistent study routine' },
                  { feature: 'attendance', name: 'Attendance', impact: '+2.1 pts', direction: 'positive', description: 'High class attendance' },
                ],
              },
            ],
          },
          error: undefined,
        } as never);
      }
      return Promise.resolve({ data: null, error: undefined } as never);
    });

    renderWithProviders(<StudentDashboard />);

    expect(await screen.findByText(/Computer Networks \(CS101\)/i)).toBeInTheDocument();
    expect(screen.getAllByText('78.5%').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Model A (Baseline)')).toBeInTheDocument();
    expect(screen.getByText(/Study Hours: \+4.2 pts/i)).toBeInTheDocument();
  });

  it('renders insufficient habit data notice when predictions lack sufficient logs', async () => {
    vi.spyOn(apiClient, 'GET').mockImplementation((path: string) => {
      if (path.includes('predictions')) {
        return Promise.resolve({
          data: {
            predictions: [
              {
                subject_code: 'CS102',
                subject_name: 'Operating Systems',
                semester: 3,
                predicted_score: null,
                confidence_score: null,
                risk_band: 'insufficient_data',
                model_slot: 'baseline',
                model_version: 1,
                model_label: 'Ridge (α=1.0)',
                insufficient_data: true,
                insufficient_data_reasons: ['No study habit logs recorded in past 7 days'],
                factors: [],
              },
            ],
          },
          error: undefined,
        } as never);
      }
      return Promise.resolve({ data: null, error: undefined } as never);
    });

    renderWithProviders(<StudentDashboard />);

    expect(await screen.findByText(/Operating Systems \(CS102\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Insufficient Habit Data for this Subject/i)).toBeInTheDocument();
    expect(screen.getByText(/No study habit logs recorded in past 7 days/i)).toBeInTheDocument();
  });
});
