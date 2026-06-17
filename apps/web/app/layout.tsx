import React from 'react';
import '@bnb/ui/index.css';

export const metadata = {
  title: 'bits&bytes™ Motherboard — Platform specs',
  description: 'Operations platform and governance specifications for GOBITSNBYTES FOUNDATION.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="scroll-smooth">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Merriweather:ital,wght@0,300;0,400;0,700;1,300;1,400&display=swap" rel="stylesheet" />
      </head>
      <body className="bg-black text-white antialiased overflow-x-hidden font-body">
        {children}
      </body>
    </html>
  );
}
