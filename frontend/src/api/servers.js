import api from "./http";

export const listServers = () => api.get("/servers");
export const updateServer = (id, payload) => api.patch(`/servers/${id}`, payload);
export const getServerConf = () => api.get("/servers/config");
export const updateServerConf = (payload) => api.put("/servers/config", payload);
export const controlServer = (action) => api.post(`/servers/control/${action}`);
