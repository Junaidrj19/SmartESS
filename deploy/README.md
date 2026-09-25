# SmartESS scientific artifact package

The canonical investigation (`syn-mod-0042`, `inv-70207e0ffd15`) needs frozen M6–M8 artifacts, the Chroma evidence store, corpus PDFs, and stored investigation records. Those files are gitignored. They must be copied from a working host, not regenerated.

## Build the archive

On a host that already has the working artifacts:

```text
python3 scripts/package_scientific_artifacts.py
```

Produces:

- `deploy/smartess-scientific-artifacts.tar` — exact working files
- `deploy/scientific-artifacts.manifest` — SHA-256 and size of each file

The script does not train, score, evaluate, ingest, or rewrite investigations.

## Restore on a deployment host

From the repository root:

```text
tar -xf deploy/smartess-scientific-artifacts.tar
```

Then confirm `GET /readiness` reports every scientific artifact as `PRESENT`.
