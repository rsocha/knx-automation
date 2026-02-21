#!/usr/bin/env python3
"""
KNX Automation License Key Generator

Usage:
    python generate_license.py <email> [days]
    
Example:
    python generate_license.py user@example.com 365
"""

import hashlib
import sys
from datetime import datetime, timedelta

# IMPORTANT: This must match LICENSE_SECRET in api/routes.py
LICENSE_SECRET = "KNX-AUTO-2024-SECRET"

def generate_license_key(email: str, valid_days: int = 365) -> dict:
    """Generate a license key for an email"""
    created = datetime.now()
    expires = created + timedelta(days=valid_days)
    
    # Create signature
    data = f"{email}:{created.isoformat()}:{expires.isoformat()}:{LICENSE_SECRET}"
    signature = hashlib.sha256(data.encode()).hexdigest()[:12].upper()
    
    # Format: KNX-XXXX-XXXX-XXXX
    key = f"KNX-{signature[:4]}-{signature[4:8]}-{signature[8:12]}"
    
    return {
        "key": key,
        "email": email,
        "created": created.isoformat(),
        "expires": expires.isoformat(),
        "valid_days": valid_days
    }

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    email = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 365
    
    license_data = generate_license_key(email, days)
    
    print("\n" + "="*50)
    print("  KNX Automation License Key")
    print("="*50)
    print(f"\n  Email:      {license_data['email']}")
    print(f"  Key:        {license_data['key']}")
    print(f"  Valid for:  {license_data['valid_days']} days")
    print(f"  Expires:    {license_data['expires'][:10]}")
    print("\n" + "="*50)
    print("\n  Aktivierung im Dashboard:")
    print(f"    1. Öffne http://dein-server:8000/")
    print(f"    2. Gib den Schlüssel und die E-Mail ein")
    print(f"    3. Klicke auf 'Lizenz aktivieren'")
    print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    main()
