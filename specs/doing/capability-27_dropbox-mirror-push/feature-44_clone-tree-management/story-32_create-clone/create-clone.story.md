# Story: Create Clone from Snapshot

## Observable Outcome

A clone can be created from a ZFS snapshot with proper mountpoint, readonly flag, and management property. The clone can be identified as belonging to cloud-mirror for safe cleanup.

## Functional Requirements

### FR1: Create clone with management property

```gherkin
GIVEN snapshot testpool/data@snap exists
WHEN create_clone(dataset, snapshot_name, clone_dataset, mountpoint, logger) called
THEN clone is created at clone_dataset
AND clone has mountpoint set correctly
AND clone is readonly
AND clone has property ch.srvr.cloudmirror:managed=true
```

### FR2: Identify our clones

```gherkin
GIVEN dataset with ch.srvr.cloudmirror:managed=true property
WHEN is_our_clone(dataset, logger) called
THEN returns True

GIVEN dataset without our management property
WHEN is_our_clone(dataset, logger) called
THEN returns False
```

### FR3: Get clone names from source

```gherkin
GIVEN dataset testpool/data
WHEN get_clone_dataset_name(dataset) called
THEN returns testpool/data.cloudmirror

GIVEN mountpoint /testpool/data
WHEN get_clone_mountpoint(mountpoint) called
THEN returns /testpool/data.cloudmirror
```

## Implementation Notes

- Clone suffix: `.cloudmirror`
- ZFS user property: `ch.srvr.cloudmirror:managed=true`
- Must handle altroot (TrueNAS SCALE sets altroot=/mnt on pools)
