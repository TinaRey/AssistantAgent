"use client";
import { useHealth } from "@/hooks/useHealth";

export function StatusBadge() {
  const { health, error } = useHealth();
  if (error) return <p className="status bad">Assistant offline ({error})</p>;
  if (!health) return <p className="status">Connecting…</p>;
  return (
    <p className="status ok">
      Assistant online · {health.llm_configured ? `model ${health.model}` : "no API key set yet"}
    </p>
  );
}
