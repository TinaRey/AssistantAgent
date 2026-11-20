"use client";
import { useEffect, useState } from "react";
import { getHealth, type Health } from "@/lib/api";

export function useHealth() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getHealth().then(setHealth).catch((e: Error) => setError(e.message));
  }, []);
  return { health, error };
}
