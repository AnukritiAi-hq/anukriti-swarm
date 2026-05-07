# MCP Integration Strategy

> Model Context Protocol (MCP) integration for structured tool access to databases, retrieval systems, and genomic datasets.

---

## Why MCP

MCP provides a standardized interface for LLM agents to access external tools and data sources. In Anukriti Swarm, MCP enables:

- **Uniform tool interface** — All agents access data through the same protocol
- **Auditable tool calls** — Every MCP invocation is logged with parameters and results
- **Swappable backends** — Change from MongoDB to PostgreSQL without agent code changes
- **Schema enforcement** — Tool inputs/outputs are typed and validated

---

## MCP Server Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      AGENT LAYER                            │
│  (Orchestrator, Population, Chromosome, Pharma, etc.)      │
└────────────────────────────┬────────────────────────────────┘
                             │ MCP Protocol
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    MCP SERVER LAYER                          │
├───────────────────┬───────────────────┬─────────────────────┤
│  MongoDB MCP      │  Retrieval MCP    │  Dataset MCP        │
│  Server           │  Server           │  Server             │
├───────────────────┼───────────────────┼─────────────────────┤
│  • genomic_facts  │  • vector_search  │  • vcf_parse        │
│  • interactions   │  • pubmed_search  │  • frequency_lookup │
│  • guidelines     │  • guideline_get  │  • gene_annotation  │
│  • audit_write    │  • embed_text     │  • population_data  │
└───────────────────┴───────────────────┴─────────────────────┘
         │                   │                    │
         ▼                   ▼                    ▼
┌──────────────┐   ┌──────────────┐    ┌──────────────────┐
│   MongoDB    │   │    Qdrant    │    │  Reference Files │
│              │   │              │    │  (VCF, TSV, BED) │
└──────────────┘   └──────────────┘    └──────────────────┘
```

---

## 1. MongoDB MCP Server

**Purpose:** Structured access to validated genomic knowledge (Memory Layer 2).

### Tools Exposed

| Tool | Parameters | Returns |
|------|-----------|---------|
| `genomic_facts.query` | `gene`, `category`, `population?` | Matching facts with source attribution |
| `interactions.lookup` | `gene`, `drug` | Known interactions with evidence level |
| `guidelines.get` | `gene`, `source` (CPIC/DPWG) | Guideline recommendations |
| `alleles.star_lookup` | `gene`, `haplotype` | Star allele classification |
| `audit.append` | `event_type`, `payload` | Confirmation of write |

### Access Control

- Read tools: Available to all agents
- Write tools (`audit.append`): Available to all agents (append-only)
- No delete or update operations exposed via MCP

---

## 2. Retrieval MCP Server

**Purpose:** Semantic and keyword search over literature and knowledge bases (Memory Layer 3).

### Tools Exposed

| Tool | Parameters | Returns |
|------|-----------|---------|
| `vector.search` | `query`, `top_k`, `filters?` | Ranked passages with scores |
| `vector.search_by_gene` | `gene`, `context`, `top_k` | Gene-specific evidence |
| `pubmed.search` | `query`, `max_results` | PubMed abstracts with PMIDs |
| `guideline.retrieve` | `gene`, `drug`, `source` | Full guideline text |
| `embed.text` | `text` | Embedding vector (for custom similarity) |

### Filters Schema

```json
{
  "gene": "CYP2D6",
  "population": "EAS",
  "document_type": "research_paper",
  "year_min": 2020
}
```

---

## 3. Dataset MCP Server

**Purpose:** Direct access to genomic reference datasets and VCF processing.

### Tools Exposed

| Tool | Parameters | Returns |
|------|-----------|---------|
| `vcf.parse` | `vcf_content`, `chromosome?` | Structured variant records |
| `vcf.filter_by_gene` | `vcf_content`, `gene` | Variants within gene boundaries |
| `frequency.lookup` | `variant_id`, `population` | Allele frequency data |
| `frequency.compare` | `variant_id`, `populations[]` | Cross-population comparison |
| `annotation.functional` | `variant_id` | Functional impact prediction |
| `gene.coordinates` | `gene_symbol` | Genomic coordinates (GRCh38) |

### Supported Datasets

| Dataset | Version | Content |
|---------|---------|---------|
| gnomAD | v4.0 | Population allele frequencies |
| ClinVar | 2024-01 | Clinical variant classifications |
| PharmVar | 6.0 | Star allele definitions |
| CPIC | Current | Drug-gene guidelines |
| RefSeq | GRCh38 | Gene coordinates and transcripts |

---

## MCP Configuration

```json
{
  "mcpServers": {
    "mongodb": {
      "command": "python",
      "args": ["-m", "anukriti_swarm.mcp.mongodb_server"],
      "env": {
        "MONGODB_URI": "${MONGODB_URI}",
        "DATABASE": "anukriti_genomics"
      }
    },
    "retrieval": {
      "command": "python",
      "args": ["-m", "anukriti_swarm.mcp.retrieval_server"],
      "env": {
        "QDRANT_URL": "${VECTOR_DB_URL}",
        "EMBEDDING_MODEL": "text-embedding-3-small"
      }
    },
    "datasets": {
      "command": "python",
      "args": ["-m", "anukriti_swarm.mcp.dataset_server"],
      "env": {
        "DATASETS_PATH": "./datasets",
        "REFERENCE_GENOME": "GRCh38"
      }
    }
  }
}
```

---

## Audit Integration

Every MCP tool call is automatically logged:

```python
@dataclass
class MCPAuditEntry:
    timestamp: datetime
    agent_id: str
    server: str          # "mongodb" | "retrieval" | "datasets"
    tool: str            # e.g., "interactions.lookup"
    parameters: dict
    result_hash: str     # SHA-256 of result for integrity
    latency_ms: int
    correlation_id: str
```

---

## Error Handling

| Error | MCP Response | Agent Behavior |
|-------|-------------|----------------|
| Tool not found | `ToolNotFoundError` | Agent reports capability gap |
| Invalid parameters | `ValidationError` | Agent retries with corrected params |
| Backend timeout | `TimeoutError` | Agent retries (max 2), then escalates |
| No results | Empty result set | Agent proceeds with available data |
