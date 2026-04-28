import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { I18nProvider } from "@/lib/i18n/I18nProvider";
import { ThemeProvider } from "@/lib/theme/ThemeProvider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin", "latin-ext"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://fanumfraud.local"),
  title: {
    default: "FanumFraud — Rejestr ryzyka",
    template: "%s · FanumFraud",
  },
  description:
    "Rejestr reputacji podmiotów gospodarczych i analiza sygnałów AML w oparciu o publikacje medialne.",
  applicationName: "FanumFraud",
  keywords: ["AML", "rejestr ryzyka", "reputacja firm", "due diligence"],
  manifest: "/assets/favicon/site.webmanifest",
  icons: {
    icon: [
      { url: "/assets/favicon/favicon.ico" },
      { url: "/assets/favicon/favicon-16x16.png", sizes: "16x16", type: "image/png" },
      { url: "/assets/favicon/favicon-32x32.png", sizes: "32x32", type: "image/png" },
    ],
    apple: [{ url: "/assets/favicon/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
  openGraph: {
    title: "FanumFraud — Rejestr ryzyka",
    description:
      "Monitor reputacji podmiotów gospodarczych wspierający procesy due diligence i analizę ryzyka AML.",
    type: "website",
    locale: "pl_PL",
  },
};

// Runs before paint to set the data-theme attribute and avoid a light-flash
// when the user prefers dark or has previously selected dark.
const themeInitScript = `(function(){try{var s=localStorage.getItem('fanumfraud:theme');var d=s==='dark'||(s===null&&window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches);if(d)document.documentElement.setAttribute('data-theme','dark');}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pl"
      className={`${geistSans.variable} ${geistMono.variable} h-full`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <I18nProvider>{children}</I18nProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
