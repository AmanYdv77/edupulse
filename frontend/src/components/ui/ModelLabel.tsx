import React from 'react';
import clsx from 'clsx';
import './ModelLabel.css';

export interface ModelLabelProps extends React.HTMLAttributes<HTMLSpanElement> {
  slot?: 'baseline' | 'institute' | string;
  version?: number | string;
  algorithm?: string;
  isActive?: boolean;
}

export const ModelLabel: React.FC<ModelLabelProps> = ({
  slot = 'baseline',
  version = 1,
  algorithm = 'Ridge (α=1.0)',
  isActive = true,
  className,
  ...props
}) => {
  const slotName = slot === 'baseline' ? 'Model A (Baseline)' : 'Model B (Institute)';

  return (
    <span className={clsx('model-label', className)} title={`Serving Model: ${slotName} v${version} (${algorithm})`} {...props}>
      <span className={clsx('model-label-dot', !isActive && 'inactive')} aria-hidden="true" />
      <span className="model-label-slot">{slotName}</span>
      <span className="model-label-version">v{version}</span>
      {algorithm && <span className="model-label-algo">[{algorithm}]</span>}
    </span>
  );
};
