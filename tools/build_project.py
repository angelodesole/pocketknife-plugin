#! python3
r"""Builds the Rhino 8 Script Editor project of Pocket Knife.

Writes two files in ``project/``:

* ``pocketknife.gh``: one Python 3 Script component per file in
  ``grasshopper/``, with the nickname, inputs (type hint, access) and outputs
  listed in ``COMPONENTS`` (the same as ``grasshopper/README.md``).
* ``pocketknife.rhproj``: the project, with the six commands in ``commands/``,
  the Grasshopper components from ``pocketknife.gh``, the ``pocketknife``
  library from ``src/`` and the SVG icons from ``icons/svg/``.

Run it inside Rhino 8 (8.11 or later), from the repository clone::

    _-RunPythonScript "C:\dev\pocketknife-plugin\tools\build_project.py"

Then build the plug-in (``.rhp``, ``.gha``, ``.yak``) without Rhino::

    python tools\build_plugin.py

The project and component ids below are fixed: the build turns them into the
plug-in and component GUIDs, so changing them breaks installed copies and
saved Grasshopper definitions.
"""

import os
import re
import uuid

import System
from System import Guid, Uri

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
PROJECT_DIR = os.path.join(ROOT, "project")
RHPROJ_PATH = os.path.join(PROJECT_DIR, "pocketknife.rhproj")
GH_PATH = os.path.join(PROJECT_DIR, "pocketknife.gh")
SVG_DIR = os.path.join(ROOT, "icons", "svg")

PROJECT_ID = "9e3c1f4a-6b2d-4c8e-a5f7-3d1b9e0c7a42"
PROJECT_NAME = "PocketKnife"
DESCRIPTION = (
    "Pocket Knife: free, open-source Rhino 8 commands and Grasshopper "
    "components (layers, inner points, minimum bounding boxes and rectangles)."
)
AUTHOR = "Angelo"
# RhinoCode needs an email for the author; the GitHub no-reply address keeps
# a personal one out of the public package.
AUTHOR_EMAIL = "203355151+angelodesole@users.noreply.github.com"
LICENSE = "MIT"
COPYRIGHT = "Copyright (c) 2026 Pocket Knife contributors"
URL = "https://github.com/angelodesole/pocketknife-plugin"
GH_CATEGORY = "Pocket Knife"
GH_SUBCATEGORY = "Geometry"

COMMANDS = (
    "pkLayerColorFromMaterial",
    "pkCopyToLayerCopy",
    "pkInnerPoint",
    "pkMinBoundingBox",
    "pkMinBoundingRect",
    "pkOrientToMinRect",
)

# name: (instance id, nickname, description, inputs, outputs).
# Input: (name, type hint, access, required, description).
# Output: (name, description).
COMPONENTS = {
    "pkInnerPoint": (
        "4f6d2b8a-1c3e-4a5b-9d7f-0e2c4a6b8d10",
        "pkInnerPt",
        "Point always inside a geometry (pole of inaccessibility of the XY outline).",
        (
            (
                "G",
                "GeometryBase",
                "item",
                True,
                "Closed curve, hatch, surface, brep, SubD or mesh",
            ),
            (
                "M",
                "bool",
                "item",
                False,
                "True: Z at mid height inside the object. False: Z = 0",
            ),
            (
                "B",
                "bool",
                "item",
                False,
                "True: only the biggest region. False: one point per region",
            ),
            ("A", "int", "item", False, "Accuracy 1-6 (precision = size / 10^A)"),
        ),
        (
            ("P", "Inner points"),
            ("D", "Distance from each point to the outline"),
        ),
    ),
    "pkMinBoundingBox": (
        "6a1e3c5b-2d4f-4b6c-8e9a-1f3d5b7c9e21",
        "pkMinBox",
        "Minimum-volume oriented bounding box.",
        (
            ("G", "GeometryBase", "list", True, "Geometry"),
            (
                "U",
                "bool",
                "item",
                False,
                "True: one box for all. False: one box per geometry",
            ),
            ("A", "int", "item", False, "Accuracy: 0 Fast, 1 Normal, 2 Precise"),
        ),
        (
            ("B", "Boxes"),
            ("V", "Volumes"),
        ),
    ),
    "pkMinBoundingRect": (
        "7b2f4d6c-3e5a-4c7d-9f0b-2a4e6c8d0f32",
        "pkMinRect",
        "Minimum bounding rectangle on the XY plane (Z = 0).",
        (
            ("G", "GeometryBase", "list", True, "Geometry"),
            (
                "U",
                "bool",
                "item",
                False,
                "True: one rectangle for all. False: one per geometry",
            ),
            (
                "P",
                "bool",
                "item",
                False,
                "True: minimize the perimeter. False: the area",
            ),
        ),
        (
            ("R", "Rectangles (local X along the rectangle width)"),
            ("A", "Areas"),
        ),
    ),
    "pkOrientToMinRect": (
        "8c3a5e7d-4f6b-4d8e-a01c-3b5f7d9e1a43",
        "pkOrient",
        "Rotates geometry around Z so the long side of its minimum XY "
        "rectangle is parallel to X or Y.",
        (
            ("G", "GeometryBase", "list", True, "Geometry"),
            ("Y", "bool", "item", False, "True: long side along Y. False: along X"),
            (
                "U",
                "bool",
                "item",
                False,
                "True: rotate all together. False: each on its own",
            ),
        ),
        (
            ("O", "Rotated geometry"),
            ("X", "Transformations (to apply to other geometry too)"),
        ),
    ),
}

PYTHON3_COMPONENT = Guid("719467e6-7cf5-4848-99b0-c5dd57e5442c")
GRASSHOPPER_PLUGIN = Guid("b45a29b1-4343-4035-989e-044e8580d9cf")


def _clr():
    """Loads the RhinoCode assemblies and returns the namespaces used here."""
    import clr

    for name in (
        "Rhino.Runtime.Code",
        "RhinoCodePlatform.Projects",
        "RhinoCodePlatform.Rhino3D",
        "RhinoCodePlatform.GH",
    ):
        clr.AddReference(name)
    import Rhino.Runtime.Code as rc
    import RhinoCodePlatform.Projects as rp

    return rc, rp


def _read_text(path):
    """Reads a UTF-8 text file."""
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _svg_set(name):
    """Returns the light/dark SVG icon set of an icon name.

    Args:
        name: Icon name without extension, e.g. ``"pkInnerPoint"``. The dark
            variant is ``<name>-dark.svg``; without it the light one is used.

    Returns:
        A ``Rhino.Runtime.Code.Display.SvgSet``.
    """
    from Rhino.Runtime.Code.Display import Svg, SvgSet

    light = Svg(_read_text(os.path.join(SVG_DIR, f"{name}.svg")))
    dark_path = os.path.join(SVG_DIR, f"{name}-dark.svg")
    dark = Svg(_read_text(dark_path)) if os.path.exists(dark_path) else light
    return SvgSet(light, dark)


def _language(rc, key):
    """Returns a registered RhinoCode language, loading it if needed.

    Args:
        rc: The ``Rhino.Runtime.Code`` namespace.
        key: Part of the language id, e.g. ``"pythonnet"`` or ``"gh1"``.

    Returns:
        The ``ILanguage``.
    """
    languages = rc.RhinoCode.Languages
    for waiting in languages.QueryAwaiting():
        if key in str(waiting.LanguageSpec):
            languages.WaitStatusComplete(waiting.LanguageSpec)
    return next(lang for lang in languages if key in str(lang.Id))


def project_version():
    """Reads the version from ``pyproject.toml`` (major.minor[.patch])."""
    text = _read_text(os.path.join(ROOT, "pyproject.toml"))
    return re.search(r'^version\s*=\s*"([^"]+)"', text, re.M).group(1)


def build_definition():
    """Writes ``pocketknife.gh`` with one Script component per GH script."""
    import Rhino

    Rhino.PlugIns.PlugIn.LoadPlugIn(GRASSHOPPER_PLUGIN)
    import Grasshopper
    from Grasshopper.Kernel import GH_Document, GH_DocumentIO, GH_ParamAccess
    from Grasshopper.Kernel import GH_ParameterSide as Side

    access = {"item": GH_ParamAccess.item, "list": GH_ParamAccess.list}
    document = GH_Document()
    for index, (name, spec) in enumerate(COMPONENTS.items()):
        instance_id, nickname, description, inputs, outputs = spec
        component = Grasshopper.Instances.ComponentServer.EmitObject(PYTHON3_COMPONENT)
        component.CreateAttributes()
        component.NewInstanceGuid(Guid(instance_id))
        component.Name = name
        component.NickName = nickname
        component.Description = description
        component.UsingStandardOutputParam = False

        for params in (component.Params.Input, component.Params.Output):
            for param in list(params):
                component.Params.UnregisterParameter(param)

        for i, (var, hint, acc, required, tip) in enumerate(inputs):
            param = component.CreateParameter(Side.Input, i)
            param.VariableName = var
            param.Name = var
            param.NickName = var
            param.Description = tip
            param.Access = access[acc]
            param.Optional = not required
            param.TypeHints.Select(hint)
            component.Params.RegisterInputParam(param)
        for i, (var, tip) in enumerate(outputs):
            param = component.CreateParameter(Side.Output, i)
            param.VariableName = var
            param.Name = var
            param.NickName = var
            param.Description = tip
            component.Params.RegisterOutputParam(param)

        component.SetSource(_read_text(os.path.join(ROOT, "grasshopper", f"{name}.py")))
        component.VariableParameterMaintenance()
        component.Params.OnParametersChanged()
        component.Attributes.Pivot = System.Drawing.PointF(100.0, 100.0 + 150 * index)
        document.AddObject(component, False)

    io = GH_DocumentIO(document)
    if not io.SaveQuiet(GH_PATH):
        raise RuntimeError(f"Could not save {GH_PATH}")
    return document


def _stable_id(name):
    """Returns a fixed GUID for a project item, derived from its name."""
    return Guid(str(uuid.uuid5(uuid.UUID(PROJECT_ID), name)))


def build_project():
    """Writes ``pocketknife.rhproj`` and returns the project."""
    rc, rp = _clr()
    from RhinoCodePlatform.GH import ScriptExposure

    server = next(iter(rc.RhinoCode.ProjectServers))
    project = server.CreateProject()
    project.Id = Guid(PROJECT_ID)

    # Identity: shown in the Package Manager and written to manifest.yml.
    identity = project.Identity
    identity.Name = PROJECT_NAME
    identity.Version = rc.Projects.ProjectVersion(project_version())
    identity.Description = DESCRIPTION
    identity.Copyright = COPYRIGHT
    identity.License = LICENSE
    identity.Url = Uri(URL)
    identity.Publisher = rc.Projects.PublisherIdentity(
        AUTHOR_EMAIL, AUTHOR, "", "", "", "", Uri(URL)
    )
    identity.Image = rp.Rhino3DProjectIdentityImageSet(_svg_set("pocketknife-logo"))

    # Shared library: `import pocketknife` from commands and components.
    project.Libraries.Add(
        _language(rc, "pythonnet").CreateLibrary(
            Uri(os.path.join(ROOT, "src", "pocketknife") + os.sep)
        )
    )

    folders = {path.Id: path for path in project.Traverse().GetPaths()}
    for name in COMMANDS:
        command = rp.Rhino3DCommand(
            rp.Rhino3DCommandKind.Normal,
            Uri(os.path.join(ROOT, "commands", f"{name}.py")),
        )
        command.Id = _stable_id(f"command:{name}")
        command = project.Add(folders[project.RhinoCommandsPathId], command)
        command.Title = name
        command.Image = _svg_set(name)

    source = rp.Rhino3DComponentSource(_language(rc, "gh1").CreateCode(Uri(GH_PATH)))
    source.Id = _stable_id("components:pocketknife.gh")
    source = project.Add(folders[project.GrasshopperPathId], source)
    names = {str(Guid(spec[0])): name for name, spec in COMPONENTS.items()}
    for component in source.GetEditableComponents():
        name = names[str(component.Id)]
        component.Title = name
        component.Nickname = COMPONENTS[name][1]
        component.Description = COMPONENTS[name][2]
        component.SubCategory = GH_SUBCATEGORY
        component.ScriptExposure = ScriptExposure.Level1
        component.Image = _svg_set(name)
        component.OnEdited()

    project.Store(rc.RhinoCode.StorageSites.CreateStorage(Uri(RHPROJ_PATH)))
    _make_paths_relative(RHPROJ_PATH)
    return project


def _make_paths_relative(path):
    """Rewrites the absolute ``file:///`` URIs of the project as relative paths.

    RhinoCode stores files outside the project folder with absolute URIs; the
    relative form (``../commands/x.py``) loads the same way and keeps the
    project usable from any clone of the repository.

    Args:
        path: Path of the ``.rhproj`` file.
    """
    text = _read_text(path)
    root_uri = Uri(ROOT + os.sep).AbsoluteUri  # file:///C:/.../pk-build/

    def relative(match):
        uri = match.group(1)
        target = os.path.normpath(Uri(uri).LocalPath)
        rel = os.path.relpath(target, PROJECT_DIR).replace(os.sep, "/")
        if uri.endswith("/"):
            rel += "/"
        return f'"{rel}"'

    pattern = r'"(' + re.escape(root_uri) + r'[^"]*)"'
    text = re.sub(pattern, relative, text)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main():
    """Builds the Grasshopper definition, then the project."""
    os.makedirs(PROJECT_DIR, exist_ok=True)
    build_definition()
    build_project()
    print(f"Written {GH_PATH}")
    print(f"Written {RHPROJ_PATH}")


if __name__ == "__main__":
    main()
