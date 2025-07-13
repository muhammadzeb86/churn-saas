'use client';

import { useEffect } from 'react';
import mixpanel from '../../lib/mixpanel';

export default function MixpanelInitializer() {
  useEffect(() => {
    // Track app loaded event
    mixpanel.track("App Loaded", {
      page: window.location.pathname,
      timestamp: new Date().toISOString(),
    });
  }, []);

  return null; // This component doesn't render anything
} 