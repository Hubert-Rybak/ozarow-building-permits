#!/usr/bin/env python3
"""Collect all real adapters, validate one inline-geometry generation and publish atomically."""
import argparse
import copy
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile

from investment_links import collect_links, network_orders_loader
from investment_validation import counts_for, keys, load_dataset, require, validate_dataset

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_MODULES = ('municipal', 'public', 'private')


def load_adapters():
    adapters = []
    for name in ADAPTER_MODULES:
        try:
            module = importlib.import_module('investment_sources.' + name)
        except ImportError as exc:
            raise RuntimeError(f'Missing/broken production adapter investment_sources.{name}; integrate adapters before import') from exc
        require(callable(getattr(module, 'collect', None)), f'Adapter {name} must expose collect(cache: Path, prior: dict | None)')
        adapters.append(module.collect)
    return adapters


def build_dataset(contributions, *, generated_at, prior=None, linker=None):
    records, sources, warnings = [], [], []
    for contribution in contributions:
        keys(contribution, {'records', 'sources', 'warnings'}, 'adapter contribution')
        for name in ('records', 'sources', 'warnings'):
            require(type(contribution[name]) is list, f'Adapter {name} must be list')
        records.extend(copy.deepcopy(contribution['records']))
        sources.extend(copy.deepcopy(contribution['sources']))
        warnings.extend(contribution['warnings'])
    # Validate before sorting/counting untrusted nested input; sorting never hides duplicates.
    for record in records:
        require(type(record) is dict and type(record.get('id')) is str and type(record.get('sourceId')) is str and type(record.get('geometries')) is list, 'Invalid adapter record shape')
    for source in sources:
        require(type(source) is dict and type(source.get('id')) is str, 'Invalid adapter source shape')
    require(all(type(w) is str for w in warnings), 'Invalid adapter warnings')
    records.sort(key=lambda r: r['id'])
    sources.sort(key=lambda s: s['id'])
    # Links are derived from the merged records; their own failure only adds a warning.
    links, link_warnings = (linker or collect_links)(records, prior)
    warnings.extend(link_warnings)
    dataset = dict(schemaVersion=1, generatedAt=generated_at, records=records, sources=sources, links=links,
                   warnings=sorted(set(warnings)), counts=counts_for(records, sources))
    validate_dataset(dataset, prior=prior)
    if prior is None:
        require(all(s['status'] != 'retained' for s in sources), 'Cannot initialize retained source without verified prior')
    return dataset


def no_symlinks(path):
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), 'Symlink path not allowed')


def safe_cache(cache, output):
    no_symlinks(cache)
    cache = cache.resolve()
    output = output.resolve()
    require(not cache.is_relative_to(ROOT) and not cache.is_relative_to(output), 'Investment cache must be outside repository and output')
    require(not output.is_relative_to(cache), 'Output cannot be inside investment cache')
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    require(cache.is_dir(), 'Cache must be directory')
    cache.chmod(0o700)
    return cache


def publish(output, dataset, *, prior=None):
    """Single-file commit point: serialize, fsync and revalidate before os.replace.

    No whole-directory swap, raw source data, cookies or synthetic adapter caches.
    Any failure before replacement leaves the previous artifact byte-for-byte intact.
    """
    validate_dataset(dataset, prior=prior)
    no_symlinks(output)
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'investments.json'
    require(not target.is_symlink() and (not target.exists() or target.is_file()), 'Invalid investment target')
    descriptor, name = tempfile.mkstemp(prefix='.investments-', suffix='.candidate', dir=output)
    candidate = Path(name)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(dataset, stream, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        load_dataset(candidate, prior=prior)
        candidate.chmod(0o644)
        os.replace(candidate, target)
    finally:
        candidate.unlink(missing_ok=True)


def refresh(output, cache, *, adapters=None, generated_at=None, prior_path=None, linker=None):
    output, cache = Path(output), Path(cache)
    no_symlinks(output)
    cache = safe_cache(cache, output)
    prior_target = Path(prior_path) if prior_path is not None else output / 'investments.json'
    no_symlinks(prior_target)
    if prior_path is not None:
        require(prior_target.is_file(), 'Explicit prior snapshot is missing')
    prior = load_dataset(prior_target) if prior_target.exists() else None
    collectors = load_adapters() if adapters is None else adapters
    if linker is None and adapters is None:
        # Production: documented links need the commission orders from BIP.
        loader = network_orders_loader(cache)
        linker = lambda records, prior: collect_links(records, prior, orders_loader=loader)  # noqa: E731
    require(bool(collectors), 'No investment adapters configured')
    # Every collector gets the FULL verified previous artifact, not a source-only slice.
    contributions = [collect(cache, prior=copy.deepcopy(prior)) for collect in collectors]
    generated_at = generated_at or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    dataset = build_dataset(contributions, generated_at=generated_at, prior=prior, linker=linker)
    require(dataset['counts']['records'] > 0, 'No verified investment records collected; old snapshot preserved')
    publish(output, dataset, prior=prior)
    return dataset


def main(argv=None):
    parser = argparse.ArgumentParser(description='Radar Ożarów — real-source investment aggregation (fail closed)')
    parser.add_argument('--output', type=Path, default=ROOT / 'public/data', help='Output directory; writes only investments.json')
    parser.add_argument('--cache', type=Path, default=Path(os.environ.get('TMPDIR', Path.home() / '.cache')) / 'radar-ozarow-investments', help='Private source scratch outside repository/output; no persisted raw/cookies')
    parser.add_argument('--prior', type=Path, help='Verified previous investments.json preserved before the GUNB directory swap')
    parser.add_argument('--validate', type=Path, metavar='JSON', help='Validate an existing investment artifact without fetching/writing')
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(args.validate) if args.validate is not None else refresh(args.output, args.cache, prior_path=args.prior)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f'Investment import rejected; previous snapshot preserved: {exc}\n')
    print(json.dumps(dict(generatedAt=dataset['generatedAt'], counts=dataset['counts'],
                         sources={s['id']: s['status'] for s in dataset['sources']}, warnings=dataset['warnings']), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
