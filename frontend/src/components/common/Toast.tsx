import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info';
  message: string;
}

interface ToastProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const ToastContainer: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  return (
    <div
      className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none max-w-sm w-full"
      role="region"
      aria-label="Notifications"
      aria-live="polite"
    >
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.98 }}
            transition={{ duration: 0.15, ease: 'easeOut' }}
            className="pointer-events-auto flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-[6px] bg-card-surface border border-border-subtle text-xs shadow-[var(--shadow-floating)] text-text-primary"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              {toast.type === 'success' && (
                <CheckCircle2 className="w-4 h-4 text-[#0070f3] dark:text-[#3291ff] shrink-0" aria-hidden="true" />
              )}
              {toast.type === 'error' && (
                <AlertCircle className="w-4 h-4 text-[#ee0000] dark:text-[#f87171] shrink-0" aria-hidden="true" />
              )}
              {toast.type === 'info' && (
                <Info className="w-4 h-4 text-[#0070f3] dark:text-[#3291ff] shrink-0" aria-hidden="true" />
              )}
              <span className="truncate font-medium">{toast.message}</span>
            </div>
            <button
              onClick={() => onDismiss(toast.id)}
              className="text-text-muted hover:text-text-primary p-1 rounded-[4px] hover:bg-elevated-surface transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-text-primary"
              aria-label="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" aria-hidden="true" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
};
