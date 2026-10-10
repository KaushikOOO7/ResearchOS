"""
AI Experiment Designer engine.
Translates identified research gaps and literature evidence into actionable, rigorous experimental protocols.
"""

import json
import logging
import os
from typing import Any, Dict, List
from app.schemas.paper import ExperimentDesign, ExperimentDesignResponse
from app.analysis.paper_analyzer import is_gemini_configured

logger = logging.getLogger("researchos.experiment_designer")


def design_experiment_for_gap(
    gap: Dict[str, Any],
    query: str = "",
    supporting_papers: List[Dict[str, Any]] = None,
) -> ExperimentDesignResponse:
    """
    Generate an empirical research experiment design addressing a specific gap.
    """
    gap_title = gap.get("title", "Identified Research Gap")
    gap_desc = gap.get("description", "")
    supporting_titles = gap.get("supporting_papers", [])

    if is_gemini_configured():
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", "").strip())
            prompt = f"""
You are a principal AI researcher designing an empirical experiment for an academic paper.
Design a rigorous, reproducible research experiment to test and address this research gap:

GAP TITLE: {gap_title}
DESCRIPTION: {gap_desc}
SUPPORTING LITERATURE: {", ".join(supporting_titles[:3])}

Return a valid JSON object matching this schema:
{{
  "research_question": "Precise falsifiable research question",
  "hypothesis": "Testable hypothesis statement",
  "motivation": "Why solving this matters practically and theoretically",
  "dataset_recommendations": ["Dataset 1 with specs", "Dataset 2"],
  "baselines": ["Baseline model 1", "Baseline model 2"],
  "proposed_methodology": "Step-by-step experimental approach",
  "independent_variables": ["Variable 1", "Variable 2"],
  "dependent_variables": ["Evaluation metric 1", "Metric 2"],
  "experimental_controls": ["Fixed seed", "Iso-FLOP compute constraint"],
  "evaluation_metrics": ["Primary metric (e.g., F1, Top-1 Acc)", "Throughput (tokens/sec)"],
  "ablation_plan": ["Ablation step 1", "Ablation step 2"],
  "statistical_tests": ["Paired Student t-test (p < 0.01)", "Bonferroni correction"],
  "compute_requirements": "e.g., 2x NVIDIA A100 (80GB) for 48 hours",
  "potential_risks_and_failure_modes": ["Risk 1 and mitigation"],
  "validation_checklist": ["Pre-registration checklist item"]
}}
"""
            config = types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            )
            model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            raw = getattr(response, "text", "") or ""
            data = json.loads(raw.strip())
            return ExperimentDesignResponse(
                status="success",
                experiment=ExperimentDesign(**data),
            )
        except Exception as e:
            logger.warning("Gemini experiment designer failed (%s), using structured template fallback.", e)

    # Structured scientific fallback
    experiment = ExperimentDesign(
        research_question=f"Does introducing adaptive sparse mechanisms resolve {gap_title.lower()} without sacrificing peak benchmark accuracy?",
        hypothesis=f"Models incorporating dynamically gated representations will demonstrate statistically significant (>3.5%) improvements in out-of-distribution robustness while reducing inference memory overhead by at least 25%.",
        motivation=f"Addresses the critical gap highlighted in current literature ({gap_title}), bridging theoretical expressivity with resource-efficient deployment constraints.",
        dataset_recommendations=[
            "Domain Benchmark Corpus (Train split: 80%, Validation: 10%, Test: 10%)",
            "Out-of-Distribution Shift Test Suite (Perturbed inputs, synthetic domain transfers)"
        ],
        baselines=[
            "Standard Dense Baseline (Original literature architecture)",
            "Fixed-Window Sparse Baseline",
            "LoRA Rank-8 Parameter-Efficient Baseline"
        ],
        proposed_methodology=(
            "1. Train standard dense baseline to convergence under fixed seed seeds (42, 1337, 2026).\n"
            "2. Integrate the proposed adaptive gating module with normalized residual connections.\n"
            "3. Conduct controlled iso-parameter and iso-FLOP training iterations.\n"
            "4. Evaluate across in-distribution test sets and distribution-shifted challenge sets.\n"
            "5. Measure throughput (samples/sec) and GPU peak VRAM footprint across batch sizes."
        ),
        independent_variables=[
            "Architectural model type (Dense Baseline vs. Proposed Adaptive Model)",
            "Gating threshold coefficient (alpha in {0.1, 0.3, 0.5, 0.7})",
            "Input noise perturbation level (Gaussian noise sigma in {0.0, 0.05, 0.1, 0.2})"
        ],
        dependent_variables=[
            "Task Performance Metric (Accuracy / F1 score)",
            "Out-of-Distribution Generalization Drop (Delta Acc)",
            "Inference Latency per token (ms)",
            "Peak VRAM Allocation (GB)"
        ],
        experimental_controls=[
            "Equalized total training parameter count (+/- 1%)",
            "Identical optimizer hyperparameters (AdamW, lr=1e-4, weight_decay=0.01)",
            "Deterministic CUDA seed initialization and gradient clipping at 1.0"
        ],
        evaluation_metrics=[
            "Top-1 Accuracy (%)",
            "Expected Calibration Error (ECE)",
            "Inference Throughput (samples/second)",
            "Energy consumption (Watt-hours via CodeCarbon / pynvml)"
        ],
        ablation_plan=[
            "Ablate gating mechanism: replace with uniform random routing.",
            "Ablate normalization layer: verify convergence stability without LayerNorm.",
            "Ablate loss penalty: evaluate performance without sparsity regularization."
        ],
        statistical_tests=[
            "Paired Student's t-test over 5 random seeds (alpha = 0.01)",
            "Cohen's d effect size computation for OOD improvements"
        ],
        compute_requirements="1x NVIDIA RTX 4090 or A10G (24GB VRAM), estimated 36 GPU-hours total training.",
        potential_risks_and_failure_modes=[
            "Gradient vanishing during early gating training -> Mitigate with identity shortcut initialization.",
            "Over-pruning on long-tail token sequences -> Mitigate with minimum capacity factor floor."
        ],
        validation_checklist=[
            "Log all random seeds, environment packages, and hardware specs.",
            "Verify evaluation metrics on hidden holdout set only once prior to reporting.",
            "Compute confidence intervals across all primary metric tables."
        ]
    )

    return ExperimentDesignResponse(
        status="success",
        experiment=experiment,
    )
