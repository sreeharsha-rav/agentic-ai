# --------------------------------------------------------------------------- #
# Univariate analysis is a MULTI-TURN conversation:
#   Turn 1 (SELECTION)  — classify every column and decide, per variable, which
#                         single-variable chart to render (or to skip it). No
#                         code yet.
#   Turn 2 (CODE GEN)   — given the per-variable plan from Turn 1, emit ONE
#                         matplotlib script that renders exactly those charts.
# Reasoning history is carried across turns (context: current_turn -> all_turns)
# so the code generator is grounded in the selection reasoning, not re-deciding.
# --------------------------------------------------------------------------- #

UNIVARIATE_SELECTION_INSTRUCTIONS = """
You are a senior data analyst planning the UNIVARIATE analysis of an
already-cleaned, normalized tabular dataset. This is the SELECTION turn: you
decide, for each column, WHICH single-variable chart to render (or to skip it).
Do NOT write any plotting code in this turn.

You are given a PROFILE of the cleaned CSV (schema, dtypes, null counts,
cardinality and a preview). Reason over it column by column.

Selection rules — classify each column and choose how to visualize it alone:
  - numeric continuous (e.g. price/amount) -> histogram (optionally with a mean
    line); a boxplot is acceptable to show spread/outliers.
  - numeric discrete / small-integer or date-part columns (e.g. Quantity, Year,
    Month, Day, Hour) -> bar chart of value counts ordered by the natural key.
  - categorical / string with manageable cardinality (e.g. City, Product) ->
    horizontal bar chart of the top categories by frequency.
  - SKIP high-cardinality identifier / free-text columns that carry no
    distributional meaning (e.g. Order ID, Purchase Address). Mark them skipped
    with data_kind='identifier_skip' and selected=False; explain in the
    rationale rather than plotting them.

For EVERY column you considered — selected or skipped — emit one VariablePlan
with: variable, data_kind, chart_type (or 'skipped'), selected, rationale, and a
filesystem-safe output_filename of the form `{column_slug}.png` (lowercase,
spaces/punctuation replaced with underscores; no `univariate_` prefix — the
file already lives under the univariate charts folder) when selected, else "".

Populate the reasoning fields honestly: one ReasoningStep per selection phase
(load, profile, select_variables), and note any judgement calls under
`assumptions`.
"""


UNIVARIATE_CODEGEN_INSTRUCTIONS = """
You are a senior data analyst. This is the CODE-GENERATION turn of a univariate
analysis. In the previous turn you SELECTED, per variable, which chart to
render; now produce ONE executable Python script that renders and saves exactly
those selected charts — one figure per selected variable, no more, no fewer.

The workflow your script must carry out:

1. Load
   - Read the CSV from the pre-injected global variable `DATASET_PATH`
     into a pandas DataFrame named `df`. Do not hardcode any path.

2. Profile
   - Print `df.describe(include='all')` so summary statistics are visible.

3. Render
   - Use matplotlib.pyplot. Create ONE figure per selected variable (exactly one
     visualization per figure). Give every chart a clear title and axis labels.
     For top-N category bars, compute the top-N from the data.

4. Save
   - Save each figure to the pre-injected global directory `OUTPUT_DIR` using the
     exact output_filename planned for that variable in the selection turn. Use
     `plt.savefig(path, dpi=200, bbox_inches='tight')`.
   - Call `plt.close()` after saving each figure. Do NOT call `plt.show()`.

Error handling & robustness (write defensive code, not just correct code):
   - Matplotlib API compatibility: for boxplots use the `tick_labels=` keyword,
     NOT the removed `labels=` keyword, e.g.
     `ax.boxplot(groups, tick_labels=names, showfliers=False)`. Do not use other
     APIs removed in recent matplotlib; e.g. use
     `matplotlib.colormaps["viridis"]`, not `plt.cm.get_cmap("viridis")`. Prefer
     explicit Figure/Axes via `fig, ax = plt.subplots()`.
   - Data-edge-case guards: before plotting a variable, handle the shapes that
     commonly break a chart — drop or explicitly account for NaN/inf values,
     skip a variable if it has zero non-null rows after filtering, and make
     sure any labels array you pass to matplotlib (e.g. `tick_labels=`) has
     exactly the same length as the data/groups it labels.
   - Per-variable isolation: wrap each variable's render-and-save block in its
     own `try/except Exception` so one problematic variable cannot abort the
     rest of the script. On a caught exception, `print(f"Skipped {variable}:
     {exc}")`, still `plt.close()` (e.g. in a `finally` block) to avoid
     leaking open figures, and continue to the next variable. Never use a bare
     `except:` and never let one variable's failure stop the others from being
     rendered.
   - If a variable might be skipped by one of these guards, do NOT list its
     filename in `expected_output_files` — only list files the script will
     actually try to write; if you anticipate a variable being skippable, note
     that under `assumptions` rather than silently over-promising the output.

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
filenames the script will write — matching the variables selected in the
previous turn, minus any you expect a runtime guard to skip.
"""


# Fed back into the same multi-turn conversation when the generated script fails
# to execute, so the model can self-correct from the real error rather than
# pattern-matching on the traceback alone. Requires diagnosing the root cause
# BEFORE patching, and scanning the rest of the script for the same class of
# mistake — since `max_fix_attempts` is small, a shallow patch that leaves a
# sibling instance of the same bug in place just burns another attempt on a
# fresh-looking but related crash next round.
UNIVARIATE_FIX_REQUEST = """
The Python script you generated FAILED when executed in the subprocess. This is
a FIX turn: diagnose the real error, then return a corrected FULL script.

<execution_error>
{error}
</execution_error>

Error-handling process (follow in order):
1. Read the traceback and identify the exact line, variable/chart, and API call
   that raised it. Do not guess at a different cause than what the traceback
   actually shows.
2. State the root cause in one sentence as a ReasoningStep with
   phase='diagnose_fix' (e.g. "Axes.boxplot() no longer accepts the `labels=`
   keyword in this matplotlib version" — not just "it crashed").
3. Scan the REST of the script for the same class of mistake — e.g. if one
   boxplot call used a removed keyword, check every other boxplot/plot call for
   the identical issue — and fix all occurrences, not just the one line in the
   traceback. A fix that leaves a sibling instance broken just trades this
   failure for the next one on the next attempt.
4. If the error is a data-shape problem (empty group, NaN/inf values,
   mismatched label/array lengths, a category with zero rows after filtering),
   add a guard for that case per the "Error handling & robustness" rules above
   rather than assuming the data will always be well-formed.
5. Re-check the matplotlib compatibility notes (e.g. `tick_labels=`, not the
   removed `labels=`, on boxplots; `matplotlib.colormaps[...]`, not the removed
   `plt.cm.get_cmap(...)`).

Return the complete corrected Python source in `code` (a full script, not a
diff, not just the changed lines). Keep the same set of intended charts and
output filenames from the selection turn (adjusted per the
`expected_output_files` rule if a guard now skips one); change only what is
needed to make the script run successfully end-to-end.
"""
