import sys
import re
import shutil
import argparse
from xml.etree import ElementTree as ET

SVG_PATH = sys.argv[1] if len(sys.argv) > 1 else r"c:\data\todd\thproj\hackshop\3d_print\puzzles\3d-cylinder\gruenberg\part_4\images\fish1.pattern2.svg"

# token regex matches single letters (commands) or numbers
token_re = re.compile(r"[a-zA-Z]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?")

def find_path_elements(svgfile):
    tree = ET.parse(svgfile)
    root = tree.getroot()
    paths = []
    for el in root.iter():
        if el.tag.lower().endswith('path'):
            d = el.get('d')
            if d is not None:
                paths.append(el)
    return tree, paths

def nearly_equal(a, b, eps=1e-9):
    return abs(a - b) <= eps

def clean_d(d):
    tokens = token_re.findall(d)
    out_tokens = []
    prev_pair = None
    pending = None
    # iterate tokens preserving command letters; for numeric tokens, form pairs
    for t in tokens:
        if re.fullmatch(r'[a-zA-Z]', t):
            # flush any pending single number
            if pending is not None:
                out_tokens.append(pending)
                pending = None
            out_tokens.append(t)
            continue
        # numeric token
        if pending is None:
            pending = t
        else:
            # form a candidate pair
            try:
                pair = (float(pending), float(t))
            except Exception:
                # fallback: keep both
                out_tokens.append(pending)
                out_tokens.append(t)
                pending = None
                prev_pair = None
                continue
            if prev_pair is not None and nearly_equal(prev_pair[0], pair[0]) and nearly_equal(prev_pair[1], pair[1]):
                # skip this duplicate pair
                pending = None
                # prev_pair remains the same
            else:
                out_tokens.append(pending)
                out_tokens.append(t)
                prev_pair = pair
                pending = None
    if pending is not None:
        out_tokens.append(pending)

    # Rebuild d string: join tokens with spaces, but keep letters adjacent to numbers with a space
    # This will normalize spacing but preserve commands and numeric sequence
    cleaned = []
    for tok in out_tokens:
        if cleaned:
            cleaned.append(' ')
        cleaned.append(tok)
    return ''.join(cleaned)
def find_duplicates_in_d(d):
    tokens = token_re.findall(d)
    duplicates = []
    prev_pair = None
    pending = None
    pair_index = 0
    for i, t in enumerate(tokens):
        if re.fullmatch(r'[a-zA-Z]', t):
            continue
        if pending is None:
            pending = t
        else:
            try:
                pair = (float(pending), float(t))
            except Exception:
                pending = None
                pair_index += 1
                continue
            pair_index += 1
            if prev_pair is not None and nearly_equal(prev_pair[0], pair[0]) and nearly_equal(prev_pair[1], pair[1]):
                duplicates.append({'pair_index': pair_index, 'coords': pair, 'token_pos': (i-1, i)})
            prev_pair = pair
            pending = None
    return duplicates


def list_mode(svgfile):
    tree, path_els = find_path_elements(svgfile)
    found = {}
    for el in path_els:
        pid = el.get('id') or '<no-id>'
        d = el.get('d')
        dups = find_duplicates_in_d(d)
        if dups:
            entries = []
            for idx, rec in enumerate(dups, start=1):
                label = f"{pid}@{idx}"
                entries.append({'label': label, 'pair_index': rec['pair_index'], 'coords': rec['coords']})
                print(f"{label}: pair_index={rec['pair_index']}, coords={rec['coords']}")
            found[pid] = entries
        else:
            print(f"Path id={pid}: no adjacent duplicate points")
    return found


def remove_mode(svgfile, labels_to_remove, output=None):
    tree, path_els = find_path_elements(svgfile)
    any_removed = False
    for el in path_els:
        pid = el.get('id') or '<no-id>'
        d = el.get('d')
        tokens = token_re.findall(d)
        out_tokens = []
        prev_pair = None
        pending = None
        dup_count = 0
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if re.fullmatch(r'[a-zA-Z]', t):
                if pending is not None:
                    out_tokens.append(pending)
                    pending = None
                out_tokens.append(t)
                i += 1
                continue
            if pending is None:
                pending = t
                i += 1
                continue
            try:
                pair = (float(pending), float(tokens[i]))
            except Exception:
                out_tokens.append(pending)
                out_tokens.append(tokens[i])
                pending = None
                prev_pair = None
                i += 1
                continue
            if prev_pair is not None and nearly_equal(prev_pair[0], pair[0]) and nearly_equal(prev_pair[1], pair[1]):
                dup_count += 1
                label = f"{pid}@{dup_count}"
                if label in labels_to_remove:
                    any_removed = True
                    pending = None
                    i += 1
                else:
                    out_tokens.append(pending)
                    out_tokens.append(tokens[i])
                    prev_pair = pair
                    pending = None
                    i += 1
            else:
                out_tokens.append(pending)
                out_tokens.append(tokens[i])
                prev_pair = pair
                pending = None
                i += 1
        if pending is not None:
            out_tokens.append(pending)

        if any_removed:
            cleaned = []
            for tok in out_tokens:
                if cleaned:
                    cleaned.append(' ')
                cleaned.append(tok)
            newd = ''.join(cleaned)
            if newd != d:
                el.set('d', newd)

    if any_removed:
        if output:
            # write to specified output path
            tree.write(output, encoding='utf-8', xml_declaration=True)
            print(f"Removed specified duplicates and wrote cleaned SVG to {output}")
        else:
            # overwrite original, but keep a backup
            bak = svgfile + '.bak2'
            shutil.copy2(svgfile, bak)
            tree.write(svgfile, encoding='utf-8', xml_declaration=True)
            print(f"Removed specified duplicates and wrote cleaned SVG (backup at {bak})")
        return 0
    else:
        print("No specified duplicates removed")
        return 1

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Find and selectively remove adjacent duplicate path coordinate pairs in an SVG')
    parser.add_argument('file', nargs='?', default=SVG_PATH, help='SVG file to process (default: built-in path)')
    parser.add_argument('--list', action='store_true', help='List adjacent duplicate instances (labels like pathId@N)')
    parser.add_argument('--remove', '-r', help='Comma-separated labels to remove, e.g. path1-1@1,path1-1@3')
    parser.add_argument('-o', '--output', help='Output file for removals (if omitted, input is overwritten with a backup)')

    args = parser.parse_args()

    svgfile = args.file
    if args.list:
        list_mode(svgfile)
        sys.exit(0)

    if args.remove:
        labels = [s.strip() for s in args.remove.split(',') if s.strip()]
        rc = remove_mode(svgfile, set(labels), output=args.output)
        sys.exit(rc)

    # default: list
    list_mode(svgfile)
    sys.exit(0)
