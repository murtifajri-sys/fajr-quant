"use client";

import { TickerLink } from "./TickerLink";

interface Column {
  key: string;
  label: string;
  format?: (value: any, row: any) => string;
  className?: string;
}

export function DataTable({
  columns,
  rows,
  linkKeys = ["ticker"],
}: {
  columns: Column[];
  rows: any[];
  linkKeys?: string[];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-slate-400 bg-slate-900 sticky top-0">
            {columns.map((col) => (
              <th key={col.key} className={`text-left py-2 px-3 whitespace-nowrap ${col.className || ""}`}>
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="py-8 text-center text-slate-500">
                No data found
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr key={i} className="border-t border-slate-800 hover:bg-slate-900/50">
                {columns.map((col) => {
                  const val = row[col.key];
                  const display = col.format ? col.format(val, row) : val ?? "-";
                  const isLink = linkKeys.includes(col.key) && typeof val === "string" && val;
                  return (
                    <td key={col.key} className={`py-1.5 px-3 text-xs whitespace-nowrap ${col.className || ""}`}>
                      {isLink ? (
                        <TickerLink ticker={val} />
                      ) : (
                        <span className="font-mono">{display}</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
