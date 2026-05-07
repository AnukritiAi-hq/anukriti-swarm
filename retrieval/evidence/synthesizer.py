"""Evidence synthesis with grounding and provenance.

Synthesizes retrieved evidence into grounded claims. Every claim
in the synthesis is linked to specific citations, ensuring no
unsupported statements reach the user.

Grounding rules:
- Every claim must cite at least one source
- Claims without evidence are flagged as "ungrounded"
- Confidence is derived from evidence count and relevance scores

Future: LLM-based synthesis with structured output enforcement.
Currently uses deterministic template-based synthesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from retrieval.evidence.retriever import Citation, RetrievalResult, RetrievedEvidence


@dataclass(frozen=True)
class GroundedClaim:
    """A single claim grounded in retrieved evidence."""

    claim: str
    citations: list[str]        # Citation IDs supporting this claim
    confidence: float           # Based on evidence strength
    grounded: bool              # False if no supporting evidence found
    intent: str                 # "guideline", "mechanism", "frequency", "evidence"


@dataclass
class EvidenceSynthesis:
    """Synthesized evidence with grounding and provenance."""

    query: str
    claims: list[GroundedClaim] = field(default_factory=list)
    all_citations: list[Citation] = field(default_factory=list)
    grounding_score: float = 0.0  # Fraction of claims that are grounded
    total_evidence_used: int = 0
    provenance: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EvidenceSynthesizer:
    """Synthesizes retrieved evidence into grounded claims.

    Groups evidence by intent, extracts key claims from each group,
    and links claims to their supporting citations.

    Future: LLM synthesis with citation enforcement via structured output.
    """

    def synthesize(self, result: RetrievalResult) -> EvidenceSynthesis:
        """Synthesize retrieval results into grounded claims."""
        # Group evidence by intent
        by_intent: dict[str, list[RetrievedEvidence]] = {}
        for ev in result.evidence:
            by_intent.setdefault(ev.intent, []).append(ev)

        claims: list[GroundedClaim] = []
        for intent, evidence_list in by_intent.items():
            claim = self._synthesize_group(intent, evidence_list)
            claims.append(claim)

        grounded_count = sum(1 for c in claims if c.grounded)
        grounding_score = grounded_count / len(claims) if claims else 0.0

        return EvidenceSynthesis(
            query=result.query,
            claims=claims,
            all_citations=result.citations,
            grounding_score=grounding_score,
            total_evidence_used=result.total_retrieved,
            provenance={
                "plan_id": result.plan_id,
                "method": "template_synthesis",
                "origin": "deterministic",
            },
        )

    def _synthesize_group(self, intent: str, evidence: list[RetrievedEvidence]) -> GroundedClaim:
        """Synthesize a group of evidence with the same intent into a claim."""
        if not evidence:
            return GroundedClaim(
                claim=f"No evidence found for {intent}.",
                citations=[], confidence=0.0, grounded=False, intent=intent,
            )

        # Use highest-relevance evidence as primary claim source
        best = max(evidence, key=lambda e: e.relevance_score)
        citations = [ev.citation.citation_id for ev in evidence]

        # Confidence from relevance scores
        avg_relevance = sum(e.relevance_score for e in evidence) / len(evidence)
        confidence = min(0.95, avg_relevance / max(e.relevance_score for e in evidence) * 0.9 + 0.1 * len(evidence) / 5)

        # Generate claim text from best evidence
        claim_text = self._extract_claim(intent, best)

        return GroundedClaim(
            claim=claim_text,
            citations=citations,
            confidence=round(confidence, 3),
            grounded=True,
            intent=intent,
        )

    def _extract_claim(self, intent: str, evidence: RetrievedEvidence) -> str:
        """Extract a concise claim from evidence based on intent."""
        content = evidence.content
        # Take first 2 sentences as the claim
        sentences = content.replace(". ", ".\n").split("\n")
        claim = ". ".join(s.strip() for s in sentences[:2] if s.strip())
        if not claim.endswith("."):
            claim += "."
        return claim
