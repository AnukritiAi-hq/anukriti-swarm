"""Agent identity catalog — all swarm member profiles.

Defines the identity of every agent in the Anukriti Swarm federation.
Each profile makes the agent introspectable and routable.
"""

from __future__ import annotations

from agents.profiles.identity import AgentDomain, AgentProfile, ConfidenceProfile, ReasoningMode

# --- Orchestrator ---

ORCHESTRATOR = AgentProfile(
    agent_id="orchestrator_main",
    name="Swarm Orchestrator",
    domain=AgentDomain.ORCHESTRATION,
    reasoning_mode=ReasoningMode.HYBRID,
    description="Central coordinator that decomposes queries, routes to specialists, and assembles consensus.",
    specialization="Query decomposition, agent dispatch, DAG execution, consensus assembly",
    capabilities=["query_routing", "dag_compilation", "agent_dispatch", "consensus_assembly"],
    reasoning_scope="All pharmacogenomic queries — delegates to specialists for domain reasoning.",
    routing_keywords=["orchestrate", "analyze", "pipeline"],
    priority=0,
    tags=["core", "coordinator"],
)

# --- Population Agents ---

POPULATION_SAS = AgentProfile(
    agent_id="population_sas",
    name="South Asian Population Expert",
    domain=AgentDomain.POPULATION_GENOMICS,
    reasoning_mode=ReasoningMode.DETERMINISTIC,
    description="Specialist in South Asian pharmacogenomics — allele frequencies, prevalence, and population context.",
    specialization="South Asian (SAS) allele frequencies and ethnopharmacogenomics",
    supported_populations=["SAS"],
    supported_genes=["CYP2D6", "CYP2C19", "CYP2C9", "HLA-B"],
    capabilities=["frequency_lookup", "prevalence_estimation", "risk_context", "sparse_data_detection"],
    reasoning_scope="Population-specific frequency data and contextualized interpretation for SAS.",
    confidence_profile=ConfidenceProfile(default_confidence=0.95, escalation_threshold=0.5),
    routing_keywords=["south asian", "SAS", "indian", "pakistani"],
    tags=["population", "SAS"],
)

POPULATION_AFR = AgentProfile(
    agent_id="population_afr",
    name="African Population Expert",
    domain=AgentDomain.POPULATION_GENOMICS,
    reasoning_mode=ReasoningMode.DETERMINISTIC,
    description="Specialist in African pharmacogenomics — highest genetic diversity, unique allele distributions.",
    specialization="African (AFR) allele frequencies, CYP2D6*17 expertise, genetic diversity awareness",
    supported_populations=["AFR"],
    supported_genes=["CYP2D6", "CYP2C19", "CYP2C9", "HLA-B"],
    capabilities=["frequency_lookup", "prevalence_estimation", "risk_context", "diversity_awareness"],
    reasoning_scope="Population-specific frequency data for AFR with sub-population diversity notes.",
    confidence_profile=ConfidenceProfile(default_confidence=0.95, escalation_threshold=0.5),
    routing_keywords=["african", "AFR", "sub-saharan"],
    tags=["population", "AFR"],
)

POPULATION_EUR = AgentProfile(
    agent_id="population_eur",
    name="European Population Expert",
    domain=AgentDomain.POPULATION_GENOMICS,
    reasoning_mode=ReasoningMode.DETERMINISTIC,
    description="Specialist in European pharmacogenomics — largest reference dataset, guideline bias awareness.",
    specialization="European (EUR) allele frequencies, guideline validation context",
    supported_populations=["EUR"],
    supported_genes=["CYP2D6", "CYP2C19", "CYP2C9", "HLA-B"],
    capabilities=["frequency_lookup", "prevalence_estimation", "risk_context", "guideline_bias_detection"],
    reasoning_scope="Population-specific frequency data for EUR. Notes EUR-centric bias in guidelines.",
    confidence_profile=ConfidenceProfile(default_confidence=0.95, escalation_threshold=0.5),
    routing_keywords=["european", "EUR", "caucasian"],
    tags=["population", "EUR"],
)

# --- Pharmacogene Agents ---

PHARMACOGENE_CYP2D6 = AgentProfile(
    agent_id="pharmacogene_cyp2d6",
    name="CYP2D6 Expert",
    domain=AgentDomain.PHARMACOGENOMICS,
    reasoning_mode=ReasoningMode.DETERMINISTIC,
    description="Specialist in CYP2D6 — the most complex pharmacogene, metabolizes ~25% of drugs.",
    specialization="CYP2D6 star allele assignment, activity scoring, phenotype inference, CPIC recommendations",
    supported_genes=["CYP2D6"],
    supported_drugs=["codeine", "tamoxifen", "tramadol", "amitriptyline"],
    capabilities=["diplotype_analysis", "phenotype_inference", "recommendation_lookup", "risk_classification"],
    reasoning_scope="CYP2D6 diplotype → phenotype → drug recommendations via CPIC activity score system.",
    confidence_profile=ConfidenceProfile(default_confidence=1.0, escalation_threshold=0.6),
    routing_keywords=["CYP2D6", "codeine", "tamoxifen"],
    priority=2,
    tags=["pharmacogene", "CYP2D6", "CPIC"],
)

PHARMACOGENE_CYP2C19 = AgentProfile(
    agent_id="pharmacogene_cyp2c19",
    name="CYP2C19 Expert",
    domain=AgentDomain.PHARMACOGENOMICS,
    reasoning_mode=ReasoningMode.DETERMINISTIC,
    description="Specialist in CYP2C19 — critical for antiplatelet therapy and PPIs.",
    specialization="CYP2C19 star allele assignment, clopidogrel resistance assessment",
    supported_genes=["CYP2C19"],
    supported_drugs=["clopidogrel", "omeprazole", "escitalopram"],
    capabilities=["diplotype_analysis", "phenotype_inference", "recommendation_lookup", "risk_classification"],
    reasoning_scope="CYP2C19 diplotype → phenotype → clopidogrel/PPI recommendations.",
    confidence_profile=ConfidenceProfile(default_confidence=1.0, escalation_threshold=0.6),
    routing_keywords=["CYP2C19", "clopidogrel", "antiplatelet"],
    priority=2,
    tags=["pharmacogene", "CYP2C19", "CPIC"],
)

PHARMACOGENE_HLA_B = AgentProfile(
    agent_id="pharmacogene_hla_b",
    name="HLA-B Hypersensitivity Expert",
    domain=AgentDomain.PHARMACOGENOMICS,
    reasoning_mode=ReasoningMode.DETERMINISTIC,
    description="Specialist in HLA-B*15:02 — immune-mediated adverse drug reaction risk assessment.",
    specialization="HLA-B*15:02 SJS/TEN risk for carbamazepine, oxcarbazepine, phenytoin",
    supported_genes=["HLA-B"],
    supported_drugs=["carbamazepine", "oxcarbazepine", "phenytoin"],
    capabilities=["binary_risk_assessment", "recommendation_lookup", "population_prevalence"],
    reasoning_scope="HLA-B*15:02 carrier status → drug contraindication (binary model).",
    confidence_profile=ConfidenceProfile(default_confidence=1.0, escalation_threshold=0.8),
    routing_keywords=["HLA-B", "carbamazepine", "SJS", "TEN"],
    priority=1,  # High priority — safety-critical
    tags=["pharmacogene", "HLA-B", "safety", "CPIC"],
)

# --- Retrieval Agent ---

RETRIEVAL = AgentProfile(
    agent_id="retrieval_main",
    name="Evidence Retrieval Specialist",
    domain=AgentDomain.EVIDENCE_RETRIEVAL,
    reasoning_mode=ReasoningMode.DETERMINISTIC,
    description="MA-RAG evidence retrieval — plans queries, searches knowledge bases, extracts citations.",
    specialization="Multi-source evidence retrieval: CPIC, PharmGKB, PubMed, vector indexes",
    capabilities=["query_planning", "vector_search", "citation_extraction", "evidence_synthesis", "grounding"],
    reasoning_scope="Retrieve and ground evidence for any pharmacogenomic claim.",
    confidence_profile=ConfidenceProfile(default_confidence=0.9, escalation_threshold=0.4),
    routing_keywords=["evidence", "literature", "citation", "guideline"],
    priority=3,
    tags=["retrieval", "MA-RAG", "grounding"],
)

# --- Verification Agent ---

VERIFICATION = AgentProfile(
    agent_id="verification_main",
    name="Safety Verification Agent",
    domain=AgentDomain.VERIFICATION,
    reasoning_mode=ReasoningMode.DETERMINISTIC,
    description="Safety gate — validates outputs, detects hallucinations, enforces grounding, triggers escalation.",
    specialization="Output verification, confidence assessment, TAO escalation, audit logging",
    capabilities=["evidence_grounding_check", "provenance_verification", "hallucination_detection",
                  "confidence_propagation", "escalation_assessment", "guideline_conflict_detection"],
    reasoning_scope="Verify all agent outputs before delivery. Enforce deterministic/generative boundary.",
    confidence_profile=ConfidenceProfile(default_confidence=1.0, min_confidence_to_act=0.3, escalation_threshold=0.3),
    routing_keywords=["verify", "validate", "check", "safety"],
    priority=1,  # High priority — safety-critical
    tags=["verification", "safety", "TAO", "audit"],
)

# --- All Profiles ---

ALL_PROFILES: list[AgentProfile] = [
    ORCHESTRATOR,
    POPULATION_SAS, POPULATION_AFR, POPULATION_EUR,
    PHARMACOGENE_CYP2D6, PHARMACOGENE_CYP2C19, PHARMACOGENE_HLA_B,
    RETRIEVAL, VERIFICATION,
]
