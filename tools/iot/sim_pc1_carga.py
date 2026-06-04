import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.iot.simulator import run_once


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Atajo para simular sobrecarga en el ramal fisico C-01")
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout HTTP por lectura, en segundos.",
    )
    args = parser.parse_args()
    if args.timeout is not None:
        import os

        os.environ["IOT_SIMULATOR_TIMEOUT_SECONDS"] = str(max(1.0, args.timeout))
    run_once("branch_overload")


if __name__ == "__main__":
    main()
