"""Distraction-free file writer for SigmaOS-file-writer (inspired by omawrite).

Principles: a tiny document model (open/write/stats), atomic saves, focus
statistics as a pure function, an autosave plan computed from an injected clock
(deterministic tests), fail-fast on disallowed extensions and bad intervals.
"""
import argparse, math, os, re, sys, tempfile, time

ENGINE = {
    "name": "sigma-writer",
    "summary": "Distraction-free writer: open, write, focus stats, autosave",
    "language": "python",
    "verbs": ["open", "write", "focus-stats", "autosave-plan"],
    "principles": ["KISS", "Least Astonishment", "Fail-Fast",
                   "Separation of Concerns", "Defensive Programming",
                   "Deterministic Testing"],
}

cli_doc = """\
$ sigma-writer open notes.txt
$ sigma-writer write notes.txt --text "hello world"
$ sigma-writer focus-stats --text "one two three"
words=3 chars=13 paragraphs=1 reading_minutes=1
$ sigma-writer autosave-plan --interval 60 --now 1000 --dirty
"""

DEFAULT_STORE = os.path.expanduser("~/.local/share/sigma-writer/docs.json")
ALLOWED_EXT = (".txt", ".md", ".markdown", ".log")
WORDS_PER_MINUTE = 200


class WriterError(ValueError):
    pass


def open_doc(path):
    """Open (or initialise) a document. Fail-fast on disallowed extensions."""
    ext = os.path.splitext(path)[1].lower()
    if ext and ext not in ALLOWED_EXT:
        raise WriterError(f"unsupported extension: {ext} "
                          f"(have: {', '.join(ALLOWED_EXT)})")
    if os.path.exists(path) and not os.path.isfile(path):
        raise WriterError(f"not a regular file: {path}")
    text = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    return {"path": os.path.abspath(path), "text": text, "dirty": False,
            "caret": 0}


def write_doc(doc, text, append=False):
    """Set (or append) the document text. Marks the doc dirty. Pure-ish."""
    if append:
        doc["text"] += str(text)
    else:
        doc["text"] = str(text)
    doc["caret"] = len(doc["text"])
    doc["dirty"] = True
    return doc


def save_doc(doc, path=None):
    """Apply layer: atomic save. Returns the path written."""
    target = path or doc.get("path")
    if not target:
        raise WriterError("no path to save to")
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    tmp = target + ".sigma-tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(doc["text"])
    os.replace(tmp, target)
    doc["path"] = os.path.abspath(target)
    doc["dirty"] = False
    return doc["path"]


def focus_stats(text):
    """Pure focus statistics: words, chars, paragraphs, reading time."""
    stripped = text.strip()
    words = len(re.findall(r"\S+", stripped))
    chars = len(text)
    paragraphs = len([p for p in re.split(r"\n\s*\n", stripped) if p.strip()])
    minutes = math.ceil(words / WORDS_PER_MINUTE) if words else 0
    return {"words": words, "chars": chars, "paragraphs": paragraphs,
            "reading_minutes": minutes}


def autosave_plan(doc, interval, now):
    """Pure plan: when the next autosave is due (None when clean).

    The clock is injected so tests are deterministic.
    """
    try:
        interval = float(interval)
        now = float(now)
    except (TypeError, ValueError):
        raise WriterError(f"bad autosave arguments: interval={interval!r} now={now!r}")
    if interval <= 0:
        raise WriterError(f"interval must be > 0, got {interval}")
    if not doc.get("dirty"):
        return {"dirty": False, "due_at": None, "interval": interval,
                "pending": 0}
    due = now + interval
    return {"dirty": True, "due_at": round(due, 6), "interval": interval,
            "pending": len(doc["text"])}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"], description=ENGINE["summary"])
    p.add_argument("--store", default=DEFAULT_STORE, help="doc index (JSON)")
    sub = p.add_subparsers(dest="cmd", required=True)
    op = sub.add_parser("open", help="open (create) a document and show stats")
    op.add_argument("path")
    wr = sub.add_parser("write", help="write text into a document (atomic save)")
    wr.add_argument("path")
    wr.add_argument("--text", required=True)
    wr.add_argument("--append", action="store_true")
    fs = sub.add_parser("focus-stats", help="focus statistics for text or a file")
    fs.add_argument("--text", default=None)
    fs.add_argument("--file", default=None)
    ap = sub.add_parser("autosave-plan", help="plan the next autosave (pure)")
    ap.add_argument("--file", default=None, help="base dirty state on this file")
    ap.add_argument("--interval", type=float, required=True)
    ap.add_argument("--now", type=float, default=None,
                    help="clock value (default: real time)")
    ap.add_argument("--dirty", action="store_true",
                    help="treat the document as dirty")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "open":
            doc = open_doc(args.path)
            st = focus_stats(doc["text"])
            print(f"{doc['path']}: words={st['words']} chars={st['chars']} "
                  f"paragraphs={st['paragraphs']}")
        elif args.cmd == "write":
            doc = open_doc(args.path)
            write_doc(doc, args.text, append=args.append)
            saved = save_doc(doc)
            st = focus_stats(doc["text"])
            print(f"saved {saved} (words={st['words']})")
        elif args.cmd == "focus-stats":
            if args.file:
                with open(args.file, "r", encoding="utf-8") as fh:
                    text = fh.read()
            elif args.text is not None:
                text = args.text
            else:
                print("error: need --text or --file", file=sys.stderr)
                return 1
            st = focus_stats(text)
            print(f"words={st['words']} chars={st['chars']} "
                  f"paragraphs={st['paragraphs']} "
                  f"reading_minutes={st['reading_minutes']}")
        elif args.cmd == "autosave-plan":
            doc = {"dirty": bool(args.dirty), "text": ""}
            if args.file:
                doc = open_doc(args.file)
                doc["dirty"] = bool(args.dirty) or doc["dirty"]
            plan = autosave_plan(doc, args.interval,
                                 args.now if args.now is not None else time.time())
            if plan["due_at"] is None:
                print("clean: no autosave due")
            else:
                print(f"autosave due at t={plan['due_at']} "
                      f"(every {plan['interval']}s, {plan['pending']} chars pending)")
        return 0
    except (WriterError, OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "notes.txt")
        # open: creates a new doc, or loads existing content
        doc = open_doc(path)
        assert doc["text"] == "" and doc["dirty"] is False
        write_doc(doc, "hello world")
        assert doc["dirty"] is True and doc["caret"] == 11
        saved = save_doc(doc)
        assert saved == os.path.abspath(path)
        assert doc["dirty"] is False
        again = open_doc(path)
        assert again["text"] == "hello world"
        # append vs overwrite
        write_doc(again, " and more", append=True)
        assert again["text"] == "hello world and more"
        write_doc(again, "fresh")
        assert again["text"] == "fresh"
        save_doc(again)
        # focus statistics (pure)
        st = focus_stats("one two three")
        assert (st["words"], st["chars"], st["paragraphs"]) == (3, 13, 1)
        assert st["reading_minutes"] == 1              # ceil(3/200)
        st2 = focus_stats("a " * 250)                  # 250 words -> 2 minutes
        assert st2["words"] == 250 and st2["reading_minutes"] == 2
        st3 = focus_stats("para one\n\npara two\n\n\npara three")
        assert st3["paragraphs"] == 3
        assert focus_stats("   ")["words"] == 0
        assert focus_stats("")["reading_minutes"] == 0
        # autosave plan (pure, injected clock -> deterministic)
        clean = {"dirty": False, "text": ""}
        assert autosave_plan(clean, 60, now=1000.0)["due_at"] is None
        dirty = {"dirty": True, "text": "hello"}
        plan = autosave_plan(dirty, 60, now=1000.0)
        assert plan == {"dirty": True, "due_at": 1060.0, "interval": 60.0,
                        "pending": 5}
        assert autosave_plan(dirty, 30, now=1000.0)["due_at"] == 1030.0
        for bad in (lambda: autosave_plan(dirty, 0, now=1.0),
                    lambda: autosave_plan(dirty, -5, now=1.0),
                    lambda: autosave_plan(dirty, 60, now="later")):
            try:
                bad()
            except WriterError:
                pass
            else:
                raise AssertionError("expected WriterError")
        # fail-fast on disallowed extensions / non-files
        for bad_path in (os.path.join(d, "evil.exe"), os.path.join(d, "x.bin")):
            try:
                open_doc(bad_path)
            except WriterError:
                pass
            else:
                raise AssertionError(f"should reject {bad_path}")
        try:
            open_doc(d)                     # a directory, not a file
        except WriterError:
            pass
        else:
            raise AssertionError("opening a directory not caught")
        # markdown documents are allowed; saves are atomic (no leftover tmp)
        md = open_doc(os.path.join(d, "story.md"))
        write_doc(md, "# Title\n\nOnce upon a time.")
        save_doc(md)
        assert open(os.path.join(d, "story.md"), encoding="utf-8").read() == md["text"]
        assert not os.path.exists(os.path.join(d, "story.md.sigma-tmp"))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
