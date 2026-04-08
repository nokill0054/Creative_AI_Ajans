import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools import airtable, config

def main():
    print("\n" + "=" * 55)
    print("  Airtable Schema Synchronizer")
    print("=" * 55 + "\n")

    # Check credentials
    missing = config.check_credentials()
    if missing:
        print("Missing API keys in .claude/.env")
        sys.exit(1)

    try:
        updated = airtable.sync_status_fields()
        if updated:
            print(f"\n  Successfully updated: {', '.join(updated)}")
            print("  Airtable schema is now in sync with the backend.")
        else:
            print("\n  No fields were updated.")
            
    except Exception as e:
        print(f"\n  Error: {e}")
        print("\n  Tip: Ensure your Airtable PAT has 'schema.bases:write' scope.")
        sys.exit(1)

if __name__ == "__main__":
    main()
