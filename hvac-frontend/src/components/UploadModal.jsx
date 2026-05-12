import { useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { useUploadCSV } from "../hooks/useUpload";
import Spinner from "./ui/Spinner";

const MAX_BYTES = 10 * 1024 * 1024;

const formatBytes = (b) => {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1024 / 1024).toFixed(2)} MB`;
};

export default function UploadModal({ onClose }) {
  const [file, setFile] = useState(null);
  const [showFormat, setShowFormat] = useState(false);
  const [success, setSuccess] = useState(null);
  const upload = useUploadCSV();

  const onDrop = (accepted) => {
    if (accepted?.[0]) {
      setFile(accepted[0]);
      upload.reset();
    }
  };

  const { getRootProps, getInputProps, isDragActive, fileRejections } =
    useDropzone({
      onDrop,
      accept: { "text/csv": [".csv"], "application/vnd.ms-excel": [".csv"] },
      maxFiles: 1,
      maxSize: MAX_BYTES,
    });

  useEffect(() => {
    if (success) {
      const t = setTimeout(() => onClose?.(), 3000);
      return () => clearTimeout(t);
    }
  }, [success, onClose]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const handleUpload = async () => {
    if (!file) return;
    try {
      const res = await upload.mutateAsync(file);
      const count =
        res?.uploaded ??
        res?.count ??
        res?.complaints_received ??
        res?.received ??
        null;
      setSuccess({ count });
    } catch {
      // surfaced via upload.error below
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-surface-card rounded-2xl p-6 w-full max-w-md border border-surface-border shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-bold text-ink-900 tracking-tight">
            Upload Complaint Data
          </h2>
          <button
            onClick={onClose}
            className="text-ink-500 hover:text-ink-900 transition-colors p-1 rounded hover:bg-surface-hover"
            aria-label="Close"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>

        {success ? (
          <div className="text-center py-6">
            <div className="w-14 h-14 rounded-full bg-positive/20 mx-auto flex items-center justify-center animate-fade-in">
              <svg className="w-8 h-8 text-positive" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <p className="text-ink-900 font-medium mt-4">
              {success.count != null ? `${success.count} complaints` : "Complaints"} uploaded successfully
            </p>
            <p className="text-ink-500 text-sm mt-1">
              Processing in background — clusters will update shortly
            </p>
          </div>
        ) : (
          <>
            <div
              {...getRootProps()}
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                isDragActive
                  ? "border-accent bg-accent/5"
                  : file
                  ? "border-positive/60 bg-positive/5"
                  : "border-surface-border hover:border-accent/60"
              }`}
            >
              <input {...getInputProps()} />
              {file ? (
                <div className="flex flex-col items-center gap-2">
                  <svg className="w-10 h-10 text-positive" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                    <polyline points="22 4 12 14.01 9 11.01" />
                  </svg>
                  <p className="text-ink-900 text-sm font-medium">{file.name}</p>
                  <p className="text-ink-500 text-xs">
                    {formatBytes(file.size)} · Ready to upload
                  </p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2 text-ink-500">
                  <svg className="w-10 h-10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                  <p className="text-ink-900 font-medium text-sm">
                    Drop your CSV file here
                  </p>
                  <p className="text-xs text-ink-500">
                    or click to browse · Max 10MB
                  </p>
                </div>
              )}
            </div>

            {fileRejections?.length > 0 && (
              <p className="text-xs text-critical mt-2">
                {fileRejections[0].errors?.[0]?.message ?? "File rejected."}
              </p>
            )}

            <div className="mt-3">
              <button
                type="button"
                onClick={() => setShowFormat((v) => !v)}
                className="text-xs text-ink-500 hover:text-accent transition-colors"
              >
                {showFormat ? "▼" : "▶"} Expected CSV format
              </button>
              {showFormat && (
                <pre className="mt-2 text-[11px] bg-surface px-3 py-2 rounded-md font-mono text-ink-700 border border-surface-border overflow-x-auto">
{`complaint_text,source,region,product_sku
"AC not cooling",crm,Delhi,1.5T-SPLIT`}
                </pre>
              )}
            </div>

            {upload.isError && (
              <div className="mt-3 bg-critical/10 border border-critical/40 text-critical rounded-lg p-3 text-sm flex items-start justify-between gap-3">
                <span>{upload.error?.message || "Upload failed"}</span>
                <button
                  className="text-xs underline whitespace-nowrap hover:text-ink-900"
                  onClick={handleUpload}
                >
                  Try Again
                </button>
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={!file || upload.isPending}
              className="btn-primary w-full mt-4"
            >
              {upload.isPending ? (
                <>
                  <Spinner size="sm" color="text-white" /> Uploading…
                </>
              ) : (
                "Upload Complaints"
              )}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
