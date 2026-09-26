import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { apiClient, refreshCsrf } from '../api/client';
import type { components } from '../api/schema';

export type UserMe = components['schemas']['UserMe'];

interface AuthContextType {
  user: UserMe | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  hasCapability: (capability: string) => boolean;
  login: (username: string, password: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  refetchUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserMe | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCurrentUser = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { data, error: apiError, response } = await apiClient.GET('/api/v1/me/');
      if (response.status === 200 && data) {
        setUser(data);
      } else if (response.status === 401 || response.status === 403) {
        setUser(null);
      } else if (apiError) {
        setUser(null);
        setError('Failed to authenticate session.');
      }
    } catch (err) {
      setUser(null);
      setError(err instanceof Error ? err.message : 'Network error during session fetch.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCurrentUser();
  }, [fetchCurrentUser]);

  const hasCapability = useCallback(
    (capability: string): boolean => {
      if (!user || !user.capabilities) return false;
      return user.capabilities.includes(capability);
    },
    [user]
  );

  const login = useCallback(
    async (username: string, password: string): Promise<{ success: boolean; error?: string }> => {
      setIsLoading(true);
      setError(null);
      try {
        // Ensure fresh CSRF token before post
        await refreshCsrf();
        const { data, error: loginError, response } = await apiClient.POST('/api/v1/auth/login/', {
          body: { username, password },
        });

        if (response.status === 200 && data) {
          // Immediately fetch active user profile
          await fetchCurrentUser();
          return { success: true };
        } else {
          const errObj = loginError as unknown as { detail?: string; error?: string } | undefined;
          const errMsg =
            errObj?.detail ||
            errObj?.error ||
            'Invalid credentials or login failed.';
          setError(errMsg);
          return { success: false, error: errMsg };
        }
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : 'Login network failure.';
        setError(errMsg);
        return { success: false, error: errMsg };
      } finally {
        setIsLoading(false);
      }
    },
    [fetchCurrentUser]
  );

  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      await refreshCsrf();
      await apiClient.POST('/api/v1/auth/logout/');
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      setUser(null);
      setIsLoading(false);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        error,
        hasCapability,
        login,
        logout,
        refetchUser: fetchCurrentUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
