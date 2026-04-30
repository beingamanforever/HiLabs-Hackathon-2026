from pathlib import Path

from r3hackathon.track1 import run_track1


def main() -> None:
    output_dir = Path("outputs/track1")
    run_track1(output_dir)
    print(f"Track 1 outputs written to {output_dir.resolve()}")


if __name__ == "__main__":
    main()

