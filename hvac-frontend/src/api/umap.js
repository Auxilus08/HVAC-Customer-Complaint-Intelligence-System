import client from "./client";

export const getUmapCoords = (runId = null) =>
  client.get("/umap", { params: runId ? { run_id: runId } : {} });
