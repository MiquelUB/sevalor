import type { Metadata, Viewport } from "next";
import { ChameleonProvider } from "@/lib/chameleon";
import { AuthProvider } from "@/lib/auth-context";
import "./globals.css";

export const metadata: Metadata = {
  title: "SEVALOR — Terminal de Camp",
  description: "PWA de mobilitat per a operaris i quadrilles de camp de Sevalor Suite.",
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
  themeColor: "#15803d",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ca">
      <body className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 antialiased font-sans">
        <AuthProvider>
          <ChameleonProvider>
            {children}
          </ChameleonProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
