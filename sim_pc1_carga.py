from simulator import run_once
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    run_once("branch_overload")


if __name__ == "__main__":
    main()
