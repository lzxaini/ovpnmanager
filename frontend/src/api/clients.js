import api from "./http";

export const listClients = (params = {}) => api.get("/clients", { params });
export const createClient = (payload) => api.post("/clients", payload);
export const updateClient = (id, payload) => api.patch(`/clients/${id}`, payload);
export const deleteClient = (id, payload = {}) => api.delete(`/clients/${id}`, { data: payload });
export const exportClientOvpn = (id, payload = {}) => api.post(`/clients/${id}/cert`, payload);
export const checkExportedClientOvpn = (id) => api.get(`/clients/${id}/cert/exported`);
export const disconnectClient = (id) => api.post(`/clients/${id}/disconnect`);
export const validateClient = (params = {}) => api.get("/clients/validate", { params });
