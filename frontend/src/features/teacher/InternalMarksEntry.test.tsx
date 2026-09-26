import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { InternalMarksEntry } from './InternalMarksEntry';
import { apiClient } from '../../api/client';

describe('InternalMarksEntry Component', () => {
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

  it('renders teaching assignment selection and mark entry rows', async () => {
    vi.spyOn(apiClient, 'GET').mockImplementation((path: string) => {
      if (path === '/api/v1/teaching-assignments/') {
        return Promise.resolve({
          data: [
            {
              id: 10,
              subject_id: 101,
              subject_code: 'CS101',
              subject_name: 'Data Structures',
              batch_id: 201,
              batch_code: '2024-CSE-A',
              semester: 3,
              internal_max: 30,
              credits: 4,
            },
          ],
          error: undefined,
        } as never);
      }
      return Promise.resolve({ data: null, error: undefined } as never);
    });

    renderWithProviders(<InternalMarksEntry />);

    expect(await screen.findByText(/Internal Marks Assessment Entry/i)).toBeInTheDocument();
    expect(screen.getByText(/CS101 - Data Structures/i)).toBeInTheDocument();
  });

  it('validates mark range exceeding max marks client-side', async () => {
    vi.spyOn(apiClient, 'GET').mockImplementation((path: string) => {
      if (path === '/api/v1/teaching-assignments/') {
        return Promise.resolve({
          data: [
            {
              id: 10,
              subject_id: 101,
              subject_code: 'CS101',
              subject_name: 'Data Structures',
              batch_id: 201,
              batch_code: '2024-CSE-A',
              semester: 3,
              internal_max: 30,
              credits: 4,
            },
          ],
          error: undefined,
        } as never);
      }
      return Promise.resolve({ data: null, error: undefined } as never);
    });

    renderWithProviders(<InternalMarksEntry />);

    const select = await screen.findByLabelText(/Teaching Assignment/i);
    fireEvent.change(select, { target: { value: '10' } });

    const studentInputs = screen.getAllByPlaceholderText(/Student ID/i);
    const marksInputs = screen.getAllByPlaceholderText(/Marks/i);

    fireEvent.change(studentInputs[0], { target: { value: '101' } });
    fireEvent.change(marksInputs[0], { target: { value: '45' } }); // > max 30

    const submitBtn = screen.getByRole('button', { name: /Submit Assessment Marks/i });
    fireEvent.submit(submitBtn.closest('form')!);

    expect(screen.getByText(/Marks for student 101 must be between 0 and 30./i)).toBeInTheDocument();
  });
});
