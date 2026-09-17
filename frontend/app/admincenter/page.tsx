"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../lib/auth-context";
import { createUser, fetchUsers, setUserPassword, updateUser } from "../../lib/api";
import type { UserOut, UserRole } from "../../lib/types";

const ROLES: UserRole[] = ["admin", "pruefer", "viewer"];

function NewUserForm({ onCreated }: { onCreated: (user: UserOut) => void }) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("viewer");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const user = await createUser({ name, email, password, role });
      onCreated(user);
      setName("");
      setEmail("");
      setPassword("");
      setRole("viewer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Anlegen fehlgeschlagen.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="admin-form">
      <h3>Neuen Benutzer anlegen</h3>
      <div className="form-row">
        <div className="form-field">
          <label htmlFor="new-user-name">Name</label>
          <input id="new-user-name" required value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="new-user-email">E-Mail</label>
          <input id="new-user-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="form-field">
          <label htmlFor="new-user-password">Initial-Passwort</label>
          <input
            id="new-user-password"
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <div className="form-field">
          <label htmlFor="new-user-role">Rolle</label>
          <select id="new-user-role" value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" disabled={pending}>
          {pending ? "Anlegen..." : "Anlegen"}
        </button>
      </div>
      {error && <div className="form-error">{error}</div>}
    </form>
  );
}

function SetPasswordForm({ userId, onDone }: { userId: string; onDone: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      await setUserPassword(userId, { new_password: password });
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Passwort setzen fehlgeschlagen.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="inline-form">
      <input
        type="password"
        placeholder="Neues Passwort"
        required
        minLength={8}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button type="submit" disabled={pending}>
        Setzen
      </button>
      <button type="button" onClick={onDone}>
        Abbrechen
      </button>
      {error && <div className="form-error">{error}</div>}
    </form>
  );
}

function UserRow({ user, onUpdated }: { user: UserOut; onUpdated: (user: UserOut) => void }) {
  const { user: currentUser } = useAuth();
  const [settingPassword, setSettingPassword] = useState(false);
  const isSelf = currentUser?.id === user.id;

  async function handleRoleChange(role: UserRole) {
    const updated = await updateUser(user.id, { role });
    onUpdated(updated);
  }

  async function handleToggleActive() {
    const updated = await updateUser(user.id, { active: !user.active });
    onUpdated(updated);
  }

  return (
    <tr>
      <td>{user.name}</td>
      <td>{user.email}</td>
      <td>
        <select value={user.role} onChange={(e) => handleRoleChange(e.target.value as UserRole)} disabled={isSelf}>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
      </td>
      <td>
        <button type="button" onClick={handleToggleActive} disabled={isSelf}>
          {user.active ? "Aktiv" : "Deaktiviert"}
        </button>
      </td>
      <td>
        {settingPassword ? (
          <SetPasswordForm userId={user.id} onDone={() => setSettingPassword(false)} />
        ) : (
          <button type="button" onClick={() => setSettingPassword(true)}>
            Passwort setzen
          </button>
        )}
      </td>
    </tr>
  );
}

export default function AdminCenterPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState<UserOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (user?.role !== "admin") return;
    fetchUsers()
      .then(setUsers)
      .catch((err) => setError(err instanceof Error ? err.message : "Laden fehlgeschlagen."));
  }, [user]);

  function handleUserUpdated(updated: UserOut) {
    setUsers((prev) => prev?.map((u) => (u.id === updated.id ? updated : u)) ?? prev);
  }

  function handleUserCreated(created: UserOut) {
    setUsers((prev) => (prev ? [...prev, created] : [created]));
  }

  if (loading || !user) {
    return null;
  }

  if (user.role !== "admin") {
    return (
      <>
        <h1>Admincenter</h1>
        <div className="empty-state">Kein Zugriff - diese Seite ist nur fuer Administratoren.</div>
      </>
    );
  }

  return (
    <>
      <h1>Admincenter</h1>
      <p className="subtitle">Benutzerverwaltung und Verwaltungsfunktionen</p>

      <h2>Benutzer</h2>
      {error && <div className="form-error">{error}</div>}
      {!users ? (
        <div className="empty-state">Lade Benutzer...</div>
      ) : (
        <table className="admin-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>E-Mail</th>
              <th>Rolle</th>
              <th>Status</th>
              <th>Passwort</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <UserRow key={u.id} user={u} onUpdated={handleUserUpdated} />
            ))}
          </tbody>
        </table>
      )}

      <NewUserForm onCreated={handleUserCreated} />

      <h2>Weitere Einstellungen</h2>
      <p className="subtitle">
        Tarife, Absender-Matrix, Sondervereinbarungen, Preistabellen-Import und
        Integrations-Zugangsdaten werden derzeit direkt ueber die Backend-API
        verwaltet - eigene Admincenter-Unterseiten dafuer sind noch nicht
        umgesetzt.
      </p>
    </>
  );
}
