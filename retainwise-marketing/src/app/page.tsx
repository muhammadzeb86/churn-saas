'use client';

import { useState, useEffect } from 'react';

// Type declarations for global analytics functions
declare global {
  interface Window {
    gtag?: (command: string, eventName: string, parameters?: Record<string, unknown>) => void;
    fbq?: (command: string, eventName: string, parameters?: Record<string, unknown>) => void;
    lintrk?: (command: string, parameters?: Record<string, unknown>) => void;
  }
}

export default function Home() {
  const [email, setEmail] = useState('');
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [validationError, setValidationError] = useState('');

  // Analytics helper functions
  const trackEvent = (eventName: string, parameters: Record<string, unknown> = {}) => {
    // Non-blocking analytics calls
    try {
      // Google Analytics 4
      if (typeof window !== 'undefined' && window.gtag) {
        window.gtag('event', eventName, {
          ...parameters,
          timestamp: new Date().toISOString(),
        });
      }
      
      // Meta Pixel
      if (typeof window !== 'undefined' && window.fbq) {
        window.fbq('track', eventName, {
          ...parameters,
          timestamp: new Date().toISOString(),
        });
      }
      
      // Optional: LinkedIn Insight Tag (for future B2B campaigns)
      // if (typeof window !== 'undefined' && window.lintrk) {
      //   window.lintrk('track', { conversion_id: 'YOUR_CONVERSION_ID' });
      // }
    } catch (err) {
      // Silently fail - analytics should never break the app
      console.warn('Analytics tracking failed:', err);
    }
  };

  // Track form view on component mount
  useEffect(() => {
    trackEvent('waitlist_form_viewed', {
      page_location: window.location.href,
      page_title: document.title,
    });
  }, []);

  // Email validation regex
  const validateEmail = (email: string): boolean => {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  };

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newEmail = e.target.value;
    setEmail(newEmail);
    
    // Clear validation error when user starts typing
    if (validationError) {
      setValidationError('');
    }
    
    // Clear submission error when user starts typing
    if (error) {
      setError('');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Clear previous errors
    setError('');
    setValidationError('');
    
    // Validate email
    if (!email.trim()) {
      setValidationError('Email address is required');
      trackEvent('waitlist_form_error', {
        error_type: 'validation',
        error_message: 'Email address is required',
        email_domain: email.includes('@') ? email.split('@')[1] : null,
      });
      return;
    }
    
    if (!validateEmail(email.trim())) {
      setValidationError('Please enter a valid email address');
      trackEvent('waitlist_form_error', {
        error_type: 'validation',
        error_message: 'Invalid email format',
        email_domain: email.includes('@') ? email.split('@')[1] : null,
      });
      return;
    }
    
    // Track form submission
    trackEvent('waitlist_form_submitted', {
      email_domain: email.trim().split('@')[1],
      form_location: 'hero_section',
    });
    
    setIsLoading(true);
    
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
      
      const response = await fetch(`${backendUrl}/api/waitlist`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: email.trim() }),
      });
      
      const data = await response.json();
      
      if (response.ok && data.success) {
        setIsSubmitted(true);
        setEmail('');
        setError('');
        setValidationError('');
        
        // Track successful submission
        trackEvent('waitlist_form_success', {
          email_domain: email.trim().split('@')[1],
          response_message: data.message,
          form_location: 'hero_section',
        });
      } else {
        setError(data.error || 'Failed to join waitlist. Please try again.');
        
        // Track API error
        trackEvent('waitlist_form_error', {
          error_type: 'api',
          error_message: data.error || 'Unknown API error',
          email_domain: email.trim().split('@')[1],
          response_status: response.status,
        });
      }
    } catch (err) {
      console.error('Waitlist submission error:', err);
      setError('Network error. Please check your connection and try again.');
      
      // Track network error
      trackEvent('waitlist_form_error', {
        error_type: 'network',
        error_message: 'Network connection failed',
        email_domain: email.trim().split('@')[1],
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
      {/* Hero CTA Section */}
      <section className="relative overflow-hidden">
        {/* Background Pattern */}
        <div className="absolute inset-0 bg-gradient-to-r from-blue-600/10 to-indigo-600/10"></div>
        <div className="absolute inset-0 opacity-30" style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%239C92AC' fill-opacity='0.05'%3E%3Ccircle cx='30' cy='30' r='2'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`
        }}></div>
        
        <div className="relative z-10 px-4 py-20 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-4xl text-center">
            {/* Main Headline */}
            <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-gray-900 mb-6 leading-tight">
              Predict and{' '}
              <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                never lose
              </span>{' '}
              another valued customer again
            </h1>
            
            {/* Subheading */}
            <p className="text-xl md:text-2xl text-gray-600 mb-12 leading-relaxed max-w-3xl mx-auto">
              Get early access and join the businesses already staying one step ahead of customer churn.
            </p>
            
            {/* CTA Button and Email Form */}
            <div className="space-y-6">
              {/* Primary CTA Button */}
              <button 
                onClick={() => document.getElementById('email-input')?.focus()}
                className="inline-flex items-center px-8 py-4 text-xl font-bold text-white bg-gradient-to-r from-blue-600 to-indigo-600 rounded-xl shadow-2xl hover:shadow-3xl transform hover:scale-105 transition-all duration-300 hover:from-blue-700 hover:to-indigo-700"
                aria-label="Focus on email input field"
              >
                Join Waitlist
                <svg className="ml-2 w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </button>
              
              {/* Email Input Form */}
              <form onSubmit={handleSubmit} className="max-w-md mx-auto" noValidate>
                <div className="flex flex-col sm:flex-row gap-3">
                  <div className="flex-1">
                    <label htmlFor="email-input" className="sr-only">
                      Email address
                    </label>
                    <input
                      id="email-input"
                      type="email"
                      value={email}
                      onChange={handleEmailChange}
                      placeholder="Enter your email address"
                      className={`w-full px-6 py-4 text-lg border-2 rounded-xl focus:ring-4 focus:ring-blue-200 outline-none transition-all duration-200 ${
                        validationError 
                          ? 'border-red-300 focus:border-red-500 focus:ring-red-200' 
                          : 'border-gray-200 focus:border-blue-500'
                      }`}
                      required
                      disabled={isLoading}
                      aria-describedby={validationError ? 'email-error' : undefined}
                      aria-invalid={!!validationError}
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={isLoading || !email.trim()}
                    className="px-8 py-4 bg-gray-900 text-white font-semibold rounded-xl hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 shadow-lg hover:shadow-xl min-w-[120px] focus:outline-none focus:ring-4 focus:ring-gray-300"
                    aria-label={isLoading ? 'Submitting email to waitlist' : 'Submit email to join waitlist'}
                  >
                    {isLoading ? (
                      <div className="flex items-center justify-center">
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white mr-2" aria-hidden="true"></div>
                        <span>Joining...</span>
                      </div>
                    ) : (
                      'Submit'
                    )}
                  </button>
                </div>
                
                {/* Validation Error Message */}
                {validationError && (
                  <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg" role="alert">
                    <p className="text-red-800 text-sm font-medium" id="email-error">
                      ❌ {validationError}
                    </p>
                  </div>
                )}
                
                {/* API Error Message */}
                {error && (
                  <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg" role="alert">
                    <p className="text-red-800 text-sm font-medium">
                      ❌ {error}
                    </p>
                  </div>
                )}
                
                {/* Success Message */}
                {isSubmitted && (
                  <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-lg" role="alert">
                    <p className="text-green-800 text-sm font-medium">
                      🎉 Thanks! You&apos;ve been added to our waitlist. We&apos;ll notify you when we launch!
                    </p>
                  </div>
                )}
              </form>
            </div>
            
            {/* Trust Indicators */}
            <div className="mt-16 pt-8 border-t border-gray-200">
              <p className="text-sm text-gray-500 mb-4">Trusted by forward-thinking businesses</p>
              <div className="flex justify-center items-center space-x-8 opacity-60">
                <div className="text-gray-400 font-semibold">AI-Powered</div>
                <div className="text-gray-400 font-semibold">Real-time Analytics</div>
                <div className="text-gray-400 font-semibold">Predictive Insights</div>
              </div>
            </div>
          </div>
        </div>
      </section>
      
      {/* Existing App Login Link - Moved to bottom */}
      <section className="py-12 bg-white/50">
        <div className="text-center">
          <p className="text-gray-600 mb-4">Already have access?</p>
          <a
            href="https://app.retainwiseanalytics.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center px-6 py-3 text-lg font-semibold text-indigo-600 bg-white border-2 border-indigo-200 rounded-lg hover:bg-indigo-50 hover:border-indigo-300 transition-all duration-200 shadow-sm hover:shadow-md"
          >
            Go to App Login
            <svg className="ml-2 w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
        </div>
      </section>
    </div>
  );
}
