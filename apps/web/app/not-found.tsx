import React from 'react';

export default function NotFound() {
  return (
    <main className="flex min-h-screen w-full flex-col items-center justify-center bg-[#f4f1ec] px-6 text-center text-[#120f0a]">
      <p className="font-mono text-xs font-bold uppercase tracking-[0.2em] text-[#97192c]">Motherboard / missing route</p>
      <h1 className="mt-5 font-serif text-8xl leading-none">404</h1>
      <p className="mt-5 max-w-sm text-base leading-7 text-[#120f0a]/65">That page does not exist or is no longer available.</p>
      <a href="/" className="mt-8 border-2 border-[#120f0a] bg-[#fc920d] px-5 py-3 font-mono text-xs font-bold uppercase tracking-[0.14em] shadow-[4px_4px_0_#120f0a] transition-transform hover:translate-x-1 hover:translate-y-1 hover:shadow-none">Back to home</a>
    </main>
  );
}
