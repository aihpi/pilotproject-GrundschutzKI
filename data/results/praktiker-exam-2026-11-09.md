# IT-Grundschutz-Praktiker exam run, 2026-11-09

Run by the KI-Servicezentrum on 2026-11-09, after the project. `scripts/run_praktiker_exam.py` answers the 71 multiple-choice questions of `data/data_evaluation/08_IT-GS-Praktiker-Pruefungsfragen.json` (repository pilotproject-GrundschutzKI, provided by FGHGsD) with and without retrieval. Corpus: 2516 documents built from the preprocessed Kompendium (requirements, Baustein descriptions, threat descriptions), the four BSI standards 200-1 to 200-4 in section chunks, and the glossary; embeddings octen-embedding-8b, in-memory Qdrant, top-k 5, question plus options as the query. Models gpt-oss-120b and gemma-4-31b through the AI Hub, temperature 0, answers as JSON letter sets. A question counts as correct only when the letter set matches exactly; `per_option` counts each option decision. Pass mark per issue #12: 60 percent (30 of 50); grading bands 70 to 79 "mit Erfolg", 80 to 89 "mit gutem Erfolg".

| Model | Retrieval | Exact | Per option |
|---|---|---|---|
| gpt-oss-120b | yes | 54 of 71 (76.1 percent) | 89.8 percent |
| gpt-oss-120b | no | 46 of 71 (64.8 percent) | 87.7 percent |
| gemma-4-31b | yes | 56 of 71 (78.9 percent) | 94.0 percent |
| gemma-4-31b | no | 53 of 71 (74.6 percent) | 91.2 percent |

Retrieval gained gpt-oss-120b 10 questions and lost 2. Retrieved context came mostly from the standards (200-2: 147 of 355 hits, Kompendium 65, glossary 58), since the exam asks about method. Two gemma answers with retrieval could not be parsed and count as wrong. One run per condition, no repeats.
