import React from 'react';

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const Spinner: React.FC<SpinnerProps> = ({ size = 'md', className = '' }) => {
  const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-6 h-6 border-2',
    lg: 'w-8 h-8 border-[2.5px]',
  };

  return (
    <div
      className={`animate-spin rounded-full border-border-subtle border-t-accent-primary ${sizeClasses[size]} ${className}`}
      role="status"
      aria-label="Loading"
    />
  );
};
