#!/usr/bin/env python3

import os
import sys
import fnmatch
import chardet
import yaml
from collections import deque

# List of typical image extensions we want to skip if include_images is false
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

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
    If chardet.confidence < 0.5 or encoding is None, consider it binary.
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

def extract_js_imports(file_path, include_css=False):
    """
    Look for lines in a JS file with an import statement, e.g.:
      import Something from '...';
      import { SomethingElse } from '...';
      import '...';
      or require('...')
    
    If include_css is True, we also keep CSS/SCSS imports (e.g. .css, .scss).
    Otherwise, we skip them.
    
    Return a list of local import paths that typically start with '.' or '/'.
    """
    imports = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                # A naive check: look for lines that start with 'import' or contain `require(`
                if line.startswith("import "):
                    # We'll roughly parse out whatever is in the quotes
                    start_quote = line.find("'")
                    if start_quote == -1:
                        start_quote = line.find('"')
                    end_quote = line.rfind("'")
                    if end_quote == -1:
                        end_quote = line.rfind('"')

                    if start_quote != -1 and end_quote != -1 and end_quote > start_quote:
                        import_path = line[start_quote+1:end_quote].strip()
                        imports.append(import_path)
                elif "require(" in line:
                    # e.g. const X = require('somePath');
                    start_quote = line.find("'")
                    if start_quote == -1:
                        start_quote = line.find('"')
                    end_quote = line.rfind("'")
                    if end_quote == -1:
                        end_quote = line.rfind('"')
                    if start_quote != -1 and end_quote != -1 and end_quote > start_quote:
                        import_path = line[start_quote+1:end_quote].strip()
                        imports.append(import_path)
    except Exception as e:
        print(f"Warning: Could not read file {file_path}. Error: {e}", file=sys.stderr)

    # Filter out anything that is clearly a third-party import (e.g. 'react', 'lodash', etc.).
    # We'll only keep local or relative paths that typically start with './', '../', or '/'
    local_imports = []
    for imp in imports:
        if imp.startswith('.') or imp.startswith('/'):
            # If include_css=False, skip typical style files
            if not include_css and (
                imp.endswith('.css') or
                imp.endswith('.scss') or
                imp.endswith('.sass') or
                '.module.scss' in imp
            ):
                # Skip style imports if user doesn't want them
                continue
            local_imports.append(imp)

    return local_imports

def resolve_import_path(current_file, import_path, repo_root, include_css=False):
    """
    Given the current file path and an import path like '../SomeFolder/SomeModule',
    resolve to an absolute path. We only handle .js, .jsx, .ts, .tsx by default,
    plus style files if include_css=True (CSS, SCSS, etc.).
    """
    # If it's an absolute path (e.g. '/components/SomeFile'), treat that
    # as relative to the repo root. Otherwise it's relative to the folder of current_file.
    current_dir = os.path.dirname(current_file)
    if import_path.startswith('/'):
        candidate_base = os.path.join(repo_root, import_path.lstrip('/'))
    else:
        candidate_base = os.path.join(current_dir, import_path)

    # Always try these for JS/TS
    possible_extensions = ['', '.js', '.jsx', '.ts', '.tsx', '/index.js', '/index.jsx', '/index.ts', '/index.tsx']

    # If we're including CSS, add typical style extensions
    if include_css:
        possible_extensions += [
            '.css', '.scss', '.sass', '.module.css', '.module.scss', '.module.sass',
            '/index.css', '/index.scss', '/index.sass'
        ]

    # If import_path explicitly has an extension we don't handle, we still want to check that path directly
    # For example, user wrote `import logo from './alliance_logo_xenbase.png'` — let's see if that path exists.
    # Then as a fallback, we try our typical extension guesses.
    checked_any = False
    if os.path.splitext(candidate_base)[1]:
        if os.path.isfile(candidate_base):
            return os.path.abspath(candidate_base)
        checked_any = True

    for ext in possible_extensions:
        candidate = candidate_base + ext
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)

    # If nothing is found, return None
    return None

def skip_non_text_or_images(filepath, include_images=False):
    """
    Return True if the file should be skipped due to:
      - It's not a text file (per chardet) AND it's not an allowed image
      - Or if we're not including images and it's an image file.
    Otherwise, return False (meaning: do NOT skip).
    """
    # Check extension
    _, ext = os.path.splitext(filepath)
    ext = ext.lower()

    if ext in IMAGE_EXTENSIONS:
        # If user doesn't want images, skip
        if not include_images:
            return True
        # If user does want images, we keep them. 
        # (But be aware the BFS might not parse them for further imports anyway.)
        return False

    # Not an image extension -> fallback to is_text_file check
    if not is_text_file(filepath):
        return True

    return False

def traverse_js_deps(repo_root, start_files, ignore_patterns, do_token_count=False,
                     include_css_imports=False, include_images=False, max_depth="all"):
    """
    BFS through JS/TS dependencies starting from multiple start_files, with an optional depth limit.

      - For each start file, parse its import statements (including CSS if include_css_imports is True)
      - For each local import, resolve to an actual path in the repo
      - Skip duplicates across all start files
      - Skip anything that matches ignore patterns
      - If 'max_depth' is an integer, we only expand that many levels
        of imports. If 'max_depth' == 'all', we expand fully.

    Returns:
      (all_files, total_tokens): a list of unique files, plus approximate token count (if do_token_count=True).
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

        # Check if it’s text or allowed image (skip otherwise)
        if skip_non_text_or_images(current_file, include_images=include_images):
            print(f"Skipping binary/unwanted file '{relpath}'", file=sys.stderr)
            continue

        # Optionally accumulate token count for text-based files only
        # (You might not want to count tokens in image files.)
        _, ext = os.path.splitext(current_file)
        ext = ext.lower()
        if do_token_count and ext not in IMAGE_EXTENSIONS:
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

        # If it's an image, there won't be any further imports to parse, so skip
        if ext in IMAGE_EXTENSIONS:
            continue

        # Otherwise, parse and queue up next-level imports
        local_imports = extract_js_imports(current_file, include_css=include_css_imports)
        for imp in local_imports:
            resolved_path = resolve_import_path(current_file, imp, repo_root, include_css=include_css_imports)
            if resolved_path and resolved_path not in visited:
                queue.append((resolved_path, cur_depth + 1))

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
            # If it's an image, we might not want to read binary data. 
            # So let's do a quick extension check:
            _, ext = os.path.splitext(fpath)
            ext = ext.lower()
            if ext in IMAGE_EXTENSIONS:
                # Option A: Skip writing binary data to output file
                # combined_content.append(f"===== FILE (image skipped): {relpath} =====\n")
                # Option B: just note that we found an image
                combined_content.append(f"===== FILE: {relpath} =====\n[Image file skipped]\n\n")
                continue

            # Otherwise, read text-based content
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
        print("Usage: python js_deps_from_yaml.py <config_file.yaml>", file=sys.stderr)
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

    ignore_file = config.get("ignore_file", ".repoignore")
    token_count = config.get("token_count", False)
    output_file = config.get("output", "js_flat_output.txt")

    # For including local CSS/SCSS imports
    include_css_imports = config.get("include_css_imports", False)

    # New config option for including images, default false
    include_images = config.get("include_images", False)

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
    all_files, total_tokens = traverse_js_deps(
        repo_root=repo_root,
        start_files=abs_start_files,
        ignore_patterns=ignore_patterns,
        do_token_count=token_count,
        include_css_imports=include_css_imports,
        include_images=include_images,
        max_depth=depth_setting
    )

    # Summarize
    print(f"Discovered {len(all_files)} unique files in the dependency chain.")
    if token_count:
        print(f"Approximate total tokens: {total_tokens}")

    # Create a single flat file with all code (images get "skipped" notes)
    create_flat_output(all_files, repo_root, output_file)
    print(f"Wrote combined contents to '{output_file}'.")
    
if __name__ == "__main__":
    main()
