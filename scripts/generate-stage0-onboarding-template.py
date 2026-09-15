#!/usr/bin/env python3
"""Generate the official ECIP Stage 0 restaurant onboarding workbook."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.onboarding.xlsx import generate_template  # noqa: E402


DEFAULT_OUTPUT = ROOT / "docs" / "operations" / "templates" / "ECIP_Stage0_Restaurant_Onboarding_v1.xlsx"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    generated = generate_template(output)
    print(generated.relative_to(ROOT) if generated.is_relative_to(ROOT) else generated)


if __name__ == "__main__":
    main()
