import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useQueryClient } from "@tanstack/react-query";
import client from "../api/client.js";
import { CLUSTERS_KEY } from "../api/clusters.js";

export default function UploadDropzone() {
  const [status, setStatus] = useState(null); // null | "uploading" | "success" | "error"
  const [message, setMessage] = useState("");
  const queryClient = useQueryClient();

  const onDrop = useCallback(
    async (acceptedFiles) => {
      const file = acceptedFiles[0];
      if (!file) return;

      setStatus("uploading");
      setMessage("");

      const formData = new FormData();
      formData.append("file", file);

      try {
        const { data } = await client.post("/api/v1/complaints/upload", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        setStatus("success");
        setMessage(
          `Accepted ${data.accepted} complaints, queued ${data.queued_for_embedding} for embedding.`
        );
        queryClient.invalidateQueries({ queryKey: CLUSTERS_KEY });
      } catch (err) {
        setStatus("error");
        setMessage(err.response?.data?.detail ?? "Upload failed.");
      }
    },
    [queryClient]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"] },
    maxFiles: 1,
    disabled: status === "uploading",
  });

  return (
    <div className="card">
      <h3 className="text-sm font-medium text-gray-400 mb-3">Upload Complaints CSV</h3>

      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          isDragActive
            ? "border-brand-500 bg-brand-900/20"
            : "border-gray-700 hover:border-gray-600"
        } ${status === "uploading" ? "opacity-50 pointer-events-none" : ""}`}
      >
        <input {...getInputProps()} />
        <div className="text-2xl mb-2">📥</div>
        <p className="text-sm text-gray-400">
          {isDragActive
            ? "Drop the CSV here…"
            : "Drag & drop a complaints CSV, or click to select"}
        </p>
        <p className="text-xs text-gray-600 mt-1">
          Columns: text, source, region, product_sku
        </p>
      </div>

      {status === "uploading" && (
        <p className="mt-2 text-xs text-brand-400 animate-pulse">Uploading…</p>
      )}
      {status === "success" && (
        <p className="mt-2 text-xs text-green-400">{message}</p>
      )}
      {status === "error" && (
        <p className="mt-2 text-xs text-red-400">{message}</p>
      )}
    </div>
  );
}
