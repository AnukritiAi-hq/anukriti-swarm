# Pharmacogenomic Knowledge Graph — Anukriti Swarm

**Status:** production — schema + seed + graph + indexer + reasoner shipped.
**Scope:** population-aware multi-hop pharmacogenomic reasoning only. Not a generic KG, not an ontology import, not a GraphRAG engine.

This document is the detailed companion to `architecture/evidence-sufficiency.md`. Where the main doc describes how the KG composes with the rest of the sufficiency layer, this doc describes the KG in isolation: schema, seed data, traversal semantics, and population weighting.

## Scope firewall

The `knowledge_graph/` package is **not**:

- a generic knowledge graph — the schema is closed to 10 node kinds + 7 edge kinds at the type boundary
- a biomedical ontology import — no MeSH, SNOMED, UMLS, or equivalent ingestion
- a GraphRAG engine — retrieval over the graph is population-aware path traversal, not embedding search
- a hypothesis generator — edges represent only provenanced relations from CPIC, PharmGKB, or peer-reviewed sources

Every node carries an optional `ProvenanceStamp`; every edge carries a **required** stamp with a non-empty `source_id`. Edges without a source are rejected at `add_edge` construction time. Unknown enum values cannot be constructed.

## Closed schema

### 10 node kinds — `NodeKind`

| Kind | Purpose | Seed population |
|---|---|---|
| `POPULATION` | 1000 Genomes super-population | SAS, EAS, AFR, EUR, AMR |
| `ANCESTRY` | finer-grained ancestry descriptor | empty in seed (extension point) |
| `GENE` | pharmacogene | CYP2C19, CYP2D6, HLA-B |
| `VARIANT` | SNV / structural variant reference | empty in seed (extension point) |
| `ALLELE` | star-allele | CYP2C19\*2/\*3/\*17, CYP2D6\*4/\*10/\*17, HLA-B\*15:02 |
| `PHENOTYPE` | metabolizer / HLA-risk status | CYP2C19 PM/IM, CYP2D6 PM, HLA-B\*15:02 positive |
| `DRUG` | pharmacogenomically-actionable drug | clopidogrel, prasugrel, ticagrelor, codeine, morphine, carbamazepine |
| `ADVERSE_REACTION` | ADR tied to gene+drug | MACE, SJS/TEN, respiratory depression |
| `GUIDELINE` | CPIC / PharmGKB / FDA guideline | CPIC:CYP2C19:clopidogrel:2022, CPIC:CYP2D6:codeine:2023, CPIC:HLA-B:carbamazepine:2014 |
| `EVIDENCE_PAPER` | PubMed / PharmGKB citation | 6 seed papers covering the 3 flagship scenarios |

`ANCESTRY` and `VARIANT` are intentionally present but unpopulated in the seed — they're first-class extension points. Adding a sub-population like `SAS:GIH` would be an `ANCESTRY` node; adding an rsID-level variant would be a `VARIANT`.

### 7 edge kinds — `EdgeKind`

| Kind | Typical source → target | Seed count | Notes |
|---|---|---|---|
| `METABOLIZES` | `GENE → DRUG` | 2 | directionality payload |
| `CONTRAINDICATED_FOR` | `ALLELE/PHENOTYPE → DRUG` | 5 | strength + action in payload |
| `ASSOCIATED_WITH` | multi-purpose | 8 | drug→ADR + allele→phenotype |
| `HIGHER_FREQUENCY_IN` | `ALLELE → POPULATION` | 10 | weight = population frequency |
| `SUPPORTED_BY` | any → `EVIDENCE_PAPER` | 6 | cite trail |
| `CONFLICTS_WITH` | `EVIDENCE_PAPER → EVIDENCE_PAPER` | 0 | runtime-only signal; not a structural edge |
| `GUIDELINE_RECOMMENDS` | `GUIDELINE → DRUG` | 3 | alternative-drug pointer |

The `CONFLICTS_WITH` kind is available but unused by the seed — curated contradictions are not the same thing as the runtime `ConflictDetectionAgent` (which detects contradictions at evaluation time).

### Frozen records

All three data types are frozen dataclasses; two-node equality is `node.id == node.id` (from `Node.make_id(kind, name)`), two-edge deduplication is `(src_id, edge_kind, tgt_id, stamp.source_id)`.

```
ProvenanceStamp(source_id: str, source_type: str, added_at: datetime)
Node(id: str, kind: NodeKind, name: str, payload: dict, stamp: ProvenanceStamp | None)
Edge(source_id: str, target_id: str, kind: EdgeKind, weight: float,
     payload: dict, stamp: ProvenanceStamp)  # stamp required
```

`Node.make_id(kind, name)` produces deterministic strings like `"allele:CYP2C19*2"` / `"population:SAS"` / `"drug:clopidogrel"` — the same inputs always produce the same id, which makes the whole graph reproducible.

## Seed data (37 nodes, 34 edges)

The seed is populated **only** from in-tree data:

- `guidelines/cpic.py` — CPIC guideline ids, strengths, PMIDs
- `rules/phenotype_rules.py` — activity scores, phenotype ranges
- `retrieval/evidence/documents.py` — PMIDs + PharmGKB annotation ids

No external download, no ontology import, no LLM enrichment. Extending coverage for a new gene/drug pair is a code change in `knowledge_graph/seed.py`.

### Flagship scenario coverage

**CYP2C19 + clopidogrel + SAS** — full chain present:
```
allele:CYP2C19*2  --associated_with-->  phenotype:CYP2C19 Poor Metabolizer
                                                  |
                                                  --contraindicated_for-->  drug:clopidogrel
                                                                                    |
                                                                                    --associated_with-->  adverse_reaction:MACE

allele:CYP2C19*2  --higher_frequency_in [weight=0.36]-->  population:SAS
allele:CYP2C19*2  --higher_frequency_in [weight=0.30]-->  population:EAS
allele:CYP2C19*2  --higher_frequency_in [weight=0.18]-->  population:AFR
allele:CYP2C19*2  --higher_frequency_in [weight=0.15]-->  population:EUR

guideline:CPIC:CYP2C19:clopidogrel:2022  --guideline_recommends-->  drug:prasugrel
guideline:CPIC:CYP2C19:clopidogrel:2022  --guideline_recommends-->  drug:ticagrelor
```

The 0.36 weight on the SAS edge is the **flagship signal**: it's why "Clopidogrel + SAS" is a meaningful scenario at all.

**HLA-B\*15:02 + carbamazepine + EAS** — direct contraindication:
```
allele:HLA-B*15:02  --contraindicated_for-->  drug:carbamazepine       (1 hop, direct)
allele:HLA-B*15:02  --associated_with-->  phenotype:HLA-B*15:02 positive
                                                  |
                                                  --contraindicated_for-->  drug:carbamazepine  (2 hops, via phenotype)

allele:HLA-B*15:02  --higher_frequency_in [weight=0.08]-->  population:EAS
```

Two different paths reach `carbamazepine` from `HLA-B*15:02` — this is why the `MultiHopReasoner` returns multiple paths for the flagship scenarios.

**CYP2D6 + codeine + AFR** — phenotype chain present, AFR-specific evidence absent:
```
allele:CYP2D6*4  --associated_with-->  phenotype:CYP2D6 Poor Metabolizer
                                                  |
                                                  --contraindicated_for-->  drug:codeine
                                                                                    |
                                                                                    --associated_with-->  adverse_reaction:respiratory depression

allele:CYP2D6*17  --higher_frequency_in [weight=0.20]-->  population:AFR
allele:CYP2D6*4   --higher_frequency_in [weight=0.06]-->  population:AFR
```

Notice: `HIGHER_FREQUENCY_IN` edges cover AFR, but no `EVIDENCE_PAPER` node is attached to a CYP2D6 allele *with a PubMed source whose content mentions AFR*. This is the structural reason the `evidence_sufficiency_demo` refuses to confidently synthesize for the AFR scenario — ancestry-scarcity is real in the seed, which makes the refusal an honest signal.

## Population as a first-class reasoning dimension

Every population-aware decision in the KG is a direct consequence of the schema, not a post-hoc heuristic:

### 1. Population is a node kind

`POPULATION` is one of the 10 node kinds, not a metadata field on other nodes. That forces any population-linked claim to travel through a real edge.

### 2. Edge weights are per-population frequencies

`HIGHER_FREQUENCY_IN` edges carry `weight ∈ [0, 1]` — the actual frequency. The reasoner reads this directly; nothing is computed from title text or keyword presence.

### 3. Path weights accumulate deterministically

`MultiHopReasoner.find_paths(..., target_population=...)` multiplies `weight` along any path that crosses `HIGHER_FREQUENCY_IN → target_population`. A path that never touches that edge keeps `population_weight = 1.0` — population-neutral. A path that steps into SAS with a 0.36 CYP2C19\*2 edge accumulates `0.36`. The `PathEvidenceRetriever` uses this weight directly in its score formula.

### 4. Pruning is opt-in per-query

`MultiHopReasoner(min_pop_frequency=0.05)` rejects paths that step into an ALLELE whose `target_population` frequency is below the floor. Disabled by default (`0.0`); enabling it is a per-call override. Avoids reasoning about alleles that effectively don't exist in the target ancestry.

### 5. Population-keyed indexer is precomputed

`PopulationGraphIndexer.build(graph)` walks the graph once and returns three population-keyed tables:

```
alleles_by_population   SuperPopulation -> sorted (Node, frequency) pairs
drugs_by_population     SuperPopulation -> sorted Nodes reachable via
                        CONTRAINDICATED_FOR (direct + via phenotype)
evidence_by_population  SuperPopulation -> sorted EVIDENCE_PAPER name
                        tuple (via SUPPORTED_BY from observed alleles)
```

Queries are O(1) afterward. The `PopulationEvidenceBiasDetector` consumes these tables directly to flag `ANCESTRY_SCARCITY` / `EUROCENTRIC_IMBALANCE` / `UNSUPPORTED_EXTRAPOLATION`.

## Traversal semantics

### Bounded BFS

```python
reasoner = MultiHopReasoner(max_hops=4)           # brief req #11 ceiling
paths = reasoner.find_paths(
    graph,
    start_id="allele:CYP2C19*2",
    goal_id="drug:clopidogrel",
    target_population=SuperPopulation.SAS,
    pop_indexer=indexer,
)
```

Key properties:

- **Hard hop ceiling** — default 4; enforced per-path, not per-BFS-level.
- **Cycle prevention** — visited-set per-path; the same node cannot appear twice in a single path.
- **Deterministic sort** — `(hop_count asc, -population_weight desc, start_id asc, edge-keys asc)`. Same inputs always produce the same tuple of `GraphPath`.
- **Multiple paths surfaced** — a goal reachable through multiple routes returns all routes within the budget; the caller picks or aggregates.

### Conflict-aware traversal

`MultiHopReasoner(skip_conflicts=True)` (default) never crosses `CONFLICTS_WITH` edges. Two conflicting evidence papers do not form a traversable chain — a refutation path is not a reasoning path.

### Population-weight accumulation

For each edge stepped:

```
if edge.kind is HIGHER_FREQUENCY_IN
   and target_node.kind is POPULATION
   and target_node.name == target_population.value:
       new_weight = weight * edge.weight
```

Other edges leave `weight` unchanged. The final path's `population_weight` is a product, not a sum — so a 2-hop path through two pop-edges (rare in practice) would multiply them.

## PathEvidenceRetriever — KG paths → RetrievedEvidence

The `PathEvidenceRetriever` is the bridge between the KG layer and the phase-2 retrieval stack:

```python
per = PathEvidenceRetriever(base_score=3.0, pop_weight_scale=2.0)
evidence = per.retrieve_from_paths(graph, paths)
# -> list[RetrievedEvidence] consumable by the existing selector + checkpoint
```

Score formula (deterministic, closed-form):

```
score = base_score + pop_weight_scale * best_population_weight_observed
      = 3.0 + 2.0 * [0.0 .. 1.0]
      -> [3.0 .. 5.0]
```

The output shape is identical to `retrieval.evidence.retriever.RetrievedEvidence`, so no adapter is needed to feed into the `EvidenceSelector` diversity+dedup merger or into the `SufficiencyCheckpoint.evaluate`.

The `GraphRetriever` strategy (in `retrieval/multi_strategy/graph_and_selector.py`) is currently a stub with a final public surface — its body is replaced by a thin adapter calling `reasoner.find_paths` + `per.retrieve_from_paths` once the phase-3 body ships.

## Provenance discipline

Every edge in the KG is provenance-stamped at construction time. A stamp carries:

```
ProvenanceStamp(
    source_id="CPIC:CYP2C19:clopidogrel:2022",  # non-empty; required
    source_type="cpic",                           # closed set:
                                                  # cpic | pharmgkb | pubmed
                                                  # | rule | derived
    added_at=...,                                 # ISO timestamp
)
```

The schema rejects edges without a source_id:

```
graph.add_edge(Edge(..., stamp=ProvenanceStamp(source_id="", ...)))
# ValueError: edge requires a ProvenanceStamp with a non-empty source_id
```

The schema rejects edges with dangling endpoints:

```
graph.add_edge(Edge(source_id="no-such-node", ...))
# ValueError: edge source not in graph: no-such-node
```

Edge deduplication is keyed on `(source_id, kind, target_id, stamp.source_id)` — so the same relation cited by two different sources lives as two distinct edges, preserving the citation trail.

## Determinism properties

- Building the default graph twice produces structurally-identical graphs (modulo `added_at` timestamps on stamps, which are stripped for test comparisons).
- Building the indexer over the same graph produces byte-identical `to_dict()` output.
- `MultiHopReasoner.find_paths(...)` returns byte-identical path tuples across invocations.
- `PathEvidenceRetriever.retrieve_from_paths(...)` scores are deterministic; ordering is by `(desc score, asc citation_id)`.

The entire KG layer is LLM-free, network-free, and clock-free at the reasoning surface. Timestamps exist only for audit.

## JSON-safety

Every public type in `knowledge_graph/` exposes `.to_dict()`:

```
graph.to_dict()          # full node+edge dump
indexer.to_dict()        # three population-keyed lookup tables
path.to_dict()           # hop_count + nodes + edges + weight + evidence refs
```

All three round-trip through `json.dumps` without raising.

## Out of scope (do not build here)

- Ontology import (MeSH / SNOMED / UMLS / ChEBI)
- Embedding-based KG retrieval ("GraphRAG")
- Hypothesis generation (new edges beyond what CPIC / PharmGKB / peer-reviewed literature support)
- Reasoning outside the `(gene, drug, population, genotype)` scope (symptoms, treatment plans, clinical outcomes)
- LLM-assisted edge inference (the schema is rule-only)

Each item has been deliberately declined to keep the KG narrow, auditable, and safe to extend under review.
