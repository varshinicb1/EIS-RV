# NVIDIA Alchemi — what we use, what we don't, and what each costs to wire

NVIDIA Alchemi is a family of NIMs (NVIDIA Inference Microservices)
hosted at `integrate.api.nvidia.com`, plus a Python toolkit
(`nvalchemi-toolkit`) that wraps several of them. Different
microservices use different request shapes — they are NOT all
OpenAI-compatible.

## What's hosted (as of mid-2025)

| Service | Purpose | Endpoint shape | Status in RĀMAN Studio |
|---|---|---|---|
| Llama-3.3-70B-Instruct | General chat (default in our code) | OpenAI-compatible `/v1/chat/completions` | **WIRED** — `src/ai_engine/nim_client.py` |
| Llama-3.1-8B-Instruct  | Faster chat | OpenAI-compat | WIRED via the `"fast"` model alias |
| Nemotron-4-340B / Llama-3.3-Nemotron-49B | NVIDIA-tuned chat variants | OpenAI-compat | WIRED via aliases |
| Mixtral 8x22B | Mixture-of-experts chat | OpenAI-compat | WIRED via alias |
| **MACE-MP-0**       | Universal MLIP (energies, forces, stress) | Custom NIM, ASE-style atoms input | **NOT WIRED** |
| **ORB-v3**          | Universal MLIP | Custom NIM | **NOT WIRED** |
| **SevenNet-0**      | Graph-NN MLIP | Custom NIM | **NOT WIRED** |
| **MatterSim**       | Microsoft foundation MLIP | Custom NIM | **NOT WIRED** |
| **MolMIM**          | Molecular generation (SMILES) | NIM, SMILES-in / SMILES-out | NOT WIRED |
| **DiffCSP**         | Crystal structure generation | NIM | NOT WIRED |
| **ESMFold / AlphaFold-2** | Protein structure | NIM | NOT WIRED, out of scope |
| **DiffDock**        | Docking | NIM | NOT WIRED, out of scope |
| **BioMegatron**     | Biomedical literature retrieval | NIM | NOT WIRED — we use the local research pipeline (arXiv/Crossref/S2) instead |

## Honest math on utilisation

Of Alchemi's catalogue:

- **Chat completions**: ~6 endpoints, **6 wired**. ✓
- **Materials property prediction (MLIPs)**: 4 endpoints, **0 wired**.
- **Generative materials**: 2 endpoints (MolMIM, DiffCSP), **0 wired**.
- **Bio**: 4+ endpoints, intentionally out of scope.

Excluding bio, we use roughly **6 of ~12 relevant endpoints (50 %)**, and
of those 6, all are the same OpenAI-compatible chat shape. The
MLIPs — which are arguably the headline of "Alchemi for materials" —
are not wired.

## Why the MLIPs aren't wired (yet)

Each MLIP NIM has its own request schema. Roughly:

```http
POST https://api.nvcf.nvidia.com/v2/nvcf/pexec/functions/<function-id>
{
  "atoms": {
     "positions":   [[x,y,z], ...],   # Å
     "species":     ["Au", "Au", ...],
     "cell":        [[ax,ay,az], ...],  # 3x3 lattice
     "pbc":         [true, true, true]
  },
  "task": "energy" | "forces" | "stress" | "relax"
}
```

Wiring them properly means:

1. Adding an `MLIPClient` next to `NIMClient` that talks to the
   correct function-id per model (the function ids are listed in
   <https://build.nvidia.com/explore/discover>).
2. Validating + serialising ASE-style `atoms` input.
3. Parsing the response into a uniform `MaterialPropertyResult`.
4. Cost-tracking — these calls are billed differently from chat.

Estimated work: ~1 day. The audit's previous bridge code targeted
URLs like `/optimize`, `/predict`, `/properties`, `/md`, which **do
not exist** on `integrate.api.nvidia.com`. Those calls 404'd and the
old code fell back to a 13-row hand-typed dict. The current honest
behaviour is to refuse those calls explicitly until the real MLIP
client is built.

## What to wire next, in priority order

For an electrochemistry product, the practical ranking:

1. **MACE-MP-0** — universal MLIP, predicts energies/forces well across
   the periodic table. Useful for: cohesive energy, bulk modulus,
   relative stability of phases. **Highest leverage for materials
   selection.**
2. **ORB-v3** — similar territory, different accuracy/speed tradeoff.
   Worth offering as an alternate for the same input shape.
3. **MolMIM** — generative SMILES for organic redox shuttles, electrolyte
   additives. Niche but valuable for biosensor work.
4. **DiffCSP** — crystal-structure-from-formula. Niche; nice-to-have.
5. **SevenNet, MatterSim** — alternates to MACE/ORB; defer until users
   ask for a specific one.

## What we offer **today** in lieu of MLIPs

The new `AlchemiBridge.estimate_properties` falls through these tiers:

1. **Your lab dataset** (encrypted local store, see
   `LabDatasetManager` — the new piece in this phase). Highest
   priority. Source: `lab_dataset`.
2. **Curated 48-material reference DB** under
   `src/backend/core/engines/materials_db.py`. Source: `curated_db`.
3. **LLM JSON estimate** via the OpenAI-compatible chat endpoint with
   schema validation. Source: `llm_estimate` — clearly flagged as not
   computational chemistry.
4. **Refusal**: if none of the above can supply a value, we return
   `source: unavailable` with a reason — we never fabricate.

The LLM estimate is a *real* call to a real model and the answers are
plausible (Bi₂WO₆ → 2.7 eV, matches literature), but it is not an MLIP
and we say so. Adding the MLIPs would replace tier 3 with quantum-
accurate values for materials in the periodic-table-supported range.

## Cost model

- Chat completions: priced per million tokens. A typical materials
  question costs <0.001 USD on Llama-3.3-70B.
- MLIP NIMs: priced per request (or per "function execution" in
  NVCF terminology). For inference-only, typically <0.005 USD per
  small calculation.
- The `nvalchemi-toolkit` package abstracts the billing so a single
  API key covers both.

For a $5 / month subscription tier, both chat and (eventually) MLIP
calls fit comfortably as long as we cap per-user request rates.

## Where the toolkit fits

`nvalchemi-toolkit` (which the original `requirements.txt` had
commented out as "uncomment when available") is the official Python
SDK that wraps the MLIP NIMs. When we wire MLIPs, we'll either:

- Use the toolkit directly (faster, but pulls a larger dep tree
  including ASE), or
- Talk to the function-id endpoints with `requests` (smaller dep, more
  code).

Phase 6 sticks with the curated DB + lab data + LLM tier. Phase 7
should add the MLIP client.
