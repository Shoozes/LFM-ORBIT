import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import TerrainShaderCanvas from "./TerrainShaderCanvas";
import { loadDemoPackages, packageContext, SYSTEM_PROMPT } from "./demoPackages";
import type { DemoPackage } from "./demoPackages";
import { HOSTED_ROUTE, IS_HOSTED_BUILD, resolveHostedAsset } from "./hostedConfig";
import type { BrowserModelController } from "./useBrowserModel";
import { isBrowserModelAbortError } from "./modelState";
import "./hosted.css";

type ChatLine = {
  role: "user" | "assistant";
  text: string;
};

type HostedEvidenceDemoProps = {
  model?: BrowserModelController;
};

function statusCopy(status: BrowserModelController["status"]): string {
  if (status === "loading") return "Fetching and loading in this browser";
  if (status === "ready") return "Model loaded locally in this browser";
  if (status === "generating") return "Orbit Classroom is thinking locally";
  if (status === "error") return "Browser model needs attention";
  return "Ready to fetch the browser model";
}

function modelStatusCopy(model: BrowserModelController): string {
  if (!model.modelEnabled) return "Browser inference unavailable in this build; saved packages remain available";
  return statusCopy(model.status);
}

function capabilityCopy(capability: BrowserModelController["capability"]): string {
  if (!capability) return "Checking WebAssembly, storage, and device capability";
  return capability.message;
}

function GuidedPath() {
  return (
    <div className="hosted-guided-path" data-testid="hosted-guided-path" aria-label="Saved evidence guided path">
      <span><strong>01</strong><small>Select evidence</small></span>
      <span><strong>02</strong><small>Inspect provenance</small></span>
      <span><strong>03</strong><small>Compare retention</small></span>
      <span><strong>04</strong><small>Read the lesson</small></span>
    </div>
  );
}

export default function HostedEvidenceDemo({ model }: HostedEvidenceDemoProps) {
  const modelAvailable = model?.modelEnabled === true;
  const [packages, setPackages] = useState<readonly DemoPackage[] | null>(null);
  const [packageError, setPackageError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [chat, setChat] = useState<ChatLine[]>([]);
  const [shaderStatus, setShaderStatus] = useState("Starting WebGL terrain");
  const [showLesson, setShowLesson] = useState(false);
  const requestVersionRef = useRef(0);

  const selectedPackage = useMemo(
    () => packages?.find((item) => item.id === selectedId) ?? packages?.[0],
    [packages, selectedId],
  );
  const onShaderStatus = useCallback((status: string) => setShaderStatus(status), []);
  const startModelFetch = useCallback(() => {
    if (!modelAvailable || !model) return;
    if (model.manifestStatus === "error") {
      model.retryManifest();
    } else if (model.manifestStatus === "ready") {
      void model.load();
    }
    document.getElementById("model")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [model, modelAvailable]);

  useEffect(() => {
    const controller = new AbortController();
    void loadDemoPackages(controller.signal)
      .then((loadedPackages) => {
        setPackages(loadedPackages);
        setSelectedId((current) => current ?? loadedPackages[0]?.id ?? null);
      })
      .catch((loadError: unknown) => {
        if (controller.signal.aborted) return;
        setPackageError(loadError instanceof Error ? loadError.message : String(loadError));
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    requestVersionRef.current += 1;
    setChat([]);
    setQuestion("");
    return () => model?.cancelGeneration();
  }, [model?.cancelGeneration, selectedPackage?.id]);

  useEffect(() => {
    document.title = "LFM Orbit · Hosted Edge AI Demo";
    return () => {
      document.title = "LFM Orbit";
    };
  }, []);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanQuestion = question.trim();
    if (!modelAvailable || !model || !cleanQuestion || model.status !== "ready" || !selectedPackage) return;
    setQuestion("");
    const requestVersion = ++requestVersionRef.current;
    const nextChat = [...chat, { role: "user" as const, text: cleanQuestion }];
    setChat(nextChat);
    try {
      const answer = await model.chat([
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: packageContext(selectedPackage) },
        ...chat.slice(-6).map((line) => ({ role: line.role, content: line.text })),
        { role: "user", content: cleanQuestion },
      ]);
      if (requestVersion !== requestVersionRef.current) return;
      setChat((current) => [...current, { role: "assistant", text: answer }]);
    } catch (chatError: unknown) {
      if (requestVersion !== requestVersionRef.current) return;
      if (isBrowserModelAbortError(chatError)) return;
      setChat((current) => [
        ...current,
        { role: "assistant", text: "I could not complete that local response. Check the model status above and retry." },
      ]);
    }
  }

  return (
    <main className="hosted-shell">
      <section className="hosted-hero">
        <TerrainShaderCanvas onStatus={onShaderStatus} />
        <div className="hosted-hero-wash" />
        <nav className="hosted-nav" aria-label="Hosted demo navigation">
          <a className="hosted-wordmark" href={HOSTED_ROUTE} aria-label="Orbit hosted demo home">
            <span className="hosted-wordmark-mark">O</span>
            <span>LFM ORBIT <small>HOSTED</small></span>
          </a>
          <div className="hosted-nav-links">
            <a href="#lesson">What it teaches</a>
            <a href="#evidence">Saved evidence</a>
            {!IS_HOSTED_BUILD && <a href="/">Full app (local)</a>}
          </div>
        </nav>

        <div className="hosted-hero-content">
          <p className="hosted-kicker">Browser-first edge AI field note</p>
          <h1>See how a small model turns satellite change into a compact decision.</h1>
          <p className="hosted-hero-copy">
            {modelAvailable
              ? "Fetch the Orbit model once, run the conversation locally with WebAssembly, and explore saved evidence without an API key or a backend server."
              : "Explore three saved evidence packages without an API key or backend server. Select a story, inspect its provenance, and follow the retention decision."}
          </p>
          <div className="hosted-hero-actions">
            {modelAvailable ? (
              <button className="hosted-button hosted-button-primary" type="button" onClick={startModelFetch} disabled={!model.capability?.canFetch || model.manifestStatus === "loading" || model.status === "ready" || model.status === "generating"}>
                {!model.capability
                  ? "Checking browser support"
                  : !model.capability.canFetch
                    ? "Saved packages only"
                    : model.manifestStatus === "loading"
                      ? "Reading model manifest"
                      : model.manifestStatus === "error"
                        ? "Retry model manifest"
                        : model.status === "loading"
                          ? "Fetching in this browser"
                          : model.status === "ready"
                            ? "Model ready"
                            : "Fetch the small model"}
              </button>
            ) : (
              <a className="hosted-button hosted-button-primary" href="#evidence">Explore saved evidence</a>
            )}
            <button className="hosted-button hosted-button-quiet" type="button" onClick={() => setShowLesson((value) => !value)}>
              {showLesson ? "Hide lesson map" : "Show lesson map"}
            </button>
          </div>
          <div className="hosted-hero-status">
            <span className="hosted-status-dot" />
            <span>{shaderStatus}</span>
            <span className="hosted-status-divider">·</span>
            <span>{packages ? "Saved packages ready" : "Loading saved packages"}</span>
          </div>
        </div>

        {showLesson && (
          <div className="hosted-lesson-map" id="lesson-map">
            <span>01 · observe</span>
            <span>02 · filter</span>
            <span>03 · explain</span>
            <span>04 · decide</span>
          </div>
        )}
      </section>

      <section className="hosted-content hosted-content-grid" id="model">
        <div className="hosted-copy-column">
          <p className="hosted-section-label">01 / {modelAvailable ? "local runtime" : "saved-only runtime"}</p>
          <h2>{modelAvailable ? "A hosted demo that teaches the boundary." : "A saved-evidence portfolio with a clear boundary."}</h2>
          <p>
            {modelAvailable
              ? "This presentation keeps the full Orbit application intact, then removes everything a portfolio visitor does not need: no provider settings, no credentials, no backend boot, no hidden mission controls."
              : "This public presentation is intentionally read-only. The source contains a separate local inference lane, while this build focuses on reliable evidence inspection with no model download or remote runtime request."}
          </p>
          <div className="hosted-principles">
            {modelAvailable ? (
              <>
                <div><strong>Browser-only</strong><span>Local text reasoning runs in a worker with WebAssembly.</span></div>
                <div><strong>Honest evidence</strong><span>Every package is labeled saved demo data, never live imagery.</span></div>
                <div><strong>Small surface</strong><span>One fetch action, three packages, one clear conversation.</span></div>
              </>
            ) : (
              <>
                <div><strong>Evidence first</strong><span>Start with the reviewed package, then inspect its source and scoring basis.</span></div>
                <div><strong>Boundary visible</strong><span>Provenance and retention stay on the card so the example cannot look like live detection.</span></div>
                <div><strong>No hidden work</strong><span>The saved-only build ships no model runtime, manifest, or inference request.</span></div>
              </>
            )}
          </div>
        </div>

        {modelAvailable && model ? (
          <aside className="hosted-model-card" aria-labelledby="model-heading">
            <div className="hosted-card-topline"><span>MODEL FETCH</span><span>{model.model?.sizeLabel ?? "Sealed browser artifact"}</span></div>
            <h2 id="model-heading">{model.model?.label ?? "Orbit browser model"}</h2>
            <p className="hosted-model-repo">{model.model ? `${model.model.repo} / ${model.model.file} · revision ${model.model.revision.slice(0, 12)}` : "Reading the pinned public GGUF manifest"}</p>
            <p className="hosted-model-license">{model.model ? `License: ${model.model.license} · Text reasoning only` : "Manifest identity required before any model request"}</p>
            <p className="hosted-model-capability" data-testid="hosted-model-capability">{capabilityCopy(model.capability)}</p>
            <p className="hosted-model-status">{modelStatusCopy(model)}</p>
            {model.status === "loading" && (
              <div className="hosted-progress" aria-label={`Model fetch ${Math.round(model.progress * 100)} percent`}>
                <span style={{ width: `${Math.round(model.progress * 100)}%` }} />
              </div>
            )}
            <div className="hosted-model-actions">
              {model.status === "loading" ? (
                <button className="hosted-button hosted-button-secondary" type="button" onClick={model.cancelDownload}>Cancel fetch</button>
              ) : model.status === "generating" ? (
                <button className="hosted-button hosted-button-secondary" type="button" onClick={model.cancelGeneration}>Stop generation</button>
              ) : (
                <button className="hosted-button hosted-button-secondary" type="button" onClick={() => model.manifestStatus === "error" ? model.retryManifest() : void model.load()} disabled={model.status === "ready" || !model.capability?.canFetch || model.manifestStatus === "loading"}>
                  {model.manifestStatus === "loading" ? "Reading model manifest" : model.manifestStatus === "error" ? "Retry model manifest" : model.status === "ready" ? "Model ready" : model.status === "error" ? "Retry fetch" : "Fetch + load locally"}
                </button>
              )}
              <span className="hosted-no-api">No Orbit API required</span>
            </div>
            {model.error && <p className="hosted-error" role="alert">{model.error}</p>}
            <p className="hosted-model-note">The first visit verifies and downloads the pinned public artifact. Browser storage may serve later visits from cache.</p>
          </aside>
        ) : (
          <aside className="hosted-model-card hosted-static-card" aria-labelledby="saved-runtime-heading">
            <div className="hosted-card-topline"><span>STATIC PORTFOLIO</span><span>3 PACKAGES</span></div>
            <h2 id="saved-runtime-heading">Start with a saved decision.</h2>
            <p className="hosted-model-repo">The public build is a small, read-only review surface.</p>
            <p className="hosted-model-license">No credentials, backend, model fetch, or live imagery is required.</p>
            <ol className="hosted-static-checks">
              <li><strong>Observe</strong><span>Open the package image and signal.</span></li>
              <li><strong>Verify</strong><span>Read the replay, scoring basis, and observation window.</span></li>
              <li><strong>Decide</strong><span>Compare the retention decision with the teaching point.</span></li>
            </ol>
            <a className="hosted-button hosted-button-secondary" href="#evidence">Open saved evidence</a>
          </aside>
        )}
      </section>

      <section className="hosted-content" id="evidence">
        <div className="hosted-section-heading">
          <div><p className="hosted-section-label">02 / saved evidence packages</p><h2>Choose a small story, then ask why it matters.</h2></div>
          <p>These packages make the demo reliable to host: no API quota, no live-data ambiguity, no waiting for a mission scan.</p>
        </div>
        {!modelAvailable && <GuidedPath />}
        {packageError && <p className="hosted-error" role="alert">{packageError}</p>}
        {!packageError && !selectedPackage && <p className="hosted-chat-empty">Loading saved evidence packages...</p>}
        {selectedPackage && (
          <div className="hosted-package-layout">
            <div className="hosted-package-list" role="list" aria-label="Saved demo packages">
              {packages?.map((item, index) => (
                <button
                  className={`hosted-package ${item.id === selectedPackage.id ? "is-selected" : ""}`}
                  key={item.id}
                  type="button"
                  onClick={() => setSelectedId(item.id)}
                >
                  <span className="hosted-package-number">0{index + 1}</span>
                  <span><strong>{item.title}</strong><small>{item.location}</small></span>
                  <span className="hosted-package-arrow">Open</span>
                </button>
              ))}
            </div>
            <article className="hosted-evidence-card">
              <div
                className="hosted-evidence-visual has-image"
                aria-label={selectedPackage.imageAlt}
                role="img"
                style={{ backgroundImage: `url("${resolveHostedAsset(selectedPackage.imageSrc)}")` }}
              >
                <span className="hosted-evidence-crosshair" />
                <span className="hosted-evidence-label">{selectedPackage.signal}</span>
                <span className="hosted-evidence-coordinates">{selectedPackage.location.split("·")[0]}</span>
              </div>
              <div className="hosted-evidence-body">
                <p className="hosted-section-label">Selected package</p>
                <h3>{selectedPackage.title}</h3>
                <p>{selectedPackage.summary}</p>
                <div className="hosted-fact-row">{selectedPackage.facts.map((fact) => <span key={fact}>{fact}</span>)}</div>
                <p className="hosted-evidence-provenance" data-testid="hosted-evidence-provenance">
                  Saved replay · {selectedPackage.evidence.scoringBasis} · {selectedPackage.evidence.observationWindow.start} → {selectedPackage.evidence.observationWindow.end}
                </p>
                <p className="hosted-teaching-point"><strong>Try this:</strong> {selectedPackage.teachingPoint}</p>
              </div>
            </article>
          </div>
        )}
      </section>

      {modelAvailable && model && (
        <section className="hosted-content hosted-chat-section" id="chat">
          <div className="hosted-chat-intro">
            <p className="hosted-section-label">03 / local conversation</p>
            <h2>Ask the model to explain the tradeoff.</h2>
            <p>Keep questions grounded in the selected packet. The tutor is intentionally small, local, and transparent about uncertainty.</p>
          </div>
          <div className="hosted-chat-card">
            <div className="hosted-chat-header"><span>ORBIT CLASSROOM</span><span className={model.status === "ready" ? "hosted-live" : ""}>{modelStatusCopy(model)}</span></div>
            <div className="hosted-chat-log" aria-live="polite">
              {chat.length === 0 && <p className="hosted-chat-empty">{!selectedPackage ? "Load a saved package to continue." : model.status === "ready" ? "Ask: Why should this packet be retained?" : "Fetch the model to start a local conversation."}</p>}
              {chat.map((line, index) => <div className={`hosted-chat-line hosted-chat-${line.role}`} key={`${line.role}-${index}`}><span>{line.role === "user" ? "YOU" : "ORBIT"}</span><p>{line.text}</p></div>)}
            </div>
            <form className="hosted-chat-form" onSubmit={submitQuestion}>
              <input value={question} onChange={(event) => setQuestion(event.target.value)} disabled={model.status !== "ready" || !selectedPackage} placeholder="Ask about evidence, uncertainty, or downlink..." aria-label="Ask Orbit Classroom" />
              <button className="hosted-button hosted-button-primary" type="submit" disabled={model.status !== "ready" || !selectedPackage || !question.trim()}>Ask</button>
            </form>
          </div>
        </section>
      )}

      <section className="hosted-content hosted-teaching-section" id="lesson">
        <div><p className="hosted-section-label">{modelAvailable ? "04" : "03"} / why this belongs in a classroom</p><h2>A small local model is a systems lesson, not just a chatbot.</h2></div>
        <div className="hosted-teaching-grid">
          <article><span>01</span><h3>Resource-aware design</h3><p>Students can see why model size, browser memory, worker boundaries, and cache behavior are product decisions.</p></article>
          <article><span>02</span><h3>Evidence before confidence</h3><p>Saved packets make it easy to separate pixels, derived signals, model language, and the action an operator is allowed to take.</p></article>
          <article><span>03</span><h3>Edge AI tradeoffs</h3><p>Local inference removes API keys and round trips, but introduces device limits, model fit, and honest fallback design.</p></article>
        </div>
      </section>

      <footer className="hosted-footer"><span>LFM Orbit · browser-first edge AI portfolio demo</span><span>{!IS_HOSTED_BUILD && <a href="/">Full app (local)</a>}<a href={modelAvailable ? "#model" : "#evidence"}>{modelAvailable ? "Fetch model" : "Review evidence"}</a></span></footer>
    </main>
  );
}
