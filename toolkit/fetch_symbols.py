# -*- coding: utf-8 -*-
"""fetch_symbols.py — sync toolkit/sym/ with the editor's runtime symbol library.

    python fetch_symbols.py            # write missing symbols, report changed ones
    python fetch_symbols.py --force    # overwrite every symbol with upstream
    python fetch_symbols.py --check    # list missing/changed/extra, write nothing

Since schema v58 upstream no longer ships one ``<id>.symbol.json`` asset per
symbol.  The runtime library is assembled in
``packages/symbols/src/builtins.ts``::

    builtInSymbols = [...razaviLibrarySymbols, ...expandedDeviceSymbols]

* ``razaviLibrarySymbols`` = the array ``razaviCatalogSymbols`` in
  ``razavi-catalog.generated.ts``, ordered and filtered by
  ``razaviSymbolCatalogEntries`` with the predicate of
  ``isRazaviLibraryCatalogEntry`` (razavi-catalog.ts): reviewStatus is
  "reviewed" and (provenance "house" ? no visualAuthority :
  visualAuthority.kind == "razavi-reference-v1").
* ``expandedDeviceSymbols`` = ``expandedComponentSymbols`` in
  ``expanded-components.generated.ts``.

Both are TypeScript source files.  We never execute downloaded code: a small
tokenizer below reads the two array literals (bare keys, trailing commas,
comments) into plain Python values and raises on anything that is not a
literal (identifiers, spreads, template strings, calls ...).  Each symbol is
stored as ``sym/<id>.json`` in the same format as before (json indent=1,
ensure_ascii=False, trailing newline, LF), which is what ``icproj.sym()``
reads.

Treat ``sym/`` as a cache of upstream: rerun this whenever the editor changes.
"""
import io, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SYMDIR = os.path.join(HERE, "sym")
REPO = "cascode-ai/analog-canvas"
BRANCH = "main"
SRC = "packages/symbols/src/"
RAZAVI = SRC + "razavi-catalog.generated.ts"
EXPANDED = SRC + "expanded-components.generated.ts"
RAW = "https://raw.githubusercontent.com/%s/%s/" % (REPO, BRANCH)


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "analog-canvas-toolkit"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


# ---------------------------------------------------------------- tokenizer
class LiteralError(ValueError):
    pass


_TOKEN = re.compile(r'''
    (?P<ws>\s+)
  | (?P<lcomment>//[^\n]*)
  | (?P<bcomment>/\*.*?\*/)
  | (?P<num>-?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<str>"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')
  | (?P<ident>[A-Za-z_$][A-Za-z0-9_$]*)
  | (?P<punct>[\[\]{}:,])
''', re.S | re.X)

_ESC = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v",
        "0": "\0", "\\": "\\", "'": "'", '"': '"', "/": "/", "\n": ""}


def _unquote(s):
    body, out, i = s[1:-1], [], 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        n = body[i + 1]
        if n == "u":
            if body[i + 2] == "{":
                j = body.index("}", i)
                out.append(chr(int(body[i + 3:j], 16)))
                i = j + 1
            else:
                out.append(chr(int(body[i + 2:i + 6], 16)))
                i += 6
            continue
        if n == "x":
            out.append(chr(int(body[i + 2:i + 4], 16)))
            i += 4
            continue
        if n not in _ESC:
            raise LiteralError("unsupported escape \\%s" % n)
        out.append(_ESC[n])
        i += 2
    s = "".join(out)
    # JS strings are UTF-16: re-pair surrogates written as two \\u escapes
    return s.encode("utf-16", "surrogatepass").decode("utf-16")


def tokens(text, pos):
    """Yield (kind, value, offset) from ``pos`` on, skipping blanks/comments."""
    n = len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            raise LiteralError("unexpected %r at offset %d"
                               % (text[pos:pos + 20], pos))
        kind = m.lastgroup
        if kind not in ("ws", "lcomment", "bcomment"):
            yield kind, m.group(), pos
        pos = m.end()


def parse_literal(text, pos):
    """Parse one JS literal starting at ``pos``; return (value, end_offset)."""
    it = tokens(text, pos)
    look = []

    def nxt():
        if look:
            return look.pop()
        try:
            return next(it)
        except StopIteration:
            raise LiteralError("unexpected end of input")

    def value(tok):
        kind, v, at = tok
        if kind == "num":
            return float(v) if re.search(r"[.eE]", v) else int(v)
        if kind == "str":
            return _unquote(v)
        if kind == "ident":
            if v in ("true", "false", "null"):
                return {"true": True, "false": False, "null": None}[v]
            raise LiteralError("non-literal identifier %r at offset %d" % (v, at))
        if v == "[":
            out = []
            while True:
                t = nxt()
                if t[1] == "]":
                    return out
                out.append(value(t))
                t = nxt()
                if t[1] == "]":
                    return out
                if t[1] != ",":
                    raise LiteralError("expected , or ] at offset %d" % t[2])
        if v == "{":
            out = {}
            while True:
                t = nxt()
                if t[1] == "}":
                    return out
                if t[0] == "ident":
                    key = t[1]
                elif t[0] == "str":
                    key = _unquote(t[1])
                elif t[0] == "num":
                    key = t[1]
                else:
                    raise LiteralError("bad key %r at offset %d" % (t[1], t[2]))
                c = nxt()
                if c[1] != ":":     # shorthand {a} / methods / spreads
                    raise LiteralError("expected : after key %r at offset %d"
                                       % (key, c[2]))
                if key in out:
                    raise LiteralError("duplicate key %r at offset %d" % (key, t[2]))
                out[key] = value(nxt())
                t = nxt()
                if t[1] == "}":
                    return out
                if t[1] != ",":
                    raise LiteralError("expected , or } at offset %d" % t[2])
        raise LiteralError("unexpected %r at offset %d" % (v, at))

    first = nxt()
    v = value(first)
    # end offset: scan to the closing bracket we just consumed
    end = _skip_value(text, first[2])
    return v, end


def _skip_value(text, pos):
    depth = 0
    for kind, v, at in tokens(text, pos):
        if v in "[{" and kind == "punct":
            depth += 1
        elif v in "]}" and kind == "punct":
            depth -= 1
        if depth == 0:
            return at + len(v)
    raise LiteralError("unterminated literal")


def exported_array(src, name):
    """The literal assigned by ``export const <name>: T = [...] (as const);``."""
    m = re.search(r"export\s+const\s+%s\b[^=]*=" % re.escape(name), src)
    if not m:
        raise LiteralError("export %s not found" % name)
    val, end = parse_literal(src, m.end())
    tail = src[end:end + 40]
    if not re.match(r"\s*(?:as\s+const\s*)?;", tail):
        raise LiteralError("%s: literal not followed by ';' (%r) -- not a "
                           "plain literal?" % (name, tail))
    if not isinstance(val, list):
        raise LiteralError("%s is not an array" % name)
    return val


# ------------------------------------------------------------- the library
def is_library_entry(e):
    """Port of isRazaviLibraryCatalogEntry (razavi-catalog.ts)."""
    if e.get("reviewStatus") != "reviewed":
        return False
    if e.get("provenance") == "house":
        return e.get("visualAuthority") is None
    return (e.get("visualAuthority") or {}).get("kind") == "razavi-reference-v1"


def builtin_symbols(razavi_src, expanded_src):
    """Port of builtins.ts: [...razaviLibrarySymbols, ...expandedDeviceSymbols]."""
    syms = {s["id"]: s for s in exported_array(razavi_src, "razaviCatalogSymbols")}
    entries = exported_array(razavi_src, "razaviSymbolCatalogEntries")
    lib = [syms[e["symbolId"]] for e in entries
           if is_library_entry(e) and e["symbolId"] in syms]
    lib += exported_array(expanded_src, "expandedComponentSymbols")
    seen = set()
    for s in lib:
        if not (s.get("id") and "pins" in s and "primitives" in s):
            raise LiteralError("not a symbol: %r" % s.get("id"))
        if s["id"] in seen:
            raise LiteralError("duplicate symbol id %s" % s["id"])
        seen.add(s["id"])
    return lib


def dump(sym):
    return json.dumps(sym, ensure_ascii=False, indent=1) + "\n"


def main(argv=()):
    force, check = "--force" in argv, "--check" in argv
    lib = builtin_symbols(get(RAW + RAZAVI), get(RAW + EXPANDED))
    if not os.path.isdir(SYMDIR) and not check:
        os.makedirs(SYMDIR)
    have = {f[:-5] for f in os.listdir(SYMDIR) if f.endswith(".json")} \
        if os.path.isdir(SYMDIR) else set()
    missing, changed, same = [], [], 0
    for s in lib:
        text = dump(s)
        path = os.path.join(SYMDIR, s["id"] + ".json")
        if s["id"] not in have:
            missing.append(s["id"])
        else:
            with io.open(path, encoding="utf-8") as f:
                if f.read() == text:
                    same += 1
                    continue
            changed.append(s["id"])
        write = not check and (s["id"] in missing or force)
        if write:
            with io.open(path + ".tmp", "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            os.replace(path + ".tmp", path)
    extra = sorted(have - {s["id"] for s in lib})
    print("upstream %d symbols, local %d: %d identical, %d missing, %d changed, "
          "%d not upstream" % (len(lib), len(have), same, len(missing),
                               len(changed), len(extra)))
    for label, ids in (("missing", missing), ("changed", changed),
                       ("not upstream", extra)):
        if ids:
            print("  %-12s %s" % (label + ":", ", ".join(ids)))
    if check:
        print("  (--check: nothing written)")
        return 1 if missing or changed else 0
    print("  wrote %d (%s)" % (len(missing) + (len(changed) if force else 0),
                               "missing + changed" if force else "missing only"))
    if changed and not force:
        print("  ! %d local symbol(s) differ from upstream; rerun with --force "
              "to overwrite" % len(changed))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
