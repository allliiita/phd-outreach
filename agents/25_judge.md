# Judge (cheap model; one batch file, no browsing)

Input: one `data/judge/in/<stem>_NN.md` file. Each `## <id>` block is one person: name | title | department,
then their own research text, recent paper titles (indexed), and verbatim recruiting/start lines (indexed).
Use ONLY what is in the file. Do not open web pages. Do not use what you remember about these people.

Applicant (for `fit`): M.S. Statistics. Interests: statistical ML for scientific data, especially neural and
biological imaging; self-supervised / representation learning with limited labels; evaluation and
interpretability of deep models. Project keys: arborphy (CV, foundation models, biodiversity, evaluation),
calcium (calcium imaging, self-supervised denoising, matrix factorization, comp. neuroscience),
interp (LLM mechanistic interpretability), flywire (Bayesian SBM on connectome, networks),
eeg (EEG decoding, BCI, time series), agents (LLM systems, reliability, evaluation).

Write one JSON line per person to `data/judge/out/<stem>_NN.jsonl`:
```json
{"id":"...","relevance":"yes|borderline|no","relevance_reason":"<=20 words, cite research text or paper [i]",
 "keywords":["3-8 specific phrases COPIED from the research text or paper titles"],
 "papers":[0,2],"fit":1,"fit_projects":["calcium"],
 "recruiting":"Confirmed|Not recruiting|Unknown","recruiting_index":0,"start_year":2023,
 "position_class":null,"notes":""}
```
- **relevance** (rule 7 of 00_rules.md): `yes` if research text or ≥1 paper is ML, deep learning, NLP, CV, RL,
  statistical learning, Bayesian methods, causal inference, comp. biology, bioinformatics, genomics,
  AI for science, computational neuroscience/medicine. `borderline` if unclear or there is no research text
  and titles are ambiguous. For `FILTER: ML-relevant faculty only` units, `yes` needs clear ML/statistical work.
- **keywords**: exact substrings (case-insensitive) of the research text or titles; specific
  ("conformal inference", "single-cell RNA-seq"), never "machine learning" / "statistics" / "AI". Phrases that
  are not substrings are deleted automatically, so do not paraphrase.
- **papers**: indices of up to 3 papers, most relevant to the applicant first.
- **fit** 1-5: 5 = their work directly overlaps an applicant project (name it in fit_projects); 3 = adjacent
  methods; 1 = unrelated. Judge the overlap of *topics*, not prestige.
- **recruiting**: `Confirmed` / `Not recruiting` only if a `recruit[i]` line says so about PhD students, give
  its index. Otherwise `Unknown` (code sets `Possible` for assistant professors itself).
- **start_year**: only if a `start:` line states when they joined this institution; else null.
- **position_class**: null unless the text shows the roster title misleads (e.g. primary appointment at
  another university → `other`, with the reason in notes).
- **notes**: uncertainty only (e.g. "papers look like a different person"). Empty is fine.

Output nothing but the JSONL file. Report back one line: `<file>: N judged, Y yes, B borderline`.
