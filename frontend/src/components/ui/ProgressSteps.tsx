import React from 'react';
import { Check } from 'lucide-react';

export interface StepItem {
  number: number;
  label: string;
  description?: string;
}

export interface ProgressStepsProps {
  steps: StepItem[];
  currentStep: number;
  className?: string;
}

export function ProgressSteps({
  steps,
  currentStep,
  className = '',
}: ProgressStepsProps) {
  return (
    <nav aria-label="Progress" className={`w-full ${className}`}>
      <ol className="flex items-center justify-between gap-2 overflow-x-auto pb-4 sm:pb-0 scrollbar-hide">
        {steps.map((step, idx) => {
          const isCompleted = currentStep > step.number;
          const isCurrent = currentStep === step.number;
          const isPending = currentStep < step.number;

          return (
            <li
              key={step.number}
              className="flex-1 min-w-[110px] relative flex flex-col items-center text-center group"
            >
              {/* Connector line */}
              {idx > 0 && (
                <div
                  className={`absolute top-4 right-1/2 left-[-50%] h-[2px] -z-0 transition-all duration-300 ${
                    isCompleted ? 'bg-emerald-500' : isCurrent ? 'bg-slate-300' : 'bg-slate-200'
                  }`}
                  aria-hidden="true"
                />
              )}

              {/* Step circle */}
              <div
                className={`relative z-10 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-300 ${
                  isCompleted
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : isCurrent
                    ? 'bg-brand-600 text-white ring-4 ring-brand-100 shadow-glow-brand'
                    : 'bg-slate-50 text-slate-400 border-2 border-slate-200'
                }`}
              >
                {isCompleted ? <Check className="w-3.5 h-3.5" /> : step.number}
              </div>

              {/* Step Label */}
              <span
                className={`mt-2 text-[11px] font-semibold tracking-tight transition-colors truncate max-w-[120px] ${
                  isCompleted
                    ? 'text-slate-800'
                    : isCurrent
                    ? 'text-brand-700 font-bold'
                    : 'text-slate-400'
                }`}
              >
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
