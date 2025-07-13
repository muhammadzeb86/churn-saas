// src/hooks/useMixpanel.ts
"use client";
import mixpanel from "../lib/mixpanel";

export function useMixpanel() {
  const track = (event: string, properties?: Record<string, unknown>) => {
    if (typeof window !== "undefined" && mixpanel) {
      try {
        mixpanel.track(event, properties);
      } catch (error) {
        console.warn('Mixpanel tracking failed:', error);
      }
    }
  };
  return { track };
} 