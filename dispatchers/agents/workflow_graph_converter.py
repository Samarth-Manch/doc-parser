#!/usr/bin/env python3
"""
Workflow Graph Converter

Takes the Inter-Panel stage output (panels + rules) and a logical approval
graph JSON, and emits an augmented JSON that preserves every panel unchanged
while adding a top-level `_meta.workflow_data_node_data` entry containing the
stringified React Flow graph expected by `template.workFlowDataNodeData`.

No LLM calls — pure Python. Participants and condition IDs default to constants
sourced from the Vendor Creation reference (valid Manch DB values). A later
stage can replace them with vision/text-derived IDs.

Logical graph format (input to --graph):

    {
      "tempId": "3802",
      "nodes": [
        {"key": "saved",      "type": "SAVED",                "label": "Saved"},
        {"key": "sent",       "type": "SENT_TO_SECOND_PARTY", "label": "Second Party",
                              "externalName": "Sent to Vendor"},
        {"key": "vhead",      "type": "AWAITING_APPROVAL",
                              "externalName": "Pending for Vertical Head Approval"},
        {"key": "accepted",   "type": "ACCEPTED",             "label": "Accepted"}
      ],
      "edges": [
        {"from": "saved",  "to": "sent",     "label": "default"},
        {"from": "sent",   "to": "vhead",    "label": "default"},
        {"from": "vhead",  "to": "accepted", "label": "Approve"},
        {"from": "vhead",  "to": "saved",    "label": "Send Back"}
      ]
    }

Usage:

    python3 workflow_graph_converter.py \\
        --input  output/inter_panel/all_panels_inter_panel.json \\
        --graph  input/approval_graphs/vendor_creation_3.json \\
        --output output/workflow_graph/all_panels_with_workflow.json
"""

import argparse
import json
import sys
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_PARTICIPANT_ID = 3260
DEFAULT_CONDITION_ID = 644

NODE_MEASURED = {
    "SAVED": {"width": 83, "height": 50},
    "SENT_TO_SECOND_PARTY": {"width": 138, "height": 50},
    "AWAITING_APPROVAL": {"width": 210, "height": 50},
    "ACCEPTED": {"width": 105, "height": 50},
}

PARTICIPANT_TYPE = {
    "SAVED": "CREATED_BY",
    "SENT_TO_SECOND_PARTY": "GENERIC_PARTY",
    "AWAITING_APPROVAL": "APPROVER",
    "ACCEPTED": "ACCEPTED",
}

EDGE_STYLE = {
    "default": {
        "type": "default",
        "color": "#262424",
        "label": "default arrow",
        "show_icon": False,
    },
    "Approve": {
        "type": "approval",
        "color": "green",
        "label": "Approve",
        "show_icon": True,
    },
    "Send Back": {
        "type": "approval",
        "color": "#ff8831",
        "label": "Send Back",
        "show_icon": False,
    },
}

COLUMN_WIDTH = 300
ROW_HEIGHT = 140


def _assign_node_ids(nodes: List[Dict]) -> Dict[str, str]:
    """Generate stable node-<ts+i> ids keyed by the logical 'key' field."""
    base = int(time.time() * 1000)
    return {n["key"]: f"node-{base + i}" for i, n in enumerate(nodes)}


def _rank_nodes(nodes: List[Dict], edges: List[Dict]) -> Dict[str, int]:
    """BFS rank from the SAVED node along forward (non-Send Back) edges."""
    start = next((n["key"] for n in nodes if n["type"] == "SAVED"), nodes[0]["key"])

    forward = defaultdict(list)
    for e in edges:
        if e.get("label") != "Send Back":
            forward[e["from"]].append(e["to"])

    rank: Dict[str, int] = {start: 0}
    q = deque([start])
    while q:
        k = q.popleft()
        for nxt in forward.get(k, []):
            if nxt not in rank:
                rank[nxt] = rank[k] + 1
                q.append(nxt)

    max_rank = max(rank.values(), default=0)
    for n in nodes:
        rank.setdefault(n["key"], max_rank + 1)
    return rank


def _layout(nodes: List[Dict], rank: Dict[str, int]) -> Dict[str, Dict[str, float]]:
    """Layered grid layout: x by rank, y by sibling order within a rank."""
    by_rank: Dict[int, List[str]] = defaultdict(list)
    for n in nodes:
        by_rank[rank[n["key"]]].append(n["key"])

    pos: Dict[str, Dict[str, float]] = {}
    for r, keys in by_rank.items():
        for i, k in enumerate(keys):
            pos[k] = {"x": float(r * COLUMN_WIDTH), "y": float(i * ROW_HEIGHT)}
    return pos


def build_react_flow(graph: Dict) -> Dict:
    """Convert a logical graph into the React Flow shape used by Manch."""
    nodes = graph["nodes"]
    edges = graph["edges"]

    id_map = _assign_node_ids(nodes)
    rank = _rank_nodes(nodes, edges)
    pos = _layout(nodes, rank)

    nodes_data: List[Dict[str, Any]] = []
    for idx, n in enumerate(nodes):
        ntype = n["type"]
        if ntype not in PARTICIPANT_TYPE:
            raise ValueError(f"Unknown node type: {ntype}")

        data: Dict[str, Any] = {"index": idx}
        if ntype == "AWAITING_APPROVAL":
            data["externalName"] = n.get("externalName") or n.get("label") or "Pending for Approval"
        else:
            data["label"] = n.get("label") or ntype.replace("_", " ").title()
            if ntype == "SENT_TO_SECOND_PARTY" and "externalName" in n:
                data["externalName"] = n["externalName"]

        entry: Dict[str, Any] = {
            "id": id_map[n["key"]],
            "type": ntype,
            "position": pos[n["key"]],
            "participantType": PARTICIPANT_TYPE[ntype],
            "data": data,
            "measured": NODE_MEASURED[ntype],
            "selected": False,
            "dragging": False,
        }

        if ntype == "AWAITING_APPROVAL":
            entry["participantId"] = n.get("participantId") or DEFAULT_PARTICIPANT_ID
            entry["style"] = {}

        nodes_data.append(entry)

    edges_data: List[Dict[str, Any]] = []
    for e in edges:
        label = e.get("label", "default")
        style = EDGE_STYLE.get(label)
        if style is None:
            raise ValueError(f"Unknown edge label: {label!r}. Expected one of {list(EDGE_STYLE)}")

        src = id_map[e["from"]]
        tgt = id_map[e["to"]]

        edge_data: Dict[str, Any] = {
            "showButton": False,
            "label": style["label"],
            "showIcon": style["show_icon"],
            "error": False,
        }
        if label == "Approve":
            edge_data["conditionId"] = e.get("conditionId") or DEFAULT_CONDITION_ID

        edges_data.append({
            "source": src,
            "target": tgt,
            "type": style["type"],
            "error": False,
            "notificationId": None,
            "markerEnd": {
                "type": "arrowclosed",
                "width": 25,
                "height": 25,
                "color": style["color"],
            },
            "data": edge_data,
            "id": f"xy-edge__{src}-{tgt}",
            "selected": False,
        })

    return {
        "tempId": graph.get("tempId", ""),
        "nodesData": nodes_data,
        "edgesData": edges_data,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Workflow Graph Converter — inject workFlowDataNodeData into pipeline flow."
    )
    parser.add_argument("--input", required=True, help="Inter-panel stage output JSON (Stage 6)")
    parser.add_argument("--graph", required=True, help="Logical approval graph JSON")
    parser.add_argument("--output", required=True, help="Augmented output JSON")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: inter-panel input not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    graph_path = Path(args.graph)
    if not graph_path.exists():
        print(f"Error: approval graph not found: {graph_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading inter-panel output: {input_path}")
    with input_path.open("r") as f:
        panels_data = json.load(f)

    print(f"Reading approval graph:     {graph_path}")
    with graph_path.open("r") as f:
        graph = json.load(f)

    print(
        f"Building React Flow graph: {len(graph['nodes'])} nodes, "
        f"{len(graph['edges'])} edges"
    )
    react_flow = build_react_flow(graph)

    workflow_str = json.dumps(react_flow, separators=(",", ":"))

    output: Dict[str, Any] = dict(panels_data)
    existing_meta = output.get("_meta") if isinstance(output.get("_meta"), dict) else {}
    meta = dict(existing_meta)
    meta["workflow_data_node_data"] = workflow_str
    meta["workflow_graph_raw"] = graph
    output["_meta"] = meta

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)

    panel_count = sum(1 for k in panels_data if not k.startswith("_"))
    print("")
    print("=" * 70)
    print("WORKFLOW GRAPH CONVERSION COMPLETE")
    print("=" * 70)
    print(f"  Input panels preserved : {panel_count}")
    print(f"  Graph nodes            : {len(react_flow['nodesData'])}")
    print(f"  Graph edges            : {len(react_flow['edgesData'])}")
    print(f"  Default participantId  : {DEFAULT_PARTICIPANT_ID}")
    print(f"  Default conditionId    : {DEFAULT_CONDITION_ID}")
    print(f"  Output                 : {out_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
