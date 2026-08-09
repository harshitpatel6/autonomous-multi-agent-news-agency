import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Daily",
  description: "AI industry news, funding, and startup launches — researched, written, and fact-checked end-to-end by an autonomous AI newsroom.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
