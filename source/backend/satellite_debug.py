"""
satellite_debug.py -- Live debug dashboard for the satellite agent.

STATUS: Optional dev utility -- NOT part of the main run path.

Runs a standalone FastAPI app on port 8080. Shows a live chat-like view of the
agent_bus.sqlite message queue with real-time SSE streaming, thinking-tab reveal,
tool call expansion and heartbeat pulse.

Run manually:
    uvicorn source.backend.satellite_debug:app --port 8080 --reload
    # or from within source/backend/:
    python satellite_debug.py

Main application runs on port 8000 (api/main.py).
"""

import json
import os
import sqlite3
import asyncio
import html as html_mod
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Satellite Debug Hub")


def _debug_cors_allow_origins() -> list[str]:
    configured = os.getenv("ORBIT_DEBUG_CORS_ALLOW_ORIGINS", "").strip()
    if configured:
        origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
        if origins:
            return origins
    return ["http://127.0.0.1:8080", "http://localhost:8080"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_debug_cors_allow_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path(__file__).parent.parent.parent / "runtime-data" / "agent_bus.sqlite"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _get_stats() -> dict:
    if not DB_PATH.exists():
        return {"error": "DB not found", "feed": [], "total_messages": 0,
                "satellite_dispatched": 0, "unread_queued_to_ground": 0,
                "latest_heartbeat": "Offline"}
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM agent_messages").fetchone()[0]
        sat_sent = conn.execute(
            "SELECT COUNT(*) FROM agent_messages WHERE sender='satellite'"
        ).fetchone()[0]
        unread = conn.execute(
            "SELECT COUNT(*) FROM agent_messages WHERE read=0"
        ).fetchone()[0]
        hb = conn.execute(
            "SELECT payload FROM agent_messages WHERE msg_type='heartbeat' ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        rows = conn.execute(
            "SELECT id, sender, recipient, msg_type, payload, timestamp "
            "FROM agent_messages ORDER BY timestamp DESC LIMIT 60"
        ).fetchall()

    feed = []
    for row in reversed(rows):
        try:
            pl = json.loads(row["payload"])
        except Exception:
            pl = row["payload"]
        feed.append({
            "id": row["id"],
            "sender": row["sender"],
            "recipient": row["recipient"],
            "msg_type": row["msg_type"],
            "payload": pl,
            "time": row["timestamp"],
        })

    hb_text = "Offline"
    if hb:
        try:
            hb_data = json.loads(hb[0])
            hb_text = hb_data.get("note", hb[0])[:80]
        except Exception:
            hb_text = str(hb[0])[:80]

    return {
        "total_messages": total,
        "satellite_dispatched": sat_sent,
        "unread_queued_to_ground": unread,
        "latest_heartbeat": hb_text,
        "feed": feed,
    }


def _get_model_status() -> dict:
    try:
        import sys
        import os
        sys.path.insert(0, str(Path(__file__).parent))
        from core.inference import model_status
        return model_status()
    except Exception as exc:
        return {"loaded": False, "reason": str(exc)}


def _last_message_id() -> int:
    if not DB_PATH.exists():
        return 0
    with _connect() as conn:
        row = conn.execute("SELECT MAX(id) FROM agent_messages").fetchone()
        return row[0] or 0


def _messages_since(last_id: int) -> list:
    if not DB_PATH.exists():
        return []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, sender, recipient, msg_type, payload, timestamp "
            "FROM agent_messages WHERE id > ? ORDER BY id ASC LIMIT 50",
            (last_id,),
        ).fetchall()
    out = []
    for row in rows:
        try:
            pl = json.loads(row["payload"])
        except Exception:
            pl = row["payload"]
        out.append({
            "id": row["id"],
            "sender": row["sender"],
            "recipient": row["recipient"],
            "msg_type": row["msg_type"],
            "payload": pl,
            "time": row["timestamp"],
        })
    return out


@app.get("/api/stats")
def api_stats():
    return _get_stats()


@app.get("/api/model")
def api_model_status():
    return _get_model_status()


@app.get("/api/sse/messages")
async def sse_messages():
    """Server-Sent Events endpoint — streams new bus messages as they arrive."""
    last_id = _last_message_id()

    async def generator():
        nonlocal last_id
        while True:
            await asyncio.sleep(1.2)
            msgs = _messages_since(last_id)
            if msgs:
                last_id = msgs[-1]["id"]
                data = json.dumps(msgs)
                yield f"data: {data}\n\n"
            else:
                # Keepalive
                yield ": ping\n\n"

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/", response_class=HTMLResponse)
def index():
    stats = _get_stats()
    model_st = _get_model_status()
    unread = stats.get("unread_queued_to_ground", 0)
    link_severed = unread > 0

    model_badge = (
        '<span class="badge badge-ok">LFM LOADED</span>'
        if model_st.get("loaded")
        else f'<span class="badge badge-warn">LFM OFFLINE — {html_mod.escape(model_st.get("reason", "unknown"))}</span>'
    )

    return HTMLResponse(_build_html(stats, model_badge, link_severed))


def _build_html(stats: dict, model_badge: str, link_severed: bool) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Orbit Link — Satellite Debug</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap');

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg0:     #080d19;
    --bg1:     #0d1527;
    --bg2:     #111c35;
    --bg3:     #162040;
    --border:  #1e2e52;
    --sat:     #38bdf8;
    --grnd:    #10b981;
    --warn:    #f59e0b;
    --crit:    #ef4444;
    --think:   #a78bfa;
    --tool:    #fb923c;
    --muted:   #4a5a7a;
    --text:    #d4e3ff;
    --text2:   #8899bb;
    --mono:    'JetBrains Mono', monospace;
    --sans:    'Inter', sans-serif;
  }}

  html, body {{ height: 100%; overflow: hidden; background: var(--bg0); color: var(--text); font-family: var(--sans); }}

  /* ── Layout ── */
  .shell {{ display: flex; flex-direction: column; height: 100vh; }}

  /* ── Header ── */
  header {{
    flex-shrink: 0;
    background: var(--bg1);
    border-bottom: 1px solid var(--border);
    padding: 12px 20px;
    display: flex; align-items: center; gap: 18px;
    box-shadow: 0 2px 20px rgba(0,0,0,.5);
  }}
  .sat-icon {{ font-size: 28px; animation: orbit 8s linear infinite; display: inline-block; }}
  @keyframes orbit {{ from {{ transform: rotate(0deg) translateX(3px) rotate(0deg); }} to {{ transform: rotate(360deg) translateX(3px) rotate(-360deg); }} }}
  .header-title {{ font-size: 11px; font-weight: 700; letter-spacing: .18em; text-transform: uppercase; color: var(--text); font-family: var(--mono); }}
  .header-sub {{ font-size: 9px; letter-spacing: .12em; text-transform: uppercase; margin-top: 2px; }}
  .link-ok   {{ color: var(--grnd); }}
  .link-sev  {{ color: var(--crit); animation: pulse-text 1.4s ease-in-out infinite; }}
  @keyframes pulse-text {{ 0%,100% {{ opacity: 1; }} 50% {{ opacity: .4; }} }}

  .hdr-stats {{ display: flex; gap: 20px; margin-left: auto; font-family: var(--mono); }}
  .hdr-stat {{ display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }}
  .hdr-stat .label {{ font-size: 8px; color: var(--muted); text-transform: uppercase; letter-spacing: .1em; }}
  .hdr-stat .value {{ font-size: 11px; font-weight: 700; }}
  .v-sat   {{ color: var(--sat); }}
  .v-warn  {{ color: var(--warn); }}
  .v-grnd  {{ color: var(--grnd); }}
  .v-muted {{ color: var(--muted); }}

  /* ── Model strip ── */
  .model-strip {{
    flex-shrink: 0;
    background: var(--bg2);
    border-bottom: 1px solid var(--border);
    padding: 5px 20px;
    display: flex; align-items: center; gap: 10px;
    font-family: var(--mono); font-size: 9px; color: var(--muted);
  }}
  .badge {{ padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 8px; letter-spacing: .1em; text-transform: uppercase; }}
  .badge-ok   {{ background: rgba(16,185,129,.15); color: var(--grnd); border: 1px solid rgba(16,185,129,.3); }}
  .badge-warn {{ background: rgba(245,158,11,.12); color: var(--warn); border: 1px solid rgba(245,158,11,.3); }}

  /* ── Chat feed ── */
  .chat-wrap {{
    flex: 1; overflow-y: auto; padding: 16px 20px;
    display: flex; flex-direction: column; gap: 10px;
    scroll-behavior: smooth;
  }}
  .chat-wrap::-webkit-scrollbar {{ width: 4px; }}
  .chat-wrap::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}

  /* ── Message bubbles ── */
  .msg {{ display: flex; flex-direction: column; max-width: 88%; }}
  .msg.from-satellite {{ align-items: flex-start; }}
  .msg.from-ground    {{ align-items: flex-end; }}
  .msg.from-operator  {{ align-items: center; }}
  .msg.from-broadcast {{ align-items: flex-start; opacity: .75; }}

  .msg-meta {{ display: flex; align-items: baseline; gap: 6px; margin-bottom: 3px; padding: 0 2px; }}
  .msg-meta .sender     {{ font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; font-family: var(--mono); }}
  .msg-meta .ts         {{ font-size: 8px; color: var(--muted); font-family: var(--mono); }}
  .msg-meta .type-tag   {{ font-size: 7px; padding: 1px 5px; border-radius: 3px; background: var(--bg3); color: var(--muted); text-transform: uppercase; letter-spacing: .08em; border: 1px solid var(--border); }}

  .satellite .sender {{ color: var(--sat); }}
  .ground    .sender {{ color: var(--grnd); }}
  .operator  .sender {{ color: var(--warn); }}

  .bubble {{
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 2px 10px rgba(0,0,0,.3);
  }}
  .from-satellite .bubble {{ border-left: 2px solid var(--sat); background: var(--bg2); }}
  .from-ground    .bubble {{ border-right: 2px solid var(--grnd); background: var(--bg1); }}
  .from-operator  .bubble {{ border-left: 2px solid var(--warn); border-right: 2px solid var(--warn); background: var(--bg3); }}
  .from-broadcast .bubble {{ border-left: 1px solid var(--border); background: var(--bg1); }}

  /* ── Tab system (thinking / tools / response) ── */
  .tabs {{ display: flex; gap: 0; border-bottom: 1px solid var(--border); background: rgba(0,0,0,.2); }}
  .tab-btn {{
    padding: 5px 12px; font-size: 8px; font-family: var(--mono); font-weight: 700;
    text-transform: uppercase; letter-spacing: .1em; color: var(--muted);
    background: none; border: none; cursor: pointer; border-bottom: 2px solid transparent;
    transition: color .15s, border-color .15s;
  }}
  .tab-btn:hover  {{ color: var(--text); }}
  .tab-btn.active {{ color: var(--text); }}
  .tab-btn.t-think {{ border-bottom-color: var(--think) !important; color: var(--think); }}
  .tab-btn.t-tool  {{ border-bottom-color: var(--tool)  !important; color: var(--tool);  }}
  .tab-btn.t-resp  {{ border-bottom-color: var(--sat)   !important; color: var(--sat);   }}

  .tab-panel {{ display: none; padding: 10px 12px; }}
  .tab-panel.active {{ display: block; }}

  /* Plain note fallback */
  .plain-body {{ padding: 10px 12px; font-size: 12px; line-height: 1.6; color: var(--text); }}

  /* ── Thinking content ── */
  .think-body {{
    font-family: var(--mono); font-size: 10px; line-height: 1.7;
    color: #c4b5fd; white-space: pre-wrap; word-break: break-word;
    max-height: 200px; overflow-y: auto;
  }}

  /* ── Tool calls ── */
  .tool-call {{
    background: var(--bg0); border: 1px solid rgba(251,146,60,.2);
    border-radius: 6px; padding: 8px 10px; font-family: var(--mono); font-size: 10px;
    margin-bottom: 6px;
  }}
  .tool-name {{ color: var(--tool); font-weight: 700; }}
  .tool-args {{ color: var(--text2); margin-top: 4px; white-space: pre-wrap; font-size: 9px; }}

  /* ── Response text ── */
  .resp-text {{ font-size: 13px; line-height: 1.65; color: var(--text); }}

  /* ── Status / action tags ── */
  .action-tag {{ display: inline-block; margin-right: 6px; margin-bottom: 4px; padding: 2px 8px; border-radius: 4px; font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; font-family: var(--mono); }}
  .tag-action {{ background: rgba(56,189,248,.1); color: var(--sat); border: 1px solid rgba(56,189,248,.3); }}
  .tag-status {{ background: rgba(16,185,129,.1); color: var(--grnd); border: 1px solid rgba(16,185,129,.3); }}
  .tag-warn   {{ background: rgba(245,158,11,.1); color: var(--warn); border: 1px solid rgba(245,158,11,.3); }}

  /* ── Heartbeat pulse strip ── */
  .hb-strip {{
    display: flex; align-items: center; gap: 6px; padding: 4px 12px;
    font-size: 9px; color: var(--muted); font-family: var(--mono); border-top: 1px solid rgba(255,255,255,.04);
  }}
  .hb-dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--grnd); animation: hbpulse 1.6s ease-in-out infinite; }}
  @keyframes hbpulse {{ 0%,100% {{ opacity: 1; transform: scale(1); }} 50% {{ opacity: .3; transform: scale(.7); }} }}

  /* ── New message flash ── */
  @keyframes newmsg {{ from {{ background: rgba(56,189,248,.08); }} to {{ background: transparent; }} }}
  .new-msg {{ animation: newmsg 2s ease-out; }}

  /* ── LLM streaming indicator ── */
  .llm-streaming {{
    display: flex; align-items: center; gap: 8px; padding: 6px 12px;
    font-family: var(--mono); font-size: 9px; color: var(--think);
    border-top: 1px solid rgba(167,139,250,.15);
    background: rgba(167,139,250,.05);
  }}
  .llm-dots span {{ display: inline-block; width: 4px; height: 4px; border-radius: 50%; background: var(--think); margin: 0 1px; animation: llmdot 1.2s ease-in-out infinite; }}
  .llm-dots span:nth-child(2) {{ animation-delay: .2s; }}
  .llm-dots span:nth-child(3) {{ animation-delay: .4s; }}
  @keyframes llmdot {{ 0%,80%,100% {{ transform: scale(.6); opacity: .4; }} 40% {{ transform: scale(1); opacity: 1; }} }}
</style>
</head>
<body>
<div class="shell">

  <header>
    <span class="sat-icon" title="Orbital Satellite Agent">&#128752;</span>
    <div>
      <div class="header-title">Orbit Link &mdash; Satellite Agent Debug</div>
      <div class="header-sub {'link-sev' if link_severed else 'link-ok'}">
        {'&#9888; COMMS SEVERED &mdash; AUTONOMOUS MODE' if link_severed else '&#9679; COMMS ESTABLISHED'}
      </div>
    </div>
    <div class="hdr-stats">
      <div class="hdr-stat">
        <span class="label">Total Msgs</span>
        <span class="value v-sat">{stats['total_messages']}</span>
      </div>
      <div class="hdr-stat">
        <span class="label">SAT Dispatched</span>
        <span class="value v-sat">{stats['satellite_dispatched']}</span>
      </div>
      <div class="hdr-stat">
        <span class="label">Outbound Buffer</span>
        <span class="value {'v-warn' if link_severed else 'v-grnd'}">{stats['unread_queued_to_ground']} queued</span>
      </div>
    </div>
  </header>

  <div class="model-strip">
    <span>INFERENCE ENGINE:</span>
    {model_badge}
    <span style="margin-left:auto; color:var(--muted);">runtime-data/models/lfm2.5-vlm-450m/LFM2.5-VL-450M-Q4_0.gguf</span>
  </div>

  <div class="chat-wrap" id="chat">
    {_render_feed(stats.get('feed', []))}
    <div id="live-anchor"></div>
  </div>

  <div class="hb-strip">
    <div class="hb-dot"></div>
    <span id="hb-text" title="Last heartbeat">{html_mod.escape(stats.get('latest_heartbeat', 'Offline')[:120])}</span>
  </div>

</div><!-- .shell -->

<script>
(function() {{
  // Scroll to bottom on load
  const chat = document.getElementById('chat');
  chat.scrollTop = chat.scrollHeight;

  let lastId = {stats['feed'][-1]['id'] if stats.get('feed') else 0};
  let pendingLLM = null; // cell_id currently being reasoned on

  function escHtml(s) {{
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }}

  function renderPayload(payload, msgType, sender) {{
    if (typeof payload !== 'object' || payload === null) {{
      return '<div class="plain-body">' + escHtml(String(payload)) + '</div>';
    }}

    const hasTabs = payload.thinking || (payload.tool_calls && payload.tool_calls.length) || payload.response;
    if (!hasTabs) {{
      // Plain note/status
      const parts = [];
      if (payload.action) parts.push('<span class="action-tag tag-action">Action: ' + escHtml(payload.action) + '</span>');
      if (payload.status) parts.push('<span class="action-tag tag-status">Status: ' + escHtml(payload.status) + '</span>');
      const note = payload.note || payload.content || payload.message || '';
      const tagsHtml = parts.length ? '<div style="padding:8px 12px 4px">' + parts.join('') + '</div>' : '';
      const noteHtml = note ? '<div class="plain-body">' + escHtml(note) + '</div>' : '';
      return tagsHtml + noteHtml || '<div class="plain-body" style="color:var(--muted)">(empty)</div>';
    }}

    const uid = 'msg' + Date.now() + Math.random().toString(36).slice(2,6);
    const tabs = [];
    const panels = [];

    if (payload.thinking) {{
      tabs.push('<button class="tab-btn t-think active" onclick="switchTab(\\''+uid+'\\',\\'think\\',this)">&#129504; Thinking</button>');
      panels.push('<div class="tab-panel active" id="'+uid+'-think"><div class="think-body">'+escHtml(payload.thinking)+'</div></div>');
    }}
    if (payload.tool_calls && payload.tool_calls.length) {{
      const first = !payload.thinking;
      tabs.push('<button class="tab-btn t-tool'+(first?' active':'')+'" onclick="switchTab(\\''+uid+'\\',\\'tool\\',this)">&#128295; Tools ('+payload.tool_calls.length+')</button>');
      let tcHtml = '';
      for (const tc of payload.tool_calls) {{
        tcHtml += '<div class="tool-call"><span class="tool-name">' + escHtml(tc.name||'unknown') + '</span>';
        const args = tc.arguments||{{}};
        tcHtml += '<div class="tool-args">' + escHtml(JSON.stringify(args, null, 2)) + '</div></div>';
      }}
      panels.push('<div class="tab-panel'+(first?' active':'')+'" id="'+uid+'-tool">'+tcHtml+'</div>');
    }}
    if (payload.response) {{
      const first = !payload.thinking && !(payload.tool_calls && payload.tool_calls.length);
      tabs.push('<button class="tab-btn t-resp'+(first?' active':'')+'" onclick="switchTab(\\''+uid+'\\',\\'resp\\',this)">&#128226; Response</button>');
      panels.push('<div class="tab-panel'+(first?' active':'')+'" id="'+uid+'-resp"><div class="resp-text">'+escHtml(payload.response)+'</div></div>');
    }}

    return '<div class="tabs">' + tabs.join('') + '</div>' + panels.join('');
  }}

  function switchTab(uid, panel, btn) {{
    // Deactivate all tabs in this message's tab bar
    const bar = btn.closest('.tabs');
    bar.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    // Hide all panels for this uid
    ['think','tool','resp'].forEach(p => {{
      const el = document.getElementById(uid + '-' + p);
      if (el) el.classList.remove('active');
    }});
    const target = document.getElementById(uid + '-' + panel);
    if (target) target.classList.add('active');
  }}
  window.switchTab = switchTab;

  function senderClass(sender) {{
    if (sender === 'satellite') return 'from-satellite satellite';
    if (sender === 'ground')    return 'from-ground ground';
    if (sender === 'operator')  return 'from-operator operator';
    return 'from-broadcast';
  }}

  function renderMessage(msg) {{
    const cls = senderClass(msg.sender);
    const msgId = Number.isFinite(Number(msg.id)) ? Number(msg.id) : 0;
    const ts = escHtml((msg.time||'').slice(11,19));
    const meta = '<div class="msg-meta"><span class="sender">' + escHtml(msg.sender) + '</span>' +
                 '<span class="ts">' + ts + '</span>' +
                 '<span class="type-tag">' + escHtml(msg.msg_type) + '</span></div>';
    const body = renderPayload(msg.payload, msg.msg_type, msg.sender);
    let extra = '';
    // LLM streaming status for llm_thinking messages
    if (msg.msg_type === 'llm_thinking') {{
      extra = '<div class="llm-streaming"><div class="llm-dots"><span></span><span></span><span></span></div>LFM reasoning in progress&hellip;</div>';
    }}
    return '<div class="msg ' + cls + ' new-msg" id="m' + msgId + '">' +
           meta + '<div class="bubble">' + body + extra + '</div></div>';
  }}

  // SSE stream
  const evtSrc = new EventSource('/api/sse/messages');
  evtSrc.onmessage = function(e) {{
    let msgs;
    try {{ msgs = JSON.parse(e.data); }} catch(ex) {{ return; }}
    if (!Array.isArray(msgs) || !msgs.length) return;

    const anchor = document.getElementById('live-anchor');
    msgs.forEach(msg => {{
      // Remove llm_thinking bubble once llm_complete arrives for same cell
      if (msg.msg_type === 'llm_complete' && msg.payload && msg.payload.cell_id) {{
        const thinking = chat.querySelector('[data-cell="'+msg.payload.cell_id+'"][data-mtype="llm_thinking"]');
        if (thinking) thinking.remove();
      }}

      const el = document.createElement('div');
      el.innerHTML = renderMessage(msg);
      const node = el.firstChild;
      if (msg.cell_id) node.dataset.cell = msg.cell_id;
      node.dataset.mtype = msg.msg_type;
      anchor.before(node);
      lastId = Math.max(lastId, msg.id);
    }});

    // Scroll to bottom
    chat.scrollTop = chat.scrollHeight;

    // Update heartbeat
    const hbMsg = msgs.slice().reverse().find(m => m.msg_type === 'heartbeat');
    if (hbMsg) {{
      const note = (hbMsg.payload && hbMsg.payload.note) || '';
      document.getElementById('hb-text').textContent = note.slice(0,120);
    }}
  }};

  evtSrc.onerror = function() {{
    // On SSE error fallback to polling
    setTimeout(() => window.location.reload(), 5000);
  }};
}})();
</script>
</body>
</html>"""


def _render_feed(feed: list) -> str:
    parts = []
    for item in feed:
        sender = item.get("sender", "broadcast")
        sender_class = {
            "satellite": "from-satellite satellite",
            "ground": "from-ground ground",
            "operator": "from-operator operator",
        }.get(sender, "from-broadcast")

        item_id = html_mod.escape(str(item.get("id", "")))
        timestamp = str(item.get("time", ""))
        ts = html_mod.escape(timestamp[11:19] if len(timestamp) > 18 else timestamp)
        msg_type = str(item.get("msg_type", ""))
        mtype = html_mod.escape(msg_type)
        sender_esc = html_mod.escape(str(sender))

        meta = (
            f'<div class="msg-meta">'
            f'<span class="sender">{sender_esc}</span>'
            f'<span class="ts">{ts}</span>'
            f'<span class="type-tag">{mtype}</span>'
            f'</div>'
        )
        body = _render_payload_server(item.get("payload"), msg_type)
        extra = ""
        if msg_type == "llm_thinking":
            extra = (
                '<div class="llm-streaming">'
                '<div class="llm-dots"><span></span><span></span><span></span></div>'
                'LFM reasoning in progress&hellip;</div>'
            )

        cell_attr = f' data-cell="{html_mod.escape(str(item.get("cell_id","") or ""))}"' if item.get("cell_id") else ""
        parts.append(
            f'<div class="msg {sender_class}" id="m{item_id}" data-mtype="{mtype}"{cell_attr}>'
            f'{meta}<div class="bubble">{body}{extra}</div></div>'
        )
    return "\n".join(parts)


def _render_payload_server(payload, msg_type: str) -> str:
    if not isinstance(payload, dict):
        return f'<div class="plain-body">{html_mod.escape(str(payload))}</div>'

    has_tabs = (
        payload.get("thinking")
        or (payload.get("tool_calls") and len(payload["tool_calls"]) > 0)
        or payload.get("response")
    )

    if not has_tabs:
        parts = []
        if payload.get("action"):
            parts.append(f'<span class="action-tag tag-action">Action: {html_mod.escape(str(payload["action"]))}</span>')
        if payload.get("status"):
            parts.append(f'<span class="action-tag tag-status">Status: {html_mod.escape(str(payload["status"]))}</span>')
        note = payload.get("note") or payload.get("content") or payload.get("message") or ""
        tags_html = f'<div style="padding:8px 12px 4px">{"".join(parts)}</div>' if parts else ""
        note_html = f'<div class="plain-body">{html_mod.escape(str(note))}</div>' if note else ""
        return tags_html + note_html or '<div class="plain-body" style="color:var(--muted)">(empty)</div>'

    import random
    import string
    uid = "srv" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    tabs = []
    panels = []

    if payload.get("thinking"):
        tabs.append(
            f'<button class="tab-btn t-think active" onclick="switchTab(\'{uid}\',\'think\',this)">&#129504; Thinking</button>'
        )
        panels.append(
            f'<div class="tab-panel active" id="{uid}-think">'
            f'<div class="think-body">{html_mod.escape(payload["thinking"])}</div>'
            f'</div>'
        )

    tool_calls = payload.get("tool_calls") or []
    if isinstance(tool_calls, str):
        try:
            tool_calls = json.loads(tool_calls)
        except Exception:
            tool_calls = []
    if tool_calls:
        first = not payload.get("thinking")
        tabs.append(
            f'<button class="tab-btn t-tool{"  active" if first else ""}" '
            f'onclick="switchTab(\'{uid}\',\'tool\',this)">&#128295; Tools ({len(tool_calls)})</button>'
        )
        tc_html = ""
        for tc in tool_calls:
            name = html_mod.escape(str(tc.get("name", "unknown")))
            args = tc.get("arguments", {})
            tc_html += (
                f'<div class="tool-call">'
                f'<span class="tool-name">{name}</span>'
                f'<div class="tool-args">{html_mod.escape(json.dumps(args, indent=2))}</div>'
                f'</div>'
            )
        panels.append(
            f'<div class="tab-panel{"  active" if first else ""}" id="{uid}-tool">{tc_html}</div>'
        )

    if payload.get("response"):
        first = not payload.get("thinking") and not tool_calls
        tabs.append(
            f'<button class="tab-btn t-resp{"  active" if first else ""}" '
            f'onclick="switchTab(\'{uid}\',\'resp\',this)">&#128226; Response</button>'
        )
        panels.append(
            f'<div class="tab-panel{"  active" if first else ""}" id="{uid}-resp">'
            f'<div class="resp-text">{html_mod.escape(str(payload["response"]))}</div>'
            f'</div>'
        )

    return '<div class="tabs">' + "".join(tabs) + "</div>" + "".join(panels)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("satellite_debug:app", host="0.0.0.0", port=8080, reload=True)
