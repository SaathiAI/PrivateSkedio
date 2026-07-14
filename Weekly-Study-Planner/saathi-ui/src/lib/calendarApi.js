import { API, authGet, authPost, buildQuery, readApiJson, apiErrorMessage } from "./api.js";

export const calendarApi = {
  async status() {
    const response = await authGet(`${API}/auth/calendar/status`);
    const data = await readApiJson(response, {});
    if (!response.ok) {
      throw new Error(data.detail || data.message || "Calendar status check failed");
    }
    return data;
  },

  async connectUrl(returnUrl = window.location.origin) {
    const query = buildQuery({ return_url: returnUrl });
    const response = await authGet(`${API}/auth/calendar/connect?${query}`);
    const data = await readApiJson(response, {});
    if (!response.ok) {
      throw new Error(data.detail || data.message || "Could not start Google Calendar connection");
    }
    return data.auth_url || "";
  },

  async disconnect() {
    const response = await authPost(`${API}/auth/calendar/disconnect`, {});
    if (!response.ok) {
      throw new Error(await apiErrorMessage(response, "Calendar disconnect failed"));
    }
    return true;
  },

  async externalEvents(startDate, endDate) {
    const query = buildQuery({ start_date: startDate, end_date: endDate });
    const response = await authGet(`${API}/calendar/events/external?${query}`);
    const data = await readApiJson(response, {});
    if (!response.ok) {
      throw new Error(data.detail || data.message || "Calendar blockers unavailable");
    }
    return data?.events?.blocked_slots || [];
  },
};
