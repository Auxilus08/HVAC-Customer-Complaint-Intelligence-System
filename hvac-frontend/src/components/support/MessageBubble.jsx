import { formatRelativeTime } from "../../utils/format";

const VARIANTS = {
  inbound: {
    align: "items-start",
    bubble: "bg-surface border border-surface-border text-ink-900",
    label: "Customer",
  },
  outbound_bot: {
    align: "items-center",
    bubble: "bg-ink-100 text-ink-700 italic",
    label: "Bot",
  },
  outbound_agent: {
    align: "items-end",
    bubble: "bg-carrier text-white",
    label: "You",
  },
};

export default function MessageBubble({ message }) {
  const v = VARIANTS[message.direction] || VARIANTS.inbound;
  const ocr = message.llm_metadata?.kind === "image_ocr"
    ? message.llm_metadata
    : null;
  return (
    <div className={`flex flex-col gap-1 ${v.align}`}>
      <div className="text-[11px] uppercase tracking-wide text-ink-500">
        {v.label} · {formatRelativeTime(message.created_at)}
        {message.has_image ? " · 📷 photo" : ""}
      </div>
      {message.has_image ? (
        <a
          href={`/api/v1/support/messages/${message.id}/image`}
          target="_blank"
          rel="noreferrer"
          className="max-w-[78%] block rounded-2xl overflow-hidden border border-surface-border bg-surface"
          title="Open full size"
        >
          <img
            src={`/api/v1/support/messages/${message.id}/image`}
            alt="Customer attachment"
            className="max-h-72 w-auto object-contain block"
          />
        </a>
      ) : null}
      {message.body ? (
        <div
          className={`max-w-[78%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${v.bubble}`}
        >
          {message.body}
        </div>
      ) : null}
      {ocr ? (
        <div className="max-w-[78%] text-[11px] text-ink-500 italic px-1">
          Vision OCR · confidence {Math.round((ocr.confidence ?? 0) * 100)}%
          {ocr.summary ? ` — ${ocr.summary}` : ""}
        </div>
      ) : null}
      {message.llm_metadata?.kind === "ai_resolution" &&
      message.direction === "outbound_bot" ? (
        <div className="text-[10px] text-ink-500 italic">
          AI-resolved · confidence{" "}
          {Math.round((message.llm_metadata.confidence ?? 0) * 100)}%
        </div>
      ) : null}
    </div>
  );
}
