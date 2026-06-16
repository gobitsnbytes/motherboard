import React from 'react';

export const metadata = {
  title: 'bnb-motherboard',
  description: 'bits&bytes network operations dashboard',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
