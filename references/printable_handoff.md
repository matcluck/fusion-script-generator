# Neutral printable-body handoff

Use this handoff only when the user wants exported meshes for a downstream slicer workflow. Keep printer- and slicer-specific decisions out of the Fusion script.

## Output

Place exports outside the Fusion Scripts folder:

```text
<project-directory>/Printable Body Exports/
  top_shell.3mf
  accent_row.3mf
  bottom_cover.3mf
  printable_manifest.json
```

Use one 3MF or STL per printable body. Prefer body-role filenames that remain correct if the user changes colours or printers.

## Manifest

Write UTF-8 JSON:

```json
{
  "schema_version": 1,
  "source": "Autodesk Fusion",
  "units": "millimeter",
  "parts": [
    {
      "name": "Top shell",
      "file": "top_shell.3mf",
      "suggested_print_orientation": "exterior top face down",
      "role": "structural shell"
    }
  ]
}
```

Require:

- `schema_version`: `1`
- `source`: `Autodesk Fusion`
- `units`: `millimeter`
- `parts`: one entry per final printable solid
- `name`: exact Fusion body name
- `file`: relative export filename
- `suggested_print_orientation`: physical orientation stated without slicer coordinates
- `role`: short geometry/assembly role

Optional neutral fields include `notes`, `requires_support`, `brim_recommended`, and `assembly_group`.

Do not include:

- printer model or nozzle
- Bambu/Orca/Prusa preset IDs
- AMS or extruder slots
- filament brands or colours
- slicer plate IDs or world coordinates
- purge/flush settings
- layer-change G-code
- cloud, printer, or account settings

The downstream slicer skill must create its own project manifest from this geometry handoff and the user's printer/filament choices.
