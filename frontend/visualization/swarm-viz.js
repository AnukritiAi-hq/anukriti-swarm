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

  // Live run (sync for now; commit 12 switches to WebSocket streaming).
  renderLiveStart({ drug, gene, population, genotype });
  try {
    const r = await fetch(`${BACKEND}/api/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ drug, gene, population, genotype }),
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
    "swarm-activity", "orchestration-viz", "population-section",
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
  renderOrchestrationFromReport(report);
  renderPopulationFromReport(report);
  renderPharmacogeneFromReport(report);
  renderEvidenceFromReport(report);
  renderVerificationFromReport(report);
  renderConfidenceFromReport(report);
  renderNarrativeFromReport(report);
  renderProvenanceFromReport(report);
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
