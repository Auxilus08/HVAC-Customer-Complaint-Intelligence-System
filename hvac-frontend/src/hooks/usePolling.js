import { useEffect, useRef } from "react";

/**
 * Generic polling hook that calls `fn` every `intervalMs` milliseconds.
 * Cleans up on unmount or when dependencies change.
 */
export function usePolling(fn, intervalMs, enabled = true) {
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (!enabled || intervalMs <= 0) return;

    const id = setInterval(() => {
      fnRef.current();
    }, intervalMs);

    return () => clearInterval(id);
  }, [intervalMs, enabled]);
}
