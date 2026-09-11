"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

export type RolGestio = "BOSS" | "ENGINYER" | "SECRETARIA";

interface GestioContextType {
  rolActiu: RolGestio;
  setRolActiu: (rol: RolGestio) => void;
  spotlightObert: boolean;
  setSpotlightObert: (obert: boolean) => void;
  isDark: boolean;
  toggleTheme: () => void;
}

const GestioContext = createContext<GestioContextType>({
  rolActiu: "BOSS",
  setRolActiu: () => {},
  spotlightObert: false,
  setSpotlightObert: () => {},
  isDark: false,
  toggleTheme: () => {},
});

export function GestioProvider({ children }: { children: React.ReactNode }) {
  const [rolActiu, setRolActiu] = useState<RolGestio>("BOSS");
  const [spotlightObert, setSpotlightObert] = useState<boolean>(false);
  const [isDark, setIsDark] = useState<boolean>(false);

  useEffect(() => {
    const savedTheme = localStorage.getItem("sevalor_theme");
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (savedTheme === "dark" || (!savedTheme && prefersDark)) {
      setIsDark(true);
      document.documentElement.classList.add("dark");
    } else {
      setIsDark(false);
      document.documentElement.classList.remove("dark");
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSpotlightObert((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const toggleTheme = () => {
    if (isDark) {
      document.documentElement.classList.remove("dark");
      localStorage.setItem("sevalor_theme", "light");
      setIsDark(false);
    } else {
      document.documentElement.classList.add("dark");
      localStorage.setItem("sevalor_theme", "dark");
      setIsDark(true);
    }
  };

  return (
    <GestioContext.Provider
      value={{
        rolActiu,
        setRolActiu,
        spotlightObert,
        setSpotlightObert,
        isDark,
        toggleTheme,
      }}
    >
      {children}
    </GestioContext.Provider>
  );
}

export function useGestio() {
  return useContext(GestioContext);
}
