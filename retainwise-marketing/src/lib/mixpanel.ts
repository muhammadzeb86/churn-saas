// src/lib/mixpanel.ts
import mixpanel from "mixpanel-browser";

const token = process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;

if (typeof window !== "undefined" && token) {
  mixpanel.init(token, { debug: false });
}

export default mixpanel; 