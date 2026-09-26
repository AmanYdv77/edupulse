import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatCard } from './StatCard';

describe('StatCard', () => {
  it('renders label, value, subtitle, and positive trend', () => {
    render(
      <StatCard
        label="Overall Pass Rate"
        value="88.5%"
        subtitle="Across all departments"
        change={{ value: '2.5%', trend: 'positive' }}
      />
    );

    expect(screen.getByText('Overall Pass Rate')).toBeInTheDocument();
    expect(screen.getByText('88.5%')).toBeInTheDocument();
    expect(screen.getByText('Across all departments')).toBeInTheDocument();
    expect(screen.getByText('↑ 2.5%')).toBeInTheDocument();
  });
});
