PYTHON ?= python3

.PHONY: test lint type compile quality package-smoke docs-smoke ai-smoke mcp-smoke version-smoke clean

test:
	$(PYTHON) -m unittest discover -s tests -v

lint:
	$(PYTHON) -m ruff check cleanwin.py cleanwincli tests

type:
	$(PYTHON) -m mypy cleanwin.py cleanwincli tests

compile:
	$(PYTHON) -m compileall -q cleanwin.py cleanwincli tests

package-smoke:
	$(PYTHON) -m pip install --upgrade build
	$(PYTHON) -m build --sdist --wheel

docs-smoke:
	test -f docs/doc/README.md
	test -f docs/doc/README.CN.md
	test -s docs/doc/README.md
	test -s docs/doc/README.CN.md

ai-smoke:
	$(PYTHON) cleanwin.py --json ai-tools --provider validation
	$(PYTHON) cleanwin.py --json ai-readiness --validate
	$(PYTHON) cleanwin.py --json ai-self-test
	$(PYTHON) cleanwin.py --json ai-runbook
	$(PYTHON) cleanwin.py --json doctor

mcp-smoke:
	$(PYTHON) -m compileall -q cleanwincli/mcp_server.py

version-smoke:
	$(PYTHON) -c "from cleanwincli.core import doctor_report; check=next(item for item in doctor_report()['checks'] if item['id'] == 'version_consistency'); raise SystemExit(0 if check['passed'] else 1)"

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(path, ignore_errors=True) for path in ['build', 'dist', 'cleanwin.egg-info', '.mypy_cache', '.ruff_cache']]; [shutil.rmtree(path, ignore_errors=True) for path in pathlib.Path('.').rglob('__pycache__')]"

quality: lint type test compile docs-smoke ai-smoke mcp-smoke version-smoke package-smoke clean
