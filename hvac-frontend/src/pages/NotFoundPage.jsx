import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="flex items-center justify-center min-h-full p-8">
      <div className="bg-surface rounded-xl border border-surface-border p-8 shadow-sm text-center max-w-sm w-full">
        <h1 className="text-4xl font-bold text-ink-900 mb-2">404</h1>
        <p className="text-ink-500 text-sm mb-6">We couldn&apos;t find that page.</p>
        <Link
          to="/overview"
          className="bg-carrier text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-carrier-dark transition-colors inline-block"
        >
          Back to Overview
        </Link>
      </div>
    </div>
  );
}
