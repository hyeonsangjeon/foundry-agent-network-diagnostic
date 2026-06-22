#!/usr/bin/env python3
"""
SDK vs Playground A/B helper (OPTIONAL — not part of the read-only diagnostic).

Why this exists
---------------
A useful signal when triaging a Foundry Agent private-network issue: call the *same*
gateway connection from the Agent SDK and compare against the Playground UI.

  * SDK succeeds  +  Playground fails  → likely a UI/Playground support-scope issue
                                         rather than your network path. Note it in the
                                         support case.
  * Both fail                          → consistent with the network-path break the main
                                         diagnostic investigates (run ``src/diagnose.py``).

This script only does the SDK half (the Playground half is a manual click). It does NOT
auto-decide the verdict — comparison is a human judgement, as the README explains.

NOTE: unlike the 6 read-only checks, this script *creates a temporary agent + thread* to
issue one prompt, then deletes the agent it created. Run it only if you are comfortable
with that. It is intentionally kept out of ``src/`` for that reason.

Requirements (optional extras):
    pip install azure-identity azure-ai-projects

Usage:
    python examples/sdk_ab_test.py \
        --project-endpoint https://<your-foundry>.services.ai.azure.com/api/projects/<your-project> \
        --model <your-chat-deployment> \
        --prompt "ping through the BYO gateway"
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SDK vs Playground A/B helper (optional).")
    parser.add_argument("--project-endpoint", required=True,
                        help="Foundry project endpoint, e.g. https://<your-foundry>.services.ai.azure.com/api/projects/<your-project>")
    parser.add_argument("--model", required=True, help="Chat model/deployment name to back the agent.")
    parser.add_argument("--prompt", default="Reply with 'ok' if you can reach the backend.",
                        help="Prompt to send through the agent.")
    args = parser.parse_args(argv)

    try:
        from azure.identity import DefaultAzureCredential
        from azure.ai.projects import AIProjectClient
    except ImportError:
        print(
            "Optional dependencies missing. Install them first:\n"
            "    pip install azure-identity azure-ai-projects",
            file=sys.stderr,
        )
        return 2

    print(f"[a/b] connecting to project: {args.project_endpoint}")
    client = AIProjectClient(endpoint=args.project_endpoint, credential=DefaultAzureCredential())

    agent = None
    try:
        agents = client.agents
        agent = agents.create_agent(
            model=args.model,
            name="fand-ab-test-temp",
            instructions="You are a connectivity probe. Answer briefly.",
        )
        print(f"[a/b] created temp agent: {agent.id}")

        thread = agents.threads.create()
        agents.messages.create(thread_id=thread.id, role="user", content=args.prompt)
        run = agents.runs.create_and_process(thread_id=thread.id, agent_id=agent.id)
        print(f"[a/b] run status: {run.status}")

        if str(run.status).lower() == "completed":
            msgs = agents.messages.list(thread_id=thread.id)
            print("[a/b] SDK call SUCCEEDED.")
            for m in msgs:
                print(f"    {getattr(m, 'role', '?')}: {getattr(m, 'text_messages', m)}")
            print("\nNow try the SAME connection in the Playground UI.")
            print("  - Playground FAILS while this SDK call succeeded → likely a UI support-scope issue.")
            print("  - Playground also fails → run src/diagnose.py to localize the network-path break.")
        else:
            print(f"[a/b] SDK call did NOT complete (status={run.status}, error={getattr(run,'last_error',None)}).")
            print("This is consistent with a network-path break — run src/diagnose.py for the 6-check diagnosis.")
        return 0
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic helper
        print(f"[a/b] SDK call raised: {exc}")
        print("Compare with Playground behavior; run src/diagnose.py for the network-path diagnosis.")
        return 1
    finally:
        if agent is not None:
            try:
                client.agents.delete_agent(agent.id)
                print(f"[a/b] cleaned up temp agent: {agent.id}")
            except Exception as exc:  # noqa: BLE001
                print(f"[a/b] WARNING: could not delete temp agent {agent.id}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
