import { API, authGet } from "./api.js";

export const statsApi = {
  async dashboard() {
    const response = await authGet(`${API}/stats/dashboard`);
    if (!response.ok) return null;
    return response.json();
  },

  async graph() {
    const response = await authGet(`${API}/stats/graph`);
    if (!response.ok) return { nodes: [], links: [] };
    return response.json();
  },
};
