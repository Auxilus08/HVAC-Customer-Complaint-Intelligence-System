export default function SkeletonCard() {
  return (
    <div className="card animate-pulse mb-3">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-2.5 h-2.5 rounded-full bg-surface-border" />
        <div className="h-3 bg-surface-border rounded w-2/3" />
      </div>
      <div className="h-2.5 bg-surface-border rounded w-1/2 mb-2" />
      <div className="h-6 bg-surface-border rounded w-full mb-2" />
      <div className="h-2.5 bg-surface-border rounded w-1/3" />
    </div>
  );
}
