from __future__ import annotations

import argparse
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ephemeral workspace main entrypoint")
    parser.add_argument("--mode", choices=["cli", "gui"], default="cli", help="Run as cli or gui")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "gui":
        import ui

        ui.main()
        return 0

    import launcher

    return launcher.main()


if __name__ == "__main__":
    sys.exit(main())
