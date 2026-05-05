const SIZES = { sm: "w-4 h-4", md: "w-8 h-8", lg: "w-12 h-12" };

export default function Spinner({ size = "md", color = "text-accent", className = "" }) {
  const dim = SIZES[size] || SIZES.md;
  return (
    <svg
      className={`animate-spin ${dim} ${color} ${className}`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
      />
    </svg>
  );
}
