import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
# Load environment variables from module .env file
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Raw source data lives under the agentic_eda/data/ directory.
DATA_DIR = BASE_DIR / "data"

# Agent outputs, kept inside agentic_eda so the module is self-contained.
OUTPUT_DIR = BASE_DIR / "outputs"
CLEANED_DATA_DIR = OUTPUT_DIR / "cleaned"   # normalized CSVs from the prep agent
CHARTS_DIR = OUTPUT_DIR / "charts"          # PNGs from the analysis agents
UNIVARIATE_CHARTS_DIR = CHARTS_DIR / "univariate"      # PNGs from the univariate agent
MULTIVARIATE_CHARTS_DIR = CHARTS_DIR / "multivariate"  # PNGs from the multivariate agent
REPORTS_DIR = OUTPUT_DIR / "reports"        # markdown reports from the report agent

for _dir in (
    OUTPUT_DIR,
    CLEANED_DATA_DIR,
    CHARTS_DIR,
    UNIVARIATE_CHARTS_DIR,
    MULTIVARIATE_CHARTS_DIR,
    REPORTS_DIR,
):
    _dir.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Default cutoff for treating a numeric-numeric correlation as "meaningful".
# The multivariate agent applies this when selecting which relationships to plot;
# it may justify analytically-interesting exceptions in its reasoning.
CORRELATION_THRESHOLD = 0.3
