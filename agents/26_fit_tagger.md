# Fit tagger (Haiku; one batch file of person cards)

You get data/tag/in/<batch>.jsonl: one card per person {id, name, department, title, research, papers}.
Applicant: M.S. Statistics (Columbia). Goal: AI industry research scientist. Wants a PhD advisor who DEVELOPS
AI/ML methods; AI-for-biology is welcome, but biology-first labs are not. Her projects: self-supervised
denoising of calcium imaging, BioCLIP/EfficientNet fusion (CV, evaluation), LLM circuit tracing / probing
(interpretability), Bayesian stochastic block models on a connectome, EEG decoding, multi-agent LLM systems.

For each card output one JSON line to data/tag/out/<batch>.jsonl:
{"id", "fit":"A|B|C|?", "theme":"core-ML/CV|AI-for-science|NeuroAI|medical-AI|stats-methods|other",
 "summary":"<=20 words, what the lab does, from the card only", "hook":"<which applicant project matches, or ''>"}
A = develops ML / AI methods, models or architectures (any domain, including pure CV / NLP / RL / theory of ML,
    statistical learning, generative models for molecules or proteins, AI for science).
B = applies deep learning / ML heavily to biological, medical, neural or imaging data with method contributions.
C = biology / clinical / wet-lab first, or CS work with no ML (systems, security, algorithms, PL, networking, HCI
    without ML) -> will be dropped.
? = card too thin to tell (no research text, no papers).
Use ONLY the card. Never invent topics. A summary must be supported by words in research or paper titles.
