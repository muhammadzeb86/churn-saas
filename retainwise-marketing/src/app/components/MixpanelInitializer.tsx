'use client';

import { useEffect } from 'react';
import mixpanel from '../../lib/mixpanel';

export default function MixpanelInitializer() {
  useEffect(() => {
    // Track app loaded event
    if (typeof window !== "undefined" && mixpanel) {
      try {
        mixpanel.track("App Loaded", {
          page: window.location.pathname,
          timestamp: new Date().toISOString(),
        });
      } catch (error) {
        console.warn('Mixpanel initialization failed:', error);
      }
    }
  }, []);

  return null; // This component doesn't render anything
} 