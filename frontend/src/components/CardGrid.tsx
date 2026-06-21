import { useRef, useState } from "react";
import type { ReactNode } from "react";
import { useCardOrder } from "../hooks/useCardOrder";

// A masonry-packed, drag-to-reorder grid of dashboard cards. Order persists per `storageKey`.
export function CardGrid({
  storageKey,
  defaultOrder,
  wide,
  cards,
}: {
  storageKey: string;
  defaultOrder: string[];
  wide: Set<string>;
  cards: Record<string, ReactNode>;
}) {
  const [order, setOrder] = useCardOrder(storageKey, defaultOrder);
  const dragId = useRef<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);

  const onDragEnter = (overId: string) => {
    const from = dragId.current;
    if (!from || from === overId) return;
    const next = order.filter((k) => k !== from);
    next.splice(next.indexOf(overId), 0, from);
    setOrder(next);
  };
  const endDrag = () => {
    dragId.current = null;
    setDragging(null);
  };

  return (
    <div className="dash">
      {order
        .filter((id) => cards[id])
        .map((id) => (
          <div
            key={id}
            className={
              "dash__cell" +
              (wide.has(id) ? " dash__cell--wide" : "") +
              (dragging === id ? " is-dragging" : "")
            }
            onDragEnter={() => onDragEnter(id)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              endDrag();
            }}
          >
            <span
              className="dash__grip"
              draggable
              title="Drag to reorder"
              onDragStart={(e) => {
                dragId.current = id;
                setDragging(id);
                const cell = (e.currentTarget as HTMLElement).closest(".dash__cell") as HTMLElement | null;
                if (cell) e.dataTransfer.setDragImage(cell, 24, 24);
                e.dataTransfer.effectAllowed = "move";
              }}
              onDragEnd={endDrag}
            >
              ⠿
            </span>
            {cards[id]}
          </div>
        ))}
    </div>
  );
}
