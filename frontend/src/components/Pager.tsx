import { useEffect, useState } from "react";

// 10 items per page on mobile, 20 on desktop (recomputed on resize).
export function usePageSize(mobile = 10, desktop = 20): number {
  const calc = () => (typeof window !== "undefined" && window.innerWidth <= 760 ? mobile : desktop);
  const [size, setSize] = useState(calc);
  useEffect(() => {
    const onResize = () => setSize(calc());
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mobile, desktop]);
  return size;
}

// Slice helper: clamps the page to a valid range and returns the visible window + a Pager.
export function paginate<T>(items: T[], page: number, size: number) {
  const pages = Math.max(1, Math.ceil(items.length / size));
  const p = Math.min(Math.max(0, page), pages - 1);
  return { pages, page: p, slice: items.slice(p * size, (p + 1) * size) };
}

export function Pager({
  page,
  pages,
  total,
  onPage,
}: {
  page: number;
  pages: number;
  total: number;
  onPage: (p: number) => void;
}) {
  if (pages <= 1) return null;
  return (
    <div className="pager">
      <button className="btn btn--ghost btn--sm" disabled={page <= 0} onClick={() => onPage(page - 1)}>
        ‹ Prev
      </button>
      <span className="muted" style={{ fontSize: 12 }}>
        Page {page + 1} / {pages} · {total} items
      </span>
      <button className="btn btn--ghost btn--sm" disabled={page >= pages - 1} onClick={() => onPage(page + 1)}>
        Next ›
      </button>
    </div>
  );
}
