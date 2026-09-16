import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "BEGA Frachtpreisrechner",
  description: "Automatisierte Frachtpreispruefung fuer Spediteure",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>
        <nav className="top-nav">
          <div className="top-nav-inner">
            <span className="top-nav-brand">BEGA Frachtpreisrechner</span>
            <div className="top-nav-links">
              <Link href="/">Dashboard</Link>
              <Link href="/historie">Historie</Link>
            </div>
          </div>
        </nav>
        <main className="page">{children}</main>
      </body>
    </html>
  );
}
