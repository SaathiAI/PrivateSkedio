import { API, authGet } from "./api.js";
import { normalizePlan } from "./planAdapter.js";

export const planApi = {
  async bootstrap() {
    const response = await authGet(`${API}/app/bootstrap`);
    if (!response.ok) {
      return {
        plan: null,
        progress: { by_subject: {} },
        stats: null,
      };
    }
    const data = await response.json();
    return {
      plan: normalizePlan(data?.plan || null),
      progress: data?.progress || { by_subject: {} },
      stats: data?.stats || null,
    };
  },

  async listAll() {
    const response = await authGet(`${API}/plan/all`);
    if (!response.ok) return [];
    const data = await response.json();
    return Array.isArray(data) ? data : (data?.plans || []);
  },

  async getActive() {
    const response = await authGet(`${API}/plan/active`);
    if (!response.ok) return null;
    return normalizePlan(await response.json());
  },

  async allocationSummary() {
    const response = await authGet(`${API}/plan/allocation-summary`);
    if (!response.ok) return {};
    return response.json();
  },

  async getProgress() {
    const response = await authGet(`${API}/plan/progress`);
    if (!response.ok) return { by_subject: {} };
    return response.json();
  },
};
