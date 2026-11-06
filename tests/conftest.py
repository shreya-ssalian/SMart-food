import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from analyzer import SmartFoodAnalyzer
from knowledge.kb_loader import load_kb, read_csv


@pytest.fixture(scope="session")
def analyzer():
    return SmartFoodAnalyzer(load_kb("demo"))      # tests always use the illustrative demo KB


@pytest.fixture(scope="session")
def demo_products():
    return {r["test_id"]: r for r in read_csv(config.DEMO_TEST_DIR / "test_products.csv")}


@pytest.fixture(scope="session")
def results(analyzer, demo_products):
    return {k: analyzer.analyze(v) for k, v in demo_products.items()}
