import Link from "next/link";
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin", "latin-ext"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin", "latin-ext"],
});

export const metadata: Metadata = {
  title: "growthOS",
  description: "Career Growth Engine — co mě posune nejvíc",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="cs"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-zinc-950 text-zinc-100">
        <nav
          aria-label="Hlavní navigace"
          className="flex flex-wrap gap-5 border-b border-white/10 px-6 py-4 text-sm"
        >
          <Link href="/" className="font-semibold text-emerald-300">
            growthOS
          </Link>
          <Link href="/profile">Profil</Link>
          <Link href="/growth?tab=imports">Importy</Link>
          <Link href="/growth?tab=plan">Týden</Link>
          <Link href="/growth?tab=history">Historie</Link>
          <Link href="/growth?tab=calendar">Kalendář</Link>
        </nav>
        {children}
      </body>
    </html>
  );
}
