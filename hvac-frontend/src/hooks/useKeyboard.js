import { useEffect } from "react";

const isTypingTarget = (el) => {
  if (!el) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (el.isContentEditable) return true;
  return false;
};

export function useKeyboard(keymap, options = {}) {
  const { enabled = true } = options;
  useEffect(() => {
    if (!enabled) return undefined;
    const handler = (e) => {
      if (isTypingTarget(e.target)) {
        if (e.key === "Escape" && keymap.Escape) {
          keymap.Escape(e);
        }
        return;
      }
      const fn = keymap[e.key] || keymap[e.key?.toLowerCase()];
      if (fn) {
        e.preventDefault();
        fn(e);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [keymap, enabled]);
}
