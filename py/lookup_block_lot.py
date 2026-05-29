"""
lookup_block_lot.py
-------------------
Bulk address → Block/Lot lookup for NJ properties using the
NJ Geographic Information Network (NJGIN) public ArcGIS REST API.

Reads barsky_property_sites_v3.csv, fills in missing block/lot and all
tax-record fields (owner address, assessed value, deed info, etc.),
writes barsky_property_sites_v4.csv.

Requirements:
    pip install requests pandas

Usage:
    python lookup_block_lot.py

Notes:
- Rows already having block/lot are queried by block/lot (precise).
- Rows missing block/lot are queried by address (fuzzy PROP_LOC match).
- Rows where api_address is already populated are skipped (idempotent).
- Municipality code 1114 = Princeton (consolidated, post-2013 merger).
  For addresses in other towns, codes are set per TOWN column.
- The API returns current tax parcel data. Parcels that were
  subdivided or renumbered since the Barsky transactions may show
  the current lot number, not the historic one. Always cross-check
  against the deed instrument.
- Owner names are redacted per Daniel's Law; owner mailing address
  (ST_ADDRESS / CITY_STATE) is present and populated.
"""

import time
import re
import requests
import pandas as pd

# ── Municipality codes (NJ MOD-IV 4-digit codes) ──────────────────────────
MUN_CODES = {
    'Princeton':          '1114',   # consolidated since 2013
    'Hopewell Borough':   '1105',
    'Hopewell Township':  '1106',
    'Ewing Township':     '1102',
    'West Windsor':       '1115',
    'East Windsor':       '1201',   # Mercer County
    'Trenton':            '1111',
    'Robbinsville':       '1110',
    'Hamilton Township':  '1104',
    'Lawrence Township':  '1108',
    'Plainsboro':         '1117',   # Middlesex County — different dataset
    'Morristown':         '1401',   # Morris County — different dataset
}

# ── ArcGIS REST endpoint ───────────────────────────────────────────────────
# Service was renamed from Parcels_and_MOD_IV_Composite_of_NJ; field names also changed.
BASE_URL = (
    "https://services2.arcgis.com/XVOqAjTOJ5P6ngMu/ArcGIS/rest/services/"
    "Parcels_Composite_NJ_WM/FeatureServer/0/query"
)

OUT_FIELDS = (
    "PCLBLOCK,PCLLOT,PCLQCODE,PROP_LOC,PAMS_PIN,"
    "ST_ADDRESS,CITY_STATE,ZIP_CODE,"
    "NET_VALUE,LAST_YR_TX,SALE_PRICE,"
    "DEED_BOOK,DEED_PAGE,DEED_DATE,"
    "YR_CONSTR,DWELL,PROP_CLASS,CALC_ACRE,BLDG_DESC"
)


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


def _normalize(val: str) -> str:
    """Strip trailing .0 from whole-number block/lot values (artifact of CSV float storage)."""
    try:
        f = float(val)
        return str(int(f)) if f == int(f) else val
    except (ValueError, OverflowError):
        return val


def query_parcel_by_block_lot(block: str, lot: str, mun_code: str, session: requests.Session):
    """
    Query NJGIN API by block/lot — precise lookup for rows that already
    have known block/lot values. Uses the first lot if the field contains
    a comma-separated list.
    """
    first_lot = _normalize(lot.split(',')[0].strip())
    block     = _normalize(block)
    where = f"PCL_MUN='{mun_code}' AND PCLBLOCK='{block}' AND PCLLOT='{first_lot}'"
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
            print(f"  [API ERROR] block {block} lot {first_lot}: {data['error']}")
            return []
        return [f['attributes'] for f in data.get('features', [])]
    except requests.RequestException as e:
        print(f"  [REQUEST ERROR] block {block} lot {first_lot}: {e}")
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
    input_file  = '../dat/barsky_property_sites_v3.csv'
    output_file = '../dat/barsky_property_sites_v4.csv'

    df = pd.read_csv(input_file, dtype=str).fillna('')

    # Target every row that hasn't been enriched yet (api_address still blank)
    needs_lookup = df['api_address'].eq('')
    targets = df[needs_lookup].copy()
    print(f"Rows needing API enrichment: {len(targets)}")

    session = requests.Session()
    session.headers.update({'User-Agent': 'barsky-research/1.0'})

    results = []

    for idx, row in targets.iterrows():
        address  = row['address']
        town     = row['town'] if row['town'] else 'Princeton'
        mun_code = MUN_CODES.get(town, '1114')
        block    = row['block'].strip()
        lot      = row['lot'].strip()

        have_block_lot = bool(block and lot)

        if have_block_lot:
            print(f"  Querying by block/lot: {address!r} (block={block}, lot={lot}) ...", end=' ')
            features = query_parcel_by_block_lot(block, lot, mun_code, session)
        else:
            print(f"  Querying by address: {address!r} (mun={mun_code}) ...", end=' ')
            features = query_parcel(address, mun_code, session)

        best = pick_best_match(features, address)

        if best:
            api_block = str(best.get('PCLBLOCK', '')).lstrip('0') or ''
            api_lot   = str(best.get('PCLLOT',   '')).lstrip('0') or ''
            pams      = str(best.get('PAMS_PIN', '') or '').strip()
            api_addr  = str(best.get('PROP_LOC', '') or '').strip()
            raw_date  = str(best.get('DEED_DATE', '') or '').strip()
            deed_date = (
                f"20{raw_date[0:2]}-{raw_date[2:4]}-{raw_date[4:6]}"
                if len(raw_date) == 6 else raw_date
            )
            print(f"→ Block {api_block}, Lot {api_lot}  [{api_addr}]")
            results.append({
                'idx':            idx,
                'found':          True,
                'block':          api_block,
                'lot':            api_lot,
                'pams_pin':       pams,
                'api_address':    api_addr,
                'owner_street':   str(best.get('ST_ADDRESS', '') or '').strip(),
                'owner_city_st':  str(best.get('CITY_STATE', '') or '').strip(),
                'net_value':      str(best.get('NET_VALUE',  '') or ''),
                'last_yr_tax':    str(best.get('LAST_YR_TX', '') or ''),
                'sale_price':     str(best.get('SALE_PRICE', '') or ''),
                'deed_book':      str(best.get('DEED_BOOK',  '') or '').strip(),
                'deed_page':      str(best.get('DEED_PAGE',  '') or '').strip(),
                'deed_date':      deed_date,
                'yr_constr':      str(best.get('YR_CONSTR',  '') or ''),
                'dwell_units':    str(best.get('DWELL',       '') or ''),
                'prop_class':     str(best.get('PROP_CLASS', '') or '').strip(),
                'calc_acre':      str(best.get('CALC_ACRE',  '') or ''),
                'bldg_desc':      str(best.get('BLDG_DESC',  '') or '').strip(),
                'status': 'RECORDS GAP - SEARCH NEEDED'
                          if row['status'] == 'BLOCK/LOT NEEDED'
                          else row['status'],
            })
        else:
            print(f"→ NOT FOUND")
            new_status = 'BLOCK/LOT NOT FOUND' if not have_block_lot else row['status']
            results.append({
                'idx': idx, 'found': False,
                'status': new_status,
            })

        time.sleep(0.3)   # be polite to the API

    # Ensure all API-derived columns exist in the right order after 'lot'
    api_cols = [
        'pams_pin', 'api_address',
        'owner_street', 'owner_city_st',
        'net_value', 'last_yr_tax', 'sale_price',
        'deed_book', 'deed_page', 'deed_date',
        'yr_constr', 'dwell_units', 'prop_class', 'calc_acre', 'bldg_desc',
    ]
    insert_after = df.columns.get_loc('lot') + 1
    for col in api_cols:
        if col not in df.columns:
            df.insert(insert_after, col, '')
        insert_after = df.columns.get_loc(col) + 1

    for r in results:
        i = r['idx']
        df.at[i, 'status'] = r['status']
        if not r['found']:
            continue
        # Only overwrite block/lot if the row didn't already have them
        if not df.at[i, 'block']:
            df.at[i, 'block'] = r['block']
        if not df.at[i, 'lot']:
            df.at[i, 'lot'] = r['lot']
        for col in api_cols:
            if r.get(col, '') != '':
                df.at[i, col] = r[col]

    df.to_csv(output_file, index=False)
    print(f"\nDone. Written to {output_file}")
    print(f"  Enriched:    {sum(1 for r in results if r['found'])}")
    print(f"  Not found:   {sum(1 for r in results if not r['found'])}")


if __name__ == '__main__':
    main()
