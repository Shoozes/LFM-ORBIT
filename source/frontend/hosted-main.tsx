import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";

const HostedDemo = lazy(() => import("./hosted/HostedDemo.tsx"));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Suspense fallback={<div className="app-route-loading">Loading Orbit presentation...</div>}>
      <HostedDemo />
    </Suspense>
  </StrictMode>,
);
