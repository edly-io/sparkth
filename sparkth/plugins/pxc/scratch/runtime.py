"""The runtime a scratch run drives: one throwaway course, activity instance and learner."""

from pathlib import Path

from pxc.lib.field_store import MemoryKVStore
from pxc.lib.file_storage import MemoryFileStorage
from pxc.lib.permission import Permission
from pxc.lib.runtime import ActivityRuntime

from sparkth.plugins.pxc.constants import PXC_SCRATCH_CONTEXT_ID


def scratch_runtime(directory: Path, store: MemoryKVStore, permission: Permission) -> ActivityRuntime:
    """A runtime for the activity in ``directory`` on ``store``, as the throwaway learner."""
    return ActivityRuntime(
        directory,
        store,
        MemoryFileStorage(),
        PXC_SCRATCH_CONTEXT_ID,
        PXC_SCRATCH_CONTEXT_ID,
        PXC_SCRATCH_CONTEXT_ID,
        permission,
    )
