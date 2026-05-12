import { useRegionHeatmap } from "../hooks/useAnalytics";

const BOROUGH_META = [
  { code: "MAN", full: "Manhattan" },
  { code: "BKN", full: "Brooklyn" },
  { code: "QNS", full: "Queens" },
  { code: "BRX", full: "Bronx" },
  { code: "SI", full: "Staten Island" },
];

const NAVY = [30, 58, 95]; // #1E3A5F

function cellStyle(count, maxValue) {
  if (maxValue === 0 || count === 0) return {};
  const ratio = Math.min(1, Math.max(0.05, count / maxValue));
  return { backgroundColor: `rgba(${NAVY[0]}, ${NAVY[1]}, ${NAVY[2]}, ${ratio})` };
}

function cellTextClass(count, maxValue) {
  if (count === 0) return "text-ink-300";
  const ratio = count / maxValue;
  return ratio >= 0.5 ? "text-white" : "text-ink-900";
}

function SkeletonGrid() {
  return (
    <div className="card p-6 animate-pulse">
      <div className="h-7 w-64 bg-ink-100 rounded mb-2" />
      <div className="h-4 w-96 bg-ink-100 rounded mb-6" />
      <div className="grid gap-1" style={{ gridTemplateColumns: "320px repeat(5, 64px)" }}>
        {Array.from({ length: 66 }).map((_, i) => (
          <div key={i} className="h-14 bg-ink-100 rounded" />
        ))}
      </div>
    </div>
  );
}

const LEGEND_STEPS = [0.05, 0.2, 0.4, 0.6, 0.8, 1.0];

export default function BoroughHeatmap() {
  const { data, isLoading, isError } = useRegionHeatmap();

  if (isLoading) return <SkeletonGrid />;

  if (isError) {
    return (
      <div className="card p-6">
        <p className="text-ink-500 text-sm">Couldn&apos;t load region data.</p>
      </div>
    );
  }

  const themes = data?.themes ?? [];
  const matrix = data?.matrix ?? [];
  const maxValue = data?.max_value ?? 0;

  const totalNyc = matrix.reduce((sum, row) => sum + row.reduce((s, v) => s + v, 0), 0);

  // Borough column totals
  const colTotals = BOROUGH_META.map((_, j) =>
    matrix.reduce((sum, row) => sum + (row[j] ?? 0), 0)
  );

  return (
    <div className="card p-6">
      <h2 className="text-2xl font-bold text-ink-900 mb-1">Where Each Issue Concentrates</h2>
      <p className="text-ink-500 text-sm mb-6">
        Top complaint themes broken down by NYC borough. Darker cells mean more complaints. Hover for the count.
      </p>

      {themes.length === 0 ? (
        <div className="flex items-center justify-center h-40 text-ink-500 text-sm">
          No NYC complaints clustered yet.
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="border-separate" style={{ borderSpacing: "4px" }}>
              <thead>
                <tr>
                  {/* empty corner */}
                  <th className="sticky left-0 bg-surface z-10 w-80" />
                  {BOROUGH_META.map((b, j) => (
                    <th
                      key={b.code}
                      title={b.full}
                      className="text-center pb-1"
                      style={{ minWidth: 64 }}
                    >
                      <span className="block text-xs font-semibold text-ink-700">{b.code}</span>
                      <span className="block text-xs text-ink-500">
                        {colTotals[j].toLocaleString()}
                      </span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {themes.map((theme, i) => (
                  <tr key={i}>
                    <td
                      className="sticky left-0 bg-surface z-10 pr-3 py-1 text-sm font-medium text-ink-900 truncate"
                      style={{ maxWidth: 320 }}
                      title={theme.label}
                    >
                      {theme.label}
                    </td>
                    {(matrix[i] ?? []).map((count, j) => (
                      <td
                        key={j}
                        title={`${theme.label} — ${BOROUGH_META[j].full}: ${count}`}
                        className={`text-center text-sm font-medium rounded-md transition-shadow hover:ring-2 hover:ring-carrier cursor-default ${cellTextClass(count, maxValue)}`}
                        style={{
                          minWidth: 64,
                          height: 56,
                          ...cellStyle(count, maxValue),
                          borderRadius: 6,
                        }}
                      >
                        {count === 0 ? (
                          <span className="text-ink-300">—</span>
                        ) : (
                          count.toLocaleString()
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Footer */}
          <div className="mt-5 flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-2 text-xs text-ink-500">
              <span>Fewer</span>
              {LEGEND_STEPS.map((alpha) => (
                <span
                  key={alpha}
                  className="inline-block w-5 h-5 rounded"
                  style={{ backgroundColor: `rgba(${NAVY[0]}, ${NAVY[1]}, ${NAVY[2]}, ${alpha})` }}
                />
              ))}
              <span>More</span>
            </div>
            <span className="text-ink-500 text-sm">
              Total: {totalNyc.toLocaleString()} NYC complaints
            </span>
          </div>
        </>
      )}
    </div>
  );
}
