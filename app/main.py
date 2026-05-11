import argparse

from app.logger import get_logger, setup_logging
from app.orchestrator.runner import run

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SQL agent pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Generate SQL from a natural language message")
    generate.add_argument("message", help="Natural language query")

    return parser.parse_args()


def main():
    setup_logging()
    args = parse_args()

    if args.command == "generate":
        result = run(args.message)
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
