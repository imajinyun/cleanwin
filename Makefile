PYTHON ?= python3

.PHONY: test lint type compile quality package-smoke package-install-smoke sdist-install-smoke mcp-install-smoke docs-smoke ai-smoke mcp-smoke version-smoke clean

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

package-install-smoke: package-smoke
	$(PYTHON) -c "import atexit, glob, json, pathlib, shutil, subprocess, sys, tempfile; tmp=tempfile.mkdtemp(prefix='cleanwin-install-smoke-'); atexit.register(shutil.rmtree, tmp, ignore_errors=True); bindir=pathlib.Path(tmp) / 'venv' / ('Scripts' if sys.platform == 'win32' else 'bin'); subprocess.run([sys.executable, '-m', 'venv', str(bindir.parent)], check=True); py=bindir / ('python.exe' if sys.platform == 'win32' else 'python'); cli=bindir / ('cleanwin.exe' if sys.platform == 'win32' else 'cleanwin'); mcp=bindir / ('cleanwin-mcp.exe' if sys.platform == 'win32' else 'cleanwin-mcp'); wheel=sorted(glob.glob('dist/cleanwin-*.whl'))[-1]; subprocess.run([str(py), '-m', 'pip', 'install', wheel], check=True); module_payload=json.loads(subprocess.check_output([str(py), '-m', 'cleanwin', '--json', 'doctor'], text=True)); cli_payload=json.loads(subprocess.check_output([str(cli), '--json', 'doctor'], text=True)); mcp_payload=json.loads(subprocess.check_output([str(mcp)], input=json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize'}), text=True)); raise SystemExit(0 if cli.exists() and mcp.exists() and module_payload.get('ready') is True and cli_payload.get('ready') is True and mcp_payload.get('result', {}).get('serverInfo', {}).get('name') == 'cleanwin-mcp' else 1)"

sdist-install-smoke: package-smoke
	$(PYTHON) -c "import atexit, glob, json, pathlib, shutil, subprocess, sys, tempfile; tmp=tempfile.mkdtemp(prefix='cleanwin-sdist-smoke-'); atexit.register(shutil.rmtree, tmp, ignore_errors=True); bindir=pathlib.Path(tmp) / 'venv' / ('Scripts' if sys.platform == 'win32' else 'bin'); subprocess.run([sys.executable, '-m', 'venv', str(bindir.parent)], check=True); py=bindir / ('python.exe' if sys.platform == 'win32' else 'python'); cli=bindir / ('cleanwin.exe' if sys.platform == 'win32' else 'cleanwin'); mcp=bindir / ('cleanwin-mcp.exe' if sys.platform == 'win32' else 'cleanwin-mcp'); sdist=sorted(glob.glob('dist/cleanwin-*.tar.gz'))[-1]; subprocess.run([str(py), '-m', 'pip', 'install', sdist], check=True); module_payload=json.loads(subprocess.check_output([str(py), '-m', 'cleanwin', '--json', 'doctor'], text=True)); cli_payload=json.loads(subprocess.check_output([str(cli), '--json', 'doctor'], text=True)); mcp_payload=json.loads(subprocess.check_output([str(mcp)], input=json.dumps({'jsonrpc':'2.0','id':1,'method':'initialize'}), text=True)); raise SystemExit(0 if cli.exists() and mcp.exists() and module_payload.get('ready') is True and cli_payload.get('ready') is True and mcp_payload.get('result', {}).get('serverInfo', {}).get('name') == 'cleanwin-mcp' else 1)"

mcp-install-smoke: package-install-smoke sdist-install-smoke

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

quality: lint type test compile docs-smoke ai-smoke mcp-smoke version-smoke mcp-install-smoke clean
