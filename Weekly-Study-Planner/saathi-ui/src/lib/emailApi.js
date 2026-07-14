import { API, authGet, readApiJson } from "./api.js";

export const emailApi = {
  async status() {
    const response = await authGet(`${API}/email/status`);
    const data = await readApiJson(response, {});
    if (!response.ok) {
      throw new Error(data.detail || data.message || "Email status check failed");
    }
    return data;
  },
};
