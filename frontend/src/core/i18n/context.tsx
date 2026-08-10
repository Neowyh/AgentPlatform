"use client";

import {
  createContext,
  useContext,
  useLayoutEffect,
  useState,
  type ReactNode,
} from "react";

import { getLocaleFromCookie, setLocaleInCookie } from "./cookies";
import { normalizeLocale, type Locale } from "./locale";

export interface I18nContextType {
  locale: Locale;
  setLocale: (locale: Locale) => void;
}

export const I18nContext = createContext<I18nContextType | null>(null);

export function I18nProvider({
  children,
  initialLocale,
}: {
  children: ReactNode;
  initialLocale: Locale;
}) {
  const [locale, setLocale] = useState<Locale>(initialLocale);

  useLayoutEffect(() => {
    const savedLocale = getLocaleFromCookie();
    if (savedLocale && savedLocale !== normalizeLocale(savedLocale)) {
      setLocaleInCookie(normalizeLocale(savedLocale));
    }
  }, [initialLocale]);

  const handleSetLocale = (newLocale: Locale) => {
    setLocale(newLocale);
    document.cookie = `locale=${newLocale}; path=/; max-age=31536000`;
  };

  return (
    <I18nContext.Provider value={{ locale, setLocale: handleSetLocale }}>
      {children}
    </I18nContext.Provider>
  );
}

export function useI18nContext() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return context;
}
