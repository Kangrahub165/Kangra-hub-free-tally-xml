'use client';

import React, { useEffect, useRef } from 'react';

/**
 * ==============================================================================
 * DEDICATED RAZORPAY PAYMENT BUTTON COMPONENT
 * Kangra Hub — Staff Membership (Rs 499, Manual Renewal)
 * ==============================================================================
 * PRD Section 2: One clearly named, dedicated location in the codebase where the
 * exact Razorpay Payment Button code provided by the owner is inserted, so it can
 * be updated later without touching other files.
 *
 * OWNER CODE BLOCK:
 * <form><script src="https://checkout.razorpay.com/v1/payment-button.js" data-payment_button_id="pl_Tk9nSzYSLpyHvZ" async> </script> </form>
 * ==============================================================================
 */
export function RazorpayStaffPaymentButton() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Clear any previously injected script/form on remount to avoid duplicates
    container.innerHTML = '';

    // Create the exact form and script provided by Razorpay
    const form = document.createElement('form');
    const script = document.createElement('script');
    script.src = 'https://checkout.razorpay.com/v1/payment-button.js';
    script.setAttribute('data-payment_button_id', 'pl_Tk9nSzYSLpyHvZ');
    script.async = true;

    form.appendChild(script);
    container.appendChild(form);

    return () => {
      if (container) {
        container.innerHTML = '';
      }
    };
  }, []);

  return (
    <div className="razorpay-payment-button-wrapper flex justify-center items-center my-3">
      <div
        ref={containerRef}
        id="razorpay-button-container"
        className="min-h-[48px] flex items-center justify-center transition-transform hover:scale-[1.01]"
      />
    </div>
  );
}

export default RazorpayStaffPaymentButton;
