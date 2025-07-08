# Analytics Setup Guide

## Environment Variables

Create a `.env.local` file in the root directory:

```bash
# Google Analytics 4 Measurement ID (format: G-XXXXXXXX)
NEXT_PUBLIC_GA4_ID=G-XXXXXXXX

# Meta (Facebook) Pixel ID
NEXT_PUBLIC_FB_PIXEL_ID=123456789012345

# Backend API URL
NEXT_PUBLIC_BACKEND_URL=https://your-backend-domain.com
```

## Testing Instructions

1. **Set up environment variables** in `.env.local`
2. **Run development server**: `npm run dev`
3. **Open browser dev tools** > Network tab
4. **Check for requests** to:
   - `googletagmanager.com` (GA4)
   - `facebook.com` (Meta Pixel)
5. **Use browser extensions**:
   - Google Analytics Debugger
   - Facebook Pixel Helper
6. **Test events in console**:
   ```javascript
   // GA4
   window.gtag('event', 'test_event', {test: true})
   
   // Meta Pixel
   window.fbq('track', 'test_event', {test: true})
   ```

## Usage Examples

```typescript
import { useAnalytics } from './hooks/useAnalytics';

function MyComponent() {
  const { trackEvent, trackPageView } = useAnalytics();
  
  // Track custom event
  trackEvent('button_click', {
    button_name: 'cta_button',
    location: 'hero_section'
  });
  
  // Track page view
  trackPageView('/new-page');
}
```

## File Structure

- `src/app/layout.tsx` - Main layout with analytics scripts
- `src/app/components/AnalyticsScripts.tsx` - Analytics script loader
- `src/app/hooks/useAnalytics.ts` - Analytics hook and helpers 