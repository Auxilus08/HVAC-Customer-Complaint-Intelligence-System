import { formatRelativeTime } from "../../utils/format";

const STATUS_BADGES = {
  bot_collecting: { label: "Bot · collecting", className: "bg-ink-100 text-ink-700" },
  bot_resolved: {
    label: "Bot · resolved",
    className: "bg-status-positive/10 text-status-positive",
  },
  escalated: {
    label: "Escalated",
    className: "bg-status-critical/10 text-status-critical",
  },
  agent_active: {
    label: "Agent active",
    className: "bg-status-high/10 text-status-high",
  },
  closed: { label: "Closed", className: "bg-ink-100 text-ink-500" },
};

export default function TicketListItem({ ticket, selected, onClick }) {
  const status = STATUS_BADGES[ticket.status] || {
    label: ticket.status,
    className: "bg-ink-100 text-ink-700",
  };
  const product = ticket.matched_product;
  const direction = ticket.last_message_direction;
  const prefix =
    direction === "outbound_bot"
      ? "Bot:"
      : direction === "outbound_agent"
      ? "You:"
      : direction === "inbound"
      ? "Customer:"
      : "";

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 border-b border-surface-border transition-colors ${
        selected
          ? "bg-carrier-light"
          : "bg-surface hover:bg-ink-100"
      }`}
    >
      <div className="flex items-center justify-between mb-1.5 gap-2">
        <span className="text-xs font-medium text-ink-500">
          Ticket #{ticket.id}
        </span>
        <span
          className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full whitespace-nowrap ${status.className}`}
        >
          {status.label}
        </span>
      </div>
      <div className="text-sm font-medium text-ink-900 truncate mb-1">
        {product
          ? `${product.family || ""} ${product.model_name}`.trim()
          : "Product not matched yet"}
      </div>
      <div className="text-xs text-ink-500 line-clamp-2 leading-snug">
        {prefix && <span className="font-medium text-ink-700">{prefix} </span>}
        {ticket.last_message_preview || "(no messages yet)"}
      </div>
      <div className="flex items-center justify-between mt-1.5 text-[11px] text-ink-500">
        <span>{ticket.message_count} msgs</span>
        <span>{formatRelativeTime(ticket.last_message_at)}</span>
      </div>
    </button>
  );
}
