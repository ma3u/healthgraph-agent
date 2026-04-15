# How to export your Apple Health data

## Steps

1. Open the **Health** app on your iPhone
2. Tap your **profile picture** (or initials) in the top-right corner
3. Scroll down and tap **Export All Health Data**
4. Confirm the export — this can take several minutes depending on how much data you have
5. When ready, share the `export.zip` file to yourself (AirDrop, Files, Mail, or iCloud Drive)

## What you get

The zip file contains:

```
apple_health_export/
├── export.xml              ← Main file (100MB - 2GB+)
├── export_cda.xml          ← Clinical documents (if any)
├── electrocardiograms/     ← ECG PDFs (if recorded)
├── workout-routes/         ← GPX files per workout
└── clinical-records/       ← JSON files from health providers
```

## For this project

1. Unzip `export.zip`
2. Place `export.xml` in the `data/` directory of this repo (it's gitignored)
3. Run the pipeline: `bash scripts/run_pipeline.sh`

## File size notes

- 1 year of Apple Watch data ≈ 100-300MB XML
- 5+ years ≈ 500MB - 2GB+
- The importer uses streaming XML parsing, so it handles any size without loading everything into memory

## Known Apple bugs

Apple's XML export has a few known issues that our parser handles automatically:

- **Broken DTD**: The embedded DTD has syntax errors — we skip DTD validation entirely
- **Duplicate attributes**: Some records have `startDate` listed twice — we use a fault-tolerant parser
- **Timezone inconsistency**: Timestamps include timezone offsets but may not account for DST correctly
