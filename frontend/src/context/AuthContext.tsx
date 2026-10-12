import React, { createContext, useContext, useState, useEffect } from 'react';
import { UserProfile, AuthResponseData } from '../types';
import {
  loginUser,
  registerUser,
  logoutUser,
  LoginPayload,
  RegisterPayload
} from '../services/api';

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<AuthResponseData>;
  register: (payload: RegisterPayload) => Promise<AuthResponseData>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(() => {
    try {
      const raw = localStorage.getItem('equifolio_user');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshUser = async () => {
    try {
      const res = await fetch('/api/v1/auth/me', {
        credentials: 'include'
      });
      if (res.ok) {
        const json = await res.json();
        if (json.data) {
          const profile: UserProfile = {
            id: json.data.id,
            username: json.data.username,
            email: json.data.email,
            riskScore: json.data.riskScore,
            riskAversionLambda: json.data.riskAversionLambda || 5.0,
            riskProfile: json.data.riskProfile || 'BALANCED'
          };
          setUser(profile);
          try {
            localStorage.setItem('equifolio_user', JSON.stringify(profile));
          } catch {}
          return;
        }
      }
      // Phiên đăng nhập cookie không tồn tại hoặc đã hết hạn
      if (res.status === 401) {
        setUser(null);
        localStorage.removeItem('equifolio_user');
      }
    } catch (e) {
      console.warn("Failed to load user profile via cookie session", e);
    }
  };

  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      await refreshUser();
      setIsLoading(false);
    };
    initAuth();
  }, []);

  const login = async (payload: LoginPayload) => {
    const data = await loginUser(payload);
    const profile: UserProfile = {
      id: data.id,
      username: data.username,
      email: data.email,
      riskScore: data.riskScore,
      riskAversionLambda: Number((10 - (0.09 * (data.riskScore || 50))).toFixed(2)),
      riskProfile: data.riskProfile
    };
    setUser(profile);
    return data;
  };

  const register = async (payload: RegisterPayload) => {
    const data = await registerUser(payload);
    const profile: UserProfile = {
      id: data.id,
      username: data.username,
      email: data.email,
      riskScore: data.riskScore,
      riskAversionLambda: Number((10 - (0.09 * (data.riskScore || 50))).toFixed(2)),
      riskProfile: data.riskProfile
    };
    setUser(profile);
    return data;
  };

  const logout = async () => {
    await logoutUser();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token: user ? 'cookie-session' : null,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        refreshUser
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
