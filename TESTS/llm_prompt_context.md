# LLM Active Learning Prompt — Context & Recommended Additions

## What the LLM currently has (system prompt in `activeLearning_29.py`)

- Goal: "maximize modulus" ← **WRONG** (outdated)
- Parameter ranges
- Prior observations (final_report per condition, concatenated)

---

## What the LLM is missing

### 1. Correct optimization objective

**Minimize Strain at 50 bar** (lower strain = stiffer membrane = better mechanical performance under pressure).  
Elastic Modulus is a secondary signal — use it directionally when Strain at 50 bar is unavailable.

### 2. Process physics — what each parameter actually does

| Parameter | Range | Effect on membrane |
|---|---|---|
| `mixing_temp` | 25–80°C | Higher temp → better polymer dissolution, lower solution viscosity, more homogeneous casting film. Too low → undissolved chains, heterogeneous structure. |
| `bath_temp` | 5–25°C | Lower temp → slower non-solvent diffusion → denser, more symmetric pore structure → lower strain (stiffer). Higher temp → faster exchange → open finger-like pores → more compliant. |
| `weight_percent` | 10–17% | Higher concentration → more polymer per unit volume → denser matrix → lower strain. Too high → very viscous, hard to cast uniformly. |
| `pullcast_speed` | 1–20 mm/s | Faster speed → thinner film → thinner membrane → may affect surface smoothness and skin layer. Slower → thicker, more uniform. |
| `coupon_to_bath_wait_time` | 0–600 s | Time between casting and bath immersion. Longer = more solvent evaporation = thicker skin layer. Too long → skin seals surface, blocks non-solvent ingress → weak or no phase separation below skin → mechanically degenerate or no membrane at all. Too short → no skin, open structure, compliant. |
| `nitrogen` | True/False | If True: coupon is blown with dry N₂ during wait time, removing ambient humidity. Prevents moisture-induced premature phase separation at the surface. When nitrogen=True and wait time is very long, the skin may become too dense. |
| `nips_bath_wait_time` | 1200–1800 s | Time in coagulation bath. Longer = more complete phase separation and solvent exchange = better-defined structure. Rarely the limiting variable once ≥1200 s. |

### 3. How to read OUTCOME codes in observations

Each prior observation ends with an OUTCOME block. Interpretation rules:

| OUTCOME | Meaning for parameter suggestion |
|---|---|
| `NO_MEMBRANE` | Hardware failure — zero chemical information. Do NOT use this result to change parameters. Note it happened and move on. |
| `PARTIAL_SINGLE_*` | Solution ran out or positional offset. Weak signal at best. Make a broad exploratory move, not fine-tuning. |
| `PARTIAL_COVERAGE_GOOD_FIT` | Real data, low N. Use strain directionally. Minor tweak acceptable. |
| `PARTIAL_COVERAGE_MIXED_FIT` | Near phase boundary. Larger change warranted. |
| `PARTIAL_COVERAGE_NO_FIT` | Structurally bad. Major change needed. |
| `GOOD` | High-confidence data. Fine-tune toward objective. |
| `MOSTLY_GOOD` | Reliable. Moderate refinement. Don't over-index on CV. |
| `POOR_FIT` | Mechanically inconsistent. Significant change needed. |
| `NO_FIT` | Structurally degenerate. Major change required — not just tweaking one param. |

### 4. Search strategy the LLM should follow

- **Don't get stuck in local search.** If 3+ consecutive conditions have `NO_FIT`, `PARTIAL_COVERAGE_NO_FIT`, or `POOR_FIT`, this is not a fine-tuning problem — jump to a different region of parameter space.
- **Respect `NO_MEMBRANE` as hardware noise.** A run of `NO_MEMBRANE` outcomes contains zero information about chemistry. Don't increment `coupon_to_bath_wait_time` in response to them.
- **When `GOOD` exists:** identify which parameter values correlate with low Strain at 50 bar and refine in that direction. Use the CV to gauge consistency.
- **The evaporation time (`coupon_to_bath_wait_time`) has a cliff.** Too long → no membrane or structurally degenerate. The cliff appears to be around 300–400 s with N₂. Shorter no-N₂ waits (50–100 s) have produced the only confirmed membranes so far.
- **Nitrogen on + long wait = death zone** based on observations. If continuing to explore N₂=True, try shorter waits (< 300 s). Consider trying N₂=False with varied wait times.
- **Don't hold all other parameters constant** while searching one variable. If a 1D search along `coupon_to_bath_wait_time` keeps failing, change `nitrogen`, `mixing_temp`, or `bath_temp` simultaneously.

### 5. Output format

The LLM must return a JSON object (inside a ```json ... ``` code fence or as raw JSON) with exactly these keys:

```json
{
  "mixing_temp": <int or float>,
  "bath_temp": <int or float>,
  "weight_percent": <int or float>,
  "volume": <int or float>,
  "pullcast_speed": <int or float>,
  "nitrogen": <true or false>,
  "coupon_to_bath_wait_time": <int or float>,
  "nips_bath_wait_time": <int or float>
}
```

`volume` is fixed at 1000. Do not omit any key.

---

## Recommended system prompt additions (paste into `activeLearning_29.py` system content)

```
OBJECTIVE: Minimize "Strain at 50 bar Mean". Lower values mean a stiffer, mechanically superior membrane. Elastic Modulus is a secondary directional signal only.

PROCESS CONTEXT:
- This is NIPS (non-solvent induced phase separation) membrane fabrication using polysulfone in PolarClean solvent.
- Coagulation bath (water) causes phase separation. Bath temperature, evaporation time, and polymer concentration are the dominant variables controlling pore structure and mechanical properties.
- mixing_temp controls polymer dissolution quality. bath_temp controls phase separation kinetics (lower = slower = denser = stiffer). weight_percent controls matrix density. coupon_to_bath_wait_time + nitrogen control skin layer formation.
- Very long evaporation times (especially with nitrogen) can cause the skin layer to seal the surface, blocking phase separation below — producing a structurally degenerate or absent membrane.

OUTCOME CODE RULES:
- NO_MEMBRANE: hardware failure. Contains zero chemical information. Do not adjust parameters based on this.
- NO_FIT / POOR_FIT / PARTIAL_COVERAGE_NO_FIT: membrane formed but mechanically unacceptable. Major parameter change required.
- GOOD / MOSTLY_GOOD: reliable data. Use Strain at 50 bar to guide refinement.
- PARTIAL_SINGLE_* or PARTIAL_COVERAGE_*: weak or noisy signal. Make broad moves, not fine-tuning.

SEARCH STRATEGY:
- If 3 or more consecutive conditions have NO_FIT, POOR_FIT, or NO_MEMBRANE outcomes, abandon the current region and make a large multi-parameter jump.
- Do not increment a single parameter by small amounts when surrounded by failed outcomes.
- Vary multiple parameters simultaneously when the current region is consistently failing.
- nitrogen=True with coupon_to_bath_wait_time > 300 s has repeatedly failed. Adjust accordingly.

OUTPUT: Return a single JSON object with keys: mixing_temp, bath_temp, weight_percent, volume, pullcast_speed, nitrogen, coupon_to_bath_wait_time, nips_bath_wait_time. volume is always 1000.
```

---

## Notes for future prompt updates

- Add known-good anchor points once more `GOOD` conditions accumulate (e.g., "conditions with Strain at 50 bar < 0.3 used mixing_temp=X, bath_temp=Y...")
- Consider adding a "reasoning" field to the output so the LLM explains its suggestion — useful for debugging why it stays stuck
- As hardware improves and NO_MEMBRANE rate drops, the NO_MEMBRANE instruction can be softened
