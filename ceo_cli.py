#!/usr/bin/env python3
"""
CEO CLI (Task 2.3): command-line interface for the board member to talk to ALEX (CEO Agent).

Usage:
    python ceo_cli.py status
    python ceo_cli.py status --detailed
    python ceo_cli.py ask "How many stories did we send this week?"
    python ceo_cli.py command "Switch to weekly digest mode"
"""
import argparse
import sys

from agents.ceo_agent import ceo_agent
from utils.metrics_collector import MetricsCollector


def cmd_status(args):
    print("\n📊 Fetching status report from ALEX (CEO Agent)...\n")
    report = ceo_agent.generate_status_report(detailed=args.detailed)
    print("=" * 70)
    print(report)
    print("=" * 70)


def cmd_ask(args):
    question = " ".join(args.question)
    if not question.strip():
        print("Error: provide a question, e.g. ceo_cli.py ask \"What's our quality score?\"")
        sys.exit(1)
    print(f"\n🗣️  You: {question}\n")
    answer = ceo_agent.handle_query(question)
    print(f"🤖 ALEX: {answer}\n")


def cmd_command(args):
    command = " ".join(args.command)
    if not command.strip():
        print("Error: provide a command, e.g. ceo_cli.py command \"Pause the agency\"")
        sys.exit(1)
    print(f"\n📋 Strategic command: {command}\n")
    response = ceo_agent.handle_strategic_command(command)
    print(f"🤖 ALEX: {response}\n")


def cmd_metrics(args):
    print("\n📈 System metrics (Task 3.2)\n")
    report = MetricsCollector().full_report()
    print("Agent performance:")
    for row in report["agent_performance"]:
        print(f"  - {row['agent_name']}: {row['total_actions']} actions, "
              f"success={row['success_rate']}, avg_latency={row['avg_latency_ms']}ms")
    print("\nAPI health:")
    for provider, h in report["api_health"].items():
        print(f"  - {provider}: {h['total_calls']} calls, success={h['success_rate']}")
    print(f"\nDigest stats: {report['digest_stats']}")
    print(f"Quality metrics: {report['quality_metrics']}\n")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="ceo_cli.py",
        description="Talk to ALEX, the CEO Agent of your autonomous AI news agency.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_status = sub.add_parser("status", help="Get an executive status report")
    p_status.add_argument("--detailed", action="store_true", help="Include agent-level performance breakdown")
    p_status.set_defaults(func=cmd_status)

    p_ask = sub.add_parser("ask", help="Ask ALEX a free-form question")
    p_ask.add_argument("question", nargs="+", help="Your question (quote it or pass as multiple words)")
    p_ask.set_defaults(func=cmd_ask)

    p_command = sub.add_parser("command", help="Issue a strategic command to ALEX")
    p_command.add_argument("command", nargs="+", help="The command to issue")
    p_command.set_defaults(func=cmd_command)

    p_metrics = sub.add_parser("metrics", help="Show agent performance and system health metrics")
    p_metrics.set_defaults(func=cmd_metrics)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        print(f"❌ CEO CLI error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
