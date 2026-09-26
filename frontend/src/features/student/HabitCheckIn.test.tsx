import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { HabitCheckIn } from './HabitCheckIn';
import { apiClient } from '../../api/client';

describe('HabitCheckIn Component', () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  const renderWithProviders = (ui: React.ReactElement) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{ui}</MemoryRouter>
      </QueryClientProvider>
    );
  };

  it('renders check-in form and habit history logs', async () => {
    vi.spyOn(apiClient, 'GET').mockImplementation((path: string) => {
      if (path === '/api/v1/habits/check-ins/') {
        return Promise.resolve({
          data: {
            count: 1,
            results: [
              {
                id: 1,
                log_type: 'DAILY',
                log_date: '2026-09-26',
                hours_studied: 5.5,
                sleep_hours: 7.0,
                physical_activity: 1.0,
                tutoring_sessions: 0,
                motivation_level: 'High',
                notes: 'Reviewed algorithms',
              },
            ],
          },
          error: undefined,
        } as never);
      }
      return Promise.resolve({ data: null, error: undefined } as never);
    });

    renderWithProviders(<HabitCheckIn />);

    expect(await screen.findByText('2026-09-26')).toBeInTheDocument();
    expect(screen.getByText('5.5')).toBeInTheDocument();
    expect(screen.getByText('DAILY')).toBeInTheDocument();
  });

  it('validates study hours boundary on submission', async () => {
    vi.spyOn(apiClient, 'GET').mockResolvedValue({
      data: { count: 0, results: [] },
      error: undefined,
    } as never);

    renderWithProviders(<HabitCheckIn />);

    const studyInput = await screen.findByLabelText(/Hours Studied/i);
    const sleepInput = screen.getByLabelText(/Sleep Hours/i);
    const submitBtn = screen.getByRole('button', { name: /Save Check-In/i });

    // Enter out-of-bounds study hours (> 16)
    fireEvent.change(studyInput, { target: { value: '25' } });
    fireEvent.change(sleepInput, { target: { value: '8' } });
    fireEvent.submit(submitBtn.closest('form')!);

    expect(screen.getByText(/Study hours must be between 0.0 and 16.0 hours./i)).toBeInTheDocument();
  });
});
