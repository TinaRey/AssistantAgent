"use client";
import { SIDEBAR_MAX, SIDEBAR_MIN } from "@/hooks/useSidebarWidth";

type Props = { width: number; onResize: (w: number) => void; onReset: () => void };

/** Drag to resize, arrow keys to adjust, double-click to reset. */
export function SidebarResizer({ width, onResize, onReset }: Props) {
  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    e.preventDefault();
    const startX = e.clientX;
    const startWidth = width;
    const target = e.currentTarget;
    target.setPointerCapture(e.pointerId);
    document.body.style.userSelect = "none";

    const move = (ev: PointerEvent) => onResize(startWidth + ev.clientX - startX);
    const up = () => {
      document.body.style.userSelect = "";
      target.removeEventListener("pointermove", move);
      target.removeEventListener("pointerup", up);
    };
    target.addEventListener("pointermove", move);
    target.addEventListener("pointerup", up);
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === "ArrowLeft") { e.preventDefault(); onResize(width - 20); }
    if (e.key === "ArrowRight") { e.preventDefault(); onResize(width + 20); }
  }

  return (
    <div
      className="resizer" role="separator" aria-orientation="vertical" tabIndex={0}
      aria-label="Largeur de la liste des conversations"
      aria-valuemin={SIDEBAR_MIN} aria-valuemax={SIDEBAR_MAX} aria-valuenow={width}
      title="Glissez pour agrandir ou réduire · double-clic pour réinitialiser"
      onPointerDown={onPointerDown} onKeyDown={onKeyDown} onDoubleClick={onReset}
    />
  );
}
