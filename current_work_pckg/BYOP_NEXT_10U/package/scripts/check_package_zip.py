#!/usr/bin/env python3
"""Reject bundled big raw/processed payloads; valid ZIP has only placeholder markers."""
from pathlib import Path
import sys,zipfile
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path('BYOP_NEXT_10U_Engineering_POI_Cost_Autonomous.zip')
assert p.exists(),p
with zipfile.ZipFile(p) as z:
    bad=z.testzip();assert bad is None,bad
    folders=('/engineering_data/raw/','/engineering_data/processed/')
    embedded=[i.filename for i in z.infolist() if any(f in i.filename for f in folders) and not (i.filename.endswith('/') or i.filename.endswith(('PUT_ORIGINAL_RAW_HERE.txt','PUT_ORIGINAL_PROCESSED_HERE.txt')))]
    assert not embedded, f'Payload data bundled: {embedded[:10]}'
    print('ZIP_SELFTEST_PASS',len(z.infolist()),'entries; raw/processed only placeholder markers')
