"""Generate the TestProof Excalidraw canvas from a small deterministic layout."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "diagrams" / "testproof.excalidraw"
UPDATED = 1_761_516_000_000

INK = "#1e1e1e"
MUTED = "#495057"
BLUE = "#1971c2"
BLUE_FILL = "#e7f5ff"
GREEN = "#2f9e44"
GREEN_FILL = "#ebfbee"
ORANGE = "#e8590c"
ORANGE_FILL = "#fff4e6"
PURPLE = "#6741d9"
PURPLE_FILL = "#f3f0ff"
GRAY = "#868e96"
GRAY_FILL = "#f8f9fa"


def _id(prefix: str, *parts: object) -> str:
    digest = hashlib.sha1("|".join(str(part) for part in parts).encode()).hexdigest()
    return f"{prefix}-{digest[:16]}"


def _seed(element_id: str) -> int:
    return int(hashlib.sha1(element_id.encode()).hexdigest()[:8], 16)


def _common(
    element_id: str, element_type: str, x: float, y: float, width: float, height: float
) -> dict[str, Any]:
    return {
        "id": element_id,
        "type": element_type,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "angle": 0,
        "strokeColor": INK,
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": None,
        "seed": _seed(element_id),
        "version": 1,
        "versionNonce": _seed(element_id) ^ 0x5F3759DF,
        "isDeleted": False,
        "boundElements": [],
        "updated": UPDATED,
        "link": None,
        "locked": False,
        "customData": {},
    }


def add_text(
    elements: list[dict[str, Any]],
    name: str,
    x: float,
    y: float,
    width: float,
    text: str,
    size: int = 16,
    color: str = INK,
    align: str = "center",
    family: int = 1,
) -> None:
    line_count = text.count("\n") + 1
    height = size * 1.25 * line_count
    element = _common(_id("text", name), "text", x, y, width, height)
    element.update(
        {
            "strokeColor": color,
            "strokeWidth": 1,
            "text": text,
            "fontSize": size,
            "fontFamily": family,
            "textAlign": align,
            "verticalAlign": "top",
            "containerId": None,
            "originalText": text,
            "lineHeight": 1.25,
            "autoResize": True,
            "baseline": int(size * 0.8),
        }
    )
    elements.append(element)


def add_box(
    elements: list[dict[str, Any]],
    name: str,
    x: float,
    y: float,
    width: float,
    height: float,
    label: str,
    fill: str = GRAY_FILL,
    stroke: str = GRAY,
    label_size: int = 15,
    label_color: str = INK,
    dashed: bool = False,
) -> None:
    element = _common(_id("box", name), "rectangle", x, y, width, height)
    element.update(
        {
            "strokeColor": stroke,
            "backgroundColor": fill,
            "strokeStyle": "dashed" if dashed else "solid",
            "roundness": {"type": 3},
        }
    )
    elements.append(element)
    line_count = label.count("\n") + 1
    text_height = label_size * 1.25 * line_count
    add_text(
        elements,
        f"{name}-label",
        x + 8,
        y + (height - text_height) / 2,
        width - 16,
        label,
        size=label_size,
        color=label_color,
    )


def add_arrow(
    elements: list[dict[str, Any]],
    name: str,
    points: list[tuple[float, float]],
    color: str = MUTED,
    both_ends: bool = False,
) -> None:
    start_x, start_y = points[0]
    relative = [(point_x - start_x, point_y - start_y) for point_x, point_y in points]
    xs = [point[0] for point in relative]
    ys = [point[1] for point in relative]
    element = _common(
        _id("arrow", name),
        "arrow",
        start_x,
        start_y,
        max(xs) - min(xs),
        max(ys) - min(ys),
    )
    element.update(
        {
            "strokeColor": color,
            "strokeWidth": 2,
            "points": [[round(dx, 2), round(dy, 2)] for dx, dy in relative],
            "lastCommittedPoint": None,
            "startBinding": None,
            "endBinding": None,
            "startArrowhead": "arrow" if both_ends else None,
            "endArrowhead": "arrow",
            "elbowed": False,
        }
    )
    elements.append(element)


def build() -> dict[str, Any]:
    elements: list[dict[str, Any]] = []

    add_text(elements, "title", 48, 28, 800, "TestProof", size=34, align="left")
    add_text(
        elements,
        "subtitle",
        50,
        78,
        860,
        "Architecture, evidence loop, and build gates",
        size=17,
        color=MUTED,
        align="left",
    )
    add_text(
        elements,
        "thesis",
        1120,
        38,
        460,
        "Deterministic measurement\nAgentic repair",
        size=16,
        color=MUTED,
        align="right",
    )

    add_text(elements, "inputs-heading", 50, 140, 240, "Inputs", size=20, align="left")
    add_text(elements, "core-heading", 330, 140, 460, "Deterministic core", size=20, align="left")
    add_text(
        elements,
        "repair-heading",
        850,
        140,
        260,
        "Agentic repair",
        size=20,
        color=PURPLE,
        align="left",
    )
    add_text(elements, "outputs-heading", 1180, 140, 260, "Outputs", size=20, align="left")

    add_box(elements, "repo", 50, 190, 230, 70, "Repository plus diff", BLUE_FILL, BLUE)
    add_box(elements, "test-command", 50, 290, 230, 70, "Project test command", BLUE_FILL, BLUE)
    add_box(elements, "config", 50, 390, 230, 70, "Config and threshold", BLUE_FILL, BLUE)

    add_box(elements, "core-frame", 320, 180, 480, 520, "", GRAY_FILL, GRAY, dashed=True)
    add_box(elements, "diff", 345, 205, 190, 65, "Diff resolver", "#ffffff", BLUE)
    add_box(elements, "adapters", 565, 205, 210, 65, "Language adapters", "#ffffff", BLUE)
    add_box(elements, "mutate", 345, 300, 190, 65, "Mutant discovery", "#ffffff", BLUE)
    add_box(elements, "sandbox", 565, 300, 210, 65, "Sandbox workspace", "#ffffff", BLUE)
    add_box(elements, "runner", 345, 395, 430, 65, "Project test runner", "#ffffff", BLUE)
    add_box(elements, "classify", 345, 490, 430, 65, "Classifier and scorer", "#ffffff", BLUE)
    add_box(elements, "report", 345, 585, 430, 65, "Report builder", "#ffffff", BLUE)

    add_box(elements, "repair-agent", 850, 205, 260, 70, "Repair agent", PURPLE_FILL, PURPLE)
    add_box(elements, "model", 850, 305, 260, 70, "Open source model", PURPLE_FILL, PURPLE)
    add_box(elements, "verifier", 850, 405, 260, 70, "Kill verifier", PURPLE_FILL, PURPLE)
    add_text(
        elements,
        "repair-note",
        850,
        500,
        260,
        "The model proposes.\nThe engine verifies.\nNo unverified test is kept.",
        size=14,
        color=MUTED,
    )

    add_box(elements, "json", 1180, 205, 250, 65, "JSON report", GREEN_FILL, GREEN)
    add_box(elements, "markdown", 1180, 300, 250, 65, "Markdown report", GREEN_FILL, GREEN)
    add_box(elements, "check", 1180, 395, 250, 65, "Pull request check", GREEN_FILL, GREEN)
    add_box(elements, "artifact", 1180, 490, 250, 65, "Alan task artifact", GREEN_FILL, GREEN)
    add_text(
        elements,
        "output-note",
        1180,
        575,
        250,
        "Partial runs and suspected\nequivalents are reported,\nnever hidden.",
        size=14,
        color=MUTED,
    )

    add_arrow(elements, "repo-to-diff", [(280, 225), (345, 237)])
    add_arrow(elements, "test-to-runner", [(280, 325), (345, 427)])
    add_arrow(elements, "config-to-mutate", [(280, 425), (345, 332)])
    add_arrow(elements, "diff-to-mutate", [(440, 270), (440, 300)])
    add_arrow(elements, "adapters-to-sandbox", [(670, 270), (670, 300)])
    add_arrow(elements, "mutate-to-sandbox", [(535, 332), (565, 332)])
    add_arrow(elements, "sandbox-to-runner", [(670, 365), (670, 395)])
    add_arrow(elements, "runner-to-classify", [(560, 460), (560, 490)])
    add_arrow(elements, "classify-to-report", [(560, 555), (560, 585)])

    add_arrow(
        elements,
        "report-to-json",
        [
            (775, 617),
            (800, 617),
            (800, 690),
            (1125, 690),
            (1125, 237),
            (1180, 237),
        ],
    )
    add_arrow(elements, "json-to-agent", [(1180, 237), (1110, 240)])
    add_arrow(elements, "agent-to-model", [(980, 275), (980, 305)], color=PURPLE, both_ends=True)
    add_arrow(
        elements,
        "agent-to-verifier",
        [(1110, 240), (1130, 240), (1130, 440), (1110, 440)],
        color=PURPLE,
    )
    add_arrow(elements, "verifier-to-runner", [(850, 440), (775, 427)], color=PURPLE)
    add_arrow(elements, "json-to-markdown", [(1305, 270), (1305, 300)], color=GREEN)
    add_arrow(elements, "markdown-to-check", [(1305, 365), (1305, 395)], color=GREEN)
    add_arrow(elements, "check-to-artifact", [(1305, 460), (1305, 490)], color=GREEN)

    add_text(
        elements, "gates-heading", 50, 725, 700, "Build gates and cut lines", size=20, align="left"
    )

    phases = [
        ("P0", 50, "Phase 0\nFoundation\nCLI and diff\nmake check", BLUE_FILL, BLUE),
        (
            "P1",
            270,
            "Phase 1\nEngine\nscore and survivors\nsame input, same score",
            BLUE_FILL,
            BLUE,
        ),
        ("P2", 490, "Phase 2\nCI gate\nthreshold and Action\nPR fails below", BLUE_FILL, BLUE),
        (
            "P3",
            710,
            "Phase 3\nVerified repair\nopen model and verifier\nscore rises with proof",
            PURPLE_FILL,
            PURPLE,
        ),
        (
            "P4",
            930,
            "Phase 4\nAlan skill\nsession and artifact\nreal recording",
            ORANGE_FILL,
            ORANGE,
        ),
        (
            "P5",
            1150,
            "Phase 5\nBenchmark and demo\nbefore and after\nvideo under 3 minutes",
            GREEN_FILL,
            GREEN,
        ),
        (
            "P6",
            1370,
            "Phase 6\nSubmit\nfresh clone and release\nbefore 22:00 IST",
            GRAY_FILL,
            MUTED,
        ),
    ]
    for name, x, label, fill, stroke in phases:
        add_box(elements, f"phase-{name}", x, 765, 190, 110, label, fill, stroke, label_size=14)

    for left, right in zip(phases, phases[1:], strict=False):
        add_arrow(elements, f"{left[0]}-to-{right[0]}", [(left[1] + 190, 820), (right[1], 820)])

    add_text(
        elements,
        "gates-note",
        50,
        905,
        1500,
        "Cut at a gate. Never lower the quality bar. "
        "The report is the contract across the CLI, the skill, and CI.",
        size=16,
        color=MUTED,
        align="left",
    )

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "https://excalidraw.com",
        "elements": elements,
        "appState": {
            "gridSize": 20,
            "viewBackgroundColor": "#ffffff",
            "currentItemFontFamily": 1,
            "currentItemStrokeColor": INK,
            "currentItemBackgroundColor": "transparent",
            "currentItemFillStyle": "solid",
            "currentItemStrokeWidth": 2,
            "currentItemRoughness": 1,
            "currentItemOpacity": 100,
            "currentItemFontSize": 20,
            "currentItemTextAlign": "left",
            "currentItemStartArrowhead": None,
            "currentItemEndArrowhead": "arrow",
            "scrollX": 0,
            "scrollY": 0,
            "zoom": {"value": 1},
            "theme": "light",
        },
        "files": {},
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build()
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT} with {len(payload['elements'])} elements")


if __name__ == "__main__":
    main()
