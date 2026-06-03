"""Fix synthetic export.xml for lxml on Windows (DTD + device attribute quirks)."""
import re
import sys
from pathlib import Path

def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/export.xml")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "data/export.clean.xml")
    raw = src.read_bytes()
    raw = re.sub(br"<!DOCTYPE[^>]*\[.*?\]>", b"", raw, flags=re.DOTALL)
    raw = re.sub(br'device="<<[^"]*"', b'device="Apple Watch"', raw)
    raw = raw.decode("utf-8", errors="replace").encode("utf-8")
    out.write_bytes(raw)
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")

if __name__ == "__main__":
    main()
