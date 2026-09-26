import React from 'react';
import clsx from 'clsx';
import './Badge.css';

export type BadgeVariant =
  | 'neutral'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'risk-low'
  | 'risk-moderate'
  | 'risk-high'
  | 'risk-insufficient';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  riskBand?: 'low' | 'moderate' | 'high' | 'insufficient_data' | string;
  icon?: React.ReactNode;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  riskBand,
  icon,
  className,
  ...props
}) => {
  let resolvedVariant: BadgeVariant = variant;

  if (riskBand) {
    if (riskBand === 'low') resolvedVariant = 'risk-low';
    else if (riskBand === 'moderate') resolvedVariant = 'risk-moderate';
    else if (riskBand === 'high') resolvedVariant = 'risk-high';
    else if (riskBand === 'insufficient_data') resolvedVariant = 'risk-insufficient';
  }

  return (
    <span className={clsx('badge', `badge-${resolvedVariant}`, className)} {...props}>
      {icon && <span className="badge-icon">{icon}</span>}
      {children || (riskBand ? formatRiskBand(riskBand) : null)}
    </span>
  );
};

function formatRiskBand(band: string): string {
  switch (band) {
    case 'low':
      return 'Low Risk';
    case 'moderate':
      return 'Moderate Risk';
    case 'high':
      return 'High Risk';
    case 'insufficient_data':
      return 'Insufficient Data';
    default:
      return band;
  }
}
