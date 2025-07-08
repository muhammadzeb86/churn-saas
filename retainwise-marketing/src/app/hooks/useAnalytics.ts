'use client';

import { useCallback } from 'react';

// Type declarations for global analytics functions
declare global {
  interface Window {
    gtag?: (command: string, eventName: string, parameters?: Record<string, unknown>) => void;
    fbq?: (command: string, eventName: string, parameters?: Record<string, unknown>) => void;
    dataLayer?: unknown[];
  }
}

export const useAnalytics = () => {
  const trackEvent = useCallback((
    eventName: string, 
    parameters: Record<string, unknown> = {},
    platforms: ('ga4' | 'fb')[] = ['ga4', 'fb']
  ) => {
    try {
      // Google Analytics 4
      if (platforms.includes('ga4') && typeof window !== 'undefined' && window.gtag) {
        window.gtag('event', eventName, {
          ...parameters,
          timestamp: new Date().toISOString(),
        });
      }
      
      // Meta Pixel
      if (platforms.includes('fb') && typeof window !== 'undefined' && window.fbq) {
        window.fbq('track', eventName, {
          ...parameters,
          timestamp: new Date().toISOString(),
        });
      }
    } catch (err) {
      // Silently fail - analytics should never break the app
      console.warn('Analytics tracking failed:', err);
    }
  }, []);

  const trackPageView = useCallback((url?: string) => {
    try {
      // GA4 page view
      if (typeof window !== 'undefined' && window.gtag && process.env.NEXT_PUBLIC_GA4_ID) {
        window.gtag('config', process.env.NEXT_PUBLIC_GA4_ID, {
          page_path: url || window.location.pathname,
          page_title: document.title,
        });
      }
      
      // FB Pixel page view
      if (typeof window !== 'undefined' && window.fbq) {
        window.fbq('track', 'PageView');
      }
    } catch (err) {
      console.warn('Page view tracking failed:', err);
    }
  }, []);

  const trackConversion = useCallback((value?: number, currency: string = 'USD') => {
    try {
      // GA4 conversion
      if (typeof window !== 'undefined' && window.gtag) {
        window.gtag('event', 'conversion', {
          send_to: `${process.env.NEXT_PUBLIC_GA4_ID}/AW-CONVERSION_ID`,
          value: value,
          currency: currency,
        });
      }
      
      // FB Pixel conversion
      if (typeof window !== 'undefined' && window.fbq) {
        window.fbq('track', 'Purchase', {
          value: value,
          currency: currency,
        });
      }
    } catch (err) {
      console.warn('Conversion tracking failed:', err);
    }
  }, []);

  return {
    trackEvent,
    trackPageView,
    trackConversion,
  };
};

// Helper function for common events - moved outside to avoid hooks rules violation
export const trackWaitlistSignup = (emailDomain: string, source: string = 'landing_page') => {
  try {
    // Google Analytics 4
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('event', 'waitlist_signup', {
        email_domain: emailDomain,
        source: source,
        timestamp: new Date().toISOString(),
      });
    }
    
    // Meta Pixel
    if (typeof window !== 'undefined' && window.fbq) {
      window.fbq('track', 'waitlist_signup', {
        email_domain: emailDomain,
        source: source,
        timestamp: new Date().toISOString(),
      });
    }
  } catch (err) {
    console.warn('Waitlist signup tracking failed:', err);
  }
};

export const trackButtonClick = (buttonName: string, location: string) => {
  try {
    // Google Analytics 4
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('event', 'button_click', {
        button_name: buttonName,
        location: location,
        timestamp: new Date().toISOString(),
      });
    }
    
    // Meta Pixel
    if (typeof window !== 'undefined' && window.fbq) {
      window.fbq('track', 'button_click', {
        button_name: buttonName,
        location: location,
        timestamp: new Date().toISOString(),
      });
    }
  } catch (err) {
    console.warn('Button click tracking failed:', err);
  }
}; 