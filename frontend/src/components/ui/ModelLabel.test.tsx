import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ModelLabel } from './ModelLabel';

describe('ModelLabel', () => {
  it('renders baseline model information correctly', () => {
    render(<ModelLabel slot="baseline" version={1} algorithm="Ridge (α=1.0)" isActive={true} />);

    expect(screen.getByText('Model A (Baseline)')).toBeInTheDocument();
    expect(screen.getByText('v1')).toBeInTheDocument();
    expect(screen.getByText('[Ridge (α=1.0)]')).toBeInTheDocument();
  });

  it('renders institute model information correctly', () => {
    render(<ModelLabel slot="institute" version={2} algorithm="GradientBoosting" isActive={false} />);

    expect(screen.getByText('Model B (Institute)')).toBeInTheDocument();
    expect(screen.getByText('v2')).toBeInTheDocument();
  });
});
