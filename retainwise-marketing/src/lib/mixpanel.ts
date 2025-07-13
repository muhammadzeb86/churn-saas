// src/lib/mixpanel.ts
import mixpanel from "mixpanel-browser";

const token = process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;

if (typeof window !== "undefined" && token) {
  try {
    mixpanel.init(token, { debug: false });
  } catch (error) {
    console.warn('Mixpanel initialization failed:', error);
  }
}

export default mixpanel; 