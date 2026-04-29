"""
Ground Station Knowledge base and chat reply generator.
"""
def get_ground_agent_reply(user_msg: str) -> str:
    """
    LFM-style intent classifier for the Ground Station operator.
    Reads live DB state and explains everything visible in the UI.
    Zero external deps.
    """
    from core.queue import get_alert_counts
    from core.metrics import read_metrics_summary
    from core.agent_bus import list_pins
    from core.config import REGION

    counts = get_alert_counts()
    metrics = read_metrics_summary()
    msg = user_msg.lower().strip()

    # ── status / overview ───────────────────────────────────────────────────
    if any(k in msg for k in ("status", "overview", "summary", "how many", "report")):
        return (
            f"Ground Station nominal. "
            f"Downlinked {counts['total_alerts']} alert packets "
            f"({counts.get('total_payload_bytes', 0)} bytes total payload). "
            f"Bandwidth saved vs raw imagery: {metrics.get('total_bandwidth_saved_mb', 0):.1f} MB. "
            f"Latest discard ratio: {metrics.get('latest_discard_ratio', 0):.1%}. "
            f"Completed scan cycles: {metrics.get('total_cycles_completed', 0)}."
        )

    # ── bandwidth ───────────────────────────────────────────────────────────
    if any(k in msg for k in ("bandwidth", "saving", "downlink", "payload", "bytes")):
        saved = metrics.get("total_bandwidth_saved_mb", 0)
        alerts = counts["total_alerts"]
        raw_mb = alerts * 5.0
        return (
            f"Bandwidth triage active. Orbital agent filtered raw imagery down to "
            f"{counts.get('total_payload_bytes', 0)} bytes of alert packets. "
            f"Estimated {saved:.1f} MB saved vs raw downlink "
            f"({alerts} alerts × ~5 MB/frame = ~{raw_mb:.0f} MB avoided). "
            f"This fits comfortably within the 10 MB satellite downlink budget."
        )

    # ── discard ratio ────────────────────────────────────────────────────────
    if any(k in msg for k in ("discard", "ratio", "filter", "threw", "pruned", "ignored")):
        ratio = metrics.get("latest_discard_ratio", 0)
        total = metrics.get("total_cells_scanned", 0)
        alerts = counts["total_alerts"]
        return (
            f"DISCARD RATIO: {ratio:.1%}. "
            f"Of {total} cells evaluated by the orbital Pruner, only "
            f"{alerts} crossed the anomaly threshold (Δscore ≥ 0.32) and were downlinked. "
            f"The rest were silently discarded in orbit — no data wasted on 10 MB downlink. "
            f"A higher discard ratio means the satellite is doing more work so you don't have to."
        )

    # ── alerts / anomalies ──────────────────────────────────────────────────
    if any(k in msg for k in ("alert", "anomal", "flagged", "deforest", "detection")):
        examples = metrics.get("flagged_examples", [])
        if examples:
            top = examples[0]
            return (
                f"{counts['total_alerts']} deforestation alerts downlinked. "
                f"Latest flagged cell: {top.get('cell_id', 'N/A')} "
                f"(change score {top.get('change_score', 0):.3f}, "
                f"confidence {top.get('confidence', 0):.3f}). "
                f"Select an amber hex cell on the map to inspect temporal imagery and run LFM analysis."
            )
        return (
            f"{counts['total_alerts']} alerts in queue. "
            f"Scan in progress — click any flagged hex on the map to inspect it."
        )

    # ── scan / progress ─────────────────────────────────────────────────────
    if any(k in msg for k in ("scan", "progress", "cycle", "grid", "h3", "hex", "cell")):
        return (
            f"H3 hex-grid scan active over Amazonas Focus Region. "
            f"Resolution 5 (≈ 252 km² cells), ring-6 grid = 127 cells. "
            f"Completed {metrics.get('total_cycles_completed', 0)} full cycles, "
            f"{metrics.get('total_cells_scanned', 0)} cells evaluated total. "
            f"The orbital Pruner scores each cell and downlinks only the anomaly index "
            f"— a 15-byte H3 string instead of a 5 MB image. "
            f"Cells pulse cyan when scanned, turn amber when flagged, fade out when discarded."
        )

    # ── map / what am I looking at / point out tools ────────────────────────
    if any(k in msg for k in ("point out", "where are", "show me tools", "what parts of the app do")):
        from core.agent_bus import upsert_pin
        # Drop UI-pointing mock locations around the bounds
        upsert_pin("ground", -1.5, -57.5, "Mission Control", "Operator Tool located on the top right HUD.")
        upsert_pin("ground", -3.119, -63.5, "Evidence Gallery", "Operator Tool located on the left HUD to review visual captures.")
        upsert_pin("ground", -5.5, -60.025, "Agent Dialogue", "Located at the bottom left to view our communication bus.")
        return "I have placed Ground Agent pins on your map representing where you can find our primary tools! Check the HUD boundaries."

    if any(k in msg for k in ("map", "what am i", "looking at", "satellite imagery", "basemap", "esri")):
        return (
            "The map shows ESRI World Imagery satellite basemap (context only — not used in scoring). "
            "Overlaid on it is the H3 hex-grid of the Amazonas focus region. "
            "◆ Cyan pins = satellite-flagged cells. ● Green pins = ground-confirmed detections. "
            "★ Amber pins = your operator markers (click anywhere on the map to drop one). "
            "Click any amber hex cell to open the Validation Panel with before/after imagery."
        )

    # ── pins / markers ──────────────────────────────────────────────────────
    if any(k in msg for k in ("pin", "marker", "dot", "symbol", "icon", "drop a")):
        pins = list_pins()
        sat_pins = sum(1 for p in pins if p["pin_type"] == "satellite")
        gnd_pins = sum(1 for p in pins if p["pin_type"] == "ground")
        opr_pins = sum(1 for p in pins if p["pin_type"] == "operator")
        return (
            f"Map pin system: three actor types, three distinct symbols. "
            f"◆ Cyan = Satellite Pruner flags ({sat_pins} active). "
            f"● Green = Ground Validator confirmations ({gnd_pins} active). "
            f"★ Amber = Operator-placed markers ({opr_pins} active). "
            f"To drop your own pin, hold Shift and click anywhere on the map. "
            f"Pins persist in the SQLite bus database and survive page refresh."
        )

    # ── validation panel ────────────────────────────────────────────────────
    if any(k in msg for k in ("validation", "inspect", "panel", "before", "after", "chip", "imagery")):
        return (
            "The Validation Panel (right side) opens when you click a flagged hex cell. "
            "It shows: (1) the H3 cell ID and event signature, (2) before/after satellite imagery chips "
            "(ESRI context, or real Sentinel-2 if credentials are set), "
            "(3) band deltas — NDVI, NBR, NIR drops that drove the anomaly score, "
            "(4) ANALYZE (LFM) button — runs the offline LFM model on the temporal evidence, "
            "(5) the LFM analysis summary with severity assessment and findings."
        )

    # ── temporal evidence ────────────────────────────────────────────────────
    if any(k in msg for k in ("temporal", "ndvi", "nbr", "nir", "band", "spectral", "delta", "change score")):
        return (
            "Temporal evidence = spectral band comparison between two observation windows. "
            "NDVI (vegetation index): drops indicate biomass loss. "
            "NIR (near-infrared): drops >25% suggest canopy removal. "
            "NBR (burn ratio): shifts indicate disturbance or clearing. "
            "The composite change score weights these: NDVI×0.5 + NIR×0.25 + NBR×0.25. "
            "Threshold is 0.32 — anything above is flagged and downlinked."
        )

    # ── agent dialogue ────────────────────────────────────────────────────
    if any(k in msg for k in ("agent dialogue", "dialogue", "bus", "message bus", "agents talking", "sat gnd", "sat →")):
        from core.agent_bus import get_bus_stats
        stats = get_bus_stats()
        return (
            f"The Agent Dialogue Bus is a SQLite-backed message queue connecting the two autonomous agents. "
            f"Satellite Pruner posts FLAG messages when it finds anomalies. "
            f"Ground Validator pulls those flags, runs LFM analysis, and replies with CONFIRM or REJECT. "
            f"Current bus: {stats['total_messages']} total messages — "
            f"{stats['from_satellite']} from satellite, {stats['from_ground']} from ground. "
            f"Open the 'Agent Dialogue' button (bottom-left) to watch them converse in real-time."
        )

    # ── sidebar left ─────────────────────────────────────────────────────────
    if any(k in msg for k in ("sidebar", "left panel", "scan progress", "satellite scanner", "link open", "telemetry")):
        return (
            "Left sidebar — Satellite Scanner panel. Shows: "
            "LINK OPEN = WebSocket to the backend orbital scan stream is connected. "
            "SCAN PROGRESS = cells evaluated / total cells in this H3 grid. "
            "DISCARD RATIO = fraction of cells the orbital Pruner threw away. "
            "ALERTS = count of anomaly packets downlinked this session. "
            "BANDWIDTH SAVED = estimated MB saved vs raw downlink. "
            "CYCLE = current orbital pass number. "
            "DEMO MODE = seeded / live (controls whether deterministic anomalies are injected)."
        )

    # ── sidebar right ─────────────────────────────────────────────────────────
    if any(k in msg for k in ("right panel", "flagged examples", "recent alerts", "triage", "region-only")):
        return (
            "Right sidebar — Triage Summary. Shows: "
            "REGION-ONLY TRIAGE: the system scans one fixed region at a time (Amazonas). "
            "TEMPORAL EVIDENCE: click a flagged cell to see before/after band comparisons. "
            "FLAGGED EXAMPLES: the 5 most recent anomaly cells downlinked this session. "
            "RECENT ALERTS: raw alert records from the SQLite queue."
        )

    # ── settings ─────────────────────────────────────────────────────────────
    if any(k in msg for k in ("settings", "gear", "provider", "config", "credential", "sentinel hub")):
        return (
            "Settings panel (⚙ icon, top-left of scanner card). Shows: "
            "PROVIDER STATUS — which imagery source is active (SimSat > SentinelHub > semi-real fallback). "
            "CREDENTIAL STATUS — whether Sentinel Hub OAuth2 tokens are configured. "
            "AI MODEL — default is offline_lfm_v1 (no API key needed), optional GPT-4o-mini with key. "
            "EVIDENCE EXPORT — links to download demo metrics JSON for submission."
        )

    # ── architecture / how it works ─────────────────────────────────────────
    if any(k in msg for k in ("architect", "how", "work", "pipeline", "lfm", "model")):
        return (
            "Dual-agent pipeline: "
            "(1) Satellite Pruner — runs on NVIDIA Orin in orbit, scores H3 cells using "
            "spectral delta math, downlinks only anomaly cell IDs (≈15 bytes each). "
            "(2) Ground Validator — receives cell IDs, fetches high-res imagery via ESRI/SimSat, "
            "runs LFM2-VL vision analysis to confirm deforestation. "
            "No Docker. Native FastAPI + Vite stack. SQLite queue, zero external state."
        )

    # ── provider / imagery ──────────────────────────────────────────────────
    if any(k in msg for k in ("provider", "imagery", "simsat", "sentinel", "esri", "image")):
        return (
            f"Active observation mode: {REGION.observation_mode}. "
            f"Provider fallback order: simsat_sentinel -> simsat_mapbox -> sentinelhub_direct -> nasa_api_direct -> cached proxy loader. "
            f"Context imagery sourced from ESRI World Imagery (always available). "
            f"Before/after chips use SimSat Sentinel API when token is configured."
        )

    # ── help ────────────────────────────────────────────────────────────────
    if any(k in msg for k in ("help", "command", "what can", "capabilit", "list")):
        return (
            "Ground Agent topics: status · bandwidth · discard ratio · alerts · scan/hex · "
            "map · pins/markers · validation panel · temporal/bands · agent dialogue · "
            "left sidebar · right sidebar · settings · architecture · provider · help. "
            "Or just ask 'what am I looking at?' for a map overview. "
            "Shift-click the map to drop your own operator pin."
        )

    # ── default ─────────────────────────────────────────────────────────────
    return (
        f"Ground Station online. "
        f"{counts['total_alerts']} alerts downlinked, "
        f"{metrics.get('total_bandwidth_saved_mb', 0):.1f} MB saved. "
        f"Ask me: 'what am I looking at?', 'explain discard ratio', 'what are the pins?', "
        f"or 'help' for all topics."
    )
