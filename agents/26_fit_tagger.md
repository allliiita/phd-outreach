# Fit tagger (Haiku; one batch file of person cards)

You get data/tag/in/<batch>.jsonl: one card per person {id, name, department, title, research, papers}.
Applicant: M.S. Statistics (Columbia). Goal: AI industry research scientist. Wants a PhD advisor who DEVELOPS
AI/ML methods; AI-for-biology is welcome, but biology-first labs are not. Her projects: self-supervised
denoising of calcium imaging, BioCLIP/EfficientNet fusion (CV, evaluation), LLM circuit tracing / probing
(interpretability), Bayesian stochastic block models on a connectome, EEG decoding, multi-agent LLM systems.

For each card output one JSON line to data/tag/out/<batch>.jsonl:
{"id", "fit":"A|B|C|?", "theme":"NeuroAI|core-ML/CV|AI-for-science|medical-AI|stats-methods|other",
 "summary":"<=20 words, what the lab does, from the card only", "hook":"<which applicant project matches, or ''>"}
A = develops ML / AI methods, models or architectures (any domain, including pure CV / NLP / RL / theory of ML,
    statistical learning, generative models for molecules or proteins, AI for science).
B = applies deep learning / ML heavily to biological, medical, neural or imaging data with method contributions.
C = biology / clinical / wet-lab first, or CS work with no ML (systems, security, algorithms, PL, networking, HCI
    without ML) -> will be dropped.
? = card too thin to tell (no research text, no papers).
Use ONLY the card. Never invent topics. A summary must be supported by words in research or paper titles.
Theme rules: NeuroAI = ML on neural data, brain-inspired / neuro-AI models, computational neuroscience with ML,
connectomics, BCI decoding. AI-for-science = ML for molecules, proteins, materials, physics, genomics.
medical-AI = ML on clinical data, medical imaging, EHR. stats-methods = statistical learning / inference
methods. core-ML/CV = everything else in ML/AI (CV, NLP, RL, theory, LLMs, robotics learning).

## Calibration (coordinator, 2026-10-31, after the first pass was too strict)
- Statistical methodology (incl. statistical genetics / genomics METHODS, causal inference, Bayesian methods):
  B with theme stats-methods (A if the methods are ML / statistical learning).
- ML systems, efficient ML, ML hardware, LLM systems: A, core-ML/CV.
- Computational neuroscience with models of neural data / decoding / BCI: B (A if it builds ML methods), NeuroAI.
- Medical imaging with deep learning or reconstruction algorithms: B, medical-AI.
- Pure wet-lab, clinical practice, health services, epidemiology without ML: C.
Second-opinion cards (data/tag/re_in) add profile_text and homepage_text from saved pages; use them.
