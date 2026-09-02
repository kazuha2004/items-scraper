import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

// Next.js optimised font — self-hosted, no layout shift, no double load
const inter = Inter({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "DealHunter — Compare prices across Amazon, Flipkart & Meesho",
  description: "Search once and compare product prices across Amazon, Flipkart, and Meesho in one place.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <head>
        <meta name="theme-color" content="#ffffff" />
      </head>
      <body>{children}</body>
    </html>
  );
}
