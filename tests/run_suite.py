"""Executa a suíte e guarda evidência UTF-8 sem redirecionamentos do PowerShell."""
import logging
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
logging.getLogger('werkzeug').setLevel(logging.ERROR)
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_*.py')
output=ROOT/'data'/'qa'/'test-results.txt'
output.parent.mkdir(parents=True,exist_ok=True)
with output.open('w',encoding='utf-8') as stream:
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
print(output.read_text(encoding='utf-8'))
sys.exit(0 if result.wasSuccessful() else 1)
