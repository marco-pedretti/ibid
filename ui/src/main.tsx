import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "./index.css";

const radice = document.getElementById("root");
if (!radice) throw new Error("manca #root in index.html");

createRoot(radice).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
