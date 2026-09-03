"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider({
  children,
  ...props
}: React.ComponentProps<typeof NextThemesProvider>) {
  // P0-2A: route-based forced theming was removed. The workbench palette is
  // now the app-wide default, and the landing page scopes its own dark look
  // via a local `.dark` wrapper instead of hijacking the global theme.
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
