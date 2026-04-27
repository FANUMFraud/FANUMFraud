import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://fanumfraud.local"),
  title: {
    default: "FANUMFraud",
    template: "%s | FANUMFraud",
  },
  description:
    "Platforma do monitoringu reputacji firm i analizy sygnałów AML na podstawie publikacji medialnych.",
  applicationName: "FANUMFraud",
  keywords: [
    "AML",
    "reputacja firm",
    "monitoring mediów",
    "risk scoring",
    "due diligence",
  ],
  openGraph: {
    title: "FANUMFraud",
    description:
      "Monitor reputacji firm wspierający procesy due diligence i analizę ryzyka AML.",
    type: "website",
    locale: "pl_PL",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pl"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
