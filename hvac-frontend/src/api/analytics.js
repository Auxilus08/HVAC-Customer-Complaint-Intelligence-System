import client from "./client";

export const getStats = () => client.get("/analytics/stats");
export const getHeatmap = () => client.get("/analytics/heatmap");
export const getSkus = () => client.get("/analytics/skus");
export const getSources = () => client.get("/analytics/sources");
export const getBuildings = () => client.get("/analytics/buildings");
export const getRegionHeatmap = () => client.get("/analytics/region_heatmap");
export const getGeo = (level) => client.get("/analytics/geo", { params: { level } });
export const getCities = () => client.get("/analytics/cities");
