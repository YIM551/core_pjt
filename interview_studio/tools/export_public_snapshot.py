"""Export an allowlisted source snapshot, never user data or model weights."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = (
    'backend/app', 'backend/alembic', 'backend/tests', 'backend/scripts',
    'backend/skills', 'frontend/src', 'frontend/scripts', 'frontend/skills', 'frontend/docs', 'docs', 'tools',
)
FILES = (
    'README.md', 'docker-compose.yml', '.gitignore', '.env.example',
    'backend/AGENTS.md', 'backend/AI.md', 'backend/Dockerfile',
    'backend/alembic.ini', 'backend/pytest.ini', 'backend/requirements.txt',
    'backend/requirements-local.txt', 'backend/requirements-audio.txt',
    'frontend/AGENTS.md', 'frontend/AI.md', 'frontend/Dockerfile',
    'frontend/nginx.conf', 'frontend/index.html', 'frontend/package.json',
    'frontend/package-lock.json', 'frontend/vite.config.js', 'frontend/vitest.config.js',
    'frontend/.env.example',
)
EXTENSIONS = {'.py', '.js', '.mjs', '.vue', '.css', '.json', '.md', '.txt', '.yml', '.yaml', '.ini', '.html', '.conf', '.svg'}
BLOCKED_PARTS = {'__pycache__', '.pytest_cache', 'node_modules', '.venv', 'models', 'uploads', '.test-artifacts', 'dist', '.git'}
SECRET_PATTERNS = (
    re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
    re.compile(r'\bgithub_pat_[A-Za-z0-9_]{35,}\b'),
    re.compile(r'\bhf_[A-Za-z0-9]{25,}\b'),
    re.compile(r'\bAKIA[A-Z0-9]{16}\b'),
    re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b'),
)

def source_files():
    paths = {ROOT / name for name in FILES if (ROOT / name).is_file()}
    for name in DIRECTORIES:
        folder = ROOT / name
        if not folder.is_dir():
            continue
        for path in folder.rglob('*'):
            if path.is_file() and path.suffix in EXTENSIONS:
                rel = path.relative_to(ROOT)
                if not BLOCKED_PARTS.intersection(rel.parts) and not path.is_symlink():
                    paths.add(path)
    return sorted(paths)

def export(destination: Path):
    destination = destination.resolve()
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError('Destination must be outside the private application directory')
    paths = source_files()
    records = []
    for path in paths:
        content = path.read_bytes()
        if len(content) > 2_000_000:
            raise ValueError(f'Unexpected large source file: {path.relative_to(ROOT)}')
        text = content.decode('utf-8-sig')
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            raise ValueError(f'Potential credential in {path.relative_to(ROOT)}; export stopped')
        rel = path.relative_to(ROOT)
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8', newline='\n')
        records.append({'path': rel.as_posix(), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(), 'bytes': target.stat().st_size})
    manifest = {
        'format': 1, 'files': records,
        'excluded': ['private .env', 'user documents and corpus', 'audio/video', 'database and dumps',
                     'model weights and generated WASM', 'dependencies and build outputs', 'local test artifacts'],
    }
    (destination / 'PUBLIC_SNAPSHOT.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(records), 'bytes': sum(r['bytes'] for r in records)}, ensure_ascii=False))

def json_batch(destination: Path, start: int, count: int):
    manifest = json.loads((destination / 'PUBLIC_SNAPSHOT.json').read_text(encoding='utf-8'))
    entries = manifest['files'] + [{'path': 'PUBLIC_SNAPSHOT.json'}]
    output = []
    for record in entries[start:start + count]:
        path = destination / record['path']
        output.append({'path': 'interview_studio/' + record['path'], 'mode': '100644', 'type': 'blob', 'content': path.read_text(encoding='utf-8')})
    print(json.dumps(output, ensure_ascii=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--json-batch', nargs=2, type=int)
    args = parser.parse_args()
    if args.json_batch:
        json_batch(args.destination, *args.json_batch)
    else:
        export(args.destination)
