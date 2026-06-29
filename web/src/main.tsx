import React from "react";
import ReactDOM from "react-dom/client";
import App, { ErrorBoundary } from "./App";
import "./index.css";
import { I18nProvider } from "./i18n";
import { applyLocale, loadLocale } from "./localeSettings";
import { applyTheme, loadTheme, saveTheme } from "./themeSettings";

const theme = loadTheme();
applyTheme(theme);
saveTheme(theme);
applyLocale(loadLocale());

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <I18nProvider>
        <App />
      </I18nProvider>
    </ErrorBoundary>
  </React.StrictMode>
);
