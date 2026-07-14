import { API, authGet } from "./api.js";

export const backlogApi = {
  async chapters() {
    const response = await authGet(`${API}/backlog/chapters`);
    if (!response.ok) return {};
    return response.json();
  },
};
