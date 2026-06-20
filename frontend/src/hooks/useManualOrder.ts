import { useRef, useState } from "react";

// Persisted manual ordering of list items (e.g. accounts) by id, with drag handlers.
// `reconcile(ids)` returns the effective order: saved positions first, new ids appended,
// removed ids dropped. `over(targetId, allow?)` moves the dragged item before `targetId`
// (optionally gated by a predicate, e.g. "same date only").

function load(key: string): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(key) || "null");
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

export function useManualOrder(key: string) {
  const [order, setOrder] = useState<string[]>(() => load(key));
  const dragId = useRef<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const effRef = useRef<string[]>(order);

  const reconcile = (ids: string[]): string[] => {
    const known = order.filter((id) => ids.includes(id));
    const fresh = ids.filter((id) => !known.includes(id));
    const eff = [...known, ...fresh];
    effRef.current = eff;
    return eff;
  };

  const persist = (next: string[]) => {
    effRef.current = next;
    setOrder(next);
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  };

  const start = (id: string) => {
    dragId.current = id;
    setDragging(id);
  };

  const over = (targetId: string, allow?: (from: string, to: string) => boolean) => {
    const from = dragId.current;
    if (!from || from === targetId) return;
    if (allow && !allow(from, targetId)) return;
    const eff = [...effRef.current];
    if (eff.indexOf(from) === -1 || eff.indexOf(targetId) === -1) return;
    eff.splice(eff.indexOf(from), 1);
    eff.splice(eff.indexOf(targetId), 0, from);
    persist(eff);
  };

  const end = () => {
    dragId.current = null;
    setDragging(null);
  };

  return { dragging, reconcile, start, over, end };
}
