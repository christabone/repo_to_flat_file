#!/usr/bin/env python3

import os
import argparse
import fnmatch
import chardet  # For file encoding detection
import sys

def parse_ignore_file(ignore_file):
    """
    Read the ignore file line by line, ignoring comments (#)
    and blank lines. Return a list of ignore patterns.
    """
    patterns = []
    if not os.path.isfile(ignore_file):
        return patterns  # No file found, no patterns

    with open(ignore_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comment lines
            if not line or line.startswith('#'):
                continue
            patterns.append(line)
    return patterns

def should_ignore(relpath, ignore_patterns):
    """
    Check if relpath matches any of the ignore patterns.
    We use fnmatch for wildcard matching.

    If it matches, return (True, matched_pattern).
    Otherwise, return (False, None).
    """
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(relpath, pattern):
            return True, pattern
    return False, None

def is_text_file(filepath, max_bytes=1024):
    """
    Attempt to guess if a file is text by reading a small chunk and checking encoding.
    Returns True if likely text, otherwise False.
    """
    try:
        with open(filepath, 'rb') as f:
            rawdata = f.read(max_bytes)
        result = chardet.detect(rawdata)
        # If confidence is low or encoding is not text-based, skip
        if result['encoding'] is None or result['confidence'] < 0.5:
            return False
        return True
    except Exception:
        # If there's an error reading, consider it non-text for safety
        return False

def approximate_token_count(text):
    """
    Roughly estimate token count.
    We split on whitespace and multiply by ~1.2 to guess the number of tokens.
    """
    words = text.split()
    return int(len(words) * 1.2)

def scan_repository(repo_path, index_file_path, do_token_count=False, ignore_patterns=None):
    """
    Recursively scan the repo_path for text files.
    - Writes an index file (ID \t RELPATH).
    - If do_token_count=True, it also reads each text file to accumulate a rough total token count.
    - Ignores any file or directory whose relative path matches an entry in ignore_patterns.

    Returns:
      file_map: dict {file_id: relative_path}
      total_tokens: int (estimated), or 0 if do_token_count=False
    """
    if ignore_patterns is None:
        ignore_patterns = []

    file_map = {}
    current_id = 1
    total_tokens = 0

    with open(index_file_path, 'w', encoding='utf-8') as index_file:
        # Walk the tree
        for root, dirs, files in os.walk(repo_path):
            # Skip directories matching ignore patterns (so we don't descend into them)
            for d in list(dirs):
                full_dirpath = os.path.join(root, d)
                rel_dirpath = os.path.relpath(full_dirpath, repo_path)
                ignored, matched_pattern = should_ignore(rel_dirpath, ignore_patterns)
                if ignored:
                    print(f"Skipping directory '{rel_dirpath}' due to ignore pattern '{matched_pattern}'", file=sys.stderr)
                    dirs.remove(d)

            # Handle files in the current directory
            for filename in files:
                filepath = os.path.join(root, filename)
                relpath = os.path.relpath(filepath, repo_path)

                # Check if we should ignore this file
                ignored, matched_pattern = should_ignore(relpath, ignore_patterns)
                if ignored:
                    print(f"Skipping file '{relpath}' due to ignore pattern '{matched_pattern}'", file=sys.stderr)
                    continue

                # Check if it's text
                if is_text_file(filepath):
                    # If requested, read the file to accumulate token count
                    if do_token_count:
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                                file_content = f.read()
                            file_tokens = approximate_token_count(file_content)
                            total_tokens += file_tokens
                        except Exception as e:
                            print(f"Warning: Could not open or read file {relpath}. Error: {e}", file=sys.stderr)
                            continue

                    # Write to index
                    file_map[current_id] = relpath
                    index_file.write(f"{current_id}\t{relpath}\n")
                    current_id += 1
                else:
                    # Print a warning if binary/unreadable
                    print(f"Warning: Skipping binary or unreadable file: {relpath}", file=sys.stderr)

    return file_map, total_tokens

def parse_file_ids(files_arg):
    """
    Parse a string like "1,2,5,7-15,30" into a list of integers.
    - Single IDs (e.g., "1", "5") become individual integers.
    - Ranges (e.g., "7-15") expand to [7,8,9,10,11,12,13,14,15].
    - Ignores empty or malformed parts (though typical usage shouldn't produce them).
    """
    all_ids = []
    parts = files_arg.split(',')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Check for range
        if '-' in part:
            try:
                start_str, end_str = part.split('-', 1)
                start = int(start_str)
                end = int(end_str)
                # If user reversed them (e.g., "15-7"), let's handle that gracefully
                if start > end:
                    start, end = end, start
                all_ids.extend(range(start, end + 1))
            except ValueError:
                # If parsing fails, ignore or handle differently
                continue
        else:
            # Single number
            try:
                val = int(part)
                all_ids.append(val)
            except ValueError:
                continue
    return all_ids

def extract_files(repo_path, index_file_path, selection, output_file_path):
    """
    Read the index_file to get the mapping of IDs -> file paths.
    For the given selection (which can include commas and hyphens),
    read those files and output them to output_file_path, with
    a numbered header above each file's content.

    Also prints an approximate token count of just the extracted content.
    """
    # Build dictionary from index file
    id_to_path = {}
    with open(index_file_path, 'r', encoding='utf-8') as index_f:
        for line in index_f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('\t', 1)
            if len(parts) == 2:
                file_id_str, relpath = parts
                try:
                    file_id = int(file_id_str)
                    id_to_path[file_id] = relpath
                except ValueError:
                    continue

    # Parse the selection string (e.g., "1,2,3,10-15")
    selected_ids = parse_file_ids(selection)

    if not selected_ids:
        print("Warning: No valid file IDs parsed from selection. Exiting extraction.")
        return

    combined_content = []
    for file_id in selected_ids:
        if file_id not in id_to_path:
            print(f"Warning: File ID {file_id} not found in index. Skipping.")
            continue

        relpath = id_to_path[file_id]
        full_path = os.path.join(repo_path, relpath)

        # Verify it's still text
        if not is_text_file(full_path):
            print(f"Warning: File {relpath} is not a text file. Skipping.")
            continue

        try:
            with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                file_content = f.read()
            section_header = f"===== FILE ID {file_id} : {relpath} =====\n"
            combined_content.append(section_header + file_content + "\n")
        except Exception as e:
            print(f"Warning: Could not open or read file {relpath}. Error: {e}", file=sys.stderr)
            continue

    # Write combined content to output file
    final_output = "".join(combined_content)
    with open(output_file_path, 'w', encoding='utf-8') as out_f:
        out_f.write(final_output)

    # Print approximate token count of extracted content
    tok_count = approximate_token_count(final_output)
    print(f"File '{output_file_path}' has been produced with an estimated {tok_count} tokens.")

def main():
    parser = argparse.ArgumentParser(
        description="Scan a repository for text files and/or extract specified files into a flat file for LLM consumption."
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Path to the repository you want to scan or extract from."
    )
    parser.add_argument(
        "--index",
        default="index.txt",
        help="Path to the index file to create or use for extraction."
    )
    parser.add_argument(
        "--output",
        default="flat_output.txt",
        help="Output file for combined contents."
    )
    parser.add_argument(
        "--ignore-file",
        default=".repoignore",
        help="Path to a file listing patterns (like .gitignore) to ignore during scanning."
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan the repo to generate an index file (skips reading all file contents unless --token is used)."
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract specified files based on their IDs (requires --files)."
    )
    parser.add_argument(
        "--files",
        default="",
        help="Comma-separated list of file IDs (e.g., '1,2,5') or ranges (e.g., '7-15') to extract. Combine them: '1,2,5,7-15,30'"
    )
    parser.add_argument(
        "--token",
        action="store_true",
        help="If used with --scan (or default mode), also read file contents to produce a total token count."
    )

    args = parser.parse_args()

    # Parse the ignore file for patterns
    ignore_patterns = parse_ignore_file(args.ignore_file)
    if ignore_patterns:
        print(f"Found {len(ignore_patterns)} ignore patterns in '{args.ignore_file}'")
    else:
        print(f"No ignore patterns found in '{args.ignore_file}' (or file does not exist).")

    # Default mode: if neither --scan nor --extract is provided,
    # do a "scan + extract everything" in one go.
    if not args.scan and not args.extract:
        print("No mode specified. Defaulting to scanning and extracting ALL files.")
        file_map, total_tokens = scan_repository(
            repo_path=args.repo,
            index_file_path=args.index,
            do_token_count=args.token,
            ignore_patterns=ignore_patterns
        )
        if args.token:
            print(f"Scan complete. Estimated total tokens across all text files: {total_tokens}")
        # Extract ALL file IDs
        all_ids_str = ",".join(str(fid) for fid in file_map.keys())
        extract_files(args.repo, args.index, all_ids_str, args.output)
        sys.exit(0)

    # If scan is requested
    if args.scan:
        print("Scanning repository to build index file ...")
        file_map, total_tokens = scan_repository(
            repo_path=args.repo,
            index_file_path=args.index,
            do_token_count=args.token,
            ignore_patterns=ignore_patterns
        )
        print(f"Index file '{args.index}' has been created with {len(file_map)} entries.")
        if args.token:
            print(f"Estimated total tokens across all text files: {total_tokens}")

    # If extract is requested
    if args.extract:
        if not args.files:
            print("Error: --extract requires --files argument (comma-separated IDs or ranges).")
            sys.exit(1)
        print(f"Extracting specified files from the index: {args.files}")
        extract_files(args.repo, args.index, args.files, args.output)

if __name__ == "__main__":
    main()
