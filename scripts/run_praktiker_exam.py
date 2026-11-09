"""Run the IT-Grundschutz-Praktiker exam questions against the GSKI corpus, with and without retrieval.

Usage: uv run python scripts/run_praktiker_exam.py . data/results/praktiker-exam-<date> [models...]
Reads LITELLM_API_BASE, LITELLM_API_KEY and EMBEDDING_MODEL from the environment (an OpenAI-compatible gateway; AISC_API_KEY and the AI Hub as fallback). Caches embeddings in <out_dir>. Answers issue #15.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

BASE_URL = os.environ.get("LITELLM_API_BASE", "https://api.aisc.hpi.de/v1")
EMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "octen-embedding-8b")
TOP_K = 5
SYSTEM = (
    "Du bist ein Experte für Informationssicherheit und IT-Grundschutz (BSI). "
    "Beantworte die Multiple-Choice-Frage. Es können mehrere Antworten korrekt sein. "
    "Antworte ausschließlich mit JSON der Form {\"answers\": [\"A\", \"C\"]}."
)
SYSTEM_RAG = SYSTEM + " Stütze dich auf die bereitgestellten Dokumentauszüge; wenn sie nicht ausreichen, nutze dein Wissen über den IT-Grundschutz."


def build_docs(repo: Path) -> list[dict]:
    gs = json.load(open(repo / "data/data_preprocessed/grundschutz.json"))
    docs: list[dict] = []
    for schicht in gs.get("schichten", []):
        for b in schicht.get("bausteine", []):
            bid, titel = b.get("id"), b.get("titel")
            for key in ("beschreibung", "gefaehrdungslage"):
                text = (b.get(key) or {}).get("text", "") if isinstance(b.get(key), dict) else (b.get(key) or "")
                if text:
                    docs.append({"id": f"{bid}:{key}", "text": f"{bid} {titel}, {key}: {text}", "src": f"Kompendium {bid}"})
            anf = b.get("anforderungen") or {}
            for level, reqs in anf.items():
                for req in reqs if isinstance(reqs, list) else []:
                    text = req.get("inhalt", "")
                    if text:
                        docs.append({"id": req.get("id"), "text": f"{req.get('id')} ({level}): {text}", "src": f"Kompendium {req.get('id')}"})
    for g in gs.get("elementare_gefaehrdungen", []):
        text = (g.get("beschreibung") or "") + " " + " ".join(g.get("beispiele") or [])
        if text.strip():
            docs.append({"id": g["id"], "text": f"{g['id']} {g.get('titel')}: {text}", "src": f"Kompendium {g['id']}"})
    for f in sorted((repo / "data/data_preprocessed/standards").glob("standard_*/*.json")):
        d = json.load(open(f))
        text = d.get("content", "")
        if text:
            src = d.get("source", {}).get("document", f.parent.name)
            pages = d.get("pages", {})
            docs.append({"id": f"{f.parent.name}:{d.get('id')}", "text": f"{d.get('header', '')}\n{text}", "src": f"{src} S. {pages.get('start')}"})
    gl = json.load(open(repo / "data/data_preprocessed/glossar.json"))
    for t in gl.get("terms", []) if isinstance(gl.get("terms"), list) else []:
        term = t.get("term") or t.get("begriff") or ""
        defi = t.get("definition") or t.get("text") or ""
        if term and defi:
            docs.append({"id": f"glossar:{term}", "text": f"{term}: {defi}", "src": "Glossar"})
    return docs


def embed(client: OpenAI, texts: list[str], cache: Path) -> np.ndarray:
    if cache.exists():
        arr = np.load(cache)
        if len(arr) == len(texts):
            return arr
    out: list[list[float]] = []
    for i in range(0, len(texts), 32):
        batch = [t[:6000] for t in texts[i : i + 32]]
        for attempt in range(5):
            try:
                r = client.embeddings.create(model=EMBED_MODEL, input=batch)
                out.extend([e.embedding for e in r.data])
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 4:
                    raise
                time.sleep(2 * (attempt + 1))
                print("embed retry", i, exc, file=sys.stderr)
        print(f"embedded {len(out)}/{len(texts)}", file=sys.stderr)
    arr = np.array(out, dtype=np.float32)
    np.save(cache, arr)
    return arr


def parse_answers(text: str) -> list[str]:
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            a = json.loads(m.group(0)).get("answers", [])
            return sorted({str(x).strip().upper()[:1] for x in a if str(x).strip()})
        except json.JSONDecodeError:
            pass
    return sorted(set(re.findall(r"\b([A-F])\b", text)))


def ask(client: OpenAI, model: str, q: dict, context: list[dict] | None) -> dict:
    opts = "\n".join(f"{o['letter']}) {o['text']}" for o in q["options"])
    user = f"Frage: {q['question']}\n{opts}"
    if context:
        ctx = "\n\n".join(f"[{d['src']}] {d['text'][:1500]}" for d in context)
        user = f"Dokumentauszüge:\n{ctx}\n\n{user}"
    for attempt in range(5):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": SYSTEM_RAG if context else SYSTEM}, {"role": "user", "content": user}],
                temperature=0.0,
                max_tokens=4000,
            )
            text = r.choices[0].message.content or ""
            break
        except Exception as exc:  # noqa: BLE001
            if attempt == 4:
                raise
            time.sleep(3 * (attempt + 1))
            print("chat retry", q["id"], exc, file=sys.stderr)
    given = parse_answers(text)
    correct = sorted(q["correct"])
    letters = [o["letter"] for o in q["options"]]
    per_option = sum((l in given) == (l in correct) for l in letters) / len(letters)
    return {"id": q["id"], "given": given, "correct": correct, "exact": given == correct, "per_option": per_option,
            "sources": [d["src"] for d in context] if context else [], "raw": text[-300:]}


def main() -> None:
    repo, out = Path(sys.argv[1]), Path(sys.argv[2])
    models = sys.argv[3:] or ["gpt-oss-120b"]
    out.mkdir(parents=True, exist_ok=True)
    client = OpenAI(base_url=BASE_URL, api_key=os.environ.get("LITELLM_API_KEY") or os.environ["AISC_API_KEY"])
    qs = json.load(open(repo / "data/data_evaluation/08_IT-GS-Praktiker-Pruefungsfragen.json"))["questions"]
    docs = build_docs(repo)
    print(f"{len(qs)} questions, {len(docs)} documents", file=sys.stderr)
    vecs = embed(client, [d["text"] for d in docs], out / "doc_embeddings.npy")
    qvecs = embed(client, [q["question"] + "\n" + "\n".join(o["text"] for o in q["options"]) for q in qs], out / "question_embeddings.npy")
    qd = QdrantClient(":memory:")
    qd.create_collection("gski", vectors_config=VectorParams(size=vecs.shape[1], distance=Distance.COSINE))
    qd.upsert("gski", [PointStruct(id=i, vector=vecs[i].tolist(), payload={"i": i}) for i in range(len(docs))])
    contexts = []
    for qv in qvecs:
        hits = qd.query_points("gski", query=qv.tolist(), limit=TOP_K).points
        contexts.append([docs[h.payload["i"]] for h in hits])
    summary = {}
    for model in models:
        for cond in ("rag", "no_rag"):
            with ThreadPoolExecutor(4) as ex:
                res = list(ex.map(lambda qc: ask(client, model, qc[0], qc[1] if cond == "rag" else None), zip(qs, contexts)))
            exact = sum(r["exact"] for r in res)
            per_opt = sum(r["per_option"] for r in res) / len(res)
            summary[f"{model}/{cond}"] = {"exact": exact, "n": len(res), "exact_pct": round(100 * exact / len(res), 1), "per_option_pct": round(100 * per_opt, 1)}
            json.dump(res, open(out / f"results_{model}_{cond}.json", "w"), ensure_ascii=False, indent=1)
            print(model, cond, summary[f"{model}/{cond}"], file=sys.stderr)
    json.dump({"docs": len(docs), "top_k": TOP_K, "embed_model": EMBED_MODEL, "summary": summary}, open(out / "summary.json", "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
