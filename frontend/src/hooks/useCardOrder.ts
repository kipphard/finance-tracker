import { useState } from "react";

// Persisted dashboard card order, keyed per section. Merges in any new cards and drops removed ones.
export function useCardOrder(
  key: string,
  defaultOrder: string[],
): [string[], (order: string[]) => void] {
  const [order, setOrder] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(key) || "null");
      if (Array.isArray(saved)) {
        const merged = saved.filter((k: string) => defaultOrder.includes(k));
        // Insert any new cards near their default position instead of at the bottom.
        defaultOrder.forEach((k, i) => {
          if (!merged.includes(k)) merged.splice(Math.min(i, merged.length), 0, k);
        });
        return merged;
      }
    } catch {
      /* ignore */
    }
    return defaultOrder;
  });

  const update = (next: string[]) => {
    setOrder(next);
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  };

  return [order, update];
}
