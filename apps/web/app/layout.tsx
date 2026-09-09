import React from 'react';
import '@bnb/ui/index.css';
import AuthProvider from '../components/dashboard/AuthProvider';

export const metadata = {
  title: {
    default: 'bits&bytes™',
    template: '%s | bits&bytes™',
  },
  description: 'The bits&bytes™ operations platform.',
  icons: {
    icon: 'https://gobitsnbytes.org/logo',
    shortcut: 'https://gobitsnbytes.org/logo',
    apple: 'https://gobitsnbytes.org/logo',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&family=Merriweather:ital,wght@0,300;0,400;0,700;1,300;1,400&display=swap" rel="stylesheet" />
      </head>
      <body className="bg-[#120f0a] text-white antialiased min-h-screen w-full font-body selection:bg-orange selection:text-black">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
