import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import { IS_HOSTED_BUILD } from "./hosted/hostedConfig";

const FullDemo = IS_HOSTED_BUILD ? null : lazy(() => import("./App.tsx"));
const HostedDemo = lazy(() => import("./hosted/HostedDemo.tsx"));

function isHostedDemoRoute(): boolean {
  if (typeof window === "undefined") return false;
  if (IS_HOSTED_BUILD) return true;
  const path = window.location.pathname.replace(/\/+$/, "") || "/";
  const params = new URLSearchParams(window.location.search);
  return path === "/hosted" || params.get("presentation") === "hosted";
}

function AppSurface() {
  const hosted = isHostedDemoRoute();
  return (
    <Suspense fallback={<div className="app-route-loading">Loading Orbit presentation...</div>}>
      {hosted || !FullDemo ? <HostedDemo /> : <FullDemo />}
    </Suspense>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppSurface />
  </StrictMode>
);
