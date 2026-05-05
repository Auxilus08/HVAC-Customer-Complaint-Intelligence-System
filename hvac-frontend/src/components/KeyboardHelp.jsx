import { useState } from "react";

const SHORTCUTS = [
  ["/", "Open search"],
  ["Esc", "Close any open panel"],
  ["←", "Back to cluster map"],
  ["U", "Cluster Map tab"],
  ["A", "Analytics tab"],
  ["D", "Toggle Demo Mode"],
  ["R", "Refresh all data"],
];

export default function KeyboardHelp() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-30 w-9 h-9 rounded-full bg-surface-card border border-surface-border text-slate-300 hover:text-accent hover:border-accent shadow-lg flex items-center justify-center text-sm font-bold"
        aria-label="Keyboard shortcuts"
        title="Keyboard shortcuts"
      >
        ?
      </button>
      {open && (
        <div
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setOpen(false)}
        >
          <div
            className="bg-surface-card border border-surface-border rounded-xl p-6 max-w-sm w-full shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-white mb-4 tracking-tight">Keyboard Shortcuts</h3>
            <ul className="space-y-2">
              {SHORTCUTS.map(([key, desc]) => (
                <li key={key} className="flex items-center justify-between text-sm">
                  <span className="text-slate-300">{desc}</span>
                  <kbd className="bg-surface text-accent border border-surface-border rounded px-2 py-0.5 font-mono text-xs">
                    {key}
                  </kbd>
                </li>
              ))}
            </ul>
            <button
              onClick={() => setOpen(false)}
              className="btn-ghost w-full mt-4 text-sm"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </>
  );
}
