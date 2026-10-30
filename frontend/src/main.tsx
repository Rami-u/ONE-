import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./index.css";

// BrowserRouter: paths like /signup, /login, /teacher/login resolve per host
// (the main domain or a teacher sub-domain — see src/lib/slug.ts). In
// production the reverse proxy serves this SPA at "/" on every host.
import { BrowserRouter } from "react-router-dom";

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
