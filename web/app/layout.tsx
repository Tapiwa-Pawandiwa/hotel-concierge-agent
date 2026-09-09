import type { Metadata } from "next";
import { Cormorant_Garamond, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

// Display/editorial type -- wordmark, page titles, welcome statements, room
// names (CLAUDE.md's JANET design system, "Display/brand" family). Not a
// variable font on Google Fonts, so the exact weights we use (500 for most
// display sizes, 600 for H3/card titles) have to be listed explicitly.
const cormorantGaramond = Cormorant_Garamond({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600"],
});

// Interface/functional type -- chat messages, buttons, nav, forms.
const inter = Inter({
  variable: "--font-ui",
  subsets: ["latin"],
});

// System-trace/monospace type -- tool names, idempotency keys, JSON.
const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Janet Hotels & Resorts",
  description: "A Hotel Agent orchestrating bookings, check ins, answering guest questions etc",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${cormorantGaramond.variable} ${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}