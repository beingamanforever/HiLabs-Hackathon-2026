from pathlib import Path

from r3hackathon.track2 import run_track2


def main() -> None:
    output_dir = Path("outputs/track2")
    run_track2(output_dir)
    print(f"Track 2 outputs written to {output_dir.resolve()}")


if __name__ == "__main__":
    main()

