import React from 'react';
import clsx from 'clsx';
import './Skeleton.css';

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  width?: string | number;
  height?: string | number;
  circle?: boolean;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  width,
  height,
  circle = false,
  className,
  style,
  ...props
}) => {
  const customStyles: React.CSSProperties = {
    width: width !== undefined ? width : '100%',
    height: height !== undefined ? height : '1rem',
    borderRadius: circle ? '50%' : undefined,
    ...style,
  };

  return (
    <div
      className={clsx('skeleton', className)}
      style={customStyles}
      aria-hidden="true"
      {...props}
    />
  );
};
