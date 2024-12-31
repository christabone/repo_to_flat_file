Java Dependency Scanner
=======================

**Java Dependency Scanner** is a Python script for discovering and collecting Java file dependencies within a repository. It parses imports from specified Java files and recursively expands those imports---up to a configurable maximum depth---so that you can gather a single, comprehensive set of Java source code files. It also optionally outputs a combined, flat file with all discovered code.

Features
--------

1.  **Multiple entry points**\
    Provide a list of initial Java files in your YAML configuration. The script will parse imports and build a dependency chain from each file.

2.  **Depth-limited BFS**\
    Control how many "levels" of imports to follow---`0`, `1`, `2`, or `"all"` (unlimited).

3.  **Ignore patterns**\
    Respect optional `.repoignore` or other ignore file patterns (in `fnmatch` style).

4.  **Approximate token counting**\
    If desired, see a rough estimate of the total tokens across discovered files.

5.  **Flat output**\
    Combine the discovered Java source code into a single file, each preceded by a descriptive header.

Requirements
------------

-   **Python 3.6+**
-   **PyYAML** (for reading the YAML config)
-   **chardet** (for file encoding detection)

`pip install pyyaml chardet`

Quick Start
-----------

1.  **Clone your repository** (the one containing the Java source):

    `git clone https://github.com/YourUser/YourJavaRepo.git`

2.  **Place the script** (e.g., `java_deps_from_yaml.py`) and your YAML config file (`config_file.yaml`) at an appropriate location.

3.  **Edit your YAML config** to specify:

    -   `repo`: The absolute or relative path to your repo root
    -   `java_source_root`: Usually `src/main/java`, or wherever your .java files live
    -   `ignore_file`: File containing patterns to exclude
    -   `token_count`: `true` or `false` to enable/disable approximate token count
    -   `output`: File path for the combined output
    -   `depth`: An integer (0, 1, 2, ...) or `"all"` for unlimited
    -   `files`: A list of Java files (relative to `repo`) to start scanning from

    Example YAML:

    `repo: "/home/user/workspace/YourJavaRepo"
    java_source_root: "src/main/java"
    ignore_file: ".repoignore"
    token_count: true
    output: "java_flat_output.txt"
    depth: 1
    files:
      - "src/main/java/org/example/dao/FooDAO.java"
      - "src/main/java/org/example/model/Foo.java"`

4.  **Run the script**:

    `python java_deps_from_yaml.py config_file.yaml`

    -   If everything goes well, it should discover all relevant imports (up to the specified depth).
    -   It then writes a single merged file containing all discovered sources to the `output` path in your config.

Command-Line Usage
------------------

`python java_deps_from_yaml.py <config_file.yaml>`

-   `<config_file.yaml>` is a required argument pointing to your YAML configuration file.

Configuration Details
---------------------

In your YAML file:

-   **`repo`** (string)\
    Path to your repository root directory.

-   **`java_source_root`** (string, optional)\
    Defaults to `src/main/java`. The subdirectory under `repo` that typically contains `.java` files.

-   **`ignore_file`** (string, optional)\
    Defaults to `.repoignore`. A text file listing patterns (one per line) to exclude. Patterns follow `fnmatch` rules (like `**/Test*`, `*.jar`, etc.).

-   **`token_count`** (boolean, optional)\
    If `true`, the script estimates the total tokens across discovered files.

-   **`output`** (string, optional)\
    Defaults to `java_flat_output.txt`. The file path for writing combined Java code.

-   **`depth`** (integer or `"all"`, optional)\
    Limits how many "import-levels" of scanning to perform. If set to `1`, the script only expands each starting file's imports once. If `"all"`, unlimited.

-   **`files`** (list, **required**)\
    A list of Java files (relative to `repo`) to begin scanning from. Must be valid paths. If missing or empty, the script aborts.

Example `.repoignore`
---------------------

`# Comments and blank lines are ignored
**/test/**
**/tests/**
**/some/large/dir/*
*.jar
*.class`

Output Explanation
------------------

1.  **On the command line**:

    -   The script logs discovered files, "already processed" messages, or "skipping" lines if ignoring.
    -   It also displays final stats on how many Java files were found and a token count (if enabled).
2.  **In the output file**:

    -   Each discovered file's content is preceded by a header line:

        `===== FILE: path/relative/to/repo =====`

        This helps keep track of which file contributed each block of code.

Advanced Notes
--------------

-   To reduce the dependency chain, set a smaller `depth`. For example, `depth: 0` means only scan the starting files themselves---no imports.
-   You can pass multiple starting files in the `files:` list, and the script will unify dependencies from all of them (avoiding duplicates).
-   The approximate token count is a rough heuristic (word count * 1.2).

Contributing
------------

1.  **Fork** this repository.
2.  Create a **feature branch**.
3.  **Commit** your changes.
4.  **Open a Pull Request**.

We welcome bug reports, suggestions, or contributions.

License
-------

This project is available under the MIT License. Feel free to use it in your own projects!

* * * * *