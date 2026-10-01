import React from 'react';
import { CheckCircle2, XCircle } from 'lucide-react';
import type { ConfusionMatrix } from '../../types/simulation';

interface ConfusionMatrixCardProps {
  matrix: ConfusionMatrix;
}

export const ConfusionMatrixCard: React.FC<ConfusionMatrixCardProps> = ({ matrix }) => {
  const { true_positives, true_negatives, false_positives, false_negatives, total_samples } = matrix;

  const actualPositives = true_positives + false_negatives;
  const actualNegatives = true_negatives + false_positives;
  const predictedPositives = true_positives + false_positives;
  const predictedNegatives = true_negatives + false_negatives;

  return (
    <div className="bg-card-surface border border-border-subtle rounded-[12px] p-5 flex flex-col justify-between space-y-4 shadow-[var(--shadow-whisper)]">
      <div className="flex items-center justify-between pb-3 border-b border-border-subtle">
        <div>
          <h3 className="text-sm font-semibold text-text-primary tracking-[-0.28px]">
            Classification Confusion Matrix
          </h3>
          <p className="text-xs text-text-secondary mt-0.5">
            Binary evaluation of model predictions against synthetic ground-truth labels
          </p>
        </div>
        <span className="text-xs font-mono text-text-muted">
          Total: <strong className="text-text-primary font-medium">{total_samples}</strong> samples
        </span>
      </div>

      {/* 2x2 Matrix Grid */}
      <div className="overflow-x-auto">
        <table className="w-full text-center text-xs border-collapse font-mono">
          <thead>
            <tr>
              <th className="p-2 border border-transparent"></th>
              <th className="p-2.5 border border-border-subtle bg-elevated-surface text-[#0070f3] dark:text-[#3291ff] font-medium">
                Actual Anomaly ({actualPositives})
              </th>
              <th className="p-2.5 border border-border-subtle bg-elevated-surface text-text-secondary font-medium">
                Actual Normal ({actualNegatives})
              </th>
              <th className="p-2.5 border border-border-subtle bg-elevated-surface/50 text-text-muted text-[10px]">
                Row Total
              </th>
            </tr>
          </thead>
          <tbody>
            {/* Predicted Anomaly Row */}
            <tr>
              <td className="p-2.5 border border-border-subtle bg-elevated-surface text-left font-medium text-text-primary whitespace-nowrap">
                Predicted Anomaly
              </td>
              {/* True Positive */}
              <td className="p-3.5 border border-border-subtle bg-[#0070f3]/10 text-[#0070f3] dark:text-[#3291ff]">
                <div className="text-base font-bold tabular-nums">{true_positives}</div>
                <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mt-0.5 flex items-center justify-center gap-1">
                  <CheckCircle2 className="w-3 h-3" aria-hidden="true" /> True Pos (TP)
                </div>
              </td>
              {/* False Positive */}
              <td className="p-3.5 border border-border-subtle bg-[#ee0000]/10 text-[#ee0000] dark:text-[#f87171]">
                <div className="text-base font-bold tabular-nums">{false_positives}</div>
                <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mt-0.5 flex items-center justify-center gap-1">
                  <XCircle className="w-3 h-3" aria-hidden="true" /> False Pos (FP)
                </div>
              </td>
              <td className="p-2.5 border border-border-subtle bg-elevated-surface/50 text-text-muted tabular-nums font-medium">
                {predictedPositives}
              </td>
            </tr>

            {/* Predicted Normal Row */}
            <tr>
              <td className="p-2.5 border border-border-subtle bg-elevated-surface text-left font-medium text-text-primary whitespace-nowrap">
                Predicted Normal
              </td>
              {/* False Negative */}
              <td className="p-3.5 border border-border-subtle bg-[#ee0000]/10 text-[#ee0000] dark:text-[#f87171]">
                <div className="text-base font-bold tabular-nums">{false_negatives}</div>
                <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mt-0.5 flex items-center justify-center gap-1">
                  <XCircle className="w-3 h-3" aria-hidden="true" /> False Neg (FN)
                </div>
              </td>
              {/* True Negative */}
              <td className="p-3.5 border border-border-subtle bg-[#0070f3]/10 text-[#0070f3] dark:text-[#3291ff]">
                <div className="text-base font-bold tabular-nums">{true_negatives}</div>
                <div className="text-[10px] uppercase font-semibold tracking-[0.05em] mt-0.5 flex items-center justify-center gap-1">
                  <CheckCircle2 className="w-3 h-3" aria-hidden="true" /> True Neg (TN)
                </div>
              </td>
              <td className="p-2.5 border border-border-subtle bg-elevated-surface/50 text-text-muted tabular-nums font-medium">
                {predictedNegatives}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Summary Footer */}
      <div className="pt-2 text-xs font-mono text-text-secondary flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle">
        <span>Correct: <strong className="text-text-primary font-medium tabular-nums">{true_positives + true_negatives}</strong> / {total_samples}</span>
        <span>Misclassifications: <strong className="text-[#ee0000] dark:text-[#f87171] font-medium tabular-nums">{false_positives + false_negatives}</strong></span>
      </div>
    </div>
  );
};
