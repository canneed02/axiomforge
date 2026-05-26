# Phase 0 Execution

## Objective

Create a real independent AxiomForge kernel that can run on the server without
depending on LiveProof.

## Deliverables

- Python package
- CLI
- event log
- SQLite registry
- local lab-note publisher
- publication policy gate
- tests
- systemd service and timer
- server deployment

## Verification

Local:

```bash
python3 -m unittest discover -s tests
python3 -m py_compile src/axiomforge/*.py
```

Server:

```bash
axiomforge init --root /root/axiomforge-state
axiomforge cycle --root /root/axiomforge-state --goal "bootstrap autonomous research memory"
axiomforge status --root /root/axiomforge-state
```

## Completion Criteria

Phase 0 is complete when:

- tests pass locally
- server package installs
- server bootstrap cycle publishes a lab note
- systemd timer is active
- state is separate from LiveProof
- old LiveProof autonomous timer is disabled

