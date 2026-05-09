/**
 * Anukriti Swarm — Live Orchestration UI
 *
 * Live backend-wired replacement for the previous static MOCK_RESULT
 * renderer. The frontend now does:
 *
 *   1. Health-check the backend on page load.
 *      - Backend reachable: use live POST /api/run (commit 11) and
 *        then WS /ws/run (commit 12) for event streaming.
 *      - Backend unreachable: fall back to the previous static
 *        mock so the demo still works offline.
 *
 *   2. On "Activate Swarm" click, submit the scope tuple to
 *      POST /api/run and render the returned UnifiedExecutionReport.
 *
 *   3. (commit 12 replaces the sync fetch with a WebSocket stream
 *      so events animate as they arrive.)
 *
 * Zero build step; pure HTML/CSS/JS + vendored D3 (commit 14).
 */

const BACKEND = "http://127.0.0.1:8000";
const STATE = {
  backend_live: false,
  last_report: null,  // UnifiedExecutionReport dict
  last_events: [],    // RuntimeEvent dicts
};

// ---------------------------------------------------------------------------
// Offline fallback — previous MOCK_RESULT kept so the page remains usable
// without the backend. Used ONLY when /api/health is unreachable.
// ---------------------------------------------------------------------------

const MOCK_RESULT = {
  correlation_id: "mock_" + Math.random().toString(36).slice(2, 10),
  source: "offline_mock",
  drug: "clopidogrel", gene: "CYP2C19", population: "SAS", genotype: "*2/*2",
  activated_agents: ["orchestrator", "population_aware_retriever",
                      "graph_reasoner", "sufficiency_checkpoint", "narrative_agent"],
  final_recommendation: {
    allows_synthesis: true,
    text: "Use prasugrel or ticagrelor instead.",
    evidence_refs: ["PMID:34032273", "PA166169660"],
  },
  evidence_sufficiency: {
    sufficiency_decision: "sufficient", verdict: "supported",
    uncertainty_score: "low", coverage_ratio: 1.0,
    trace: { retrieved_evidence: ["PMID:34032273", "PA166169660"] },
  },
  uncertainty_analysis: {
    uncertainty_score: "low", uncertainty_action: "proceed",
    bias_findings: [],
  },
  deterministic_rules: ["cpic.activity_score", "cpic.recommendation", "V10"],
};

// ---------------------------------------------------------------------------
// Backend health check on page load
// ---------------------------------------------------------------------------

async function checkBackend() {
  try {
    const r = await fetch(`${BACKEND}/api/health`, { method: "GET" });
    if (!r.ok) throw new Error("non-200");
    const body = await r.json();
    STATE.backend_live = body.status === "ok";
    renderBackendStatus(true, body);
    populateScenarios();
  } catch (err) {
    STATE.backend_live = false;
    renderBackendStatus(false, { error: String(err) });
  }
}

function renderBackendStatus(live, body) {
  let el = document.getElementById("backend-status");
  if (!el) {
    el = document.createElement("div");
    el.id = "backend-status";
    el.className = "backend-status";
    const header = document.querySelector(".header-content");
    if (header) header.appendChild(el);
  }
  if (live) {
    el.innerHTML = `<span class="status-live">● live</span>
      <span class="dim">backend v${body.version || "?"}</span>`;
  } else {
    el.innerHTML = `<span class="status-offline">● offline</span>
      <span class="dim">running in mock mode — start uvicorn on :8000 for live runs</span>`;
  }
}

// ---------------------------------------------------------------------------
// Populate scenario dropdown from /api/scenarios
// ---------------------------------------------------------------------------

async function populateScenarios() {
  try {
    const r = await fetch(`${BACKEND}/api/scenarios`);
    if (!r.ok) return;
    const body = await r.json();
    // The existing form has hard-coded gene/drug/population/genotype
    // selects. We add a "Canonical scenario" selector that auto-fills
    // those dropdowns when changed.
    const form = document.querySelector(".input-grid");
    if (!form || document.getElementById("scenario-picker")) return;

    const group = document.createElement("div");
    group.className = "input-group";
    group.style.gridColumn = "1 / -1";
    group.innerHTML = `
      <label for="scenario-picker">Canonical Scenario</label>
      <select id="scenario-picker" onchange="applyScenario(this.value)">
        <option value="">— custom —</option>
        ${body.scenarios.map(s => `<option value="${s.id}"
          data-drug="${s.drug}" data-gene="${s.gene}"
          data-population="${s.population}" data-genotype="${s.genotype}">
          ${s.title}
        </option>`).join("")}
      </select>
    `;
    form.insertBefore(group, form.firstChild);
  } catch (err) {
    console.warn("scenario populate failed:", err);
  }
}

function applyScenario(scenarioId) {
  if (!scenarioId) return;
  const opt = document.querySelector(`#scenario-picker option[value="${scenarioId}"]`);
  if (!opt) return;
  const gene = opt.dataset.gene;
  const drug = opt.dataset.drug;
  const pop = opt.dataset.population;
  const gt = opt.dataset.genotype;

  // Set existing selects if the values match; otherwise leave them alone.
  setSelect("gene", gene);
  setSelect("drug", drug);
  setSelect("population", pop);
  setSelect("alleles", gt);
}

function setSelect(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  // Add the option if it doesn't exist (handles HLA-B*15:02/positive etc.)
  if (!Array.from(el.options).some(o => o.value === value)) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = value;
    el.appendChild(opt);
  }
  el.value = value;
}

// ---------------------------------------------------------------------------
// Main entry — "Activate Swarm" button
// ---------------------------------------------------------------------------

async function runAnalysis() {
  const gene = document.getElementById("gene").value;
  const drug = document.getElementById("drug").value;
  const population = document.getElementById("population").value;
  const genotype = document.getElementById("alleles").value;

  revealSections();

  if (!STATE.backend_live) {
    // Offline fallback — fill the original sections with the mock.
    renderFromMock();
    return;
  }

  renderLiveStart({ drug, gene, population, genotype });
  STATE.last_events = [];

  // Prefer WebSocket streaming when available; fall back to sync
  // fetch on WS failure (e.g. browser blocks WS, proxy strips it).
  try {
    await runAnalysisWebSocket({ drug, gene, population, genotype });
  } catch (wsErr) {
    console.warn("WS run failed, falling back to POST /api/run:", wsErr);
    await runAnalysisFetch({ drug, gene, population, genotype });
  }
}

// --- WebSocket path (live streaming) ---------------------------------------

function runAnalysisWebSocket(scope) {
  return new Promise((resolve, reject) => {
    const wsUrl = BACKEND.replace(/^http/, "ws") + "/ws/run";
    let ws;
    try {
      ws = new WebSocket(wsUrl);
    } catch (err) {
      reject(err);
      return;
    }

    let finalized = false;
    ws.onopen = () => {
      ws.send(JSON.stringify(scope));
    };
    ws.onmessage = (msg) => {
      let data;
      try {
        data = JSON.parse(msg.data);
      } catch (err) {
        console.warn("non-JSON WS frame:", msg.data);
        return;
      }
      if (data.type === "event") {
        handleLiveEvent(data);
      } else if (data.type === "report") {
        STATE.last_report = data.report;
        renderFinalizeFromReport(data.report);
        finalized = true;
      } else if (data.type === "error") {
        renderRunError(`${data.code}: ${data.detail}`);
        finalized = true;
      }
    };
    ws.onclose = () => {
      if (finalized) resolve();
      else reject(new Error("WS closed before report"));
    };
    ws.onerror = (err) => {
      if (!finalized) reject(err);
    };
  });
}

// Incremental event handler — appends to the trace + incrementally
// refreshes the orchestration + metrics panels so the UI animates.
function handleLiveEvent(event) {
  STATE.last_events.push(event);
  appendTraceLine(event);

  // On specific event kinds, partially populate panels so the user
  // sees progress before the run completes.
  switch (event.kind) {
    case "retrieval_complete":
      renderInlineRetrieval(event.payload);
      break;
    case "graph_traversal":
      renderInlineGraph(event.payload);
      break;
    case "sufficiency_decision":
      renderInlineSufficiency(event.payload);
      break;
    case "verification_checkpoint":
      renderInlineVerdict(event.payload);
      break;
    case "uncertainty_transition":
      renderInlineUncertainty(event.payload);
      break;
  }
}

function appendTraceLine(event) {
  const el = document.getElementById("trace-output");
  if (!el) return;
  const cls = event.kind === "run_failed" ? "error"
            : event.kind === "safe_abstention" ? "warning" : "success";
  const kindLabel = event.kind.replace(/_/g, " ");
  const detail = formatEventDetail(event);
  const line = document.createElement("div");
  line.className = `trace-line ${cls}`;
  line.innerHTML = `● ${kindLabel}
    <span style="color:var(--text-dim)">${detail}</span>`;
  // First event clears the "Connecting..." placeholder.
  if (el.dataset.firstEventReceived !== "true") {
    el.innerHTML = "";
    el.dataset.firstEventReceived = "true";
  }
  el.appendChild(line);
  // Autoscroll to the newest event.
  el.scrollTop = el.scrollHeight;
}

function renderInlineRetrieval(payload) {
  const el = document.getElementById("evidence-output");
  if (!el) return;
  el.innerHTML = `
    <div class="established"><strong>Retrieval in progress:</strong>
      ${payload.total_retrieved} docs via ${payload.strategy}</div>
    <div style="margin-top:0.5rem">${(payload.citations || []).map(c =>
      `<div class="citation" style="margin:0.2rem 0">📄 ${c}</div>`).join("")}</div>
  `;
}

function renderInlineGraph(payload) {
  const el = document.getElementById("agent-graph");
  if (!el) return;
  el.innerHTML = `<pre style="font-size:0.75rem;color:var(--text-secondary);line-height:1.4">
  KG traversal:

    ${payload.start_id || "(no start)"}
       ⇣  (${payload.path_count} path${payload.path_count === 1 ? "" : "s"})
    ${payload.goal_id || "(no goal)"}
  </pre>`;
}

function renderInlineSufficiency(payload) {
  const el = document.getElementById("population-output");
  if (!el) return;
  const coverage = Math.round((payload.coverage_ratio || 0) * 100);
  el.innerHTML = `
    <div class="metric-card"><div class="metric-value">${payload.decision}</div>
      <div class="metric-label">Sufficiency Decision</div></div>
    <div class="metric-card"><div class="metric-value">${coverage}%</div>
      <div class="metric-label">Coverage</div></div>
    <div class="metric-card"><div class="metric-value">${(payload.missing_facets || []).length}</div>
      <div class="metric-label">Missing Facets</div></div>
    <div class="metric-card"><div class="metric-value">${(payload.uncertain_facets || []).length}</div>
      <div class="metric-label">Uncertain Facets</div></div>
  `;
}

function renderInlineVerdict(payload) {
  const el = document.getElementById("verification-output");
  if (!el) return;
  const color = payload.verdict === "supported" ? "var(--accent-green)"
              : payload.verdict === "uncertain" ? "var(--accent-yellow)"
              : "var(--accent-red)";
  el.innerHTML = `
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-value" style="color:${color}">${payload.verdict}</div>
        <div class="metric-label">Verdict (${payload.rule_id})</div></div>
      <div class="metric-card">
        <div class="metric-value">${payload.pathway_count || 0}</div>
        <div class="metric-label">KG Paths</div></div>
    </div>
    <div style="margin-top:0.75rem;font-family:var(--font-mono);font-size:0.8rem;color:var(--text-dim)">
      ${payload.rationale || ""}
    </div>
  `;
}

function renderInlineUncertainty(payload) {
  const el = document.getElementById("confidence-output");
  if (!el) return;
  const score = payload.score;
  const confidence = { low: 0.95, moderate: 0.7, high: 0.4, unsafe: 0.1 }[score] || 0.5;
  const cls = confidence >= 0.85 ? "high" : confidence >= 0.6 ? "moderate" : "low";
  el.innerHTML = `
    <div class="conf-bar"><span class="conf-label">Uncertainty</span>
      <div class="conf-track"><div class="conf-fill ${cls}"
        style="width:${Math.min(100, confidence * 100)}%"></div></div>
      <span class="conf-value">${score}</span></div>
    <div style="margin-top:0.5rem;font-family:var(--font-mono);font-size:0.8rem;color:var(--text-dim)">
      action: ${payload.action} · ${payload.rationale || ""}
    </div>
  `;
}

function renderFinalizeFromReport(report) {
  // Terminal call once the run completes; fills any panels that
  // weren't populated inline and refreshes the full narrative /
  // provenance / orchestration panels with the aggregated report.
  renderSufficiencyPanel(report);
  renderPopulationIntel(report);
  renderKnowledgeGraph(report);
  renderGovernance(report);
  renderOrchestrationFromReport(report);
  renderPharmacogeneFromReport(report);
  renderNarrativeFromReport(report);
  renderProvenanceFromReport(report);
}

// --- Fetch fallback (sync) -------------------------------------------------

async function runAnalysisFetch(scope) {
  try {
    const r = await fetch(`${BACKEND}/api/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(scope),
    });
    if (!r.ok) throw new Error(`backend returned ${r.status}: ${await r.text()}`);
    const body = await r.json();
    STATE.last_report = body.report;
    STATE.last_events = body.events;
    renderFromReport(body.report, body.events);
  } catch (err) {
    console.error("live run failed:", err);
    renderRunError(err);
  }
}

function revealSections() {
  const sections = [
    "swarm-activity", "sufficiency-section", "population-intel-section",
    "kg-explorer-section", "governance-section",
    "orchestration-viz", "population-section",
    "pharmacogene-section", "evidence-section", "verification-section",
    "confidence-section", "narrative-section", "provenance-section",
  ];
  sections.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.remove("hidden");
  });
}

function renderLiveStart(scope) {
  const el = document.getElementById("trace-output");
  if (!el) return;
  el.dataset.firstEventReceived = "false";
  el.innerHTML = `<div class="trace-line success">● Connecting to swarm runtime...</div>
    <div class="trace-line">  drug=${scope.drug} gene=${scope.gene}
      population=${scope.population} genotype=${scope.genotype}</div>`;
}

function renderRunError(err) {
  const el = document.getElementById("trace-output");
  if (!el) return;
  el.innerHTML = `<div class="trace-line error">● Run failed: ${String(err)}</div>`;
}

// ---------------------------------------------------------------------------
// Rendering from a live UnifiedExecutionReport
// ---------------------------------------------------------------------------

function renderFromReport(report, events) {
  renderTraceFromEvents(events || []);
  renderSufficiencyPanel(report);
  renderPopulationIntel(report);
  renderKnowledgeGraph(report);
  renderGovernance(report);
  renderOrchestrationFromReport(report);
  renderPopulationFromReport(report);
  renderPharmacogeneFromReport(report);
  renderEvidenceFromReport(report);
  renderVerificationFromReport(report);
  renderConfidenceFromReport(report);
  renderNarrativeFromReport(report);
  renderProvenanceFromReport(report);
}

// ---------------------------------------------------------------------------
// Dedicated panels — Evidence Sufficiency + Population Intelligence
// ---------------------------------------------------------------------------

function renderSufficiencyPanel(report) {
  const el = document.getElementById("sufficiency-output");
  if (!el) return;
  const ev = report.evidence_sufficiency || {};
  const unc = report.uncertainty_analysis || {};
  const rec = report.final_recommendation || {};

  const decision = ev.sufficiency_decision || "?";
  const verdict = ev.verdict || "?";
  const uncertainty = unc.uncertainty_score || "?";
  const gate = rec.allows_synthesis;

  // Colour based on decision family.
  const decisionColor = decisionColorFor(decision);
  const verdictColor = verdictColorFor(verdict);
  const uncertaintyColor = uncertaintyColorFor(uncertainty);
  const gateColor = gate ? "var(--accent-green)" : "var(--accent-red)";
  const gateLabel = gate ? "SYNTHESIS ALLOWED" : "SYNTHESIS BLOCKED";

  const trace = ev.trace || {};
  const missing = ev.missing_facets || trace.missing_hops || [];
  const coverage = Math.round((ev.coverage_ratio || 0) * 100);

  el.innerHTML = `
    <div class="metrics-grid">
      <div class="metric-card"><div class="metric-value" style="color:${decisionColor}">${decision}</div>
        <div class="metric-label">Sufficiency Decision</div></div>
      <div class="metric-card"><div class="metric-value" style="color:${verdictColor}">${verdict}</div>
        <div class="metric-label">Set-Level Verdict</div></div>
      <div class="metric-card"><div class="metric-value" style="color:${uncertaintyColor}">${uncertainty}</div>
        <div class="metric-label">Uncertainty Tier</div></div>
      <div class="metric-card"><div class="metric-value">${coverage}%</div>
        <div class="metric-label">Facet Coverage</div></div>
    </div>
    <div style="margin-top:1rem;padding:0.75rem;background:var(--bg-secondary);
         border-left:3px solid ${gateColor};border-radius:var(--radius)">
      <div style="font-family:var(--font-mono);font-size:0.85rem;color:${gateColor};
           font-weight:600">${gateLabel}</div>
      ${!gate ? `<div style="margin-top:0.25rem;font-size:0.85rem;color:var(--text-secondary)">
        ${rec.blocking_reason || ""}</div>` : ""}
    </div>
    ${missing.length > 0 ? `
      <div style="margin-top:0.75rem">
        <div style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:0.25rem;
             text-transform:uppercase;letter-spacing:0.05em">Missing / Uncertain Facets</div>
        <div style="font-family:var(--font-mono);font-size:0.85rem">
          ${missing.map(f => `<span class="chip chip-warn">${f}</span>`).join(" ")}
        </div>
      </div>
    ` : ""}
    ${(report.deterministic_rules || []).length > 0 ? `
      <div style="margin-top:0.75rem">
        <div style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:0.25rem;
             text-transform:uppercase;letter-spacing:0.05em">Rules Triggered</div>
        <div style="font-family:var(--font-mono);font-size:0.85rem">
          ${report.deterministic_rules.map(r => `<span class="chip">${r}</span>`).join(" ")}
        </div>
      </div>
    ` : ""}
  `;
}

function renderPopulationIntel(report) {
  const el = document.getElementById("population-intel-output");
  if (!el) return;
  const unc = report.uncertainty_analysis || {};
  const bias = unc.bias_findings || [];
  const ev = report.evidence_sufficiency || {};
  const paths = report.graph_traversal || [];

  const popFreqs = extractPopulationFrequencies(paths, report.population);

  el.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem">
      <div>
        <div style="font-size:0.8rem;color:var(--text-secondary);text-transform:uppercase;
             letter-spacing:0.05em;margin-bottom:0.5rem">Target Population</div>
        <div style="font-size:2rem;font-family:var(--font-mono);color:var(--accent-cyan);
             font-weight:700">${report.population}</div>
        <div style="font-size:0.85rem;color:var(--text-dim);margin-top:0.25rem">
          ${popLabel(report.population)}
        </div>
      </div>
      <div>
        <div style="font-size:0.8rem;color:var(--text-secondary);text-transform:uppercase;
             letter-spacing:0.05em;margin-bottom:0.5rem">Allele Frequency (on path)</div>
        ${popFreqs.length === 0
          ? `<div style="color:var(--text-dim);font-size:0.85rem">no frequency data on traversed paths</div>`
          : popFreqs.map(pf => `
            <div class="conf-bar">
              <span class="conf-label">${pf.allele}</span>
              <div class="conf-track"><div class="conf-fill high"
                style="width:${Math.min(100, pf.freq * 100)}%"></div></div>
              <span class="conf-value">${(pf.freq * 100).toFixed(1)}%</span>
            </div>
          `).join("")}
      </div>
    </div>
    <div style="margin-top:1rem">
      <div style="font-size:0.8rem;color:var(--text-secondary);text-transform:uppercase;
           letter-spacing:0.05em;margin-bottom:0.5rem">Bias Signals</div>
      ${bias.length === 0
        ? `<div style="color:var(--accent-green);font-size:0.85rem">
             ● none — target population adequately represented</div>`
        : `<div>${bias.map(b => `
            <div style="padding:0.5rem;margin:0.25rem 0;border-left:3px solid var(--accent-yellow);
                 background:var(--bg-secondary);border-radius:var(--radius);font-size:0.85rem">
              <div style="font-family:var(--font-mono);color:var(--accent-yellow);
                   font-weight:600">${b.kind}</div>
              <div style="color:var(--text-secondary);margin-top:0.25rem">${b.reason}</div>
            </div>`).join("")}</div>`
      }
    </div>
  `;
}

// Helpers --------------------------------------------------------------

function decisionColorFor(decision) {
  switch (decision) {
    case "sufficient": case "pass_with_caveat": return "var(--accent-green)";
    case "downgrade": case "request_more": case "escalate": return "var(--accent-yellow)";
    case "abstain": case "block": return "var(--accent-red)";
    default: return "var(--text-secondary)";
  }
}

function verdictColorFor(verdict) {
  switch (verdict) {
    case "supported": return "var(--accent-green)";
    case "uncertain": case "insufficient": return "var(--accent-yellow)";
    case "refuted": case "conflicting": return "var(--accent-red)";
    default: return "var(--text-secondary)";
  }
}

function uncertaintyColorFor(score) {
  switch (score) {
    case "low": return "var(--accent-green)";
    case "moderate": return "var(--accent-yellow)";
    case "high": return "var(--accent-red)";
    case "unsafe": return "var(--accent-red)";
    default: return "var(--text-secondary)";
  }
}

function popLabel(code) {
  return {
    AFR: "African", AMR: "Admixed American", EAS: "East Asian",
    EUR: "European", SAS: "South Asian",
  }[code] || code;
}

function extractPopulationFrequencies(paths, population) {
  // Scan graph paths for HIGHER_FREQUENCY_IN edges targeting the
  // current population; surface (allele, weight) pairs.
  const freqs = [];
  const seen = new Set();
  const popNode = `population:${population}`;
  for (const path of paths || []) {
    for (const edge of path.edges || []) {
      if (edge.kind === "higher_frequency_in" && edge.target_id === popNode) {
        const allele = edge.source_id.replace(/^allele:/, "");
        if (!seen.has(allele)) {
          seen.add(allele);
          freqs.push({ allele, freq: edge.weight });
        }
      }
    }
  }
  return freqs.sort((a, b) => b.freq - a.freq);
}

function renderTraceFromEvents(events) {
  const el = document.getElementById("trace-output");
  if (!el) return;
  if (events.length === 0) {
    el.innerHTML = `<div class="trace-line warning">● no events captured</div>`;
    return;
  }
  el.innerHTML = events.map(e => {
    const cls = e.kind === "run_failed" ? "error"
              : e.kind === "safe_abstention" ? "warning" : "success";
    const kindLabel = e.kind.replace(/_/g, " ");
    const detail = formatEventDetail(e);
    return `<div class="trace-line ${cls}">● ${kindLabel}
      <span style="color:var(--text-dim)">${detail}</span></div>`;
  }).join("");
}

function formatEventDetail(event) {
  const p = event.payload || {};
  switch (event.kind) {
    case "run_started":
      return `${p.drug}+${p.gene}+${p.population}`;
    case "agent_activated":
      return p.agent || "";
    case "retrieval_complete":
      return `${p.total_retrieved} docs · ${p.strategy}`;
    case "graph_traversal":
      return `${p.path_count} paths · ${p.start_id} → ${p.goal_id}`;
    case "sufficiency_decision":
      return `${p.decision} · coverage ${Math.round((p.coverage_ratio || 0) * 100)}%`;
    case "verification_checkpoint":
      return `${p.verdict} (${p.rule_id})`;
    case "uncertainty_transition":
      return `${p.score} · action=${p.action}`;
    case "provenance_persisted":
      return `${p.record_count} records`;
    case "synthesis_emitted":
      return `audiences: ${(p.audiences || []).join(", ")}`;
    case "safe_abstention":
      return `decision=${p.decision} verdict=${p.verdict}`;
    case "run_completed":
      return `${p.duration_ms}ms · ${(p.activated_agents || []).length} agents`;
    case "run_failed":
      return p.error || "";
    default:
      return "";
  }
}

function renderOrchestrationFromReport(report) {
  const el = document.getElementById("agent-graph");
  if (!el) return;
  const agents = report.activated_agents || [];
  el.innerHTML = `<pre style="font-size:0.75rem;color:var(--text-secondary);line-height:1.4">
  Orchestration lifecycle (${agents.length} agents):

  ${agents.map((a, i) => `${i + 1}. ${a}`).join("\n  ")}

  Graph paths traversed: ${(report.graph_traversal || []).length}
  Deterministic rules triggered: ${(report.deterministic_rules || []).length}
  </pre>`;
}

function renderPopulationFromReport(report) {
  const el = document.getElementById("population-output");
  if (!el) return;
  const bias = (report.uncertainty_analysis || {}).bias_findings || [];
  const ev = report.evidence_sufficiency || {};
  const freqEvents = (STATE.last_events || []).filter(e =>
    e.kind === "retrieval_complete" || e.kind === "graph_traversal"
  );
  el.innerHTML = `
    <div class="metric-card"><div class="metric-value">${report.population}</div>
      <div class="metric-label">Target Population</div></div>
    <div class="metric-card"><div class="metric-value">${Math.round(((ev.coverage_ratio) || 0) * 100)}%</div>
      <div class="metric-label">Coverage</div></div>
    <div class="metric-card"><div class="metric-value">${bias.length}</div>
      <div class="metric-label">Bias Findings</div></div>
    <div class="metric-card"><div class="metric-value">${(report.graph_traversal || []).length}</div>
      <div class="metric-label">KG Paths</div></div>
  `;
}

function renderPharmacogeneFromReport(report) {
  const el = document.getElementById("pharmacogene-output");
  if (!el) return;
  // The runtime stores phenotype via the orchestration pathway; read from
  // the trace for now.
  const ev = report.evidence_sufficiency || {};
  el.innerHTML = `
    <div class="established"><strong>Gene:</strong> ${report.gene}
      <span class="citation">[ESTABLISHED]</span></div>
    <div class="established"><strong>Genotype:</strong> ${report.genotype}</div>
    <div class="established"><strong>Decision:</strong> ${ev.sufficiency_decision || "?"}</div>
    <div class="established" style="border-color:var(--accent-red)">
      <strong>Verdict:</strong> ${ev.verdict || "?"}</div>
  `;
}

function renderEvidenceFromReport(report) {
  const el = document.getElementById("evidence-output");
  if (!el) return;
  const ev = report.evidence_sufficiency || {};
  const refs = (ev.trace || {}).retrieved_evidence || [];
  const rec = report.final_recommendation || {};
  el.innerHTML = `
    <div class="established"><strong>Evidence Grounding:</strong>
      ${Math.round(((ev.coverage_ratio) || 0) * 100)}%</div>
    <div style="margin-top:0.75rem">${refs.map(c =>
      `<div class="citation" style="margin:0.25rem 0">📄 ${c}</div>`).join("")}</div>
    <div class="established" style="margin-top:0.75rem">
      <strong>Recommendation:</strong> ${rec.text || "(refused)"}
    </div>
  `;
}

function renderVerificationFromReport(report) {
  const el = document.getElementById("verification-output");
  if (!el) return;
  const ev = report.evidence_sufficiency || {};
  const rec = report.final_recommendation || {};
  const gate = rec.allows_synthesis ? "PASS" : "BLOCK";
  const gateColor = rec.allows_synthesis ? "var(--accent-green)" : "var(--accent-red)";
  el.innerHTML = `
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-value" style="color:${gateColor}">${gate}</div>
        <div class="metric-label">Gate</div></div>
      <div class="metric-card">
        <div class="metric-value">${ev.verdict || "?"}</div>
        <div class="metric-label">Verdict</div></div>
      <div class="metric-card">
        <div class="metric-value">${report.deterministic_rules.length}</div>
        <div class="metric-label">Rules Triggered</div></div>
      <div class="metric-card">
        <div class="metric-value">${report.activated_agents.length}</div>
        <div class="metric-label">Agents Activated</div></div>
    </div>
  `;
}

function renderConfidenceFromReport(report) {
  const el = document.getElementById("confidence-output");
  if (!el) return;
  const ev = report.evidence_sufficiency || {};
  const unc = report.uncertainty_analysis || {};
  const score = unc.uncertainty_score || "unknown";
  const confidence = { low: 0.95, moderate: 0.7, high: 0.4, unsafe: 0.1 }[score] || 0.5;
  const stages = {
    Coverage: ev.coverage_ratio || 0,
    Verdict: ev.verdict === "supported" ? 1.0 : ev.verdict === "uncertain" ? 0.5 : 0.2,
    Uncertainty: confidence,
    Final: rec_confidence(report),
  };
  el.innerHTML = Object.entries(stages).map(([k, v]) => {
    const cls = v >= 0.85 ? "high" : v >= 0.6 ? "moderate" : "low";
    return `<div class="conf-bar"><span class="conf-label">${k}</span>
      <div class="conf-track"><div class="conf-fill ${cls}"
        style="width:${Math.min(100, v * 100)}%"></div></div>
      <span class="conf-value">${v.toFixed(2)}</span></div>`;
  }).join("");
}

function rec_confidence(report) {
  return (report.final_recommendation || {}).allows_synthesis ? 0.9 : 0.1;
}

function renderNarrativeFromReport(report) {
  const el = document.getElementById("narrative-output");
  if (!el) return;
  const rec = report.final_recommendation || {};
  if (!rec.allows_synthesis) {
    el.innerHTML = `
      <div class="established" style="border-color:var(--accent-red)">
        <strong>Safe Abstention:</strong> synthesis withheld.</div>
      <div class="narrative" style="color:var(--text-dim);margin-top:0.75rem">
        ${rec.blocking_reason || "(unspecified)"}
      </div>
    `;
    return;
  }
  el.innerHTML = `
    <div class="narrative">${rec.text || "(empty)"}</div>
    <div style="margin-top:0.75rem">${(rec.evidence_refs || []).map(ref =>
      `<span class="citation" style="margin-right:0.5rem">${ref}</span>`).join("")}</div>
  `;
}

function renderProvenanceFromReport(report) {
  const el = document.getElementById("provenance-output");
  if (!el) return;
  el.innerHTML = `
    <div style="font-family:var(--font-mono);font-size:0.8rem;color:var(--text-secondary);line-height:1.8">
      <div>Report ID: ${report.report_id}</div>
      <div>Correlation: ${report.correlation_id}</div>
      <div>Duration: ${report.total_duration_ms}ms</div>
      <div>Rules triggered: ${(report.deterministic_rules || []).join(", ")}</div>
      <div>Provenance records: ${(report.provenance_chain || []).length}</div>
      <div>Source: live backend</div>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Knowledge Graph Explorer (D3 force-directed) — phase 4 commit 14
// ---------------------------------------------------------------------------

function renderKnowledgeGraph(report) {
  const paths = report.graph_traversal || [];
  const svgEl = document.getElementById("kg-svg");
  const legendEl = document.getElementById("kg-legend");
  if (!svgEl || !legendEl) return;

  // Clear previous render.
  svgEl.innerHTML = "";
  legendEl.innerHTML = "";

  if (paths.length === 0) {
    svgEl.innerHTML = `<text x="50%" y="50%" fill="#64748b"
      font-family="JetBrains Mono, monospace" font-size="13"
      text-anchor="middle">no graph paths traversed for this run</text>`;
    return;
  }

  // Extract nodes + edges from all traversed paths. The paths come
  // from the backend already as GraphPath.to_dict entries, each with
  // nodes and edges arrays.
  const nodeMap = new Map();
  const edges = [];
  const edgeKeys = new Set();
  for (const path of paths) {
    for (const nodeId of (path.nodes || [])) {
      if (!nodeMap.has(nodeId)) {
        const [kind, ...nameParts] = nodeId.split(":");
        nodeMap.set(nodeId, {
          id: nodeId, kind, name: nameParts.join(":"),
        });
      }
    }
    for (const edge of (path.edges || [])) {
      const key = `${edge.source_id}|${edge.kind}|${edge.target_id}`;
      if (edgeKeys.has(key)) continue;
      edgeKeys.add(key);
      edges.push({
        source: edge.source_id,
        target: edge.target_id,
        kind: edge.kind,
        weight: edge.weight,
      });
    }
  }

  const nodes = Array.from(nodeMap.values());
  // Lazy-require d3 (loaded via the <script src> tag in index.html).
  if (typeof d3 === "undefined") {
    svgEl.innerHTML = `<text x="50%" y="50%" fill="#ef4444"
      font-family="JetBrains Mono, monospace" font-size="13"
      text-anchor="middle">d3.js not loaded — KG explorer disabled</text>`;
    return;
  }

  // Colour palette for the 10 closed NodeKinds.
  const NODE_COLOURS = {
    population: "#06b6d4",
    ancestry: "#0ea5e9",
    gene: "#10b981",
    variant: "#22c55e",
    allele: "#84cc16",
    phenotype: "#f59e0b",
    drug: "#ef4444",
    adverse_reaction: "#dc2626",
    guideline: "#8b5cf6",
    evidence_paper: "#6366f1",
  };
  const nodeColour = (n) => NODE_COLOURS[n.kind] || "#94a3b8";

  // Bounding box from the parent card; D3 uses numeric sizes.
  const rect = svgEl.getBoundingClientRect();
  const width = rect.width || 800;
  const height = 420;
  const svg = d3.select(svgEl).attr("viewBox", `0 0 ${width} ${height}`);

  // Arrowhead marker so directed edges are visible.
  svg.append("defs").append("marker")
    .attr("id", "kg-arrow")
    .attr("viewBox", "0 -5 10 10")
    .attr("refX", 22)
    .attr("refY", 0)
    .attr("markerWidth", 6)
    .attr("markerHeight", 6)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "#64748b");

  // Force simulation.
  const simulation = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(edges).id(d => d.id).distance(90).strength(0.5))
    .force("charge", d3.forceManyBody().strength(-280))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(32));

  // Edges first so they render behind nodes.
  const link = svg.append("g")
    .selectAll("line")
    .data(edges)
    .join("line")
    .attr("stroke", "#2d3748")
    .attr("stroke-width", d => 1 + (d.weight || 0) * 1.5)
    .attr("marker-end", "url(#kg-arrow)");

  // Edge-kind labels (only on non-trivial edges to reduce clutter).
  const linkLabel = svg.append("g")
    .selectAll("text")
    .data(edges.filter(e => e.kind !== "higher_frequency_in" || e.weight >= 0.05))
    .join("text")
    .attr("font-family", "JetBrains Mono, monospace")
    .attr("font-size", 8)
    .attr("fill", "#64748b")
    .attr("text-anchor", "middle")
    .text(d => d.kind);

  // Nodes.
  const node = svg.append("g")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .call(d3.drag()
      .on("start", (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on("drag", (event, d) => {
        d.fx = event.x; d.fy = event.y;
      })
      .on("end", (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null; d.fy = null;
      }));

  node.append("circle")
    .attr("r", 14)
    .attr("fill", nodeColour)
    .attr("stroke", "#0a0e17")
    .attr("stroke-width", 2);

  node.append("text")
    .text(d => d.name)
    .attr("font-family", "JetBrains Mono, monospace")
    .attr("font-size", 10)
    .attr("fill", "#e2e8f0")
    .attr("text-anchor", "middle")
    .attr("dy", 28);

  simulation.on("tick", () => {
    link
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y);
    linkLabel
      .attr("x", d => (d.source.x + d.target.x) / 2)
      .attr("y", d => (d.source.y + d.target.y) / 2 - 2);
    node.attr("transform", d => `translate(${d.x},${d.y})`);
  });

  // Legend.
  const kindsPresent = Array.from(new Set(nodes.map(n => n.kind))).sort();
  legendEl.innerHTML = `
    <div style="margin-top:1rem;display:flex;flex-wrap:wrap;gap:0.5rem;
         font-family:var(--font-mono);font-size:0.75rem">
      ${kindsPresent.map(k => `
        <div style="display:flex;align-items:center;gap:0.35rem">
          <span style="display:inline-block;width:10px;height:10px;
               background:${NODE_COLOURS[k] || "#94a3b8"};
               border-radius:50%"></span>
          <span style="color:var(--text-secondary)">${k}</span>
        </div>`).join("")}
    </div>
    <div style="margin-top:0.5rem;font-family:var(--font-mono);font-size:0.75rem;
         color:var(--text-dim)">
      ${nodes.length} nodes · ${edges.length} edges · drag to explore
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Deterministic Governance View — phase 4 commit 14
// ---------------------------------------------------------------------------

function renderGovernance(report) {
  const el = document.getElementById("governance-output");
  if (!el) return;
  const rules = report.deterministic_rules || [];
  const provenance = report.provenance_chain || [];

  // Group rules by family prefix (cpic.* / hla_b.* / verification.* /
  // decision-family single-word values like 'sufficient' / verdict V-ids
  // / uncertainty tiers).
  const families = {
    "CPIC Rules": rules.filter(r => r.startsWith("cpic.")),
    "HLA-B Rules": rules.filter(r => r.startsWith("hla_b.")),
    "Verification Rules": rules.filter(r => r.startsWith("verification.")),
    "Sufficiency Decisions": rules.filter(r => [
      "sufficient", "pass_with_caveat", "downgrade", "request_more",
      "escalate", "abstain", "block",
    ].includes(r)),
    "Verdict Rules (V1–V10)": rules.filter(r => /^V\d+$/.test(r)),
    "Uncertainty Tiers (U1–U9)": rules.filter(r => [
      "low", "moderate", "high", "unsafe",
    ].includes(r)),
  };

  el.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem">
      ${Object.entries(families)
        .filter(([_, list]) => list.length > 0)
        .map(([family, list]) => `
          <div>
            <div style="font-size:0.8rem;color:var(--text-secondary);
                 text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.4rem">
              ${family}</div>
            <div>${list.map(r => `<span class="chip">${r}</span>`).join("")}</div>
          </div>
        `).join("")}
    </div>
    <div style="margin-top:1rem">
      <div style="font-size:0.8rem;color:var(--text-secondary);
           text-transform:uppercase;letter-spacing:0.05em;margin-bottom:0.4rem">
        Provenance Chain (${provenance.length} records)
      </div>
      ${provenance.length === 0
        ? `<div style="color:var(--text-dim);font-size:0.85rem">no persisted records</div>`
        : `<div style="font-family:var(--font-mono);font-size:0.8rem;line-height:1.8">
            ${provenance.map((p, i) => `
              <div style="border-left:2px solid var(--accent-purple);
                   padding:0.5rem 0.75rem;margin:0.25rem 0;background:var(--bg-secondary);
                   border-radius:var(--radius)">
                <div style="color:var(--accent-cyan)">#${i + 1}  ${p.rule_id || "(no rule)"}</div>
                <div style="color:var(--text-secondary);margin-top:0.2rem">
                  agent: ${p.generating_agent || "?"}
                </div>
                <div style="color:var(--text-secondary)">
                  sources: ${(p.evidence_sources || []).join(", ") || "—"}
                </div>
                <div style="color:var(--text-dim);font-size:0.75rem;margin-top:0.2rem">
                  claim_id: ${(p.claim_id || "").slice(0, 10)}...
                  ${p.parent_claim_id ? `← parent: ${p.parent_claim_id.slice(0,10)}...` : ""}
                </div>
              </div>
            `).join("")}
          </div>`
      }
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Offline-mock rendering (fallback when backend is unreachable)
// ---------------------------------------------------------------------------

function renderFromMock() {
  const el = document.getElementById("trace-output");
  if (el) el.innerHTML = `<div class="trace-line warning">
    ● offline mock — start the backend to see live execution</div>`;
  renderFromReport(MOCK_RESULT, []);
}

// ---------------------------------------------------------------------------
// Tab switcher (kept from original UI)
// ---------------------------------------------------------------------------

function showTab(audience) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  event.target.classList.add("active");
  // Minimal: keep the current narrative content for all tabs in v1.
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", checkBackend);

// Expose entry points for the existing index.html onclick handlers.
window.runAnalysis = runAnalysis;
window.showTab = showTab;
window.applyScenario = applyScenario;
