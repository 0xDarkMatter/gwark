"""Tests for gwark email senders command — release validation."""

import sys
import subprocess

PYTHON = sys.executable
PASS = 0
FAIL = 0


def run(args: list[str], expect_exit: int = 0, expect_in: str | None = None, expect_not_in: str | None = None) -> bool:
    """Run a command and check expectations."""
    global PASS, FAIL
    result = subprocess.run(
        [PYTHON, "-m", "gwark", "email", "senders"] + args,
        capture_output=True, text=True, timeout=60,
        cwd="X:/Fabric/Gwark",
    )
    combined = result.stdout + result.stderr
    ok = True

    if result.returncode != expect_exit:
        print(f"  FAIL exit={result.returncode} expected={expect_exit}")
        ok = False
    if expect_in and expect_in not in combined:
        print(f"  FAIL missing: {expect_in!r}")
        ok = False
    if expect_not_in and expect_not_in in combined:
        print(f"  FAIL unexpected: {expect_not_in!r}")
        ok = False

    if ok:
        PASS += 1
        print(f"  PASS")
    else:
        FAIL += 1
        if combined.strip():
            print(f"  OUTPUT: {combined[:200]}")
    return ok


def main():
    global PASS, FAIL

    print("1. No args -> validation error")
    run([], expect_exit=4, expect_in="Provide at least one")

    print("2. --help -> shows help")
    run(["--help"], expect_exit=0, expect_in="Find unique senders")

    print("3. --name search -> finds senders")
    run(["--name", "nevill", "--max-results", "10"], expect_exit=0, expect_in="unique senders")

    print("4. Zero results -> graceful message")
    run(["--name", "zzz-nonexistent-xyz", "--days", "1"], expect_exit=0, expect_in="No emails found")

    print("5. --domain search -> works")
    run(["--domain", "evolution7.com.au", "--days", "7", "--max-results", "20"], expect_exit=0, expect_in="unique senders")

    print("6. JSON output -> valid")
    run(["--name", "nevill", "--max-results", "5", "-f", "json"], expect_exit=0, expect_in="Saved to")

    print("7. CSV output -> valid")
    run(["--name", "nevill", "--max-results", "5", "-f", "csv"], expect_exit=0, expect_in="Saved to")

    print("8. --sender prefix -> uses sender in filename")
    run(["--sender", "noreply@", "--days", "7", "--max-results", "10"], expect_exit=0, expect_in="senders_noreply")

    print("9. --enrich -> contact enrichment")
    run(["--name", "nevill", "--max-results", "5", "--enrich"], expect_exit=0, expect_in="contact status")

    print("10. No traceback on any error path")
    run([], expect_exit=4, expect_not_in="Traceback")

    print(f"\n{'='*40}")
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    print(FAIL)  # This is the metric — number of failures


if __name__ == "__main__":
    main()
