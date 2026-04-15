#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ETL_DIR="$PROJECT_DIR/etl"

# Default export.xml location
EXPORT_XML="${1:-$PROJECT_DIR/data/export.xml}"

# Import method: "python" (Method 1, default) or "csv" (Method 2)
METHOD="${METHOD:-python}"

echo "=========================================="
echo " HealthGraph Agent — ETL Pipeline"
echo "=========================================="

# Check for export.xml — offer to generate synthetic data if missing
if [ ! -f "$EXPORT_XML" ]; then
    echo ""
    echo "No export.xml found at: $EXPORT_XML"
    echo ""

    if [ "${GENERATE:-}" = "1" ] || [ "${1:-}" = "--generate" ]; then
        PERSONA="${PERSONA:-biohacker}"
        DAYS="${DAYS:-365}"
        echo "Generating $DAYS days of synthetic data (persona: $PERSONA)..."
        cd "$ETL_DIR"
        python generate_test_data.py --days "$DAYS" --persona "$PERSONA" --output "$EXPORT_XML"
        echo ""
    else
        echo "Options:"
        echo ""
        echo "  A) Use your real Apple Health data:"
        echo "     iPhone → Health → Profile → Export All Health Data"
        echo "     Unzip export.zip and place export.xml in $PROJECT_DIR/data/"
        echo ""
        echo "  B) Generate 12 months of synthetic data:"
        echo "     GENERATE=1 bash scripts/run_pipeline.sh"
        echo ""
        echo "  Personas: default | athlete | sedentary | biohacker"
        echo "     GENERATE=1 PERSONA=athlete bash scripts/run_pipeline.sh"
        echo ""
        exit 1
    fi
fi

# Check dependencies
cd "$ETL_DIR"
echo ""
echo "Checking Python dependencies..."
pip install -q -r requirements.txt

# File info
FILE_SIZE=$(du -h "$EXPORT_XML" | cut -f1)
echo ""
echo "Input: $EXPORT_XML ($FILE_SIZE)"
echo "Import method: $METHOD"
echo ""

# =============================================
# METHOD 1: Direct Python ETL → Neo4j
# =============================================
if [ "$METHOD" = "python" ]; then
    # Check .env
    if [ ! -f "$PROJECT_DIR/.env" ]; then
        echo ""
        echo "Error: .env file not found"
        echo "  cp .env.example .env"
        echo "  Then fill in NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD"
        echo ""
        echo "  Neo4j Desktop:  NEO4J_URI=bolt://localhost:7687"
        echo "  Neo4j Aura:     NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io"
        exit 1
    fi

    # Option: dry run (parse + transform only, no Neo4j)
    if [ "${DRY_RUN:-}" = "1" ]; then
        echo "Running in DRY RUN mode (no Neo4j load)"
        python load_to_neo4j.py "$EXPORT_XML" --dry-run
        exit 0
    fi

    # Full pipeline
    echo "Starting full pipeline: Parse → Transform → Load to Neo4j"
    echo ""
    python load_to_neo4j.py "$EXPORT_XML"

    echo ""
    echo "=========================================="
    echo " Pipeline complete! (Method 1: Python ETL)"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo "  1. Open Neo4j Browser and check your graph"
    echo "  2. Run longevity queries: cypher/longevity_queries.cypher"
    echo "  3. Configure your Aura Agent (see agent/agent_config.md)"

# =============================================
# METHOD 2: Export to CSV → LOAD CSV in Browser
# =============================================
elif [ "$METHOD" = "csv" ]; then
    CSV_DIR="${CSV_DIR:-$PROJECT_DIR/data/csv}"
    echo "Starting CSV export: Parse → Transform → CSV files"
    echo "Output directory: $CSV_DIR"
    echo ""
    python export_to_csv.py "$EXPORT_XML" --output "$CSV_DIR"

    echo ""
    echo "=========================================="
    echo " CSV Export complete! (Method 2: LOAD CSV)"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo ""
    echo "  Neo4j Desktop:"
    echo "    1. Copy data/csv/*.csv into your database's import/ directory"
    echo "       (Find it: Neo4j Desktop → ... → Open folder → Import)"
    echo "    2. Open Neo4j Browser"
    echo "    3. Run each block of cypher/load_csv_import.cypher one at a time"
    echo ""
    echo "  Neo4j Aura:"
    echo "    1. Upload CSVs to a publicly accessible URL"
    echo "    2. Edit cypher/load_csv_import.cypher:"
    echo "       Replace 'file:///' with your URL prefix"
    echo "    3. Run each block in the Aura Query console"
else
    echo "Error: Unknown METHOD=$METHOD (use 'python' or 'csv')"
    exit 1
fi
