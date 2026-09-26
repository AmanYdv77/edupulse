import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { ModelRegistryView } from './ModelRegistryView';
import { apiClient } from '../../api/client';

describe('ModelRegistryView Component', () => {
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

  it('renders model registry and handles activation confirmation modal flow', async () => {
    vi.spyOn(apiClient, 'GET').mockImplementation((path: string) => {
      if (path === '/api/v1/models/') {
        return Promise.resolve({
          data: [
            {
              id: 1,
              slot: 'baseline',
              version: 1,
              is_active: true,
              trained_on: 'Synthetic Baseline v1',
              n_train_rows: 1000,
              n_test_rows: 200,
              metrics: { rmse: 3.2, r2: 0.85 },
            },
            {
              id: 2,
              slot: 'institute',
              version: 2,
              is_active: false,
              trained_on: 'Institutional Cohort 2024',
              n_train_rows: 500,
              n_test_rows: 100,
              metrics: { rmse: 2.8, r2: 0.89 },
            },
          ],
          error: undefined,
        } as never);
      }
      return Promise.resolve({ data: null, error: undefined } as never);
    });

    renderWithProviders(<ModelRegistryView />);

    expect(await screen.findByText('Model A (Baseline)')).toBeInTheDocument();
    expect(screen.getByText('Model B (Institute)')).toBeInTheDocument();
    expect(screen.getByText('Serving Live')).toBeInTheDocument();

    const activateBtn = screen.getByRole('button', { name: /Activate Version/i });
    fireEvent.click(activateBtn);

    // Modal opens
    expect(screen.getByText(/Confirm Model Activation/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Confirm & Activate/i })).toBeInTheDocument();

    // Cancel modal
    const cancelBtn = screen.getByRole('button', { name: /Cancel/i });
    fireEvent.click(cancelBtn);

    expect(screen.queryByText(/Confirm Model Activation/i)).not.toBeInTheDocument();
  });
});
