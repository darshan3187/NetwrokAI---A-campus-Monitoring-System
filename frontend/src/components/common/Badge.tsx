import React from 'react';

export type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  pulse?: boolean;
  className?: string;
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  pulse = false,
  className = '',
  size = 'md',
}) => {
  const styles: Record<BadgeVariant, { bg: string; text: string; dot: string; border: string }> = {
    success: {
      bg: 'bg-[#0070f3]/10 dark:bg-[#0070f3]/15',
      border: 'border-[#0070f3]/25 dark:border-[#0070f3]/35',
      text: 'text-[#0070f3] dark:text-[#3291ff]',
      dot: 'bg-[#0070f3] dark:bg-[#3291ff]',
    },
    warning: {
      bg: 'bg-[#f5a623]/10 dark:bg-[#f5a623]/15',
      border: 'border-[#f5a623]/25 dark:border-[#f5a623]/35',
      text: 'text-[#ab570a] dark:text-[#f5a623]',
      dot: 'bg-[#f5a623]',
    },
    error: {
      bg: 'bg-[#ee0000]/10 dark:bg-[#ee0000]/15',
      border: 'border-[#ee0000]/25 dark:border-[#ee0000]/35',
      text: 'text-[#c50000] dark:text-[#f87171]',
      dot: 'bg-[#ee0000] dark:bg-[#f87171]',
    },
    info: {
      bg: 'bg-[#50e3c2]/10 dark:bg-[#50e3c2]/15',
      border: 'border-[#50e3c2]/25 dark:border-[#50e3c2]/35',
      text: 'text-[#0070f3] dark:text-[#50e3c2]',
      dot: 'bg-[#50e3c2]',
    },
    neutral: {
      bg: 'bg-[#f2f2f2] dark:bg-[#1c1c1c]',
      border: 'border-[#ebebeb] dark:border-[#262626]',
      text: 'text-[#4d4d4d] dark:text-[#a1a1a1]',
      dot: 'bg-[#8f8f8f]',
    },
  };

  const current = styles[variant];
  const sizeClasses = size === 'sm' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-0.5 text-xs';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[4px] font-mono font-medium tracking-[0.02em] border ${sizeClasses} ${current.bg} ${current.border} ${current.text} ${className}`}
    >
      {pulse ? (
        <span className="relative flex h-1.5 w-1.5 shrink-0" aria-hidden="true">
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-60 ${current.dot}`} />
          <span className={`relative inline-flex rounded-full h-1.5 w-1.5 ${current.dot}`} />
        </span>
      ) : (
        <span className={`inline-block h-1.5 w-1.5 rounded-full ${current.dot} shrink-0`} aria-hidden="true" />
      )}
      {children}
    </span>
  );
};
