import { useEffect, useRef, useState } from "react";

const STEPS = [
  { delay: 0, anchor: "stats-pills", tooltip: "System processed 500 complaints automatically" },
  { delay: 3000, anchor: "alert-banner", tooltip: "🚨 Emerging patterns detected this week" },
  {
    delay: 6000,
    anchor: "sidebar",
    tooltip: "Compressor noise growing fast — opening cluster",
    action: "select-emerging",
  },
  {
    delay: 9000,
    anchor: "metrics",
    tooltip: "Rs.1.95L exposure detected in 24 hours vs 6 weeks manually",
  },
  {
    delay: 13000,
    anchor: "metrics",
    tooltip: "Week-over-week growth visible in the trend",
  },
  {
    delay: 17000,
    anchor: "advisory",
    tooltip: "Generating Gemini field advisory…",
    action: "click-generate",
  },
  {
    delay: 22000,
    anchor: "advisory",
    tooltip: "Actionable field instructions — ready for technicians",
  },
  {
    delay: 26000,
    anchor: "advisory",
    tooltip: "Export and share with the service team",
  },
  {
    delay: 29000,
    anchor: "tab-analytics",
    tooltip: "Executive view — cost exposure by region",
    action: "go-analytics",
  },
  {
    delay: 33000,
    anchor: "analytics",
    tooltip: "Delhi accounts for highest exposure",
  },
  {
    delay: 37000,
    anchor: "tab-map",
    tooltip: "All patterns mapped semantically using multilingual NLP",
    action: "go-map",
  },
  {
    delay: 41000,
    anchor: null,
    tooltip: "Demo complete — Pattern detected in < 24 hours vs 6 weeks manually",
    isFinal: true,
  },
];

const findHighestEmergingCluster = () => {
  const cards = document.querySelectorAll("[data-cluster-id]");
  if (cards.length === 0) return null;
  let best = null;
  let bestScore = -Infinity;
  cards.forEach((el) => {
    const score = parseFloat(el.getAttribute("data-priority-score") || "0");
    const isEmerging = el.getAttribute("data-cluster-emerging") === "1";
    const adj = score + (isEmerging ? 1000 : 0);
    if (adj > bestScore) {
      bestScore = adj;
      best = el;
    }
  });
  return best;
};

export default function DemoMode({ onExit, setSelectedClusterId, setActiveTab }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [highlightRect, setHighlightRect] = useState(null);
  const timersRef = useRef([]);

  const clearTimers = () => {
    timersRef.current.forEach((t) => clearTimeout(t));
    timersRef.current = [];
  };

  useEffect(() => {
    clearTimers();
    STEPS.forEach((step, i) => {
      const t = setTimeout(() => {
        setStepIndex(i);
        if (step.action === "select-emerging") {
          const target = findHighestEmergingCluster();
          if (target) {
            const idAttr = target.getAttribute("data-cluster-id");
            const id = idAttr ? Number(idAttr) : null;
            if (id != null && Number.isFinite(id)) {
              setSelectedClusterId?.(id);
            }
          }
        } else if (step.action === "click-generate") {
          const btn = document.querySelector(
            "[data-demo-anchor='generate-advisory']"
          );
          btn?.click();
        } else if (step.action === "go-analytics") {
          setSelectedClusterId?.(null);
          setActiveTab?.("analytics");
        } else if (step.action === "go-map") {
          setSelectedClusterId?.(null);
          setActiveTab?.("map");
        }
      }, step.delay);
      timersRef.current.push(t);
    });

    const exitTimer = setTimeout(() => onExit?.(), STEPS[STEPS.length - 1].delay + 5000);
    timersRef.current.push(exitTimer);

    return () => clearTimers();
  }, [onExit, setSelectedClusterId, setActiveTab]);

  useEffect(() => {
    const step = STEPS[stepIndex];
    if (!step?.anchor) {
      setHighlightRect(null);
      return undefined;
    }
    const update = () => {
      const el = document.querySelector(`[data-demo-anchor='${step.anchor}']`);
      if (!el) {
        setHighlightRect(null);
        return;
      }
      const r = el.getBoundingClientRect();
      setHighlightRect({
        top: r.top,
        left: r.left,
        width: r.width,
        height: r.height,
      });
    };
    update();
    const onResize = () => update();
    window.addEventListener("resize", onResize);
    window.addEventListener("scroll", onResize, true);
    const interval = setInterval(update, 250);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onResize, true);
      clearInterval(interval);
    };
  }, [stepIndex]);

  const step = STEPS[stepIndex];

  return (
    <div className="fixed inset-0 z-40 pointer-events-none">
      {highlightRect && (
        <div
          className="absolute pointer-events-none transition-all duration-500 ease-out rounded-xl ring-4 ring-accent ring-offset-2 ring-offset-surface shadow-[0_0_40px_rgba(232,93,4,0.5)]"
          style={{
            top: highlightRect.top - 4,
            left: highlightRect.left - 4,
            width: highlightRect.width + 8,
            height: highlightRect.height + 8,
          }}
        />
      )}

      {step?.tooltip && (
        <div
          className="absolute pointer-events-none animate-fade-in"
          style={{
            top: highlightRect
              ? Math.min(window.innerHeight - 80, highlightRect.top + highlightRect.height + 12)
              : window.innerHeight / 2,
            left: highlightRect
              ? Math.max(16, Math.min(window.innerWidth - 360, highlightRect.left))
              : window.innerWidth / 2 - 180,
          }}
        >
          <div className={`text-white text-sm font-medium px-4 py-2 rounded-lg shadow-2xl max-w-[340px] ${
            step.isFinal ? "bg-positive" : "bg-accent"
          }`}>
            {step.tooltip}
          </div>
        </div>
      )}

      <div className="absolute top-4 right-4 pointer-events-auto flex items-center gap-2 bg-surface-card border border-surface-border rounded-lg px-3 py-1.5 shadow-2xl">
        <span className="text-xs text-slate-400">
          Step {stepIndex + 1} / {STEPS.length}
        </span>
        <button
          onClick={() => {
            clearTimers();
            onExit?.();
          }}
          className="text-xs text-accent font-medium hover:text-white transition-colors"
        >
          Exit Demo
        </button>
      </div>
    </div>
  );
}
