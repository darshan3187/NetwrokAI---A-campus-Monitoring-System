import React from 'react';

interface SkeletonProps {
  className?: string;
}

export const Skeleton: React.FC<SkeletonProps> = ({ className = '' }) => {
  return (
    <div
      className={`animate-pulse bg-elevated-surface border border-border-subtle rounded-[6px] ${className}`}
      aria-hidden="true"
    />
  );
};
