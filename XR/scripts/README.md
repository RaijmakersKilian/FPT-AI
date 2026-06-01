# XR Export Guide

This folder contains the bridge IFC and the scripts to export it to GLB files.

## Folder layout

- `IFC_Files/` - source IFC files
- `GLB_Files/` - exported GLB files and centered GLB files
- `scripts/` - export and centering scripts

## Requirements

Install the Python packages and Node tool once:

```powershell
npm install -g obj2gltf
python -m pip install ifcopenshell trimesh pygltflib numpy
```

## Export commands

### Export one element group

Use this when you want a single prefix group exported to GLB:

```powershell
python .\scripts\export_ifc_by_prefix.py .\IFC_Files\Bridge.ifc --prefixes "KCPT_Ki"
```

### Export a wildcard group

Use `*` to export all matching numbered variants:

```powershell
python .\scripts\export_ifc_by_prefix.py .\IFC_Files\Bridge.ifc --prefixes "KCPT_GO LAN CAN*"
```

### Export everything by name

This exports every detected prefix group from the IFC:

```powershell
python .\scripts\export_ifc_by_prefix.py .\IFC_Files\Bridge.ifc --all
```

## Output location

By default, exported GLBs are written to `XR/GLB_Files/`.

The script also creates a centered copy automatically:

- `Bridge.glb` -> `Bridge_centered.glb`
- `KCPT_Ki.glb` -> `KCPT_Ki_centered.glb`

## Recenter existing GLBs

If you add or export new GLBs and want to recenter them again, run:

```powershell
python .\scripts\recenter_glbs.py
```

## List available prefixes

If you want to see all element groups in the IFC first:

```powershell
python .\scripts\export_ifc_by_prefix.py .\IFC_Files\Bridge.ifc --list
```

## Notes

- `XR/IFC_Files/` should only contain the IFC source files.
- `XR/GLB_Files/` should contain the exported GLB files.
- If a GLB looks off-center in a viewer, use the centered version ending in `_centered.glb`.
