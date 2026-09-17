import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "../lib/auth-context";
import { TopNav } from "../components/TopNav";

export const metadata: Metadata = {
  title: "BEGA Frachtpreisrechner",
  description: "Automatisierte Frachtpreispruefung fuer Spediteure",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>
        <AuthProvider>
          <TopNav />
          <main className="page">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
