import client from "./client";

export const getStats = () => client.get("/analytics/stats");
export const getHeatmap = () => client.get("/analytics/heatmap");
export const getSkus = () => client.get("/analytics/skus");
