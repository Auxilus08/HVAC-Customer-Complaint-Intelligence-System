export default function EmptyState({ icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center text-center p-10 text-ink-500">
      {icon ? <div className="text-5xl mb-4 opacity-60">{icon}</div> : null}
      {title ? (
        <h3 className="text-ink-900 font-semibold text-lg mb-1">{title}</h3>
      ) : null}
      {description ? (
        <p className="text-sm text-ink-500 max-w-sm mb-4 leading-relaxed">
          {description}
        </p>
      ) : null}
      {action ? (
        <button onClick={action.onClick} className="btn-primary">
          {action.label}
        </button>
      ) : null}
    </div>
  );
}
