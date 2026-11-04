# -*- coding: utf-8 -*-
"""One stable interface for setup, generation, validation, and regression."""

import argparse
import importlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path


TOOLKIT = Path(__file__).resolve().parent
ROOT = TOOLKIT.parent
OUT = ROOT / "out"
EXAMPLES = ROOT / "examples"
MANIFEST = EXAMPLES / ".render-manifest.json"
SCHEMA_OK = re.compile(r"^\s*schema: VALID \(v\d+\)\s*$", re.M)
PNG_RE = re.compile(r"^\s*png: (preview_[^\s()]+\.png) \(", re.M)
OUTPUT_RE = re.compile(
    r'(?:out_proj|OUT_PROJ|OUT)\s*=\s*os\.path\.join\(\s*(?:OUT|ROOT),\s*'
    r'["\']([^"\']+\.icproj\.json)["\']',
    re.S,
)
# A generator that writes more than one project (one per command-line mode)
# lists them explicitly, one line each:  `# output: <file> [arg ...]`
DECLARED_RE = re.compile(r'(?m)^#\s*output:\s*(\S+\.icproj\.json)((?:[ \t]+\S+)*)'
                         r'[ \t]*$')


@dataclass(frozen=True)
class Project:
    generator: Path
    output: Path
    args: tuple = ()

    @property
    def name(self):
        return self.generator.stem + "".join(":" + a for a in self.args)

    @property
    def command(self):
        return [self.generator] + list(self.args)


def discover_projects(toolkit=TOOLKIT, out=OUT):
    """Discover generator/output pairs without importing side-effect scripts."""
    projects = []
    for generator in sorted(Path(toolkit).glob("gen_*.py")):
        text = generator.read_text(encoding="utf-8")
        declared = DECLARED_RE.findall(text)
        if declared:
            for output, args in declared:
                projects.append(Project(generator, Path(out) / output,
                                        tuple(args.split())))
            continue
        matches = OUTPUT_RE.findall(text)
        if len(matches) != 1:
            raise RuntimeError("%s declares %d outputs; expected exactly one"
                               % (generator.name, len(matches)))
        projects.append(Project(generator, Path(out) / matches[0]))
    return projects


def resolve_projects(selectors, projects):
    if selectors == ["all"]:
        return projects
    by_key = {}
    for project in projects:
        # `Path.stem` drops only `.json`: "X.icproj.json" -> "X.icproj", so
        # the bare name the README tells people to type never matched
        bare = project.output.name[:-len(".icproj.json")] \
            if project.output.name.endswith(".icproj.json") \
            else project.output.stem
        for key in (project.name, project.generator.stem,
                    project.output.name, project.output.stem, bare):
            by_key.setdefault(key.lower(), [])
            if project not in by_key[key.lower()]:
                by_key[key.lower()].append(project)
    selected = []
    for selector in selectors:
        matched = by_key.get(selector.lower())
        if not matched:
            raise SystemExit("unknown generator/output %r; run `python -m "
                             "toolkit list`" % selector)
        for project in matched:
            if project not in selected:
                selected.append(project)
    return selected


def run(args, cwd=ROOT, env=None):
    return subprocess.run([str(arg) for arg in args], cwd=str(cwd), env=env,
                          text=True, encoding="utf-8", errors="replace")


def captured(args, cwd=ROOT, env=None):
    return subprocess.run([str(arg) for arg in args], cwd=str(cwd), env=env,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=180)


def command_doctor(_args):
    checks = []

    def add(name, ok, detail):
        checks.append(ok)
        print("%s %-18s %s" % ("OK" if ok else "MISSING", name, detail))

    add("Python", sys.version_info >= (3, 8), sys.version.split()[0])
    node = shutil.which("node")
    if node:
        result = captured([node, "--version"])
        version = (result.stdout or result.stderr).strip()
        major = int(version.lstrip("v").split(".")[0]) if version else 0
        add("Node.js", result.returncode == 0 and major >= 18, version)
    else:
        add("Node.js", False, "18+ required")
    for module, label in (("numpy", "NumPy"), ("PIL", "Pillow")):
        try:
            imported = importlib.import_module(module)
            add(label, True, getattr(imported, "__version__", "installed"))
        except ImportError:
            add(label, False, "install with requirements.txt")
    symbols = list((TOOLKIT / "sym").glob("*.json"))
    add("symbol cache", bool(symbols), "%d files" % len(symbols))
    add("model", (TOOLKIT / "model.mjs").is_file(),
        "run `python -m toolkit setup`" if not (TOOLKIT / "model.mjs").is_file()
        else "downloaded")
    add("model adapter", (TOOLKIT / "model-adapter.mjs").is_file(),
        "generated" if (TOOLKIT / "model-adapter.mjs").is_file()
        else "run `python -m toolkit setup`")

    chrome = os.environ.get("CHROME_PATH") or next(
        (shutil.which(name) for name in ("google-chrome", "chromium", "chrome")
         if shutil.which(name)), None)
    if not chrome and os.name == "nt":
        known = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        chrome = str(known) if known.is_file() else None
    print("%s %-18s %s" % ("OK" if chrome else "OPTIONAL", "Chrome",
                           chrome or "set CHROME_PATH, or use --no-render"))
    return 0 if all(checks) else 1


def command_setup(_args):
    for script in ("fetch_symbols.py", "refresh_model.py"):
        result = run([sys.executable, TOOLKIT / script])
        if result.returncode:
            return result.returncode
    return command_doctor(_args)


def command_list(_args):
    projects = discover_projects()
    width = max(len(project.name) for project in projects)
    for project in projects:
        print("%-*s  %s" % (width, project.name, project.output.name))
    print("\n%d generators -> %d projects, %d tracked project outputs" %
          (len({project.generator for project in projects}), len(projects),
           len(list(OUT.glob("*.icproj.json")))))
    return 0


def required_assets():
    missing = []
    if not list((TOOLKIT / "sym").glob("*.json")):
        missing.append("sym")
    for path in (TOOLKIT / "model.mjs", TOOLKIT / "model-adapter.mjs"):
        if not path.is_file():
            missing.append(path.name)
    if missing:
        raise SystemExit("missing %s; run `python -m toolkit setup` first"
                         % ", ".join(missing))


def publish_example(project, stdout, manifest):
    """Refresh examples/<output stem>.png from the preview build() rendered.

    Only gallery images that already exist are refreshed.  Chrome's PNG is
    not byte-stable, so the manifest keeps the SHA-256 of the SOURCE SVG and
    the PNG is copied only when that SVG really changed.
    """
    import hashlib
    target = EXAMPLES / (project.output.name[:-len(".icproj.json")] + ".png")
    match = PNG_RE.search(stdout or "")
    if not target.is_file() or not match:
        return None
    png = TOOLKIT / match.group(1)
    svg = png.with_suffix(".svg")
    if not png.is_file() or not svg.is_file():
        return None
    digest = hashlib.sha256(svg.read_bytes()).hexdigest()
    if manifest.get(target.name) == digest:
        return False
    shutil.copyfile(str(png), str(target))
    manifest[target.name] = digest
    return True


def command_generate(args):
    import json
    required_assets()
    projects = resolve_projects(args.projects, discover_projects())
    env = os.environ.copy()
    if args.no_render:
        env["AC_NO_RENDER"] = "1"
    if args.examples and args.no_render:
        raise SystemExit("--examples needs the Chrome render; drop --no-render")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) \
        if args.examples and MANIFEST.is_file() else {}
    published = []
    failures = []
    for index, project in enumerate(projects, 1):
        print("\n[%d/%d] %s" % (index, len(projects), project.name),
              flush=True)
        previous = project.output.read_bytes() if project.output.is_file() else None
        result = subprocess.run(
            [str(a) for a in [sys.executable] + project.command],
            cwd=str(ROOT), env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            errors="replace")
        print(result.stdout, end="", flush=True)
        validation = None
        if result.returncode == 0 and project.output.is_file():
            # build() already ran the site's schema on the staged file and
            # only then replaced the output; its own report says so.  Ask
            # node again only when it did not (AC_FAST, a script that does
            # not go through build()) -- a second node start per figure was
            # a quarter of `generate all`.
            if SCHEMA_OK.search(result.stdout or ""):
                validation = subprocess.CompletedProcess([], 0, "", "")
            else:
                validation = validate_file(project.output)
        if result.returncode or validation is None or validation.returncode:
            # Shared generators already write atomically.  This restoration is
            # the fail-closed adapter for the two standalone legacy scripts.
            if previous is None:
                if project.output.exists():
                    project.output.unlink()
            else:
                restore = project.output.with_suffix(project.output.suffix + ".restore")
                restore.write_bytes(previous)
                os.replace(str(restore), str(project.output))
            if validation is not None and validation.returncode:
                print((validation.stdout + validation.stderr).strip())
            failures.append(project.name)
        elif args.examples and publish_example(project, result.stdout,
                                               manifest):
            published.append(project.name)
    if args.examples:
        with open(str(MANIFEST), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(manifest, indent=1, sort_keys=True,
                                ensure_ascii=False) + "\n")
        print("\nexamples: %d PNG(s) refreshed" % len(published))
    if failures:
        print("\nFAILED: " + ", ".join(failures))
        return 1
    print("\nGenerated %d project(s)." % len(projects))
    return 0


def validate_file(project_file, toolkit=TOOLKIT):
    return captured(["node", Path(toolkit) / "validate.mjs", project_file],
                    cwd=Path(toolkit).parent)


def command_validate(args):
    required_assets()
    files = [Path(value).resolve() for value in args.files] if args.files \
        else sorted(OUT.glob("*.icproj.json"))
    failed = []
    for path in files:
        result = validate_file(path)
        if result.returncode == 0:
            print("OK   %s" % path.name)
        else:
            print("FAIL %s\n%s" % (path.name,
                                    (result.stdout + result.stderr).strip()))
            failed.append(path)
    print("\n%d valid, %d failed" % (len(files) - len(failed), len(failed)))
    return 1 if failed else 0


def command_regress(args):
    """Build every generator in isolation and compare with tracked outputs."""
    required_assets()
    projects = discover_projects()
    with tempfile.TemporaryDirectory(prefix="analog-canvas-regress-") as tmp:
        temp_root = Path(tmp)
        temp_toolkit = temp_root / "toolkit"
        temp_out = temp_root / "out"
        shutil.copytree(TOOLKIT, temp_toolkit, ignore=shutil.ignore_patterns(
            "__pycache__", "preview_*.svg", "preview_*.png"))
        shutil.copytree(OUT, temp_out)

        env = os.environ.copy()
        env["AC_NO_RENDER"] = "1"

        def build(project):
            generated = temp_out / project.output.name
            if generated.exists():
                generated.unlink()
            result = captured([sys.executable, temp_toolkit / project.generator.name]
                              + list(project.args), cwd=temp_root, env=env)
            return project, generated, result

        results = []
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = [executor.submit(build, project) for project in projects]
            for future in as_completed(futures):
                results.append(future.result())

        failures = []
        changed = []
        for project, generated, result in sorted(results,
                                                  key=lambda item: item[0].name):
            if result.returncode or not generated.is_file():
                failures.append(project.name)
                log = ((result.stdout or "") + (result.stderr or "")).splitlines()
                print("FAIL %-28s\n  %s" %
                      (project.name, "\n  ".join(log[-18:])))
                continue
            # build() validated the staged file already and said so
            validation = (subprocess.CompletedProcess([], 0, "", "")
                          if SCHEMA_OK.search(result.stdout or "")
                          else validate_file(generated, temp_toolkit))
            if validation.returncode:
                failures.append(project.name)
                print("FAIL %-28s schema\n%s" %
                      (project.name, validation.stdout + validation.stderr))
                continue
            if not project.output.is_file() \
                    or generated.read_bytes() != project.output.read_bytes():
                changed.append(project.name)
                print("DIFF %-28s %s" % (project.name, project.output.name))
            else:
                print("OK   %s" % project.name)

    if failures:
        print("\n%d generator(s) failed: %s" %
              (len(failures), ", ".join(failures)))
    if changed:
        print("\n%d output(s) are stale: %s\nRun `python -m toolkit generate "
              "all --no-render` and commit the results."
              % (len(changed), ", ".join(changed)))
    if not failures and not changed:
        print("\nRegression clean: %d generators are deterministic and valid."
              % len(projects))
    return 1 if failures or changed else 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="python -m toolkit",
        description="Generate and verify Analog Canvas project files.")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="check runtimes, dependencies, and caches")
    commands.add_parser("setup", help="download symbols and the live schema")
    commands.add_parser("list", help="list built-in generators and outputs")

    generate = commands.add_parser("generate", help="run one generator or all")
    generate.add_argument("projects", nargs="+",
                          help="generator name, output name, or `all`")
    generate.add_argument("--no-render", action="store_true",
                          help="skip the optional Chrome PNG render")
    generate.add_argument("--examples", action="store_true",
                          help="also refresh the gallery PNGs in examples/ "
                               "whose source SVG changed")

    validate = commands.add_parser("validate", help="validate output files")
    validate.add_argument("files", nargs="*", help="defaults to every out/*.json")

    regress = commands.add_parser(
        "regress", help="rebuild in a temporary directory and compare outputs")
    regress.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1),
                         help="parallel generator count (default: %(default)s)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    commands = {
        "doctor": command_doctor, "setup": command_setup,
        "list": command_list, "generate": command_generate,
        "validate": command_validate, "regress": command_regress,
    }
    try:
        code = commands[args.command](args)
    except KeyboardInterrupt:
        code = 130
    raise SystemExit(code)


if __name__ == "__main__":
    main()
