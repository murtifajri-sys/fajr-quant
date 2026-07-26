"use client";

export function PaginationBar({
  offset,
  limit,
  total,
  onChange,
}: {
  offset: number;
  limit: number;
  total: number;
  onChange: (offset: number) => void;
}) {
  const page = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div className="flex items-center justify-between text-sm text-slate-400 mt-3">
      <span>
        Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <div className="flex gap-2">
        <button
          className="btn-secondary text-xs px-3 py-1"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          Prev
        </button>
        <span className="px-2 py-1 text-slate-300">
          {page} / {totalPages}
        </span>
        <button
          className="btn-secondary text-xs px-3 py-1"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
