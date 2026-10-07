'use client';

import { useEffect } from 'react';

export default function ConvertRedirectPage() {
  useEffect(() => {
    window.location.href = 'https://kangrahubtallyxml.netlify.app/';
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 text-white p-4">
      <div className="text-center space-y-4 max-w-md">
        <h1 className="text-2xl font-bold">Redirecting to Bank Statement Import...</h1>
        <p className="text-slate-400 text-sm">
          Bank statement processing is hosted on our dedicated platform. You are being redirected automatically.
        </p>
        <div>
          <a
            href="https://kangrahubtallyxml.netlify.app/"
            className="inline-flex items-center px-5 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-xl text-white font-semibold text-sm transition-colors"
          >
            Click here if not redirected →
          </a>
        </div>
      </div>
    </div>
  );
}
