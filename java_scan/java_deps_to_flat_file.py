#!/usr/bin/env python3

import os
import sys
import fnmatch
import chardet
import yaml
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
                    # remove 'package ' and trailing ';'
                    package_name = line[len("package "):].rstrip(";")
                elif line.startswith("import "):
                    # remove 'import ' and trailing ';'
                    imp = line[len("import "):].rstrip(";")
                    import_statements.append(imp)
    except Exception as e:
        print(f"Warning: Could not read file {file_path}. Error: {e}", file=sys.stderr)

    return package_name, import_statements

def import_to_filepath(java_import):
    """
    Convert a Java import (e.g., org.alliancegenome.curation_api.model.entities.SomeClass)
    into a possible relative file path, e.g.:
        org/alliancegenome/curation_api/model/entities/SomeClass.java
    """
    parts = java_import.strip().split('.')
    if not parts:
        return None
    class_name = parts[-1]
    package_part = parts[:-1]
    if not package_part or not class_name:
        return None

    package_path = "/".join(package_part)
    return os.path.join(package_path, f"{class_name}.java")

def find_file_in_repo(repo_root, relative_path, java_source_root):
    """
    Given a repo root and a relative path (like org/alliancegenome/curation_api/model/entities/Gene.java),
    return the full absolute path if it exists, else None.
    """
    prefixed_rel_path = os.path.join(java_source_root, relative_path)
    full_path = os.path.join(repo_root, prefixed_rel_path)
    if os.path.isfile(full_path):
        return full_path
    return None

def traverse_java_deps(repo_root, start_files, ignore_patterns, java_source_root,
                       do_token_count=False, max_depth="all"):
    """
    BFS through Java dependencies starting from multiple start_files, with an optional depth limit.

      - For each start file, parse its import statements
      - For each import, find the .java file in the repo (if it exists),
        queue it for further parsing
      - Skip duplicates across all start files
      - Skip anything that matches ignore patterns
      - If 'max_depth' is an integer, we only expand that many levels
        of imports. If 'max_depth' == 'all', we expand fully.

    Returns:
      (all_files, total_tokens): a list of unique Java files, plus approximate token count (if do_token_count=True).
    """
    visited = set()  # store absolute paths to avoid duplicates
    queue = deque()

    # Convert max_depth to an integer or None if "all"
    if isinstance(max_depth, str) and max_depth.lower() == "all":
        max_depth = None  # means unlimited
    elif isinstance(max_depth, int):
        pass  # keep as is
    else:
        # fallback if user typed something weird
        max_depth = None

    # Initialize the queue with all start files, each with initial depth=0
    for sf in start_files:
        queue.append((sf, 0))

    all_files = []
    total_tokens = 0

    while queue:
        current_file, cur_depth = queue.popleft()
        relpath = os.path.relpath(current_file, repo_root)

        if current_file in visited:
            print(f"Already processed '{relpath}'", file=sys.stderr)
            continue

        visited.add(current_file)

        # Check ignore patterns
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

        # If we've reached max_depth (cur_depth >= max_depth), do not expand further
        if max_depth is not None and cur_depth >= max_depth:
            continue

        # Parse and queue up next-level imports
        _, imports = extract_package_and_imports(current_file)
        for imp in imports:
            possible_rel_path = import_to_filepath(imp)
            if not possible_rel_path:
                continue
            possible_abs_path = find_file_in_repo(repo_root, possible_rel_path, java_source_root)
            if possible_abs_path and possible_abs_path not in visited:
                queue.append((possible_abs_path, cur_depth + 1))

    return all_files, total_tokens

def create_flat_output(files_list, repo_root, output_file):
    """
    Write the contents of all given files to 'output_file', each preceded
    by a header line.
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
    if len(sys.argv) < 2:
        print("Usage: python java_deps_from_yaml.py <config_file.yaml>", file=sys.stderr)
        sys.exit(1)

    config_file = sys.argv[1]
    if not os.path.isfile(config_file):
        print(f"Error: Configuration file '{config_file}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Load YAML config
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading YAML config: {e}", file=sys.stderr)
        sys.exit(1)

    # Extract config values
    repo_root = config.get("repo", "")
    if not repo_root or not os.path.isdir(repo_root):
        print(f"Error: 'repo' is not a valid directory: {repo_root}", file=sys.stderr)
        sys.exit(1)

    java_source_root = config.get("java_source_root", "src/main/java")
    ignore_file = config.get("ignore_file", ".repoignore")
    token_count = config.get("token_count", False)
    output_file = config.get("output", "java_flat_output.txt")

    start_files = config.get("files", [])
    if not start_files:
        print("Error: 'files' list is empty or not provided in the YAML config.", file=sys.stderr)
        sys.exit(1)

    # Depth can be an integer or "all"
    depth_setting = config.get("depth", "all")  # default to "all"

    # Convert all start files to absolute paths, check they exist
    abs_start_files = []
    for sf in start_files:
        full_path = os.path.join(repo_root, sf)
        if not os.path.isfile(full_path):
            print(f"Error: Start file does not exist or is not a file: {sf}", file=sys.stderr)
            sys.exit(1)
        abs_start_files.append(full_path)

    # Parse ignore patterns
    ignore_patterns = parse_ignore_file(os.path.join(repo_root, ignore_file))
    if ignore_patterns:
        print(f"Found {len(ignore_patterns)} ignore patterns in '{ignore_file}'")
    else:
        print(f"No ignore patterns found in '{ignore_file}' (or file does not exist).")

    # Traverse dependencies
    all_files, total_tokens = traverse_java_deps(
        repo_root=repo_root,
        start_files=abs_start_files,
        ignore_patterns=ignore_patterns,
        java_source_root=java_source_root,
        do_token_count=token_count,
        max_depth=depth_setting
    )

    # Summarize
    print(f"Discovered {len(all_files)} unique Java files in the dependency chain.")
    if token_count:
        print(f"Approximate total tokens: {total_tokens}")

    # Create a single flat file with all code
    create_flat_output(all_files, repo_root, output_file)
    print(f"Wrote combined Java contents to '{output_file}'.")

if __name__ == "__main__":
    main()
