import React from 'react';
import clsx from 'clsx';
import './StatCard.css';

export interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string;
  value: React.ReactNode;
  subtitle?: string;
  change?: {
    value: string | number;
    trend: 'positive' | 'negative' | 'neutral';
  };
  icon?: React.ReactNode;
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  subtitle,
  change,
  icon,
  className,
  ...props
}) => {
  return (
    <div className={clsx('stat-card', className)} {...props}>
      <div className="stat-card-top">
        <span className="stat-card-label">{label}</span>
        {icon && <div className="stat-card-icon">{icon}</div>}
      </div>

      <div className="stat-card-value">{value}</div>

      {(subtitle || change) && (
        <div className="stat-card-bottom">
          {change && (
            <span className={clsx('stat-card-change', change.trend)}>
              {change.trend === 'positive' && '↑ '}
              {change.trend === 'negative' && '↓ '}
              {change.value}
            </span>
          )}
          {subtitle && <span className="stat-card-subtitle">{subtitle}</span>}
        </div>
      )}
    </div>
  );
};
