"""J12b: `pytest` pelado desde backend/ solo recoge tests/ (los test_*.py de la raiz usarian zeus.db)."""

import configparser
from pathlib import Path


def test_pytest_ini_limita_testpaths_a_tests():
    ini = Path(__file__).resolve().parents[1] / "pytest.ini"
    cp = configparser.ConfigParser()
    cp.read(ini, encoding="utf-8")
    assert cp["pytest"]["testpaths"].split() == ["tests"]
