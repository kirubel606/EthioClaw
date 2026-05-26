import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import { Analytics } from '@vercel/analytics/next'
import './globals.css'
import { ThemeProvider } from '@/components/theme-provider'
import { APP_NAME, THEME_STORAGE_KEY } from '@/lib/env'
import { DEFAULT_THEME } from '@/lib/server-env'

import { Toaster } from '@/components/ui/toaster'

const _geist = Geist({ subsets: ["latin"] });
const _geistMono = Geist_Mono({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: `${APP_NAME} - Advanced Cognitive AI Agent`,
  description: 'An awesome AI agent chat interface with cognitive memory systems',
  generator: 'v0.app',
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="font-sans antialiased overflow-hidden bg-background text-foreground">
        <ThemeProvider
          attribute="data-theme"
          defaultTheme={DEFAULT_THEME}
          enableSystem={false}
          storageKey={THEME_STORAGE_KEY}
          themes={['toxic', 'morty', 'portal', 'custom']}

          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
        {process.env.NODE_ENV === 'production' && <Analytics />}
        <Toaster />
      </body>
    </html>
  )
}
