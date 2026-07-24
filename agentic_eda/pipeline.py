"""End-to-end orchestrator pipeline for Agentic EDA.

It coordinates the four stages:
1. Data Preparation (data_prep/agent.py)
2. Univariate Analysis (univariate_analysis/agent.py)
3. Multivariate Analysis (multivariate_analysis/agent.py)
4. Markdown Report Generation (report/agent.py)
"""

import sys
from pathlib import Path
from agentic_eda.config import DATA_DIR
from agentic_eda.data_prep.agent import run_data_prep
from agentic_eda.univariate_analysis.agent import run_univariate_analysis
from agentic_eda.multivariate_analysis.agent import run_multivariate_analysis
from agentic_eda.report.agent import collect_context, run_report

def run_pipeline(dataset_path: str | Path) -> Path:
    dataset_path = Path(dataset_path)
    dataset_name = dataset_path.stem
    print(f"Starting Agentic EDA pipeline for dataset: {dataset_name} ({dataset_path})")

    # Step 1: Data Prep
    print("\n--- Running Step 1: Data Preparation ---")
    prep_result, cleaned_path = run_data_prep(dataset_path)
    print(f"Data Prep completed. Cleaned dataset written to: {cleaned_path}")

    # Step 2a: Univariate Analysis
    print("\n--- Running Step 2a: Univariate Analysis ---")
    univariate_result, univariate_charts = run_univariate_analysis(cleaned_path)
    print(f"Univariate Analysis completed. Generated {len(univariate_charts)} charts.")

    # Step 2b: Multivariate Analysis
    print("\n--- Running Step 2b: Multivariate Analysis ---")
    multivariate_result, multivariate_charts = run_multivariate_analysis(cleaned_path)
    print(f"Multivariate Analysis completed. Generated {len(multivariate_charts)} charts.")

    # Step 3: Report Synthesis
    print("\n--- Running Step 3: Multimodal Report Synthesis ---")
    context = collect_context(
        dataset_name=dataset_name,
        cleaned_csv_path=cleaned_path,
        data_prep=prep_result,
        univariate=univariate_result,
        univariate_charts=univariate_charts,
        multivariate=multivariate_result,
        multivariate_charts=multivariate_charts,
    )
    report_path = run_report(context)
    print(f"\nPipeline successfully completed!")
    print(f"Final Report written to: {report_path}")
    return report_path

if __name__ == "__main__":
    # Default is data/sales_data.csv
    if len(sys.argv) > 1:
        csv_path = Path(sys.argv[1])
    else:
        csv_path = DATA_DIR / "sales_data.csv"

    if not csv_path.exists():
        print(f"Error: Dataset not found at '{csv_path}'. Please place your raw data there.")
        sys.exit(1)

    try:
        run_pipeline(csv_path)
    except Exception as e:
        print(f"\nPipeline failed: {e}")
        sys.exit(1)
