"""Analysis schema + LLM-output normalisation tests."""

from __future__ import annotations

import json

from app.analysis.paper_analyzer import SYSTEM_INSTRUCTION, _parse_analysis, build_prompt
from app.schemas.analysis import NOT_STATED, PaperAnalysis

REQUIRED_KEYS = {
    "research_problem",
    "existing_approach",
    "proposed_method",
    "architecture",
    "dataset",
    "model_algorithm",
    "results",
    "limitations",
    "additional_technical_limitations",
    "why_approach_may_fail",
    "research_gap",
    "possible_improvements",
    "new_research_direction",
    "overall_assessment",
}


def test_schema_exposes_exactly_the_documented_keys():
    assert set(PaperAnalysis.model_fields) == REQUIRED_KEYS


def test_placeholders_become_not_stated():
    analysis = PaperAnalysis.model_validate(
        {
            "research_problem": "N/A",
            "dataset": "unknown",
            "results": "",
            "overall_assessment": "None",
        }
    )
    assert analysis.research_problem == NOT_STATED
    assert analysis.dataset == NOT_STATED
    assert analysis.results == NOT_STATED
    assert analysis.overall_assessment == NOT_STATED


def test_bullets_are_cleaned_and_markdown_removed():
    analysis = PaperAnalysis.model_validate(
        {
            "limitations": [
                "**Author-stated limitation:** Small dataset size.",
                "- Limited to one domain.",
                {"limitation": "No ablation study"},
                "",
                "N/A",
            ],
            "research_gap": {
                "author_stated_gaps": ["Author-stated gap: no cross-domain evaluation"],
                "ai_inferred_gaps": "AI-inferred gap: no uncertainty quantification",
            },
        }
    )
    assert analysis.limitations[0] == "Author-stated limitation: Small dataset size."
    assert "Limited to one domain." in analysis.limitations
    assert any("No ablation study" in item for item in analysis.limitations)
    assert len(analysis.limitations) == 3
    # A string gap block is coerced into the AI-inferred list.
    assert analysis.research_gap.ai_inferred_gaps == [
        "AI-inferred gap: no uncertainty quantification"
    ]
    assert analysis.research_gap.author_stated_gaps[0].startswith("Author-stated gap:")


def test_prose_strings_are_split_into_items():
    analysis = PaperAnalysis.model_validate(
        {"possible_improvements": "Add uncertainty estimates. Test on more datasets."}
    )
    assert len(analysis.possible_improvements) == 2


def test_parse_analysis_accepts_fenced_json_and_wrappers():
    payload = {key: "" for key in REQUIRED_KEYS}
    payload["research_problem"] = "Graphs are hard."
    payload["research_gap"] = {"author_stated_gaps": [], "ai_inferred_gaps": []}

    fenced = "```json\n" + json.dumps(payload) + "\n```"
    parsed = _parse_analysis(fenced)
    assert parsed is not None and parsed.research_problem == "Graphs are hard."

    wrapped = json.dumps({"analysis": payload})
    assert _parse_analysis(wrapped) is not None

    assert _parse_analysis("I could not analyse this paper.") is None
    assert _parse_analysis("") is None


def test_system_instruction_states_the_honesty_rules():
    # The rules travel in the system instruction (see GeminiClient) so they
    # are always applied, independently of the paper content.
    assert "Never invent datasets" in SYSTEM_INSTRUCTION
    assert '"AI-inferred limitation:"' in SYSTEM_INSTRUCTION
    assert '"Author-stated gap:"' in SYSTEM_INSTRUCTION
    assert "Not stated in the provided paper." in SYSTEM_INSTRUCTION


def test_prompt_contains_schema_and_paper_content():
    prompt = build_prompt(
        title="Graph Neural Networks for Drug Discovery",
        abstract="An abstract about GNNs.",
        paper_text="Method: message passing.",
    )
    assert "Graph Neural Networks for Drug Discovery" in prompt
    assert "message passing" in prompt
    for key in REQUIRED_KEYS:
        assert key in prompt

    abstract_only = build_prompt("Title here", "abstract", "", abstract_only=True)
    assert "full text could not be retrieved" in abstract_only
