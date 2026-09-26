import React from 'react';
import clsx from 'clsx';
import { Button } from './Button';
import './ErrorState.css';

export interface ErrorStateProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  message?: string;
  onRetry?: () => void;
  icon?: React.ReactNode;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Something went wrong',
  message = 'An error occurred while loading this data. Please try again.',
  onRetry,
  icon,
  className,
  ...props
}) => {
  return (
    <div className={clsx('error-state', className)} role="alert" {...props}>
      <div className="error-state-icon">{icon || '⚠️'}</div>
      <h4 className="error-state-title">{title}</h4>
      <p className="error-state-message">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try Again
        </Button>
      )}
    </div>
  );
};
