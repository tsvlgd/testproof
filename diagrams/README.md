# Diagrams

This folder holds the source diagrams for the blueprint.

| File | Purpose |
| --- | --- |
| `architecture.mmd` | Product surfaces, deterministic core, repair loop, and outputs |
| `sequence.mmd` | Grade and repair sequence with verifier evidence |
| `states.mmd` | Mutant lifecycle from discovery to a terminal status |
| `phases.mmd` | Build gates, checkpoints, and cut lines |
| `testproof.excalidraw` | Editable architecture and build gate canvas |

## Render Mermaid

Open any `.mmd` file in a Mermaid capable editor, or use the Mermaid CLI:

```bash
npx @mermaid-js/mermaid-cli -i diagrams/architecture.mmd -o /tmp/architecture.svg
```

The Mermaid CLI needs a local Chromium build. If it is not installed, use the Mermaid preview in VS Code or the Mermaid Live editor.

## Open the Excalidraw canvas

Open `testproof.excalidraw` at `https://excalidraw.com` with File, Open, or use the Excalidraw desktop app. The canvas is intentionally hand drawn so a reviewer can edit the boxes and keep the arrows.

## Regenerate the canvas

```bash
uv run python scripts/make_excalidraw.py
python -m json.tool diagrams/testproof.excalidraw > /dev/null
```

The generator is deterministic. The same source produces the same element ids and the same layout.
