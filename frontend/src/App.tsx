import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ClerkProvider, SignIn, SignUp, useAuth } from '@clerk/clerk-react';
import { UserProvider } from './contexts/UserContext';
import Layout from './components/layout/Layout';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import Predictions from './pages/Predictions';
import ProtectedRoute from './components/auth/ProtectedRoute';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import './index.css';

const LoadingScreen = () => (
  <div className="min-h-screen flex items-center justify-center bg-gray-50">
    <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-primary-600"></div>
  </div>
);

const App: React.FC = () => {
  const clerkKey = process.env.REACT_APP_CLERK_PUBLISHABLE_KEY!;

  if (!clerkKey) {
    console.error('Missing Clerk Publishable Key');
    return <div>Configuration Error</div>;
  }

  return (
    <ClerkProvider
      publishableKey={clerkKey}
    >
      <UserProvider>
        <Router>
          <AppRoutes />
        </Router>
      </UserProvider>
    </ClerkProvider>
  );
};

const AppRoutes: React.FC = () => {
  const { isLoaded, isSignedIn } = useAuth();

  // Show loading screen while Clerk loads
  if (!isLoaded) {
    return <LoadingScreen />;
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={
          isSignedIn ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
              <SignIn routing="path" path="/login" fallbackRedirectUrl="/dashboard" forceRedirectUrl="/dashboard" />
            </div>
          )
        }
      />
      <Route
        path="/login/*"
        element={
          isSignedIn ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
              <SignIn
                routing="path"
                path="/login"
                fallbackRedirectUrl="/dashboard"
                forceRedirectUrl="/dashboard"
              />
            </div>
          )
        }
      />
      <Route
        path="/signup"
        element={
          isSignedIn ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
              <SignUp routing="path" path="/signup" fallbackRedirectUrl="/dashboard" forceRedirectUrl="/dashboard" />
            </div>
          )
        }
      />
      <Route
        path="/signup/*"
        element={
          isSignedIn ? (
            <Navigate to="/dashboard" replace />
          ) : (
            <div className="min-h-screen flex items-center justify-center bg-gray-50">
              <SignUp
                routing="path"
                path="/signup"
                fallbackRedirectUrl="/dashboard"
                forceRedirectUrl="/dashboard"
              />
            </div>
          )
        }
      />
      
      {/* Protected Routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Layout>
              <Dashboard />
            </Layout>
          </ProtectedRoute>
        }
      />
      
      <Route
        path="/upload"
        element={
          <ProtectedRoute>
            <Layout>
              <Upload />
            </Layout>
          </ProtectedRoute>
        }
      />
      
      <Route
        path="/predictions"
        element={
          <ProtectedRoute>
            <Layout>
              <Predictions />
            </Layout>
          </ProtectedRoute>
        }
      />
      
      {/* Redirect root to dashboard */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      
      {/* Catch all route */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

export default App;
