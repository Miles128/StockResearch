import React from "react";
import ReactDOM from "react-dom/client";
import App, { ErrorBoundary } from "./App";
import "./index.css";
import { I18nProvider } from "./i18n";
import { applyLocale, loadLocale } from "./localeSettings";
import { applyTheme, loadTheme } from "./themeSettings";

applyTheme(loadTheme());
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
