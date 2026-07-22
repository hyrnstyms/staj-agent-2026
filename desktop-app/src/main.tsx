// src/main.tsx
// React uygulama giriş noktası

import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/index.css";

// Eski App.css'i temizle — tasarım sistemi index.css'de
ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
