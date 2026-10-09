#!/usr/bin/env python3
"""Package explicitly placed binary STLs as portable, geometry-only core 3MF.

The manifest is a JSON object with title/description (optional) and an objects
list. Each object has name, stl, material, and an optional 12-number transform.
Relative STL paths resolve against the manifest's directory. Transform numbers
use the 3MF row-vector convention: 3x3 matrix then x/y/z translation.
This tool preserves geometry and does not infer printer or support settings.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import struct
import tempfile
import xml.sax.saxutils as xml_escape
import zipfile


CORE_NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
IDENTITY = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
COLORS = {"PETG": "#D8DCDDFF", "TPU": "#34393FFF"}


@dataclass
class Mesh:
    path: Path
    vertices: list[tuple[float, float, float]]
    triangles: list[tuple[int, int, int]]
    report: dict


@dataclass
class Part:
    name: str
    material: str
    transform: tuple[float, ...]
    mesh: Mesh


def number(value: float) -> str:
    # Nine significant digits round-trip binary32 STL coordinates exactly.
    return format(0.0 if value == 0.0 else value, ".9g")


def attr(value: str) -> str:
    return xml_escape.quoteattr(value)


def transformed(point: tuple[float, ...], matrix: tuple[float, ...]) -> tuple[float, ...]:
    x, y, z = point
    return (
        x * matrix[0] + y * matrix[3] + z * matrix[6] + matrix[9],
        x * matrix[1] + y * matrix[4] + z * matrix[7] + matrix[10],
        x * matrix[2] + y * matrix[5] + z * matrix[8] + matrix[11],
    )


def read_stl(path: Path) -> Mesh:
    file_size = path.stat().st_size
    vertices: list[tuple[float, float, float]] = []
    triangles: list[tuple[int, int, int]] = []
    index: dict[tuple[float, float, float], int] = {}
    edge_counts: Counter = Counter()
    directed_balance: Counter = Counter()
    signed_volume = 0.0
    with path.open("rb") as source:
        header = source.read(84)
        if len(header) != 84:
            raise ValueError(f"{path.name}: missing binary STL header")
        count = struct.unpack_from("<I", header, 80)[0]
        if count == 0 or file_size != 84 + 50 * count:
            raise ValueError(
                f"{path.name}: expected a nonempty binary STL with exactly "
                f"{84 + 50 * count} bytes, found {file_size}"
            )
        for facet in range(count):
            data = struct.unpack("<12fH", source.read(50))
            points = [tuple(0.0 if v == 0.0 else v for v in data[i : i + 3])
                      for i in (3, 6, 9)]
            if not all(math.isfinite(v) for point in points for v in point):
                raise ValueError(f"{path.name}: non-finite coordinate in facet {facet}")
            ids = []
            for point in points:
                if point not in index:
                    index[point] = len(vertices)
                    vertices.append(point)
                ids.append(index[point])
            if len(set(ids)) != 3:
                raise ValueError(f"{path.name}: collapsed facet {facet}")
            a, b, c = points
            u = tuple(b[i] - a[i] for i in range(3))
            v = tuple(c[i] - a[i] for i in range(3))
            cross = (u[1] * v[2] - u[2] * v[1],
                     u[2] * v[0] - u[0] * v[2],
                     u[0] * v[1] - u[1] * v[0])
            if not any(component != 0.0 for component in cross):
                raise ValueError(f"{path.name}: zero-area facet {facet}")
            triangles.append(tuple(ids))
            # A closed, consistently oriented mesh has exactly two opposing
            # directed uses for every edge. No welding or geometry repair.
            for first, second in ((ids[0], ids[1]), (ids[1], ids[2]), (ids[2], ids[0])):
                edge = (min(first, second), max(first, second))
                edge_counts[edge] += 1
                directed_balance[edge] += 1 if first < second else -1
            signed_volume += (
                a[0] * (b[1] * c[2] - b[2] * c[1])
                + a[1] * (b[2] * c[0] - b[0] * c[2])
                + a[2] * (b[0] * c[1] - b[1] * c[0])
            ) / 6.0
    lower = [min(point[axis] for point in vertices) for axis in range(3)]
    upper = [max(point[axis] for point in vertices) for axis in range(3)]
    report = {
        "stl": str(path), "vertices": len(vertices), "triangles": len(triangles),
        "bounds_min_mm": lower, "bounds_max_mm": upper,
        "size_mm": [upper[i] - lower[i] for i in range(3)],
        "boundary_edges": sum(count == 1 for count in edge_counts.values()),
        "nonmanifold_edges": sum(count > 2 for count in edge_counts.values()),
        "inconsistent_shared_edges": sum(
            edge_counts[edge] == 2 and balance != 0
            for edge, balance in directed_balance.items()
        ),
        "signed_volume_mm3": signed_volume,
    }
    return Mesh(path, vertices, triangles, report)


def validate_transform(values: list | tuple, label: str) -> tuple[float, ...]:
    if len(values) != 12:
        raise ValueError(f"{label}: transform needs exactly 12 numbers")
    result = tuple(float(value) for value in values)
    if not all(math.isfinite(value) for value in result):
        raise ValueError(f"{label}: transform contains a non-finite number")
    # Accept rotation and translation; reject scaling, shear, reflections, and
    # accidental transposition that would alter the exported part's dimensions.
    rows = [result[0:3], result[3:6], result[6:9]]
    for i in range(3):
        for j in range(3):
            dot = sum(rows[i][k] * rows[j][k] for k in range(3))
            if abs(dot - (1.0 if i == j else 0.0)) > 1e-5:
                raise ValueError(f"{label}: transform must be a rigid placement")
    a, b, c, d, e, f, g, h, i = result[:9]
    determinant = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(determinant - 1.0) > 1e-5:
        raise ValueError(f"{label}: transform must preserve orientation")
    return result


def load_manifest(path: Path, require_watertight: bool, print_placement: bool) -> tuple[dict, list[Part]]:
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    objects = manifest.get("objects")
    if not isinstance(objects, list) or not objects:
        raise ValueError("Manifest must contain a nonempty objects list")
    meshes: dict[Path, Mesh] = {}
    names: set[str] = set()
    parts = []
    for item in objects:
        name = str(item["name"])
        if not name or name in names:
            raise ValueError(f"Object names must be nonempty and distinct: {name!r}")
        names.add(name)
        material = str(item.get("material", "PETG")).upper()
        source = Path(item["stl"])
        source = (path.parent / source).resolve() if not source.is_absolute() else source.resolve()
        if source not in meshes:
            meshes[source] = read_stl(source)
        mesh = meshes[source]
        if require_watertight and any(mesh.report[key] for key in
                                     ("boundary_edges", "nonmanifold_edges", "inconsistent_shared_edges")):
            raise ValueError(f"{name}: mesh is not closed and consistently oriented: {mesh.report}")
        matrix = validate_transform(item.get("transform", IDENTITY), name)
        if print_placement:
            minimum_z = min(transformed(point, matrix)[2] for point in mesh.vertices)
            if abs(minimum_z) > 0.002:
                raise ValueError(f"{name}: print placement must touch z=0; min z={minimum_z:.6f}")
        parts.append(Part(name, material, matrix, mesh))
    return manifest, parts


def model_lines(manifest: dict, parts: list[Part]):
    materials = list(dict.fromkeys(part.material for part in parts))
    material_index = {material: i for i, material in enumerate(materials)}
    yield '<?xml version="1.0" encoding="UTF-8"?>\n'
    yield f'<model unit="millimeter" xml:lang="en-US" xmlns="{CORE_NS}">\n'
    for name, text in (
        ("Title", str(manifest.get("title", "Curtain box camera mount"))),
        ("Description", str(manifest.get("description", "Geometry-only generic core 3MF. No printer, filament process, or support settings are included."))),
        ("Application", "Codex Python standard-library 3MF packager"),
        ("CreationDate", datetime.now(timezone.utc).isoformat(timespec="seconds")),
    ):
        yield f'<metadata name={attr(name)}>{xml_escape.escape(text)}</metadata>\n'
    yield '<resources>\n<basematerials id="1">\n'
    for material in materials:
        yield f'<base name={attr(material)} displaycolor={attr(COLORS.get(material, "#BFC5CAFF"))}/>\n'
    yield '</basematerials>\n'
    for object_id, part in enumerate(parts, 2):
        yield f'<object id="{object_id}" type="model" name={attr(part.name)} pid="1" pindex="{material_index[part.material]}">\n<mesh>\n<vertices>\n'
        for x, y, z in part.mesh.vertices:
            yield f'<vertex x="{number(x)}" y="{number(y)}" z="{number(z)}"/>\n'
        yield '</vertices>\n<triangles>\n'
        for v1, v2, v3 in part.mesh.triangles:
            yield f'<triangle v1="{v1}" v2="{v2}" v3="{v3}"/>\n'
        yield '</triangles>\n</mesh>\n</object>\n'
    yield '</resources>\n<build>\n'
    for object_id, part in enumerate(parts, 2):
        matrix = " ".join(format(value, ".12g") for value in part.transform)
        yield f'<item objectid="{object_id}" transform="{matrix}"/>\n'
    yield '</build>\n</model>\n'


def package(path: Path, manifest: dict, parts: list[Part]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temporary sibling first so failure cannot leave a partial file.
    handle = tempfile.NamedTemporaryFile(prefix=path.stem + "-", suffix=".tmp", dir=path.parent, delete=False)
    temporary = Path(handle.name)
    handle.close()
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
            archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
            with archive.open("3D/3dmodel.model", "w", force_zip64=True) as model:
                for line in model_lines(manifest, parts):
                    model.write(line.encode("utf-8"))
        with zipfile.ZipFile(temporary) as archive:
            corrupt = archive.testzip()
            if corrupt:
                raise ValueError(f"Corrupt ZIP entry: {corrupt}")
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {"file": str(path.resolve()), "objects": [{"name": p.name, "material": p.material, "transform": p.transform, **p.mesh.report} for p in parts],
            "units": "millimeter", "printer_settings": False, "support_settings": False,
            "support_free_verified": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Single generic 3MF output")
    parser.add_argument("--material", help="Filter single output to this material")
    parser.add_argument("--split-directory", type=Path, help="Also write one 3MF per material")
    parser.add_argument("--prefix", default="curtainbox_mount")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--require-watertight", action="store_true")
    parser.add_argument("--validate-print-placement", action="store_true")
    args = parser.parse_args()
    if not args.output and not args.split_directory:
        parser.error("Specify --output and/or --split-directory")
    if args.material and not args.output:
        parser.error("--material requires --output")
    manifest, parts = load_manifest(args.manifest.resolve(), args.require_watertight, args.validate_print_placement)
    reports = []
    if args.output:
        selected = [part for part in parts if part.material == args.material.upper()] if args.material else parts
        if not selected:
            raise ValueError("The requested material has no objects")
        reports.append(package(args.output, manifest, selected))
    if args.split_directory:
        for material in dict.fromkeys(part.material for part in parts):
            suffix = "".join(character if character.isalnum() or character in "-_" else "_" for character in material)
            selected = [part for part in parts if part.material == material]
            reports.append(package(args.split_directory / f"{args.prefix}_{suffix}.3mf", manifest, selected))
    result = json.dumps({"packages": reports}, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
