"use client";

import { useEffect, useState } from "react";

type Theme = "dark" | "light";
const STORAGE_KEY = "admin-theme";

function applyTheme(theme: Theme) {
  // Dark is the implicit default (see .admin-theme in globals.css), so only
  // "light" needs an explicit attribute — keeps the no-JS/first-paint state
  // identical to the dark-theme default.
  if (theme === "light") {
    document.documentElement.setAttribute("data-theme", "light");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

/**
 * Light/dark switch for the internal ops dashboard (app/(admin)/) only — the
 * public site has no dark mode. Preference persists in localStorage; the
 * blocking script in app/layout.tsx applies it before first paint so there's
 * no flash of the wrong theme.
 */
export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    setTheme(stored === "light" ? "light" : "dark");
    setMounted(true);
  }, []);

  function choose(next: Theme) {
    setTheme(next);
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  // Avoid rendering a guess before we've read localStorage — the blocking
  // script already set the real theme on <html>, this just keeps the
  // toggle's own highlighted state from flashing the wrong side.
  if (!mounted) return <div className="theme-toggle" aria-hidden style={{ visibility: "hidden" }} />;

  return (
    <div className="theme-toggle" role="radiogroup" aria-label="Dashboard theme">
      <button
        type="button"
        className={theme === "dark" ? "active" : undefined}
        aria-pressed={theme === "dark"}
        onClick={() => choose("dark")}
      >
        🌙 Dark
      </button>
      <button
        type="button"
        className={theme === "light" ? "active" : undefined}
        aria-pressed={theme === "light"}
        onClick={() => choose("light")}
      >
        ☀️ Light
      </button>
    </div>
  );
}
