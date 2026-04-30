from pathlib import Path

from r3hackathon.track3 import run_track3


def main() -> None:
    output_dir = Path("outputs/track3")
    run_track3(output_dir)
    print(f"Track 3 outputs written to {output_dir.resolve()}")


if __name__ == "__main__":
    main()
