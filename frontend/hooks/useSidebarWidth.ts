"use client";
import { useCallback, useEffect, useState } from "react";

const KEY = "pantalelle.sidebarWidth.v1";
export const SIDEBAR_MIN = 200;
export const SIDEBAR_MAX = 560;
export const SIDEBAR_DEFAULT = 260;

const clamp = (n: number) => Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, Math.round(n)));

/** Sidebar width chosen by the user, remembered in this browser. */
export function useSidebarWidth() {
  const [width, setWidthState] = useState(SIDEBAR_DEFAULT);

  useEffect(() => {
    const saved = Number(localStorage.getItem(KEY));
    if (saved) setWidthState(clamp(saved));
  }, []);

  const setWidth = useCallback((n: number) => {
    const w = clamp(n);
    setWidthState(w);
    localStorage.setItem(KEY, String(w));
  }, []);

  return { width, setWidth, reset: () => setWidth(SIDEBAR_DEFAULT) };
}
