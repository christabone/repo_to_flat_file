# repo_to_flat_file

`repo_to_flat_file` is a Python script that helps you:

1. **Scan** a repository for text-based code files (skipping binary/unreadable files).
2. **Generate an index** mapping each file to a unique numeric ID.
3. **Extract** those files into a single *flat file* for easy feeding into Large Language Models (LLMs).
4. **Estimate token counts** (optional) to gauge how large your text corpus might be.
5. **Ignore certain files or directories** via patterns (akin to `.gitignore`).
6. **Specify IDs and Ranges** for extracting only desired files.

---

## Features

- **Default "Scan + Extract Everything"**  
  When you run the script **without** `--scan` or `--extract`, it will:
  1. **Scan** your repository and create (or overwrite) an index file (default: `index.txt`).
  2. **Extract** **all** discovered text files into a single output file (default: `flat_output.txt`).
  3. If you also include `--token`, it will read all file contents to produce a total token count across the repository.

- **Manual Scan** (`--scan`):
  - Generates or overwrites `index.txt`, enumerating all text files.  
  - Skips files matching your ignore file patterns (if any) or those that appear binary/unreadable.  
  - Optionally calculate a total token count by adding `--token`.
  - Prints how many patterns it found in your ignore file, and prints a skip message whenever a file or directory matches an ignore pattern.

- **Manual Extract** (`--extract`):
  - Uses an existing `index.txt` to extract files by ID into a single flat output file.  
  - **Now supports** a combination of single IDs and ranges in `--files`. E.g., `--files 1,2,5,7-15,30`.
  - Shows an approximate token count for the extracted subset.

- **Skip Binary Files**:
  - Automatically skips unreadable or binary files, printing warnings to `stderr`.

- **Ignore Files or Directories**:
  - Optionally use an ignore file (like `.repoignore`) to skip indexing certain files or directories.  
  - Patterns are checked with `fnmatch` against the relative path.

- **Overwrite Behavior**:
  - The index and output files are always overwritten, never appended.

- **Approximate Token Count**:
  - A simple heuristic splits on whitespace and multiplies by ~1.2 to approximate tokens.  
  - This can be replaced with a more sophisticated tokenizer if needed.

---

## Requirements

- **Python 3.6+**
- [**chardet**](https://pypi.org/project/chardet/) (for file encoding detection):

```bash
pip install chardet
