import { useState } from "react";

const KEY = "ft_card_order";

// Persisted dashboard card order. Merges in any new cards and drops removed ones.
export function useCardOrder(
  defaultOrder: string[],
): [string[], (order: string[]) => void] {
  const [order, setOrder] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(KEY) || "null");
      if (Array.isArray(saved)) {
        const merged = saved.filter((k: string) => defaultOrder.includes(k));
        for (const k of defaultOrder) if (!merged.includes(k)) merged.push(k);
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
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  };

  return [order, update];
}
