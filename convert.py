#!/usr/bin/env python3
"""Convert Daggerheart adversaries from PDF or MD to individual files.

Usage:
    python convert.py source.pdf -o output/           # Convert PDF to Arrow's Adversary Bank MD files
    python convert.py source.md -o output/            # Convert multi-adversary MD to Arrow's Adversary Bank files
    python convert.py source.pdf -o output/ --index   # Also generate master index
    python convert.py source.md --list                # List adversaries without converting
    python convert.py source.pdf --adversary-bank     # Export combined JSON only
"""
import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from models.adversary import Adversary
from models.environment import Environment
from models.parse_result import ParseResult
from parsers.md_parser import MDParser
from writers.adversary_bank_writer import AdversaryBankWriter, ENVIRONMENT_SUBFOLDER
from writers.markdown_writer import MarkdownWriter
from writers.index_generator import IndexGenerator


def parse_source(source_path: Path) -> ParseResult:
    """Parse adversaries and environments from source file (PDF or MD)."""
    suffix = source_path.suffix.lower()

    if suffix == '.pdf':
        try:
            from parsers.pdf_parser import PDFParser
        except ImportError:
            print("Error: pdfplumber is required for PDF parsing.", file=sys.stderr)
            print("Install with: pip install pdfplumber", file=sys.stderr)
            sys.exit(1)

        parser = PDFParser()
        return parser.parse_file(source_path)

    elif suffix == '.md':
        return MDParser.parse_file(source_path)

    else:
        print(f"Error: Unsupported file type: {suffix}", file=sys.stderr)
        print("Supported types: .pdf, .md", file=sys.stderr)
        sys.exit(1)


def list_adversaries(result: ParseResult) -> None:
    """Print a list of adversaries and environments found."""
    print(f"Found {len(result.adversaries)} adversaries:")
    print()
    for i, adv in enumerate(result.adversaries, 1):
        _print_record(i, adv, adv.tier, adv.adversary_type)

    if result.environments:
        print()
        print(f"Found {len(result.environments)} environments:")
        print()
        for i, env in enumerate(result.environments, 1):
            _print_record(i, env, env.tier, env.environment_type)


def _print_record(index: int, record, tier, type_name) -> None:
    tier_str = f"Tier {tier}" if tier else "Tier ?"
    type_str = type_name or "Unknown Type"
    issues = record.validate()
    issues_str = f" [{len(issues)} issues]" if issues else ""

    print(f"  {index:3}. {record.name or 'UNNAMED'} ({tier_str} {type_str}){issues_str}")


def convert_to_files(
    result: ParseResult,
    output_dir: Path,
    overwrite: bool = False,
    verbose: bool = True,
    readable_markdown: bool = False,
) -> dict[str, Path]:
    """Convert records to individual Markdown files.

    Environments are written to an ``environments/`` subfolder so an Obsidian
    library can point at either folder independently.
    """
    writer = MarkdownWriter if readable_markdown else AdversaryBankWriter

    if verbose:
        print(f"Writing {len(result.adversaries)} adversaries to {output_dir}")
        print()

    written = _write_records(
        result.adversaries, output_dir, overwrite, verbose, writer.write_adversary
    )

    if result.environments:
        env_dir = output_dir / ENVIRONMENT_SUBFOLDER
        if verbose:
            print()
            print(f"Writing {len(result.environments)} environments to {env_dir}")
            print()
        written.update(_write_records(
            result.environments, env_dir, overwrite, verbose, writer.write_environment
        ))

    return written


def _write_records(records, output_dir: Path, overwrite, verbose, write) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    used_filenames: set[str] = set()

    for record in records:
        base_name = record.safe_filename()
        output_path = output_dir / f"{base_name}.md"

        i = 1
        while output_path.name in used_filenames or (output_path.exists() and not overwrite):
            output_path = output_dir / f"{base_name}_{i}.md"
            i += 1

        used_filenames.add(output_path.name)

        key = record.name
        if key in written:
            i = 1
            while f"{record.name} ({i})" in written:
                i += 1
            key = f"{record.name} ({i})"

        write(record, output_path)
        written[key] = output_path

        if verbose:
            issues = record.validate()
            issues_mark = f" [{len(issues)} issues]" if issues else ""
            print(f"  ✓ {output_path.name}{issues_mark}")

    return written


def main():
    parser = argparse.ArgumentParser(
        description="Convert Daggerheart adversaries from PDF or MD to Arrow's Adversary Bank files"
    )
    parser.add_argument(
        'source',
        type=Path,
        help='Source file (PDF or MD with multiple adversaries)'
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output directory for individual adversary files'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List adversaries in source without converting'
    )
    parser.add_argument(
        '--index', '-i',
        action='store_true',
        help='Generate master index file in output directory'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing files'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate validation report'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress file-by-file output'
    )
    parser.add_argument(
        '--readable-markdown',
        action='store_true',
        help=(
            "Write the older human-readable stat block Markdown instead of "
            "Arrow's Adversary Bank code blocks (the default since the rebrand)"
        ),
    )
    parser.add_argument(
        '--adversary-bank',
        nargs='?',
        const='adversaries.json',
        metavar='FILENAME',
        help="Export Arrow's Adversary Bank JSON (default: adversaries.json in output dir)"
    )
    parser.add_argument(
        '--beastvault',
        nargs='?',
        const='adversaries.json',
        metavar='FILENAME',
        help="Deprecated alias for --adversary-bank"
    )

    args = parser.parse_args()

    # Validate source file
    if not args.source.exists():
        print(f"Error: Source file not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    # Parse source
    print(f"Parsing {args.source}...")
    result = parse_source(args.source)

    if not result:
        print("No adversaries or environments found in source file.")
        sys.exit(0)

    print(f"Found {len(result.adversaries)} adversaries", end="")
    if result.environments:
        print(f" and {len(result.environments)} environments", end="")
    print()
    print()

    # List mode
    if args.list:
        list_adversaries(result)
        return

    # Report mode
    if args.report:
        report = MarkdownWriter.format_validation_report(
            result.adversaries, environments=result.environments
        )
        print(report)
        return

    # Convert mode - requires output directory unless only a combined JSON file is requested.
    if args.beastvault and not args.adversary_bank:
        print(
            "warning: --beastvault is deprecated; use --adversary-bank instead.",
            file=sys.stderr,
        )
    json_export = args.adversary_bank or args.beastvault

    if not args.output and not json_export:
        print("Error: Output directory required (-o/--output)", file=sys.stderr)
        print("Use --list to see adversaries without converting", file=sys.stderr)
        sys.exit(1)

    # Convert to individual markdown files (if output dir specified)
    written = {}
    if args.output:
        written = convert_to_files(
            result,
            args.output,
            overwrite=args.overwrite,
            verbose=not args.quiet,
            readable_markdown=args.readable_markdown,
        )

    # Generate index if requested
    if args.index and args.output:
        index_path = args.output / "Adversaries_Index.md"
        IndexGenerator.write_index(
            result.adversaries,
            index_path,
            index_type="master",
            environments=result.environments,
        )
        print()
        print(f"Generated index: {index_path}")

    # Arrow's Adversary Bank JSON export
    if json_export:
        from writers.beastvault_writer import BeastvaultWriter

        json_dir = args.output if args.output else Path(".")
        json_path = json_dir / json_export
        count = BeastvaultWriter.write_adversaries(
            result.adversaries, json_path, environments=result.environments
        )
        if not args.quiet:
            print()
            print(f"Arrow's Adversary Bank JSON: {count} entries written to {json_path}")

    # Summary
    if written:
        print()
        print(f"Conversion complete: {len(written)} files written to {args.output}")

    # Show validation summary
    issues_count = sum(
        1 for record in (*result.adversaries, *result.environments) if record.validate()
    )
    if issues_count > 0:
        print(f"Warning: {issues_count} records have validation issues")
        print("Run with --report for details")


if __name__ == '__main__':
    main()
