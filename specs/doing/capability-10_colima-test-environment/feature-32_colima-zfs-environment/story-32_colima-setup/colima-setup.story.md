# Story: Colima Setup

## Functional Requirements

### FR1: Colima installed and configured for Ubuntu VM

```gherkin
GIVEN macOS with Homebrew installed
WHEN colima is installed via brew
THEN colima command is available
AND lima dependency is installed
```

#### Files created/modified

1. `docs/development-setup.md` [new]: Document Colima installation and configuration steps

**Test Validation:**

1. Manual verification: `which colima` returns path
2. Integration test: `specs/doing/capability-10_docker-test-environment/feature-32_colima-zfs-environment/story-32_colima-setup/tests/test_colima_setup.py`

### FR2: Colima starts with sufficient resources

```gherkin
GIVEN Colima installed
WHEN colima start executed with:
  | option   | value |
  | --cpu    | 4     |
  | --memory | 8     |
  | --disk   | 60    |
THEN VM starts successfully
AND resources are allocated as specified
```

#### Files created/modified

1. `scripts/start-test-vm.sh` [new]: Script to start Colima with correct settings

### FR3: Colima VM accessible via SSH

```gherkin
GIVEN Colima VM running
WHEN colima ssh executed
THEN shell access to Ubuntu VM is available
AND apt-get and other Ubuntu tools work
```

## Quality Requirements

### QR1: Startup time

**Requirement:** VM should start within reasonable time
**Target:** < 60 seconds for cold start
**Validation:** Manual timing of colima start

### QR2: Resource efficiency

**Requirement:** VM should not consume excessive resources when idle
**Target:** < 1GB memory when no tests running
**Validation:** Activity Monitor observation
