import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { ActivityIndicator, View, StyleSheet } from 'react-native';
import { Colors } from '../theme';
import { loadConfig, setToken, setBaseUrl, getBaseUrl, getToken, login as apiLogin } from '../api/client';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  serverUrl: string;
  login: (sub?: string) => Promise<void>;
  logout: () => Promise<void>;
  updateServerUrl: (url: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  isAuthenticated: false,
  isLoading: true,
  serverUrl: '',
  login: async () => {},
  logout: async () => {},
  updateServerUrl: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [serverUrl, setServerUrl] = useState('');

  useEffect(() => {
    (async () => {
      await loadConfig();
      setServerUrl(getBaseUrl());
      setIsAuthenticated(!!getToken());
      setIsLoading(false);
    })();
  }, []);

  const login = useCallback(async (sub = 'mobile') => {
    const token = await apiLogin(sub);
    await setToken(token);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(async () => {
    await setToken(null);
    setIsAuthenticated(false);
  }, []);

  const updateServerUrl = useCallback(async (url: string) => {
    await setBaseUrl(url);
    setServerUrl(url);
  }, []);

  if (isLoading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
      </View>
    );
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, serverUrl, login, logout, updateServerUrl }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: Colors.light.background,
  },
});
