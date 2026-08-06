import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# Load environment variables from module .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Raw source data lives under the agentic_eda/data/ directory.
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"          # CSVs uploaded through the web server

# Agent outputs, kept inside agentic_eda so the module is self-contained.
OUTPUT_DIR = BASE_DIR / "outputs"
CLEANED_DATA_DIR = OUTPUT_DIR / "cleaned"   # normalized CSVs from the prep agent
CHARTS_DIR = OUTPUT_DIR / "charts"          # PNGs from the analysis agents
UNIVARIATE_CHARTS_DIR = CHARTS_DIR / "univariate"      # PNGs from the univariate agent
MULTIVARIATE_CHARTS_DIR = CHARTS_DIR / "multivariate"  # PNGs from the multivariate agent
REPORTS_DIR = OUTPUT_DIR / "reports"        # markdown reports from the report agent

# Server runs get one isolated directory each, so concurrent runs never share a
# charts_dir (execute_chart_generation_code discovers PNGs by mtime watermark and
# would otherwise pick up another run's output). The flat directories above stay
# reserved for the CLI (pipeline.py) and the notebook.
RUNS_DIR = OUTPUT_DIR / "runs"

for _dir in (
    UPLOADS_DIR,
    OUTPUT_DIR,
    CLEANED_DATA_DIR,
    CHARTS_DIR,
    UNIVARIATE_CHARTS_DIR,
    MULTIVARIATE_CHARTS_DIR,
    REPORTS_DIR,
    RUNS_DIR,
):
    _dir.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Default cutoff for treating a numeric-numeric correlation as "meaningful".
# The multivariate agent applies this when selecting which relationships to plot;
# it may justify analytically-interesting exceptions in its reasoning.
CORRELATION_THRESHOLD = 0.3
