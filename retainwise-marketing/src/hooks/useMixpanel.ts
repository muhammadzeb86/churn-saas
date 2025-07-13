// src/hooks/useMixpanel.ts
"use client";
import mixpanel from "../lib/mixpanel";

export function useMixpanel() {
  const track = (event: string, properties?: Record<string, unknown>) => {
    mixpanel.track(event, properties);
  };
  return { track };
} 