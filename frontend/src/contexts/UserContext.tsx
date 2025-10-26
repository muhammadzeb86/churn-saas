import React, { createContext, useContext, useState, useEffect } from 'react';
import { useUser } from '@clerk/clerk-react';
import { authAPI } from '../services/api';

interface DBUser {
  id: number;
  email: string;
  full_name: string;
  clerk_user_id: string;
}

interface UserContextType {
  dbUser: DBUser | null;
  setDBUser: React.Dispatch<React.SetStateAction<DBUser | null>>;
  isLoading: boolean;
  error: string | null;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export const UserProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, isLoaded, isSignedIn } = useUser();
  const [dbUser, setDBUser] = useState<DBUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const syncUser = async () => {
      if (!isLoaded || !isSignedIn || !user) {
        setIsLoading(false);
        return;
      }

      try {
        // JWT token is automatically sent via interceptor
        // Backend extracts user data from token
        const response = await authAPI.syncUser();

        setDBUser(response.data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to sync user');
        console.error('Error syncing user:', err);
      } finally {
        setIsLoading(false);
      }
    };

    syncUser();
  }, [isLoaded, isSignedIn, user]);

  return (
    <UserContext.Provider value={{ dbUser, setDBUser, isLoading, error }}>
      {children}
    </UserContext.Provider>
  );
};

export const useUserContext = () => {
  const context = useContext(UserContext);
  if (context === undefined) {
    throw new Error('useUserContext must be used within a UserProvider');
  }
  return context;
}; 