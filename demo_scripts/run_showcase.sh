#!/usr/bin/env bash
# Anukriti Swarm — Demo Runner
# Usage: ./demo_scripts/run_showcase.sh

set -e
cd "$(dirname "$0")/.."

echo ""
echo "  ╔══════════════════════════════════════════════════════════════╗"
echo "  ║  🧬 Anukriti Swarm — Demo Suite                            ║"
echo "  ╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python &> /dev/null; then
    echo "  ✗ Python not found. Please install Python 3.11+."
    exit 1
fi

echo "  Select demo:"
echo ""
echo "    1) Showcase (recommended — full pipeline demo)"
echo "    2) Population Reasoning"
echo "    3) Pharmacogene Agents"
echo "    4) Evidence Retrieval"
echo "    5) Verification & Escalation"
echo "    6) Visualization"
echo "    7) Narrative Reports"
echo "    8) Biomedical Data"
echo "    9) Agent Identity"
echo "    0) Run ALL demos"
echo ""
read -p "  Choice [1]: " choice
choice=${choice:-1}

case $choice in
    1) python -m demos.showcase ;;
    2) python -m demos.population_reasoning_demo ;;
    3) python -m demos.pharmacogene_demo ;;
    4) python -m demos.retrieval_demo ;;
    5) python -m demos.verification_demo ;;
    6) python -m demos.visualization_demo ;;
    7) python -m demos.narrative_report_demo ;;
    8) python -m demos.biomedical_data_demo ;;
    9) python -m demos.agent_identity_demo ;;
    0)
        echo "  Running all demos..."
        echo ""
        for demo in showcase population_reasoning_demo pharmacogene_demo retrieval_demo verification_demo agent_identity_demo; do
            python -m demos.$demo
            echo ""
            echo "  ─────────────────────────────────────────────────────────────"
            echo ""
        done
        ;;
    *) echo "  Invalid choice." && exit 1 ;;
esac
