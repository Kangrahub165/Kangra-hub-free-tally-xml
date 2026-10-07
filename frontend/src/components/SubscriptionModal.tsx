'use client';

import React from 'react';
import { X } from 'lucide-react';
import { StaffMembershipCard } from '@/components/StaffMembershipCard';

interface SubscriptionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export function SubscriptionModal({ isOpen, onClose, onSuccess }: SubscriptionModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 animate-fadeIn">
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl">
        {/* Close button overlay */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-20 p-2 text-slate-400 hover:text-white rounded-xl bg-slate-900/50 hover:bg-slate-900/80 transition-colors cursor-pointer"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Professional Staff Membership Card */}
        <StaffMembershipCard
          onSuccess={() => {
            if (onSuccess) onSuccess();
          }}
        />
      </div>
    </div>
  );
}

export default SubscriptionModal;
