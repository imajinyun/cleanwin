PYTHON ?= python3
VENV ?= .venv

ifeq ($(OS),Windows_NT)
VENV_PYTHON := $(VENV)/Scripts/python.exe
else
VENV_PYTHON := $(VENV)/bin/python
endif

DEV_PYTHON ?= $(VENV_PYTHON)

.PHONY: venv dev-install test pytest lint type compile pytest-governance-smoke ci-smoke quality package-smoke package-install-smoke sdist-install-smoke mcp-install-smoke docs-smoke ai-smoke mcp-smoke version-smoke docker-quality clean

venv:
	$(PYTHON) -m venv $(VENV)

dev-install: venv
	$(DEV_PYTHON) -m pip install --upgrade pip build
	$(DEV_PYTHON) -m pip install -e ".[dev]"

test: dev-install
	$(DEV_PYTHON) -m pytest -q

pytest: dev-install
	$(DEV_PYTHON) -m pytest -q

lint: dev-install
	$(DEV_PYTHON) -m ruff check cleanwin.py cleanwincli tests

type: dev-install
	$(DEV_PYTHON) -m mypy cleanwin.py cleanwincli tests

compile: dev-install
	$(DEV_PYTHON) -m compileall -q cleanwin.py cleanwincli tests

pytest-governance-smoke: dev-install
	$(DEV_PYTHON) -m pytest tests/test_pytest_governance.py tests/test_ai_readiness.py::test_ai_readiness_release_gates_use_pytest_workflow -q
	$(DEV_PYTHON) -c "from pathlib import Path; makefile=Path('Makefile').read_text(encoding='utf-8'); dockerfile=Path('Dockerfile.test').read_text(encoding='utf-8'); workflow=Path('.github/workflows/ci.yml').read_text(encoding='utf-8'); assert 'ci-smoke:' in makefile; assert 'unittest discover' not in dockerfile; assert 'make pytest-governance-smoke' in workflow; assert 'make docker-quality' in workflow; assert 'python-version' in workflow"

ci-smoke: lint pytest type compile docs-smoke ai-smoke mcp-smoke version-smoke pytest-governance-smoke

package-smoke: dev-install
	$(DEV_PYTHON) -m build --sdist --wheel

package-install-smoke: package-smoke
	$(DEV_PYTHON) -c "import atexit, glob, json, pathlib, shutil, subprocess, sys, tempfile; tmp=tempfile.mkdtemp(prefix='cleanwin-install-smoke-'); atexit.register(shutil.rmtree, tmp, ignore_errors=True); bindir=pathlib.Path(tmp) / 'venv' / ('Scripts' if sys.platform == 'win32' else 'bin'); subprocess.run([sys.executable, '-m', 'venv', str(bindir.parent)], check=True); py=bindir / ('python.exe' if sys.platform == 'win32' else 'python'); cli=bindir / ('cleanwin.exe' if sys.platform == 'win32' else 'cleanwin'); mcp=bindir / ('cleanwin-mcp.exe' if sys.platform == 'win32' else 'cleanwin-mcp'); wheel=sorted(glob.glob('dist/cleanwin-*.whl'))[-1]; subprocess.run([str(py), '-m', 'pip', 'install', wheel], check=True); module_payload=json.loads(subprocess.check_output([str(py), '-m', 'cleanwin', '--json', 'doctor'], text=True)); cli_payload=json.loads(subprocess.check_output([str(cli), '--json', 'doctor'], text=True)); mcp_payload=json.loads(subprocess.check_output([str(mcp)], input=json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize'}), text=True)); raise SystemExit(0 if cli.exists() and mcp.exists() and module_payload.get('ready') is True and cli_payload.get('ready') is True and mcp_payload.get('result', {}).get('serverInfo', {}).get('name') == 'cleanwin-mcp' else 1)"

sdist-install-smoke: package-smoke
	$(DEV_PYTHON) -c "import atexit, glob, json, pathlib, shutil, subprocess, sys, tempfile; tmp=tempfile.mkdtemp(prefix='cleanwin-sdist-smoke-'); atexit.register(shutil.rmtree, tmp, ignore_errors=True); bindir=pathlib.Path(tmp) / 'venv' / ('Scripts' if sys.platform == 'win32' else 'bin'); subprocess.run([sys.executable, '-m', 'venv', str(bindir.parent)], check=True); py=bindir / ('python.exe' if sys.platform == 'win32' else 'python'); cli=bindir / ('cleanwin.exe' if sys.platform == 'win32' else 'cleanwin'); mcp=bindir / ('cleanwin-mcp.exe' if sys.platform == 'win32' else 'cleanwin-mcp'); sdist=sorted(glob.glob('dist/cleanwin-*.tar.gz'))[-1]; subprocess.run([str(py), '-m', 'pip', 'install', sdist], check=True); module_payload=json.loads(subprocess.check_output([str(py), '-m', 'cleanwin', '--json', 'doctor'], text=True)); cli_payload=json.loads(subprocess.check_output([str(cli), '--json', 'doctor'], text=True)); mcp_payload=json.loads(subprocess.check_output([str(mcp)], input=json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize'}), text=True)); raise SystemExit(0 if cli.exists() and mcp.exists() and module_payload.get('ready') is True and cli_payload.get('ready') is True and mcp_payload.get('result', {}).get('serverInfo', {}).get('name') == 'cleanwin-mcp' else 1)"

mcp-install-smoke: package-install-smoke sdist-install-smoke

docs-smoke:
	test -f docs/doc/README.md
	test -f docs/doc/README.CN.md
	test -s docs/doc/README.md
	test -s docs/doc/README.CN.md

ai-smoke: dev-install
	$(DEV_PYTHON) cleanwin.py --json ai-tools --provider validation
	$(DEV_PYTHON) cleanwin.py --json ai-readiness --validate
	$(DEV_PYTHON) cleanwin.py --json ai-self-test
	$(DEV_PYTHON) cleanwin.py --json ai-runbook
	$(DEV_PYTHON) cleanwin.py --json doctor

mcp-smoke: dev-install
	$(DEV_PYTHON) -m compileall -q cleanwincli/mcp_server.py

version-smoke: dev-install
	$(DEV_PYTHON) -c "from cleanwincli.core import doctor_report; check=next(item for item in doctor_report()['checks'] if item['id'] == 'version_consistency'); raise SystemExit(0 if check['passed'] else 1)"

docker-quality:
	docker build -f Dockerfile.test -t cleanwin-test .
	docker run --rm cleanwin-test

clean:
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(path, ignore_errors=True) for path in ['build', 'dist', 'cleanwin.egg-info', '.mypy_cache', '.ruff_cache']]; [shutil.rmtree(path, ignore_errors=True) for path in pathlib.Path('.').rglob('__pycache__')]"

quality: ci-smoke mcp-install-smoke clean
