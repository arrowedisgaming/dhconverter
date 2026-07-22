#!/usr/bin/env python3
"""Normalize Daggerheart adversary markdown files to standardized format.

Usage:
    python normalize.py .                    # Normalize all .md files in current directory
    python normalize.py . --backup           # Create .bak files before modifying
    python normalize.py . --dry-run          # Show what would change without modifying
    python normalize.py . --report           # Generate validation report
    python normalize.py . --add-sources      # Add source attribution from sources/ folder
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from models.adversary import Adversary
from parsers.md_parser import MDParser
from writers.markdown_writer import MarkdownWriter
from utils.source_finder import SourceFinder


# Arrow's Adversary Bank files carry their stat block inside a `daggerheart`
# fenced block, which this tool cannot read. Detect them so they are skipped
# rather than rewritten into an empty stat block.
ADVERSARY_BANK_FENCE_RE = re.compile(r'^```daggerheart\s*$', re.MULTILINE)


# Files to skip during normalization
SKIP_FILES = {
    '_SAMPLE.md',
    'Adversaries_Master_Index.md',
    # The name IndexGenerator actually writes. The entry above never matched
    # it, so a generated index was normalized into an empty stat block.
    'Adversaries_Index.md',
    'Adversaries_By_Type.md',
    'README.md',
    'CLAUDE.md',
}

# Directories to skip
SKIP_DIRS = {
    'environments',
    'sources',
    '.claude',
    'martial',
    'undead',
    'age-of-umbra',
    'misc',
}


def find_adversary_files(directory: Path) -> list[Path]:
    """Find all adversary markdown files in directory."""
    files = []
    for md_file in directory.glob('*.md'):
        if md_file.name in SKIP_FILES:
            continue
        if md_file.name.startswith('_'):
            continue
        files.append(md_file)
    return sorted(files)


def normalize_file(
    file_path: Path,
    backup: bool = False,
    dry_run: bool = False,
    source_finder: SourceFinder = None
) -> dict:
    """Normalize a single adversary file.

    Returns dict with:
        - success: bool
        - changed: bool
        - issues: list of validation issues
        - error: error message if failed
        - source_added: bool - whether source attribution was added
    """
    result = {
        'success': False,
        'changed': False,
        'issues': [],
        'error': None,
        'name': None,
        'source_added': False,
        'skipped': False,
        'skip_reason': None,
    }

    try:
        # Read original content
        original_content = file_path.read_text(encoding='utf-8')

        # Refuse to touch Arrow's Adversary Bank files. MDParser reads only the
        # heading from a `daggerheart` YAML block, so normalizing one would
        # rewrite it as an empty stat block and destroy the content. That
        # format is the converter's default output, so this is the likely
        # thing to point normalize.py at by mistake.
        if ADVERSARY_BANK_FENCE_RE.search(original_content):
            result['success'] = True
            result['skipped'] = True
            result['skip_reason'] = "Arrow's Adversary Bank format"
            result['name'] = file_path.stem
            return result

        # Parse adversary
        adversaries = MDParser.parse_adversaries(file_path)

        if not adversaries:
            result['error'] = "Failed to parse adversary"
            return result

        adv = adversaries[0]

        # Safety net for anything that isn't a stat block — an index, campaign
        # notes, a README copy. Rewriting one replaces its prose with an empty
        # stat block, so require real evidence of a stat block before touching
        # the file, rather than a filename blocklist that will always lag.
        #
        # Features deliberately do not count: any markdown with a "## FEATURES"
        # heading would otherwise qualify, and notes files legitimately have
        # one. Two independent core stats is the threshold — a genuine block
        # always carries several, and no amount of prose produces two by
        # accident.
        core_stats = [
            adv.tier is not None,
            adv.difficulty is not None,
            adv.hp is not None,
            adv.stress is not None,
            bool(adv.thresholds_str),
            bool(adv.attack and not adv.attack.is_empty()),
        ]
        if sum(core_stats) < 2:
            result['success'] = True
            result['skipped'] = True
            result['skip_reason'] = "no stat block found"
            result['name'] = adv.name or file_path.stem
            return result

        result['name'] = adv.name
        result['issues'] = adv.validate()

        # Add source attribution if requested and not already present
        if source_finder and not adv.source_name:
            match = source_finder.find_source(adv.name)
            if match:
                adv.source_name = match.source_name
                adv.source_page = match.source_page
                result['source_added'] = True

        # Generate normalized output
        normalized_content = MarkdownWriter.format_adversary(adv)

        # Check if content changed
        result['changed'] = original_content.strip() != normalized_content.strip()

        if dry_run:
            result['success'] = True
            return result

        if result['changed']:
            # Create backup if requested
            if backup:
                backup_path = file_path.with_suffix('.md.bak')
                shutil.copy2(file_path, backup_path)

            # Write normalized content
            file_path.write_text(normalized_content, encoding='utf-8')

        result['success'] = True

    except Exception as e:
        result['error'] = str(e)

    return result


def normalize_directory(
    directory: Path,
    backup: bool = False,
    dry_run: bool = False,
    verbose: bool = True,
    add_sources: bool = False
) -> dict:
    """Normalize all adversary files in directory.

    Returns summary dict with counts and details.
    """
    files = find_adversary_files(directory)

    # Initialize source finder if requested
    source_finder = None
    if add_sources:
        sources_dir = directory / 'sources'
        if sources_dir.exists():
            source_finder = SourceFinder(sources_dir)
        elif verbose:
            print("Warning: sources/ directory not found, skipping source attribution")

    summary = {
        'total': len(files),
        'success': 0,
        'changed': 0,
        'with_issues': 0,
        'failed': 0,
        'sources_added': 0,
        'skipped': 0,
        'details': [],
    }

    for file_path in files:
        result = normalize_file(
            file_path,
            backup=backup,
            dry_run=dry_run,
            source_finder=source_finder
        )
        result['file'] = file_path.name

        if result.get('skipped'):
            summary['skipped'] += 1
        elif result['success']:
            summary['success'] += 1
            if result['changed']:
                summary['changed'] += 1
            if result['issues']:
                summary['with_issues'] += 1
            if result.get('source_added'):
                summary['sources_added'] += 1
        else:
            summary['failed'] += 1

        summary['details'].append(result)

        if verbose:
            if result.get('skipped'):
                reason = result.get('skip_reason') or 'not a stat block'
                print(f"  - {file_path.name} (skipped: {reason})")
            else:
                status = "✓" if result['success'] else "✗"
                changed_mark = " (changed)" if result['changed'] else ""
                source_mark = " [+source]" if result.get('source_added') else ""
                issues_mark = f" [{len(result['issues'])} issues]" if result['issues'] else ""
                print(f"  {status} {file_path.name}{changed_mark}{source_mark}{issues_mark}")

    return summary


def generate_report(directory: Path) -> str:
    """Generate a validation report for all adversary files."""
    files = find_adversary_files(directory)
    adversaries = []

    for file_path in files:
        parsed = MDParser.parse_adversaries(file_path)
        adversaries.extend(parsed)

    return MarkdownWriter.format_validation_report(adversaries)


def main():
    parser = argparse.ArgumentParser(
        description='Normalize Daggerheart adversary markdown files'
    )
    parser.add_argument(
        'directory',
        type=Path,
        nargs='?',
        default=Path('.'),
        help='Directory containing adversary files (default: current directory)'
    )
    parser.add_argument(
        '--backup', '-b',
        action='store_true',
        help='Create .bak files before modifying'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Show what would change without modifying files'
    )
    parser.add_argument(
        '--report', '-r',
        action='store_true',
        help='Generate validation report'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress file-by-file output'
    )
    parser.add_argument(
        '--add-sources', '-s',
        action='store_true',
        help='Add source attribution by searching sources/ folder'
    )

    args = parser.parse_args()

    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a directory", file=sys.stderr)
        sys.exit(1)

    if args.report:
        report = generate_report(args.directory)
        print(report)
        return

    mode = "DRY RUN - " if args.dry_run else ""
    sources_mode = " (with source attribution)" if args.add_sources else ""
    print(f"{mode}Normalizing adversary files in {args.directory}{sources_mode}")
    print()

    summary = normalize_directory(
        args.directory,
        backup=args.backup,
        dry_run=args.dry_run,
        verbose=not args.quiet,
        add_sources=args.add_sources
    )

    print()
    print("Summary:")
    print(f"  Total files: {summary['total']}")
    print(f"  Successful: {summary['success']}")
    if summary.get('skipped'):
        print(f"  Skipped (not normalizable): {summary['skipped']}")
    print(f"  Changed: {summary['changed']}")
    if args.add_sources:
        print(f"  Sources added: {summary['sources_added']}")
    print(f"  With issues: {summary['with_issues']}")
    print(f"  Failed: {summary['failed']}")

    if summary['with_issues'] > 0:
        print()
        print("Files with validation issues:")
        for detail in summary['details']:
            if detail['issues']:
                print(f"  {detail['file']}:")
                for issue in detail['issues']:
                    print(f"    - {issue}")


if __name__ == '__main__':
    main()
