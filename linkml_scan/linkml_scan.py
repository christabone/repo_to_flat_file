#!/usr/bin/env python3

import json
import sys
from collections import defaultdict, deque

def main():
    """
    Usage:
        python linkml_scan.py <schema_file> <target_def> <out_file>
        
    Example:
        python linkml_scan.py alliance_model.json Gene gene.json
        
    This version does a FORWARD-ONLY traversal: it collects references
    in the direction def_name -> referenced_def, ignoring any definitions
    that merely point back to `target_def`.
    """

    if len(sys.argv) != 4:
        print("Usage: python linkml_scan.py <schema_file> <target_def> <out_file>")
        sys.exit(1)

    schema_file = sys.argv[1]
    target_def = sys.argv[2]
    out_file = sys.argv[3]

    # 1) Load the full schema from JSON
    with open(schema_file, "r", encoding="utf-8") as f:
        full_schema = json.load(f)

    # Ensure we have a top-level $defs
    if "$defs" not in full_schema:
        print("Error: The schema does not have a top-level '$defs' key.")
        sys.exit(1)

    defs_dict = full_schema["$defs"]

    # 2) Build a list of FORWARD edges from $refs.
    #    For each definition that references X, we store (currentDef -> X).
    #    We do NOT add the backward edge (X -> currentDef).
    all_edges = []

    for def_name, def_obj in defs_dict.items():
        # find references in def_obj
        referenced_defs = find_all_refs(def_obj)
        for refd_name in referenced_defs:
            # FORWARD edge only
            all_edges.append((def_name, refd_name))

    # 3) Construct adjacency from all_edges in one pass
    adjacency = defaultdict(set)
    for from_def, to_def in all_edges:
        adjacency[from_def].add(to_def)

    # 4) BFS or DFS from `target_def` to find all connected definitions, forward only
    reachable = set()
    queue = deque([target_def])

    if target_def not in defs_dict:
        print(f"Warning: '{target_def}' not found in $defs, but continuing BFS anyway.")

    while queue:
        current = queue.popleft()
        if current in reachable:
            continue
        reachable.add(current)
        for neighbor in adjacency[current]:
            if neighbor not in reachable:
                queue.append(neighbor)

    # 5) Build a new $defs containing only the reachable definitions
    new_defs = {}
    for def_name in reachable:
        if def_name in defs_dict:
            new_defs[def_name] = defs_dict[def_name]

    # 6) Replace the original $defs with our truncated version.
    minimized_schema = {}
    for k, v in full_schema.items():
        if k == "$defs":
            minimized_schema["$defs"] = new_defs
        else:
            minimized_schema[k] = v

    # 7) Prune references that point to definitions not in `reachable`.
    for def_name in list(new_defs.keys()):
        new_defs[def_name] = prune_refs(new_defs[def_name], reachable)

    # 8) Write final minimized schema to out_file
    with open(out_file, "w", encoding="utf-8") as out_f:
        json.dump(minimized_schema, out_f, indent=2)

    print(f"Done. Wrote minimized schema with {len(new_defs)} definitions to '{out_file}'.")


def find_all_refs(schema_fragment):
    """
    Recursively scan 'schema_fragment' (which can be dict, list, or primitive)
    for local references of the form:
        { "$ref": "#/$defs/SomeDefName" }
    Returns a set of all 'SomeDefName' that appear in $ref fields.
    """
    results = set()

    if isinstance(schema_fragment, dict):
        # if there's a "$ref", parse it
        if "$ref" in schema_fragment:
            ref_str = schema_fragment["$ref"]
            # We'll parse out the definition name from something like "#/$defs/XYZ"
            def_name = extract_def_name(ref_str)
            if def_name:
                results.add(def_name)

        # then recurse into values
        for value in schema_fragment.values():
            results |= find_all_refs(value)

    elif isinstance(schema_fragment, list):
        # recurse into list elements
        for item in schema_fragment:
            results |= find_all_refs(item)

    # if it's a primitive (string, int, etc.), no references
    return results


def extract_def_name(ref_str):
    """
    If ref_str is "#/$defs/XYZ", return "XYZ".
    Otherwise return None.
    """
    prefix = "#/$defs/"
    if isinstance(ref_str, str) and ref_str.startswith(prefix):
        return ref_str[len(prefix):]
    return None


def prune_refs(schema_fragment, keep_set):
    """
    Return a copy of schema_fragment (dict/list/primitive),
    removing or modifying any $ref that points to a definition *not* in keep_set.
    We'll replace them with "#/$defs/REMOVED_REFERENCE" so it's visible
    but no longer points to anything invalid.
    """

    if isinstance(schema_fragment, dict):
        new_frag = {}
        for k, v in schema_fragment.items():
            if k == "$ref":
                def_name = extract_def_name(v)
                if def_name and def_name not in keep_set:
                    # references a def we are not keeping => replace
                    new_frag[k] = "#/$defs/REMOVED_REFERENCE"
                else:
                    # keep as-is
                    new_frag[k] = v
            else:
                new_frag[k] = prune_refs(v, keep_set)
        return new_frag

    elif isinstance(schema_fragment, list):
        new_list = []
        for item in schema_fragment:
            new_list.append(prune_refs(item, keep_set))
        return new_list

    else:
        # primitive
        return schema_fragment


if __name__ == "__main__":
    main()
