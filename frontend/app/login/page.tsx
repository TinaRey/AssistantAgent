"use client";
import { useState } from "react";
import { ApiError, login } from "@/lib/api";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(password);
      window.location.href = "/";
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "Mot de passe incorrect."
          : err instanceof ApiError ? err.message : "Impossible de joindre le serveur.",
      );
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <form onSubmit={submit} className="login-card">
        <h1>Pantalelle</h1>
        <p className="muted">Assistant privé. Entrez votre mot de passe.</p>
        <input
          type="password" autoFocus autoComplete="current-password" value={password}
          onChange={(e) => setPassword(e.target.value)} placeholder="Mot de passe" aria-label="Mot de passe"
        />
        {error && <p role="alert" className="error">{error}</p>}
        <button type="submit" disabled={busy || !password}>{busy ? "Connexion…" : "Se connecter"}</button>
      </form>
    </main>
  );
}
