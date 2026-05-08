import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";

// Suppress Chrome extension errors from polluting the CRA error overlay
const _origError = window.onerror;
window.onerror = (msg, src, ...rest) => {
  if (typeof src === "string" && src.startsWith("chrome-extension://")) return true;
  return _origError ? (_origError as Function)(msg, src, ...rest) : false;
};

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
