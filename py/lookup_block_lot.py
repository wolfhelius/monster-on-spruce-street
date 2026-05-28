"""
lookup_block_lot.py
-------------------
Bulk address → Block/Lot lookup for NJ properties using the
NJ Geographic Information Network (NJGIN) public ArcGIS REST API.

Reads barsky_property_sites_v2.csv, fills in missing block/lot values,
writes barsky_property_sites_v3.csv.

Requirements:
    pip install requests pandas

Usage:
    python lookup_block_lot.py

Notes:
- Targets rows where block is blank (the 37 new RB Homes addresses
  plus any other rows still missing block/lot).
- Municipality code 1114 = Princeton (consolidated, post-2013 merger).
  For addresses in other towns, codes are set per TOWN column.
- The API returns current tax parcel data. Parcels that were
  subdivided or renumbered since the Barsky transactions may show
  the current lot number, not the historic one. Always cross-check
  against the deed instrument.
- Owner names are redacted per Daniel's Law; this script only
  retrieves block, lot, and address fields.
"""

import time
import re
import requests
import pandas as pd

# ── Municipality codes (NJ MOD-IV 4-digit codes) ──────────────────────────
MUN_CODES = {
    'Princeton':          '1114',   # consolidated since 2013
    'Hopewell Borough':   '1106',
    'Hopewell Township':  '1107',
    'Ewing Township':     '1103',
    'West Windsor':       '1116',
    'East Windsor':       '1202',   # Mercer County
    'Trenton':            '1115',
    'Robbinsville':       '1111',
    'Hamilton Township':  '1105',
    'Lawrence Township':  '1109',
    'Plainsboro':         '1118',   # Middlesex County — different dataset
    'Morristown':         '1401',   # Morris County — different dataset
}

# ── ArcGIS REST endpoint ───────────────────────────────────────────────────
# Service was renamed from Parcels_and_MOD_IV_Composite_of_NJ; field names also changed.
BASE_URL = (
    "https://services2.arcgis.com/XVOqAjTOJ5P6ngMu/ArcGIS/rest/services/"
    "Parcels_Composite_NJ_WM/FeatureServer/0/query"
)

OUT_FIELDS = "PCLBLOCK,PCLLOT,PCLQCODE,PROP_LOC,PAMS_PIN"


def parse_address(address: str):
    """
    Split '14 Bainbridge St' → ('14', 'BAINBRIDGE')
    Handles numeric prefixes including ranges like '63-65'.
    Returns (street_number, street_name_root).
    """
    address = address.strip()
    # Remove unit suffixes like 'Unit 2', '#3', etc.
    address = re.sub(r'\s+(unit|apt|#)\s*\S+', '', address, flags=re.IGNORECASE)
    # Match leading number (including ranges like 63-65)
    m = re.match(r'^([\d\-]+)\s+(.+)$', address)
    if not m:
        return None, address.upper()
    num = m.group(1)
    name_parts = m.group(2).upper().split()
    # Drop trailing street type for a broader search
    # (e.g. 'BAINBRIDGE ST' → search 'BAINBRIDGE')
    street_types = {
        'ST','STREET','AVE','AVENUE','RD','ROAD','DR','DRIVE','LN','LANE',
        'BLVD','BOULEVARD','CT','COURT','PL','PLACE','WAY','CIR','CIRCLE',
        'TERR','TER','TERRACE','HWY','HWY','PKWY','PIKE',
    }
    name_root = ' '.join(p for p in name_parts if p not in street_types)
    return num, name_root


def query_parcel(address: str, mun_code: str, session: requests.Session):
    """
    Query NJGIN API for a single address.
    Returns list of matching feature attribute dicts.
    """
    stno, stnam = parse_address(address)
    if not stno:
        print(f"  [WARN] Could not parse street number from: {address!r}")
        return []

    # PROP_LOC stores the full address string, e.g. "14 BAINBRIDGE STREET".
    # Use the first part of a hyphenated range for broader matching.
    first_num = stno.split('-')[0]
    where = (
        f"PCL_MUN='{mun_code}' "
        f"AND PROP_LOC LIKE '{first_num} %{stnam}%'"
    )

    params = {
        'where': where,
        'outFields': OUT_FIELDS,
        'returnGeometry': 'false',
        'f': 'json',
    }

    try:
        resp = session.get(BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if 'error' in data:
            print(f"  [API ERROR] {address}: {data['error']}")
            return []
        return [f['attributes'] for f in data.get('features', [])]
    except requests.RequestException as e:
        print(f"  [REQUEST ERROR] {address}: {e}")
        return []


def pick_best_match(features: list, address: str):
    """
    If multiple parcels returned, try to pick the best match.
    Usually there's only one; if multiple, prefer exact street number match.
    """
    if not features:
        return None
    if len(features) == 1:
        return features[0]
    # Try to match the exact street number at the start of PROP_LOC
    stno, _ = parse_address(address)
    exact = [f for f in features if str(f.get('PROP_LOC', '')).startswith(str(stno) + ' ')]
    if exact:
        return exact[0]
    return features[0]  # fall back to first


def main():
    input_file  = '../dat/barsky_property_sites_v2.csv'
    output_file = '../dat/barsky_property_sites_v3.csv'

    df = pd.read_csv(input_file, dtype=str).fillna('')

    # Target rows with missing block or flagged as needing lookup
    needs_lookup = df['block'].eq('') | df['status'].eq('BLOCK/LOT NEEDED')
    targets = df[needs_lookup].copy()
    print(f"Rows needing block/lot lookup: {len(targets)}")

    session = requests.Session()
    session.headers.update({'User-Agent': 'barsky-research/1.0'})

    results = []

    for idx, row in targets.iterrows():
        address = row['address']
        town    = row['town'] if row['town'] else 'Princeton'
        mun_code = MUN_CODES.get(town, '1114')

        print(f"  Querying: {address!r} (mun={mun_code}) ...", end=' ')

        features = query_parcel(address, mun_code, session)
        best     = pick_best_match(features, address)

        if best:
            block = str(best.get('PCLBLOCK', '')).lstrip('0') or ''
            lot   = str(best.get('PCLLOT',   '')).lstrip('0') or ''
            qcode = str(best.get('PCLQCODE', '')).strip()
            pams  = str(best.get('PAMS_PIN',  '')).strip()
            api_addr = str(best.get('PROP_LOC', '')).strip()
            print(f"→ Block {block}, Lot {lot}  [{api_addr}]")
            results.append({
                'idx': idx,
                'block': block,
                'lot': lot,
                'pams_pin': pams,
                'api_address': api_addr,
                'status': 'RECORDS GAP - SEARCH NEEDED'
                          if row['status'] == 'BLOCK/LOT NEEDED'
                          else row['status'],
                'notes': row['notes'],
            })
        else:
            print(f"→ NOT FOUND")
            results.append({
                'idx': idx,
                'block': '',
                'lot': '',
                'pams_pin': '',
                'api_address': '',
                'status': 'BLOCK/LOT NOT FOUND',
                'notes': row['notes'],
            })

        time.sleep(0.3)   # be polite to the API

    # Write results back to dataframe
    if 'pams_pin' not in df.columns:
        df.insert(df.columns.get_loc('block') + 2, 'pams_pin', '')
    if 'api_address' not in df.columns:
        df.insert(df.columns.get_loc('pams_pin') + 1, 'api_address', '')

    for r in results:
        i = r['idx']
        if r['block']:
            df.at[i, 'block']       = r['block']
            df.at[i, 'lot']         = r['lot']
            df.at[i, 'pams_pin']    = r['pams_pin']
            df.at[i, 'api_address'] = r['api_address']
        df.at[i, 'status'] = r['status']

    df.to_csv(output_file, index=False)
    print(f"\nDone. Written to {output_file}")
    print(f"  Resolved:    {sum(1 for r in results if r['block'])}")
    print(f"  Not found:   {sum(1 for r in results if not r['block'])}")


if __name__ == '__main__':
    main()
