"""Deterministic relevance / fit from a dossier: no LLM. Replaces the judge pass for ranking.

Applicant target (2026-10 decision): broad AI, and above all Bio-AI. Score = AI depth + bio depth, with a
bonus when both appear (AI for biology / medicine / neuroscience). Keywords are lexicon phrases found
verbatim in the person's own research text or paper titles, so nothing is invented.
The LLM looks at a person only at email time (writer decides "write / skip"), i.e. only for people we email.
"""
from __future__ import annotations

import re

AI = {  # phrase -> weight
    "machine learning": 2, "deep learning": 3, "neural network": 2, "foundation model": 3, "language model": 3,
    "llm": 3, "large language": 3, "transformer": 2, "representation learning": 3, "self-supervised": 3,
    "generative model": 3, "diffusion model": 3, "computer vision": 3, "reinforcement learning": 2,
    "interpretab": 3, "explainab": 2, "artificial intelligence": 2, "ai ": 1, "graph neural": 3,
    "statistical learning": 2, "bayesian": 1, "causal inference": 1, "high-dimensional": 1, "multimodal": 2,
    "contrastive": 2, "embedding": 1, "data-driven": 1, "computational model": 1, "variational": 1,
    "probabilistic model": 1, "optimization": 1, "uncertainty quantification": 1, "dimensionality reduction": 1,
    "statistical method": 2, "statistical model": 2, "methodolog": 1, "estimation": 1, "inference": 1,
    "regression": 1, "prediction": 1, "latent": 1, "network analysis": 1,
}
BIO = {
    "single-cell": 3, "single cell": 3, "spatial transcriptom": 3, "genomic": 2, "genetic": 1, "protein": 2,
    "biolog": 2, "biomedical": 2, "medical imag": 3, "microscopy": 3, "imaging": 2, "neuro": 2, "brain": 2,
    "neural data": 3, "neural population": 3, "calcium imaging": 3, "cell": 1, "gene ": 1, "molecular": 1,
    "drug": 2, "clinical": 1, "health": 1, "disease": 1, "electronic health record": 2, "ehr": 1, "omics": 2,
    "sequencing": 2, "pathology": 2, "cancer": 1, "biodiversity": 2, "ecolog": 1, "connectom": 3, "eeg": 2,
}


def _hits(text: str, lex: dict) -> tuple[int, list[str]]:
    t = " " + text.lower() + " "
    found = [k.strip() for k in lex if k in t]
    return sum(lex[k] for k in lex if k in t), found


def score(d: dict) -> dict:
    text = d["research"]["text"] + " " + " ".join(p["title"] for p in d.get("papers", []))
    ai, ai_kw = _hits(text, AI)
    bio, bio_kw = _hits(text, BIO)
    ai, bio = min(ai, 8), min(bio, 8)
    fit = 1 + (ai >= 3) + (ai >= 6) + (bio >= 3) + (ai >= 3 and bio >= 3)   # 1..5; 5 = Bio-AI
    rel = "yes" if ai >= 3 or (ai >= 1 and bio >= 3) else ("borderline" if ai or bio >= 3 else "no")
    kws = _phrases(text, ai_kw + bio_kw)
    return {"relevance": rel, "fit": fit, "keywords": kws, "fit_projects": [],
            "relevance_reason": f"auto: AI {ai} ({', '.join(ai_kw[:4])}); bio {bio} ({', '.join(bio_kw[:4])})"}


def _phrases(text: str, seeds: list[str]) -> list[str]:
    """Short verbatim phrases around lexicon hits (e.g. 'single-cell foundation models'), for emails/keywords."""
    out = []
    for s in seeds:
        m = re.search(r"(?<![\w-])(?:[\w-]+\s){0,2}" + re.escape(s) + r"[\w-]*(?:\s[\w-]+){0,2}", text, re.I)
        if m:
            ph = m.group(0).strip(" ,.;:")
            if ph.lower() not in (x.lower() for x in out):
                out.append(ph)
    return out[:8]
