import type { Metadata } from "next";
import "./globals.css";

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
    <html lang="en">
      <head>
        <meta name="theme-color" content="#ffffff" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  );
}
