#!/usr/bin/env python3
"""Bootstrap-Skript: legt den ersten Administrator-Login an oder setzt das
Passwort eines bestehenden Benutzers.

Es gibt bewusst KEINEN API-Endpunkt, der ohne bestehenden Login einen
Administrator anlegen kann (das waere eine Authentifizierungsluecke) - der
allererste Zugang muss ueber diesen direkten DB-Zugriff eingerichtet werden,
danach uebernimmt die Benutzerverwaltung (`POST /api/users`, Admin-Rolle).

Aufruf (im backend/-Verzeichnis, mit aktivierter venv und gesetztem
DATABASE_URL):

    python scripts/create_admin.py admin@example.com "Anna Admin"

Fragt das Passwort interaktiv ab (nicht als Kommandozeilenargument, damit es
nicht in der Shell-Historie landet).
"""
from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.security_passwords import hash_password  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("name")
    args = parser.parse_args()

    password = getpass.getpass("Passwort: ")
    password_confirm = getpass.getpass("Passwort (Wiederholung): ")
    if password != password_confirm:
        print("Passwoerter stimmen nicht ueberein.", file=sys.stderr)
        raise SystemExit(1)
    if len(password) < 8:
        print("Passwort muss mindestens 8 Zeichen lang sein.", file=sys.stderr)
        raise SystemExit(1)

    db = SessionLocal()
    try:
        user = db.execute(select(User).where(User.email == args.email)).scalars().first()
        if user is None:
            user = User(name=args.name, email=args.email, role=UserRole.ADMIN, active=True)
            db.add(user)
            action = "angelegt"
        else:
            user.role = UserRole.ADMIN
            user.active = True
            action = "aktualisiert"
        user.password_hash = hash_password(password)
        db.commit()
        print(f"Administrator '{args.email}' wurde {action}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
