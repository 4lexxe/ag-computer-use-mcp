"""Local, recorded test surface for evaluating an MCP agent without real user data."""

import argparse
import ctypes
import json
import os
import time
import tkinter as tk
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--expected", default="PRUEBA_MCP_2026")
    args = parser.parse_args()
    args.record.parent.mkdir(parents=True, exist_ok=True)
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        pass
    root = tk.Tk()
    root.title("MCP Test Lab - Prueba controlada")
    root.geometry("680x400+100+150")
    root.configure(bg="#edf2fa")
    text = tk.StringVar()
    state = {
        "expected": args.expected,
        "value": "",
        "clicks": 0,
        "verified": False,
        "closed": False,
        "events": [],
    }

    def record(event):
        state["value"] = text.get()
        state["events"].append({"event": event, "value": text.get(), "time": time.time()})
        temporary = args.record.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        os.replace(temporary, args.record)

    tk.Label(
        root, text="MCP TEST LAB", bg="#edf2fa", fg="#173451", font=("Segoe UI", 22, "bold")
    ).pack(pady=(28, 8))
    tk.Label(
        root,
        text="Ventana de ensayo: no modifica archivos personales.",
        bg="#edf2fa",
        fg="#344b64",
        font=("Segoe UI", 11),
    ).pack()
    tk.Label(root, text="Codigo de prueba", bg="#edf2fa", fg="#173451", font=("Segoe UI", 11)).pack(
        pady=(22, 6)
    )
    entry = tk.Entry(
        root, textvariable=text, font=("Segoe UI", 16), width=29, justify="center", name="test_code"
    )
    entry.pack(ipady=6)
    status = tk.Label(
        root, text="PENDIENTE", bg="#edf2fa", fg="#9a5d14", font=("Segoe UI", 14, "bold")
    )

    def validate():
        state["clicks"] += 1
        state["verified"] = text.get() == args.expected
        status.configure(
            text="VALIDADO: " + args.expected if state["verified"] else "CODIGO INCORRECTO",
            fg="#16714b" if state["verified"] else "#a53643",
        )
        record("validate")

    tk.Button(
        root,
        text="Validar",
        command=validate,
        name="validate",
        bg="#234d79",
        fg="white",
        activebackground="#326699",
        font=("Segoe UI", 13, "bold"),
        padx=30,
        pady=7,
    ).pack(pady=16)
    status.pack()
    text.trace_add("write", lambda *_: record("input"))

    def close():
        state["closed"] = True
        record("close")
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    record("opened")
    root.mainloop()


if __name__ == "__main__":
    main()
