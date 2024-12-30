#!/usr/bin/env python3

import os
import sys
import argparse
import fnmatch
import chardet
from collections import deque

def parse_ignore_file(ignore_file):
    """
    Read the ignore file line by line, ignoring comments (#) and blank lines.
    Return a list of ignore patterns.
    """
    patterns = []
    if not os.path.isfile(ignore_file):
        return patterns  # No file found, no patterns

    with open(ignore_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            patterns.append(line)
    return patterns

def should_ignore(relpath, ignore_patterns):
    """
    Check if relpath matches any of the ignore patterns (fnmatch).
    If it matches, return (True, matched_pattern). Otherwise, (False, None).
    """
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(relpath, pattern):
            return True, pattern
    return False, None

def approximate_token_count(text):
    """
    Roughly estimate token count by splitting on whitespace
    and multiplying by ~1.2 to guess the number of tokens.
    """
    words = text.split()
    return int(len(words) * 1.2)

def is_text_file(filepath, max_bytes=1024):
    """
    Attempt to guess if a file is text by reading a small chunk
    and checking encoding via chardet.
    """
    try:
        with open(filepath, 'rb') as f:
            rawdata = f.read(max_bytes)
        result = chardet.detect(rawdata)
        if result['encoding'] is None or result['confidence'] < 0.5:
            return False
        return True
    except Exception:
        return False

def extract_package_and_imports(file_path):
    """
    Read a Java file, returning:
      - package_name (string or None)
      - a list of import statements (list of strings)
    """
    package_name = None
    import_statements = []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if line.startswith("package "):
                    # e.g. package org.alliancegenome.curation_api.model.entities;
                    # remove 'package ' and trailing ';'
                    package_name = line[len("package "):].rstrip(";")
                elif line.startswith("import "):
                    # e.g. import org.alliancegenome.curation_api.model.entities.XYZ;
                    imp = line[len("import "):].rstrip(";")
                    import_statements.append(imp)
    except Exception as e:
        print(f"Warning: Could not read file {file_path}. Error: {e}", file=sys.stderr)

    return package_name, import_statements

def package_to_path(package_name):
    """
    Convert a Java package name to a relative directory path:
    e.g. org.alliancegenome.curation_api.model.entities
    -> org/alliancegenome/curation_api/model/entities
    """
    return package_name.replace('.', '/')

def import_to_filepath(java_import):
    """
    Convert a Java import (e.g., org.alliancegenome.curation_api.model.entities.SomeClass)
    into a possible relative file path, e.g.
    org/alliancegenome/curation_api/model/entities/SomeClass.java
    """
    parts = java_import.strip().split('.')
    if not parts:
        return None
    # Last part should be the class name, the rest is the package
    class_name = parts[-1]
    package_part = parts[:-1]
    if not package_part or not class_name:
        return None

    package_path = "/".join(package_part)
    return os.path.join(package_path, f"{class_name}.java")

def find_file_in_repo(repo_root, relative_path):
    """
    Given a repo root and a relative path (like org/alliancegenome/curation_api/model/entities/Gene.java),
    return the full absolute path if it exists, else None.
    """
    full_path = os.path.join(repo_root, relative_path)
    if os.path.isfile(full_path):
        return full_path
    return None

def traverse_java_deps(repo_root, start_file, ignore_patterns, do_token_count=False):
    """
    BFS (or DFS) through Java dependencies:
      - Start from 'start_file'
      - Parse its import statements
      - For each import, find the .java file in the repo (if it exists),
        queue it for further parsing
      - Skip duplicates
      - Skip anything that matches ignore patterns
      - Return a list of all discovered Java files in dependency chain

    Also returns the total approximate token count if do_token_count=True
    """
    visited = set()  # store absolute paths to avoid duplicates
    queue = deque([start_file])
    all_files = []
    total_tokens = 0

    while queue:
        current_file = queue.popleft()
        if current_file in visited:
            continue
        visited.add(current_file)

        # Build relpath to check ignore patterns
        relpath = os.path.relpath(current_file, repo_root)
        ignored, matched_pattern = should_ignore(relpath, ignore_patterns)
        if ignored:
            print(f"Skipping file '{relpath}' due to ignore pattern '{matched_pattern}'", file=sys.stderr)
            continue

        # Check if it's text
        if not is_text_file(current_file):
            print(f"Skipping binary/unreadable file '{relpath}'", file=sys.stderr)
            continue

        # Optionally accumulate token count
        if do_token_count:
            try:
                with open(current_file, 'r', encoding='utf-8', errors='replace') as f:
                    file_content = f.read()
                total_tokens += approximate_token_count(file_content)
            except Exception as e:
                print(f"Warning: Could not read file {relpath}. Error: {e}", file=sys.stderr)

        # Keep track of the file
        all_files.append(current_file)

        # Parse package/imports to find further references
        package_name, imports = extract_package_and_imports(current_file)

        # For each import, try to locate the file in the repo
        for imp in imports:
            # e.g. org.alliancegenome.curation_api.model.entities.Something
            # convert to path
            possible_rel_path = import_to_filepath(imp)
            if not possible_rel_path:
                continue
            possible_abs_path = find_file_in_repo(repo_root, possible_rel_path)
            if possible_abs_path and possible_abs_path not in visited:
                queue.append(possible_abs_path)

    return all_files, total_tokens

def create_flat_output(files_list, repo_root, output_file):
    """
    Write the contents of all given files to 'output_file', each preceded
    by a header line. Avoid duplicates (assumes files_list is already deduplicated).
    """
    combined_content = []
    for fpath in files_list:
        relpath = os.path.relpath(fpath, repo_root)
        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            header = f"===== FILE: {relpath} =====\n"
            combined_content.append(header + content + "\n")
        except Exception as e:
            print(f"Warning: Could not open file {relpath}. Error: {e}", file=sys.stderr)

    final_output = "".join(combined_content)
    with open(output_file, 'w', encoding='utf-8') as out_f:
        out_f.write(final_output)

def main():
    parser = argparse.ArgumentParser(
        description="Traverse Java file dependencies (imports) starting from a single file, "
                    "and produce a flat output of all related Java code."
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Path to the repository root."
    )
    parser.add_argument(
        "--start-file",
        required=True,
        help="Relative path (from repo root) to the initial Java file to analyze."
    )
    parser.add_argument(
        "--output",
        default="java_flat_output.txt",
        help="File to write all discovered Java contents."
    )
    parser.add_argument(
        "--ignore-file",
        default=".repoignore",
        help="Path to a file listing patterns to ignore (fnmatch style). Defaults to .repoignore"
    )
    parser.add_argument(
        "--token",
        action="store_true",
        help="If set, compute a rough token count while scanning."
    )

    args = parser.parse_args()

    # Ensure the start file is actually present
    start_abspath = os.path.join(args.repo, args.start_file)
    if not os.path.isfile(start_abspath):
        print(f"Error: The specified start file does not exist: {args.start_file}", file=sys.stderr)
        sys.exit(1)

    # Parse ignore patterns
    ignore_patterns = parse_ignore_file(args.ignore_file)
    if ignore_patterns:
        print(f"Found {len(ignore_patterns)} ignore patterns in '{args.ignore_file}'")
    else:
        print(f"No ignore patterns found in '{args.ignore_file}' (or file does not exist).")

    # Perform BFS (or DFS) to get all related Java files
    all_files, total_tokens = traverse_java_deps(
        repo_root=args.repo,
        start_file=start_abspath,
        ignore_patterns=ignore_patterns,
        do_token_count=args.token
    )

    # Summarize
    print(f"Discovered {len(all_files)} Java files in the dependency chain starting from {args.start_file}")
    if args.token:
        print(f"Approximate total tokens: {total_tokens}")

    # Create a single flat file with all code
    create_flat_output(all_files, args.repo, args.output)
    print(f"Wrote combined Java contents to '{args.output}'.")

if __name__ == "__main__":
    main()
