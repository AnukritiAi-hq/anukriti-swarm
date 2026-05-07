# Ethical Considerations

> Responsible AI in genomic intelligence: what we build, what we don't, and why.

---

## 1. Non-Clinical Use Declaration

**Anukriti Swarm is a research system. It is NOT intended for:**
- Clinical decision-making
- Patient diagnosis
- Drug prescribing
- Medical advice of any kind

**Human oversight is required** for any interpretation of outputs. The system is designed to assist researchers in understanding pharmacogenomic architecture, not to replace clinical judgment.

---

## 2. Why This Matters

Pharmacogenomic AI systems operate at the intersection of:
- **Genetic data** (sensitive, immutable, heritable)
- **Drug safety** (incorrect recommendations can cause harm)
- **Population identity** (ancestry carries cultural and political weight)
- **Health equity** (algorithmic bias can worsen disparities)

Every design decision in Anukriti Swarm is made with awareness of these dimensions.

---

## 3. Population Data Ethics

### What We Do

- Use population labels (SAS, AFR, EUR) as **statistical groupings** for allele frequency reference
- Acknowledge that these are **simplifications** of complex human diversity
- Flag when data is **sparse** for a population (explicit uncertainty)
- Note when guidelines have **EUR-centric bias**

### What We Do NOT Do

- Claim that population labels represent biological "races"
- Use population data to make deterministic claims about individuals
- Assume population homogeneity (sub-population diversity exists)
- Ignore admixed or multi-ancestry individuals (acknowledged as a limitation)

### Commitment

Population context improves pharmacogenomic accuracy. We use it to **reduce** health inequity (by surfacing population-specific risks), not to reinforce genetic determinism.

---

## 4. Hallucination and Safety

### Risk

AI systems that hallucinate in pharmacogenomics could:
- Recommend contraindicated drugs
- Assign incorrect metabolizer phenotypes
- Fabricate drug-gene interactions
- Cite non-existent evidence

### Mitigation

| Layer | Protection |
|-------|-----------|
| Deterministic core | No LLM for established science — impossible to hallucinate |
| Verification gate | 6 checks before any output reaches user |
| Evidence grounding | Every claim must cite a real source |
| Confidence scoring | Low-confidence outputs are flagged, not delivered |
| Escalation | Uncertain outputs trigger human review markers |
| Origin labeling | User always knows if output is ESTABLISHED or INFERRED |

---

## 5. Limitations We Acknowledge

| Limitation | Impact | Mitigation |
|-----------|--------|------------|
| Mock data only | Results are illustrative, not clinically valid | Clearly labeled as research |
| 3 genes covered | Vast majority of pharmacogenes not included | Modular — add genes without architecture changes |
| No admixture support | Multi-ancestry individuals not handled | Acknowledged in output; future work |
| EUR-centric guidelines | CPIC guidelines validated primarily in EUR | Population agents flag this bias |
| No longitudinal data | Single-timepoint analysis only | Future: temporal reasoning |
| No drug-drug interactions | Polypharmacy not considered | Future: pathway agents |

---

## 6. Data Privacy

- **No patient data is stored or processed** — system uses reference population data only
- **No identifiable information** — all examples use synthetic/reference genotypes
- **No data leaves the system** — runs entirely locally, no external API calls in core
- **Future consideration:** If real patient data is ever processed, HIPAA/GDPR compliance will be required

---

## 7. Bias Awareness

### Known Biases in Pharmacogenomics

1. **Research bias:** Most studies conducted in European populations
2. **Guideline bias:** CPIC recommendations validated primarily in EUR
3. **Data bias:** gnomAD sample sizes vary by population (EUR: 64k, EAS: 9k)
4. **Allele definition bias:** Star alleles defined based on EUR-common variants

### How We Address This

- Population agents explicitly note when guidelines may not generalize
- Sparse data warnings trigger when sample sizes are inadequate
- Confidence scores reflect data quality per population
- The system surfaces bias rather than hiding it

---

## 8. Responsible Development

### Principles

1. **Transparency** — All reasoning is inspectable and traceable
2. **Humility** — The system knows what it doesn't know
3. **Equity** — Population-aware design reduces, not reinforces, disparities
4. **Safety** — Verification before delivery, always
5. **Honesty** — Research-only status is never obscured

### What We Will NOT Build

- Systems that make autonomous clinical decisions
- Tools that hide uncertainty from users
- Architectures that cannot be audited
- Models that treat population as a proxy for individual biology

---

## 9. Human Oversight Expectations

This system is designed to be **human-in-the-loop**:

- Outputs are **advisory**, not prescriptive
- Escalation markers indicate when human review is needed
- The verification gate can reject outputs entirely
- No output is delivered without explicit provenance

**The system augments human expertise. It does not replace it.**

---

*Research ethics are not a feature to be added later. They are foundational to the architecture.*
