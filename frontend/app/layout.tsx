import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Threadly',
  description: 'Semantic fashion search over a 44K-product catalogue',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
