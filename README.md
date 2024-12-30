repo_to_flat_file
=================

`repo_to_flat_file` is a Python script that helps you:

1.  **Scan** a repository for text-based code files (skipping binary/unreadable files).
2.  **Generate an index** mapping each file to a unique numeric ID.
3.  **Extract** those files into a single *flat file* for easy feeding into Large Language Models (LLMs).
4.  **Estimate token counts** (optional) to gauge how large your text corpus might be.
5.  **Ignore certain files or directories** via patterns (akin to `.gitignore`).
6.  **Specify IDs and Ranges** for extracting only desired files.

* * * * *

repo_to_flat_file.py Features
-----------------------------

-   **Default "Scan + Extract Everything"**\
    When you run the script **without** `--scan` or `--extract`, it will:

    1.  **Scan** your repository and create (or overwrite) an index file (default: `index.txt`).
    2.  **Extract** **all** discovered text files into a single output file (default: `flat_output.txt`).
    3.  If you also include `--token`, it will read all file contents to produce a total token count across the repository.
-   **Manual Scan** (`--scan`):

    -   Generates or overwrites `index.txt`, enumerating all text files.
    -   Skips files matching your ignore file patterns (if any) or those that appear binary/unreadable.
    -   Optionally calculate a total token count by adding `--token`.
    -   Prints how many patterns it found in your ignore file, and prints a skip message whenever a file or directory matches an ignore pattern.
-   **Manual Extract** (`--extract`):

    -   Uses an existing `index.txt` to extract files by ID into a single flat output file.
    -   **Range Support**: You can specify single IDs (e.g. `1,2,5`) or ranges (e.g. `7-15`) or a combination (`--files 1,2,5,7-15,30`).
    -   Shows an approximate token count for the extracted subset.
-   **Skip Binary Files**:

    -   Automatically skips unreadable or binary files, printing warnings to `stderr`.
-   **Ignore Files or Directories**:

    -   Optionally use an ignore file (like `.repoignore`) to skip indexing certain files or directories.
    -   Patterns are checked with `fnmatch` against the relative path.
-   **Overwrite Behavior**:

    -   The index and output files are always overwritten, never appended.
-   **Approximate Token Count**:

    -   A simple heuristic splits on whitespace and multiplies by ~1.2 to approximate tokens.
    -   This can be replaced with a more sophisticated tokenizer if needed.

* * * * *

Requirements
------------

-   **Python 3.6+**
-   [**chardet**](https://pypi.org/project/chardet/) (for file encoding detection):

`pip install chardet`

* * * * *

Usage of `repo_to_flat_file.py`
-------------------------------

1.  **Default Mode (Scan + Extract Everything)**

    `python repo_to_flat_file.py --repo /path/to/repo`

    -   Creates `index.txt` and `flat_output.txt`.
    -   Skips files/directories if they match patterns in `.repoignore`.

    **With Token Count**:

    `python repo_to_flat_file.py --repo /path/to/repo --token`

    -   Also prints an approximate total token count for all discovered text files.
2.  **Manual Scan**

    `python repo_to_flat_file.py --repo /path/to/repo --scan`

    -   Only scans and writes `index.txt`.
    -   Overwrites any existing `index.txt`.

    **With Token Count**:

    `python repo_to_flat_file.py --repo /path/to/repo --scan --token`

    -   Reads file contents to report a total approximate token count.
3.  **Manual Extract**

    `python repo_to_flat_file.py --repo /path/to/repo --extract --files 1,2,7-15`

    -   Requires a valid `index.txt` (from a prior scan).
    -   Extracts file IDs 1, 2, and 7 through 15 into `flat_output.txt`.
    -   Prints an approximate token count for the extracted subset.
4.  **Ignoring Files/Directories**

    -   Create a `.repoignore` in your working directory, or specify `--ignore-file ignore_patterns.txt`.
    -   Each non-comment line is treated as a wildcard pattern (fnmatch).
    -   Example `.repoignore`:

        `*.pyc
        node_modules/
        dist/
        .git`

* * * * *

Example Workflows
-----------------

1.  **Full Flatten**

    `python repo_to_flat_file.py --repo path/to/myrepo`

    -   Outputs `flat_output.txt` with **all** text files.
2.  **Token Count for Entire Repo**

    `python repo_to_flat_file.py --repo path/to/myrepo --scan --token`

    -   Just scans, printing a total approximate token count.
3.  **Selective Extract**

    `python repo_to_flat_file.py --repo path/to/myrepo --extract --files 2,5,10-20`

    -   Uses `index.txt` to produce a `flat_output.txt` with selected IDs.

* * * * *

java_deps_to_flat_file
======================

`java_deps_to_flat_file.py` is a **separate** Python script designed specifically for **Java** repositories. It allows you to:

1.  **Start from a single `.java` file** in your repository.
2.  **Traverse** its import statements (and recursively, the import statements of each referenced file).
3.  **Accumulate** all discovered `.java` files in one dependency graph.
4.  **Ignore** unwanted files or directories using `.repoignore` patterns.
5.  **Optionally** count tokens (`--token`).
6.  **Flatten** everything into a single file (`java_flat_output.txt` by default).

* * * * *

java_deps_to_flat_file.py Features
----------------------------------

-   **Single Entry-Point**: You specify `--start-file src/main/java/org/alliancegenome/curation_api/model/entities/Gene.java`, for instance, and the script will find all imports in that file, plus their imports, etc.
-   **No Duplication**: A BFS or DFS approach ensures each `.java` file is included only **once**, even if multiple files import the same dependency.
-   **Ignore Patterns**: Reads a `.repoignore`-style file to skip certain files or directories (via `fnmatch`).
-   **Token Count** (optional): If `--token` is set, the script sums a rough token count across all discovered `.java` files.
-   **Flat Output**: Writes to a single output file, each file preceded by a header line.

* * * * *

Usage of `java_deps_to_flat_file.py`
------------------------------------

1.  **Basic Command**

    `python java_deps_to_flat_file.py\
        --repo /path/to/java_repo\
        --start-file src/main/java/org/alliancegenome/curation_api/model/entities/Gene.java`

    -   Looks for `.repoignore` by default (or use `--ignore-file`).
    -   Produces `java_flat_output.txt` containing the **full** source code of the starting file and its transitive dependencies (via imports).
2.  **Token Count**

    `python java_deps_to_flat_file.py\
        --repo /path/to/java_repo\
        --start-file src/main/java/org/alliancegenome/curation_api/model/entities/Gene.java\
        --token`

    -   Also prints a total approximate token count for all discovered `.java` files in the chain.
3.  **Custom Output & Ignore File**

    `python java_deps_to_flat_file.py\
        --repo /path/to/java_repo\
        --start-file src/main/java/org/alliancegenome/curation_api/model/entities/Gene.java\
        --output gene_with_deps.txt\
        --ignore-file custom_ignore.txt\
        --token`

    -   Writes all relevant `.java` content to `gene_with_deps.txt`.
    -   Ignores any patterns listed in `custom_ignore.txt`.
    -   Computes approximate tokens.

4.  **Directory Skips**

    -   If your ignore file has an entry like `test/`, any `.java` file in a `test/` directory will be excluded.
    -   The BFS skip is logged with messages like `Skipping file 'test/SomeTest.java' due to ignore pattern 'test/'`.