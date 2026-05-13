import { Package } from "lucide-react";

// Field render order — null/empty values are skipped.
const SINGLE_FIELDS = [
  ["brand", "Brand"],
  ["family", "Family"],
  ["model_name", "Model name"],
  ["model_number", "Model number"],
  ["serial_number", "Serial number"],
  ["capacity", "Capacity"],
  ["refrigerant", "Refrigerant"],
  ["install_type", "Install type"],
  ["install_location", "Install location"],
  ["purchase_date", "Purchase date"],
  ["manufacture_date", "Manufacture date"],
  ["warranty_status", "Warranty"],
  ["issue_summary", "Issue summary"],
];

const LIST_FIELDS = [
  ["symptoms", "Symptoms"],
  ["tried_already", "Already tried"],
];

function hasAnyContent(info, matchedProduct) {
  if (matchedProduct) return true;
  if (!info || typeof info !== "object") return false;
  for (const [key] of SINGLE_FIELDS) {
    if (info[key]) return true;
  }
  for (const [key] of LIST_FIELDS) {
    const v = info[key];
    if (Array.isArray(v) && v.length > 0) return true;
  }
  return false;
}

export default function ProductInfoPanel({ matchedProduct, gatheredInfo }) {
  const info = gatheredInfo || {};
  if (!hasAnyContent(info, matchedProduct)) {
    return (
      <div className="rounded-lg border border-dashed border-surface-border bg-surface px-4 py-3">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-ink-500 mb-1">
          <Package className="w-3.5 h-3.5" /> Product Information
        </div>
        <div className="text-sm text-ink-500">
          No product details gathered yet — the bot is still asking the
          customer for context.
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-surface-border bg-surface px-4 py-3">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-ink-500 mb-2">
        <Package className="w-3.5 h-3.5" /> Product Information
      </div>

      {matchedProduct ? (
        <div className="mb-3 p-2.5 bg-carrier-light rounded text-sm">
          <div className="text-[10px] uppercase tracking-wide text-carrier font-semibold mb-0.5">
            Catalog match
          </div>
          <div className="font-semibold text-ink-900">
            {[matchedProduct.family, matchedProduct.model_name]
              .filter(Boolean)
              .join(" · ")}
          </div>
          <div className="text-xs text-ink-700 mt-0.5">
            SKU {matchedProduct.sku}
            {matchedProduct.category ? ` · ${matchedProduct.category}` : ""}
            {matchedProduct.tonnage ? ` · ${matchedProduct.tonnage} ton` : ""}
          </div>
        </div>
      ) : null}

      <dl className="grid grid-cols-[max-content_1fr] gap-x-3 gap-y-1.5 text-sm">
        {SINGLE_FIELDS.map(([key, label]) => {
          const value = info[key];
          if (!value) return null;
          return (
            <div className="contents" key={key}>
              <dt className="text-ink-500 text-xs uppercase tracking-wide self-baseline">
                {label}
              </dt>
              <dd className="text-ink-900">{value}</dd>
            </div>
          );
        })}
      </dl>

      {LIST_FIELDS.map(([key, label]) => {
        const items = info[key];
        if (!Array.isArray(items) || items.length === 0) return null;
        return (
          <div key={key} className="mt-3">
            <div className="text-xs uppercase tracking-wide text-ink-500 mb-1">
              {label}
            </div>
            <ul className="list-disc list-inside space-y-0.5 text-sm text-ink-900">
              {items.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
