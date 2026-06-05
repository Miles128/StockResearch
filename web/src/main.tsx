import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import { I18nProvider } from "./i18n";
import { applyLocale, loadLocale } from "./localeSettings";
import { applyTheme, loadTheme } from "./themeSettings";

applyTheme(loadTheme());
applyLocale(loadLocale());

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <I18nProvider>
      <App />
    </I18nProvider>
  </React.StrictMode>
);
