"use client";

import Link from "next/link";
import { useAuth } from "../lib/auth-context";

export function TopNav() {
  const { user, loading, logout } = useAuth();

  return (
    <nav className="top-nav">
      <div className="top-nav-inner">
        <span className="top-nav-brand">BEGA Frachtpreisrechner</span>
        <div className="top-nav-links">
          <Link href="/">Dashboard</Link>
          <Link href="/historie">Historie</Link>
          {(user?.role === "admin" || user?.role === "preisadmin") && <Link href="/admincenter">Admincenter</Link>}
          {!loading && (
            <span className="top-nav-user">
              {user ? (
                <>
                  <span>
                    {user.name} ({user.role})
                  </span>
                  <button type="button" onClick={logout} className="top-nav-logout">
                    Abmelden
                  </button>
                </>
              ) : (
                <Link href="/login">Anmelden</Link>
              )}
            </span>
          )}
        </div>
      </div>
    </nav>
  );
}
