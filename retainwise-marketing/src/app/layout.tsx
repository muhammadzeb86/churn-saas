import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import AnalyticsScripts from "./components/AnalyticsScripts";
import MixpanelInitializer from "./components/MixpanelInitializer";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "RetainWise Analytics - Predict Customer Churn",
  description: "Get early access to AI-powered customer retention analytics. Predict and prevent customer churn before it happens.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        {/* Server-safe head content only */}
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <AnalyticsScripts />
        <MixpanelInitializer />
        {children}
      </body>
    </html>
  );
}
