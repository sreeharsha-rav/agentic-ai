# --------------------------------------------------------------------------- #
# Multivariate analysis is a MULTI-TURN conversation:
#   Turn 1 (SELECTION)  — reason over the profile + a precomputed correlation
#                         matrix and decide which relationships clear the
#                         threshold / are worth plotting. No code yet.
#   Turn 2 (CODE GEN)   — given the selected relationships from Turn 1, emit ONE
#                         matplotlib script that renders exactly those.
# Reasoning history is carried across turns (context: current_turn -> all_turns)
# so the code generator is grounded in the selection reasoning, not re-guessing.
#
# SCOPE (v1 — deliberately limited): only numeric-vs-numeric and
# numeric-vs-categorical relationships are in scope. Categorical-vs-categorical
# and any 3+ variable / time-series interaction analysis are noted as future
# work, not attempted.
# --------------------------------------------------------------------------- #

MULTIVARIATE_SELECTION_INSTRUCTIONS = """
You are a senior data analyst planning the MULTIVARIATE analysis of an
already-cleaned, normalized tabular dataset. This is the SELECTION turn: you
decide WHICH relationships are worth visualizing. Do NOT write any plotting
code in this turn.

You are given:
  - a PROFILE of the cleaned CSV (schema, dtypes, null counts, cardinality, a
    preview), and
  - a precomputed CORRELATION report: the full numeric correlation matrix plus
    every numeric pair ranked by |r|, with a threshold marker. These are REAL
    computed numbers — reason against them, do not guess correlations.

SCOPE (v1 — deliberately limited): only two relationship types are in scope.
Do not select categorical-vs-categorical relationships or interactions across
three or more variables; if the data seems to call for those, record them under
`assumptions` as future work and skip them rather than guessing.

Selection rules:
1. numeric vs numeric
   - SELECT a scatter plot for a pair only when its |r| meets the stated
     threshold, OR when it is analytically interesting for a specific reason you
     state (e.g. Price Each vs Sales as a definitional relationship). For every
     numeric pair you considered, set `correlation` to its observed r,
     `meets_threshold` to whether |r| >= threshold, and `selected` accordingly.
   - ALWAYS select exactly one overall correlation heatmap across all numeric
     columns, regardless of threshold (variable_y = "" for it).
2. numeric vs categorical
   - SELECT a grouped boxplot or grouped bar-of-means for a numeric measure
     (e.g. Sales, Quantity) against a categorical column of manageable
     cardinality (e.g. City, or Product limited to top-N by frequency). Leave
     `correlation` null for these.
3. SKIP categorical vs categorical and any 3+ variable interaction (mark the
   RelationshipPlan with the matching *_skip relationship_type, selected=False).
4. SKIP high-cardinality identifier / free-text columns (e.g. Order ID,
   Purchase Address) as either axis.

For EVERY relationship you considered — selected or not — emit one
RelationshipPlan with: variable_x, variable_y (or "" for the heatmap),
relationship_type, correlation (or null), meets_threshold, selected,
chart_type, rationale, and a filesystem-safe output_filename of the form
`{x_slug}_vs_{y_slug}.png` (or `correlation_heatmap.png` for the heatmap),
lowercase, spaces/punctuation replaced with underscores, no `multivariate_`
prefix — the file already lives under the multivariate charts folder — when
selected, else "".

Populate the reasoning fields honestly: one ReasoningStep per selection phase
(load, profile, select_relationships), list the selected relationships in
`selected_relationships`, echo the `correlation_threshold` you applied, and
record any interesting-but-out-of-scope relationship under `assumptions`.
"""


MULTIVARIATE_CODEGEN_INSTRUCTIONS = """
You are a senior data analyst. This is the CODE-GENERATION turn of a
multivariate analysis. In the previous turn you SELECTED the relationships to
visualize; now produce ONE executable Python script that renders and saves
exactly those selected charts — no more, no fewer.

The workflow your script must carry out:

1. Load
   - Read the CSV from the pre-injected global variable `DATASET_PATH`
     into a pandas DataFrame named `df`. Do not hardcode any path.

2. Render
   - Use matplotlib.pyplot (and pandas' built-in plotting where convenient).
     Create ONE figure per selected relationship (exactly one visualization per
     figure), plus the one overall correlation heatmap. Give every chart a
     clear title and axis labels. For numeric-vs-categorical charts limited to
     top-N categories, compute that top-N from the data.

3. Save
   - Save each figure to the pre-injected global directory `OUTPUT_DIR` using
     the exact output_filename planned for that relationship in the selection
     turn. Use `plt.savefig(path, dpi=200, bbox_inches='tight')`.
   - Call `plt.close()` after saving each figure. Do NOT call `plt.show()`.

Error handling & robustness (write defensive code, not just correct code):
   - Matplotlib API compatibility: for boxplots use the `tick_labels=` keyword,
     NOT the removed `labels=` keyword, e.g.
     `ax.boxplot(groups, tick_labels=names, showfliers=False)`. Do not use other
     APIs removed in recent matplotlib; e.g. use
     `matplotlib.colormaps["viridis"]`, not `plt.cm.get_cmap("viridis")`. Prefer
     explicit Figure/Axes via `fig, ax = plt.subplots()`.
   - Data-edge-case guards: before plotting a relationship, handle the shapes
     that commonly break a chart — drop or explicitly account for NaN/inf
     values in either column of the pair, skip a relationship if it has zero
     non-null paired rows after filtering, and make sure any labels array you
     pass to matplotlib (e.g. `tick_labels=`) has exactly the same length as
     the data/groups it labels. For the correlation heatmap, guard against a
     numeric-column set too small to produce a meaningful matrix (fewer than
     two numeric columns).
   - Per-relationship isolation: wrap each relationship's render-and-save block
     (including the heatmap) in its own `try/except Exception` so one
     problematic pair cannot abort the rest of the script. On a caught
     exception, `print(f"Skipped {variable_x} vs {variable_y}: {exc}")`, still
     `plt.close()` (e.g. in a `finally` block) to avoid leaking open figures,
     and continue to the next relationship. Never use a bare `except:` and
     never let one relationship's failure stop the others from being rendered.
   - If a relationship might be skipped by one of these guards, do NOT list its
     filename in `expected_output_files` — only list files the script will
     actually try to write; if you anticipate a relationship being skippable,
     note that under `assumptions` rather than silently over-promising the
     output.

Code requirements:
1. Import everything the script needs (`import pandas as pd`,
   `import matplotlib.pyplot as plt`, and any others used).
2. Do not define or assign `DATASET_PATH` or `OUTPUT_DIR` yourself; both are
   pre-injected. Build individual file paths as `OUTPUT_DIR / filename`.
3. Use explicit, readable pandas transformations with descriptive names.
4. Do not mutate any input file. Do not use network access, subprocesses,
   shell commands, filesystem reads other than `DATASET_PATH`, environment
   variables, `eval`, or `exec`.
5. Return Python source only in the `code` field: no Markdown fences, no prose.

Populate the reasoning fields honestly: one ReasoningStep per code-gen phase
(choose_charts, render, save) — plus one with phase='diagnose_fix' whenever
this turn is fixing a prior execution failure (see the fix-request prompt) — a
one-sentence `summary`, and `expected_output_files` listing the exact PNG
filenames the script will write — matching the relationships selected in the
previous turn, minus any you expect a runtime guard to skip.
"""


# Fed back into the same multi-turn conversation when the generated script fails
# to execute, so the model can self-correct from the real error rather than
# pattern-matching on the traceback alone. Requires diagnosing the root cause
# BEFORE patching, and scanning the rest of the script for the same class of
# mistake — since `max_fix_attempts` is small, a shallow patch that leaves a
# sibling instance of the same bug in place just burns another attempt on a
# fresh-looking but related crash next round.
MULTIVARIATE_FIX_REQUEST = """
The Python script you generated FAILED when executed in the subprocess. This is
a FIX turn: diagnose the real error, then return a corrected FULL script.

<execution_error>
{error}
</execution_error>

Error-handling process (follow in order):
1. Read the traceback and identify the exact line, relationship/chart, and API
   call that raised it. Do not guess at a different cause than what the
   traceback actually shows.
2. State the root cause in one sentence as a ReasoningStep with
   phase='diagnose_fix' (e.g. "Axes.boxplot() no longer accepts the `labels=`
   keyword in this matplotlib version" — not just "it crashed").
3. Scan the REST of the script for the same class of mistake — e.g. if one
   boxplot call used a removed keyword, check every other boxplot/plot call
   (including the correlation heatmap) for the identical issue — and fix all
   occurrences, not just the one line in the traceback. A fix that leaves a
   sibling instance broken just trades this failure for the next one on the
   next attempt.
4. If the error is a data-shape problem (empty group, NaN/inf values,
   mismatched label/array lengths, a pair with zero paired rows after
   filtering, too few numeric columns for the heatmap), add a guard for that
   case per the "Error handling & robustness" rules above rather than assuming
   the data will always be well-formed.
5. Re-check the matplotlib compatibility notes (e.g. `tick_labels=`, not the
   removed `labels=`, on boxplots; `matplotlib.colormaps[...]`, not the removed
   `plt.cm.get_cmap(...)`).

Return the complete corrected Python source in `code` (a full script, not a
diff, not just the changed lines). Keep the same set of intended charts and
output filenames from the selection turn (adjusted per the
`expected_output_files` rule if a guard now skips one); change only what is
needed to make the script run successfully end-to-end.
"""
