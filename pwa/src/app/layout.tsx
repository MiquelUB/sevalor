import type { Metadata, Viewport } from "next";
import { ChameleonProvider } from "@/lib/chameleon";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sevalor · SEVALOR Suite — Gestió i Terminal de Camp",
  description: "Plataforma B2B i PWA de mobilitat per a operaris i quadrilles de camp de Sevalor Suite.",
  manifest: "/manifest.json",
  icons: {
    icon: "/icons/icon-192x192.png",
    apple: "/icons/icon-192x192.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: "#022448",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ca" suppressHydrationWarning>
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
        />
      </head>
      <body className="min-h-screen bg-surface text-on-surface antialiased font-sans" suppressHydrationWarning>
        <ChameleonProvider>
          {children}
        </ChameleonProvider>
      </body>
    </html>
  );
}