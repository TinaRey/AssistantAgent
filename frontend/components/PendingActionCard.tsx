"use client";
import { useState } from "react";
import { approveAction, rejectAction } from "@/lib/api";
import type { PendingAction } from "@/lib/types";

/** Any action with an external effect waits here for an explicit human decision. */
export function PendingActionCard({ action }: { action: PendingAction }) {
  const [state, setState] = useState(action.status);
  const [busy, setBusy] = useState(false);

  async function decide(fn: typeof approveAction) {
    setBusy(true);
    try { setState((await fn(action.id)).status); } catch { setState("failed"); }
    setBusy(false);
  }

  return (
    <section className="card">
      <h3>Action en attente de votre accord</h3>
      <pre>{JSON.stringify(action.arguments, null, 2)}</pre>
      {state === "pending" ? (
        <div className="actions">
          <button className="primary" disabled={busy} onClick={() => decide(approveAction)}>Approuver</button>
          <button disabled={busy} onClick={() => decide(rejectAction)}>Refuser</button>
        </div>
      ) : (
        <p className="muted">Statut : {state}</p>
      )}
    </section>
  );
}
