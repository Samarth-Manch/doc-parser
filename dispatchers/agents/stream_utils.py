"""
Stream parser for `claude -p --output-format stream-json`.

Reads NDJSON events from a subprocess stdout and prints human-readable
real-time output showing what Claude is doing (text, tool calls, results).
Also writes a clean human-readable log file.
"""

import json
import sys
from pathlib import Path

# ANSI colors (for terminal only, not log files)
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def stream_and_print(process, verbose=True, log_file_path=None):
    """
    Read stream-json events from a subprocess and print human-readable output.

    Args:
        process: subprocess.Popen with stdout=PIPE, text=True
        verbose: if True, print real-time output to terminal
        log_file_path: optional Path/str to write human-readable log

    Returns:
        list of raw output lines (for backward compatibility)
    """
    output_lines = []
    log_handle = None
    if log_file_path:
        Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)
        log_handle = open(log_file_path, 'w')
        log_handle.write("=" * 70 + "\n")
        log_handle.write("CLAUDE AGENT STREAM LOG\n")
        log_handle.write("=" * 70 + "\n\n")

    # Track state per content block index
    blocks = {}  # index -> {"type", "name", "input_json", "text"}

    try:
        for raw_line in process.stdout:
            output_lines.append(raw_line)

            line = raw_line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                # Not JSON — print as-is
                if verbose:
                    print(raw_line, end='', flush=True)
                _log(log_handle, raw_line.rstrip())
                continue

            # Handle both wrapped and unwrapped events
            event = data.get("event", data) if data.get("type") == "stream_event" else data
            etype = event.get("type", "")

            if etype == "content_block_start":
                idx = event.get("index", 0)
                cb = event.get("content_block", {})
                cb_type = cb.get("type", "")
                blocks[idx] = {
                    "type": cb_type,
                    "name": cb.get("name", ""),
                    "input_json": "",
                    "text": "",
                }
                if cb_type == "tool_use":
                    tool_name = cb.get("name", "?")
                    if verbose:
                        print(f"\n  {_CYAN}⚡ {tool_name}{_RESET} ", end='', flush=True)
                    _log(log_handle, f"\n  [TOOL] {tool_name} ", newline=False)

            elif etype == "content_block_delta":
                idx = event.get("index", 0)
                delta = event.get("delta", {})
                delta_type = delta.get("type", "")
                block = blocks.get(idx)

                if delta_type == "text_delta":
                    text = delta.get("text", "")
                    if block:
                        block["text"] += text
                    if verbose:
                        print(text, end='', flush=True)
                    _log(log_handle, text, newline=False)

                elif delta_type == "input_json_delta":
                    partial = delta.get("partial_json", "")
                    if block:
                        block["input_json"] += partial

            elif etype == "content_block_stop":
                idx = event.get("index", 0)
                block = blocks.pop(idx, None)
                if block and block["type"] == "tool_use":
                    _print_tool_summary(block, verbose, log_handle)
                elif block and block["type"] == "text":
                    if block["text"] and not block["text"].endswith("\n"):
                        if verbose:
                            print(flush=True)
                        _log(log_handle, "")

            elif etype == "message_delta":
                usage = event.get("usage", {})
                out_tokens = usage.get("output_tokens", 0)
                if out_tokens and verbose:
                    print(f"\n  {_DIM}[tokens: {out_tokens}]{_RESET}", flush=True)
                if out_tokens:
                    _log(log_handle, f"\n  [tokens: {out_tokens}]")

            elif etype == "result":
                _print_result_event(event, verbose, log_handle)

    finally:
        if log_handle:
            log_handle.write("\n" + "=" * 70 + "\n")
            log_handle.write("END OF STREAM LOG\n")
            log_handle.write("=" * 70 + "\n")
            log_handle.close()

    return output_lines


def _log(handle, text, newline=True):
    """Write to log file if handle is open."""
    if handle:
        handle.write(text + ("\n" if newline else ""))
        handle.flush()


def _print_tool_summary(block, verbose, log_handle):
    """Print a compact summary of a completed tool call."""
    name = block["name"]
    raw_input = block["input_json"]

    try:
        inp = json.loads(raw_input) if raw_input else {}
    except json.JSONDecodeError:
        inp = {}

    summary = _get_tool_summary(name, inp)

    if verbose:
        print(f"{_DIM}→ {summary}{_RESET}", flush=True)
    _log(log_handle, f"→ {summary}")


def _get_tool_summary(name, inp):
    """Get a one-line summary string for a tool call."""
    if name == "Read":
        return inp.get("file_path", "?")

    elif name == "Write":
        path = inp.get("file_path", "?")
        content = inp.get("content", "")
        lines = content.count("\n") + 1 if content else 0
        return f"{path} ({lines} lines)"

    elif name == "Edit":
        return inp.get("file_path", "?")

    elif name == "Bash":
        cmd = inp.get("command", "?")
        return cmd[:77] + "..." if len(cmd) > 80 else cmd

    elif name == "Glob":
        return inp.get("pattern", "?")

    elif name == "Grep":
        return f"/{inp.get('pattern', '?')}/"

    else:
        parts = ", ".join(f"{k}={repr(v)[:40]}" for k, v in list(inp.items())[:2])
        return parts or name


def _print_result_event(event, verbose, log_handle):
    """Print a final result event if present."""
    result = event.get("result", "")
    if result and isinstance(result, str) and len(result) < 200:
        if verbose:
            print(f"\n  {_GREEN}Result: {result}{_RESET}", flush=True)
        _log(log_handle, f"\n  Result: {result}")
