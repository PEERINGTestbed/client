# Migration Plan: Refactoring `peering.py` into a Standalone Python Package

**Objective:** Transition the monolithic `peering.py` script into a structured, installable Python package (`peering/`). This package will be **moved to a separate repository** (`client-pylib`) to act as a standalone library. This improves maintainability, separates concerns (data, logic, CLI), and eliminates the need for `sys.path.append` hacks.

**Note:** The `ExperimentController` functionality will be dropped entirely during this migration. Downstream scripts will not be updated as part of this specific migration effort.

Furthermore, to remove the runtime dependency on the `basedir` of configurations, the package build process will use a `hatchling` build hook to parse the OpenVPN configurations during packaging and bake the `mux2id` mapping directly into a Python module.

---

## 1. Directory Structure Changes

The standalone repository (`client-pylib`) will have the following structure:

```text
client-pylib/
├── pyproject.toml       # Hatchling configuration
├── hatch_build.py       # Custom build hook to generate data modules
├── peering/             # Package directory
│   ├── __init__.py      # Exposes the public API
│   ├── _mux_data.py     # AUTO-GENERATED during build
│   ├── models.py        # Pydantic data structures
│   ├── constants.py     # Static mappings and BGP community factories
│   ├── utils.py         # Pure helper functions
│   ├── controllers/     # Core logic
│   │   ├── __init__.py
│   │   └── announcement.py
│   └── cli.py           # Argument parsing and main execution
```

*(Note: `experiment.py` and `ExperimentController` are omitted)*

---

## 2. Implement the Build Hook (`hatch_build.py`)

Since the package is standalone, it needs to access the PEERING OpenVPN configurations during the build to generate `_mux_data.py`. We will pass the configuration directory via an environment variable (`PEERING_OPENVPN_CONFIG_DIR`).

Create `hatch_build.py` in the package root:

```python
import os
import pathlib
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        config_dir = os.environ.get("PEERING_OPENVPN_CONFIG_DIR")
        if not config_dir:
            raise ValueError("PEERING_OPENVPN_CONFIG_DIR environment variable must be set during build")
        
        config_path = pathlib.Path(config_dir)
        mux_to_id = self._build_mux2id(config_path)
        
        target_file = pathlib.Path(__file__).parent / "peering" / "_mux_data.py"
        with open(target_file, "w") as f:
            f.write("# AUTO-GENERATED DURING BUILD\n")
            f.write(f"MUX_TO_ID = {repr(mux_to_id)}\n")

    def _build_mux2id(self, config_dir: pathlib.Path):
        # Implementation will parse .conf files in config_dir 
        # and return a dict mapping mux string to ID
        pass
```

The `DataPlane` class will then import the baked-in mapping, removing its dependency on `basedir`:

```python
from peering._mux_data import MUX_TO_ID

class DataPlane:
    def __init__(self, base_table_num: int = 1000) -> None:
        self.base_table_num = base_table_num

    @property
    def mux2id(self) -> dict:
        return MUX_TO_ID
```

---

## 3. Package Configuration (`pyproject.toml`)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "peering"
version = "0.1.0"
description = "PEERING Client configuration and deployment tools"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "pydantic",
    "requests",
]

[project.scripts]
peering = "peering.cli:main"

[tool.hatch.build.hooks.custom]
path = "hatch_build.py"
```

---

## 4. Implement the Public API Facade (`peering/__init__.py`)

```python
from .constants import MuxName, MUX_SETS, Vultr, PeeringCommunities
from .models import Announcement, Update, UpdateSet, ControllerConfig
from .utils import get_prio_offset, protocol_to_peerid_asn
from .controllers.announcement import AnnouncementController

__all__ = [
    "MuxName", "MUX_SETS", "Vultr", "PeeringCommunities",
    "Announcement", "Update", "UpdateSet", "ControllerConfig",
    "get_prio_offset", "protocol_to_peerid_asn",
    "AnnouncementController"
]
```

---

## 5. Installation

To install the standalone package in a development environment:

```bash
# Example installation using the configurations from the client repo
PEERING_OPENVPN_CONFIG_DIR=/path/to/client/configs/openvpn uv pip install -e /path/to/client-pylib/
```

Once the migration is complete and verified, the original `peering.py` script will be removed from the `client` repository.
