/**
 * Anukriti Swarm — Agent Orchestration & Confidence Visualization
 * Simulates the pipeline execution with progressive reveal.
 */

// Mock pipeline result (matches Python backend output)
const MOCK_RESULT = {
  correlation_id: "demo_" + Math.random().toString(36).slice(2, 10),
  gene: "CYP2C19", drug: "clopidogrel", population: "SAS",
  diplotype: "*2/*2",
  stages: [
    { name: "intake", duration: 0.1, status: "success", detail: "Validated CYP2C19 *2/*2" },
    { name: "orchestration", duration: 0.1, status: "success", detail: "Dispatched 5 agents" },
    { name: "population", duration: 0.3, status: "success", detail: "*2 freq = 36% in SAS" },
    { name: "pharmacogene", duration: 0.2, status: "success", detail: "Poor Metabolizer → high_risk" },
    { name: "retrieval", duration: 0.4, status: "success", detail: "2 passages, 100% grounded" },
    { name: "verification", duration: 0.1, status: "success", detail: "6/6 checks PASS" },
    { name: "narrative", duration: 0.1, status: "success", detail: "Report generated" },
  ],
  pharmacogene: { phenotype: "Poor Metabolizer", risk: "high_risk", score: 0.0, confidence: 1.0 },
  population: { frequency: 0.36, rarity: "common", confidence: 0.95, source: "gnomAD v4.0" },
  verification: { verdict: "pass", confidence: 0.95, escalation: "autonomous", checks: 6 },
  evidence: { citations: ["PMID:34032273", "PA166169660"], grounding: 1.0 },
  recommendation: { drug: "clopidogrel", action: "Use prasugrel or ticagrelor instead", strength: "STRONG" },
};

function runAnalysis() {
  const provider = document.getElementById("provider").value;
  const apikey = document.getElementById("apikey").value;
  MOCK_RESULT.provider = provider;
  MOCK_RESULT.apikey_set = apikey.length > 0;

  const sections = ["swarm-activity", "orchestration-viz", "population-section",
    "pharmacogene-section", "evidence-section", "verification-section",
    "confidence-section", "narrative-section", "provenance-section"];

  // Progressive reveal
  let delay = 0;
  sections.forEach((id, i) => {
    setTimeout(() => {
      document.getElementById(id).classList.remove("hidden");
      document.getElementById(id).style.opacity = "0";
      requestAnimationFrame(() => { document.getElementById(id).style.opacity = "1"; });
    }, delay);
    delay += 300;
  });

  // Populate sections
  setTimeout(() => renderTrace(), 100);
  setTimeout(() => renderOrchestration(), 400);
  setTimeout(() => renderPopulation(), 700);
  setTimeout(() => renderPharmacogene(), 1000);
  setTimeout(() => renderEvidence(), 1300);
  setTimeout(() => renderVerification(), 1600);
  setTimeout(() => renderConfidence(), 1900);
  setTimeout(() => renderNarrative(), 2200);
  setTimeout(() => renderProvenance(), 2500);
}

function renderTrace() {
  const el = document.getElementById("trace-output");
  el.innerHTML = MOCK_RESULT.stages.map(s =>
    `<div class="trace-line ${s.status}">● ${s.name} <span style="color:var(--text-dim)">${s.duration}ms</span> → ${s.detail}</div>`
  ).join("");
}

function renderOrchestration() {
  document.getElementById("agent-graph").innerHTML = `
    <pre style="font-size:0.75rem;color:var(--text-secondary);line-height:1.4">
    ┌──────────────┐
    │ ORCHESTRATOR │─── dispatch ──┐
    └──────────────┘               │
          │                       │
          ▼                       ▼
    ┌──────────┐          ┌──────────────┐
    │POPULATION│          │PHARMACOGENE  │
    │ SAS:36%  │          │ PM, high_risk│
    └────┬─────┘          └──────┬───────┘
         └────────┬──────────────┘
                  ▼
         ┌──────────────┐
         │  RETRIEVAL   │ 100% grounded
         └──────┬───────┘
                ▼
         ┌──────────────┐
         │ VERIFICATION │ 6/6 PASS
         └──────┬───────┘
                ▼
         ┌──────────────┐
         │  NARRATIVE   │
         └──────────────┘</pre>`;
}

function renderPopulation() {
  const p = MOCK_RESULT.population;
  document.getElementById("population-output").innerHTML = `
    <div class="metric-card"><div class="metric-value">${(p.frequency * 100).toFixed(0)}%</div><div class="metric-label">*2 Frequency (SAS)</div></div>
    <div class="metric-card"><div class="metric-value">${p.rarity}</div><div class="metric-label">Rarity Class</div></div>
    <div class="metric-card"><div class="metric-value">${p.confidence}</div><div class="metric-label">Confidence</div></div>
    <div class="metric-card"><div class="metric-value">${p.source}</div><div class="metric-label">Source</div></div>`;
}

function renderPharmacogene() {
  const pg = MOCK_RESULT.pharmacogene;
  document.getElementById("pharmacogene-output").innerHTML = `
    <div class="established"><strong>Diplotype:</strong> ${MOCK_RESULT.diplotype} <span class="citation">[ESTABLISHED]</span></div>
    <div class="established"><strong>Activity Score:</strong> ${pg.score}</div>
    <div class="established"><strong>Phenotype:</strong> ${pg.phenotype} <span class="citation">[ESTABLISHED]</span></div>
    <div class="established" style="border-color:var(--accent-red)"><strong>Risk:</strong> ${pg.risk}</div>`;
}

function renderEvidence() {
  const ev = MOCK_RESULT.evidence;
  document.getElementById("evidence-output").innerHTML = `
    <div class="established"><strong>Grounding:</strong> ${(ev.grounding * 100).toFixed(0)}%</div>
    <div style="margin-top:0.75rem">${ev.citations.map(c => `<div class="citation" style="margin:0.25rem 0">📄 ${c}</div>`).join("")}</div>
    <div class="established" style="margin-top:0.75rem"><strong>Recommendation [${MOCK_RESULT.recommendation.strength}]:</strong> ${MOCK_RESULT.recommendation.action}</div>`;
}

function renderVerification() {
  const v = MOCK_RESULT.verification;
  document.getElementById("verification-output").innerHTML = `
    <div class="metrics-grid">
      <div class="metric-card"><div class="metric-value" style="color:var(--accent-green)">${v.verdict.toUpperCase()}</div><div class="metric-label">Verdict</div></div>
      <div class="metric-card"><div class="metric-value">${v.confidence}</div><div class="metric-label">Confidence</div></div>
      <div class="metric-card"><div class="metric-value">${v.checks}/${v.checks}</div><div class="metric-label">Checks Passed</div></div>
      <div class="metric-card"><div class="metric-value" style="color:var(--accent-green)">${v.escalation}</div><div class="metric-label">Escalation</div></div>
    </div>`;
}

function renderConfidence() {
  const stages = { Phenotype: 1.0, Population: 0.95, Grounding: 1.0, Final: 0.95 };
  document.getElementById("confidence-output").innerHTML = Object.entries(stages).map(([k, v]) => {
    const cls = v >= 0.85 ? "high" : v >= 0.6 ? "moderate" : "low";
    return `<div class="conf-bar"><span class="conf-label">${k}</span><div class="conf-track"><div class="conf-fill ${cls}" style="width:${v * 100}%"></div></div><span class="conf-value">${v.toFixed(3)}</span></div>`;
  }).join("");
}

function renderNarrative() {
  document.getElementById("narrative-output").innerHTML = `
    <div class="established"><strong>Finding:</strong> CYP2C19 *2/*2 → Poor Metabolizer. Clopidogrel cannot be activated.</div>
    <div class="narrative" style="margin-top:0.75rem">This patient's genetic profile indicates they cannot effectively convert clopidogrel to its active form. The risk of major adverse cardiovascular events is elevated.</div>
    <div class="established" style="margin-top:0.75rem"><strong>Recommendation:</strong> Use prasugrel or ticagrelor instead. <span class="citation">PMID:34032273</span></div>
    <div class="narrative" style="margin-top:0.75rem;color:var(--text-dim)">⚠️ Research only — not for clinical decision-making.</div>`;
}

function renderProvenance() {
  const provider = MOCK_RESULT.provider || "gemini";
  const providerLabel = {gemini: "Gemini 2.0 Flash", openai: "OpenAI GPT-4o-mini", none: "None (deterministic only)"}[provider];
  document.getElementById("provenance-output").innerHTML = `
    <div style="font-family:var(--font-mono);font-size:0.8rem;color:var(--text-secondary);line-height:1.8">
      <div>Correlation: ${MOCK_RESULT.correlation_id}</div>
      <div>AI Provider: <strong>${providerLabel}</strong></div>
      <div>Rule Engine: cpic_activity_score_v1</div>
      <div>Guideline: CPIC:CYP2C19:clopidogrel:2022</div>
      <div>Origin: deterministic (core) + generative (explanation)</div>
      <div>Verification: 6/6 checks passed</div>
      <div>Escalation: autonomous</div>
      <div>Citations: ${MOCK_RESULT.evidence.citations.join(", ")}</div>
    </div>`;
}

function showTab(audience) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  event.target.classList.add("active");
  // Tab content switching would go here with full implementation
}
