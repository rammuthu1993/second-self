"""Phase 0 setup: create directories and verify configuration."""

from config import ensure_directories


def main() -> None:
    ensure_directories()
    print("SecondSelf directories ready.")


if __name__ == "__main__":
    main()
