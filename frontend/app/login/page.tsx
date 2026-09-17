"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../lib/auth-context";
import { ApiError } from "../../lib/api";

export default function LoginPage() {
  const { login, user } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  if (user) {
    router.replace("/");
    return null;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      await login(email, password);
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 403)) {
        setError("E-Mail oder Passwort ist falsch, oder das Konto ist deaktiviert.");
      } else {
        setError(err instanceof Error ? err.message : "Anmeldung fehlgeschlagen.");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="login-page">
      <h1>Anmelden</h1>
      <p className="subtitle">BEGA Frachtpreisrechner</p>
      <form onSubmit={handleSubmit} className="login-form">
        <div className="form-field">
          <label htmlFor="email">E-Mail</label>
          <input
            id="email"
            name="email"
            type="email"
            required
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="form-field">
          <label htmlFor="password">Passwort</label>
          <input
            id="password"
            name="password"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error && <div className="form-error">{error}</div>}
        <button type="submit" disabled={pending}>
          {pending ? "Anmelden..." : "Anmelden"}
        </button>
      </form>
    </div>
  );
}
