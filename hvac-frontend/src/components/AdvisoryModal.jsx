import { useState } from "react";

export default function AdvisoryModal({ advisory, onClose }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(advisory.advisory_text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg shadow-2xl">
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <div>
            <h2 className="text-base font-semibold text-white">Technician Advisory</h2>
            <p className="text-xs text-gray-500 mt-0.5 truncate max-w-xs">
              {advisory.label ?? `Cluster #${advisory.cluster_id}`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 transition-colors"
          >
            ✕
          </button>
        </div>

        <div className="p-4">
          <pre className="whitespace-pre-wrap text-sm text-gray-300 font-sans leading-relaxed">
            {advisory.advisory_text}
          </pre>
        </div>

        <div className="flex items-center justify-between p-4 border-t border-gray-800">
          <span className="text-xs text-gray-600">
            Generated {new Date(advisory.generated_at).toLocaleString()}
          </span>
          <button
            onClick={handleCopy}
            className="px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white text-sm rounded-lg transition-colors"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>
    </div>
  );
}
