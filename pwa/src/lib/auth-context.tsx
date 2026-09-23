"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { getAuthToken, clearAuthToken } from "./api";

export type RolUsuari = "SUPERADMIN" | "BOSS" | "ENGINYER" | "SECRETARIA" | "OPERARI";

export interface Usuari {
  id: string;
  email: string;
  nif?: string;
  nom: string;
  cognoms: string;
  rol: RolUsuari;
  tenant_id: string;
  tenant_nom?: string;
}

interface AuthContextType {
  usuari: Usuari | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (userData: Usuari, token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  usuari: null,
  isAuthenticated: false,
  isLoading: true,
  login: () => {},
  logout: () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [usuari, setUsuari] = useState<Usuari | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check local storage for user data
    const token = getAuthToken();
    const userDataStr = localStorage.getItem("sevalor_user");
    
    if (token && userDataStr) {
      try {
        const parsedUser = JSON.parse(userDataStr);
        setUsuari(parsedUser.user || parsedUser);
      } catch (e) {
        console.error("Error parsing user data", e);
        clearAuthToken();
        localStorage.removeItem("sevalor_user");
      }
    }
    setIsLoading(false);
  }, []);

  const login = (userData: Usuari, token: string) => {
    setUsuari(userData);
    // Token is handled by api.ts / login components, but we trigger re-render
  };

  const logout = () => {
    setUsuari(null);
    clearAuthToken();
    localStorage.removeItem("sevalor_user");
    document.cookie = "sevalor_access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    window.location.href = "/";
  };

  return (
    <AuthContext.Provider value={{ usuari, isAuthenticated: !!usuari, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
