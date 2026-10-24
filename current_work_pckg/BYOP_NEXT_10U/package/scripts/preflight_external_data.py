#!/usr/bin/env python3
"""Read-only preflight. External raw/processed are never edited or included in outgoing ZIP."""
from __future__ import annotations
from pathlib import Path
import argparse,csv,hashlib,json,re,sys

FILES = {
    'poi_e0_evidence_classified.csv':None,
    'poi_equipment_proxy_schedule.csv':None,
    'poi_site_release_parameters.csv':16,
    'poi_engineering_parameters.csv':None,
    'poi_demand_visibility.csv':160,
    'poi_investment_candidates.csv':320,
    'engineering_baseline.json':None,
}

def sha(p:Path):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def desc(p:Path):
    if p.suffix.lower()=='.csv':
        with p.open('r',encoding='utf-8-sig',newline='') as f:
            reader=csv.reader(f);hdr=next(reader,[]);n=sum(1 for _ in reader)
        return len(hdr),n,','.join(hdr)
    if p.suffix.lower()=='.json':
        with p.open('r',encoding='utf-8') as f: j=json.load(f)
        return len(j) if hasattr(j,'__len__') else 0,-1,','.join(j.keys()) if isinstance(j,dict) else ''
    return -1,-1,''

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data-dir',default='engineering_data');ap.add_argument('--out-dir',default='manifest/local_preflight');args=ap.parse_args()
    d=Path(args.data_dir).resolve(); out=Path(args.out_dir).resolve();out.mkdir(parents=True,exist_ok=True)
    reqroots=[d/'raw',d/'processed']
    optional_roots=[d/'reference']
    scanroots=reqroots+[x for x in optional_roots if x.exists()]
    findings=[]; inventory=[]; required=[]
    for sub in scanroots:
        if not sub.is_dir() and sub in reqroots: findings.append(f'MISSING_DIRECTORY {sub}')
        else:
            for p in sorted(sub.rglob('*')):
                if not p.is_file() or p.name.startswith('PUT_ORIGINAL_'):continue
                try: rel=p.relative_to(d).as_posix();size=p.stat().st_size; digest=sha(p)
                except Exception as ex:findings.append(f'UNREADABLE {p}: {ex}');continue
                inventory.append((rel,sub.name,size,digest))
    for name,expect in FILES.items():
        matches=[x for x in inventory if Path(x[0]).name.lower()==name.lower()]
        matched=[]
        for rel,sub,size,digest in matches:
            try:
                cols,n,header=desc(d/rel)
                matched.append(dict(path=rel,sha256=digest,rows=n,columns=cols,header=header))
                if expect is not None and n!=expect: findings.append(f'ROW_COUNT_REVIEW {name} {rel} {n} vs expected_history={expect}')
            except Exception as ex:findings.append(f'SCHEMA_ERROR {rel}: {ex}')
        if not matches: findings.append(('OPTIONAL_PROVENANCE_MISSING ' if name == 'engineering_baseline.json' else 'REQUIRED_MISSING ')+name)
        if len(matches)>1: findings.append('DUPLICATE_NAME_REQUIRES_SHA_RESOLUTION '+name)
        required.append(dict(filename=name,match_count=len(matches),matches=matched,historical_rows=expect))
    with (out/'INPUT_FILE_SHA256.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.writer(f);w.writerow(['relative_path','layer','bytes','sha256']);w.writerows(inventory)
    (out/'REQUIRED_INPUT_MATCHES.json').write_text(json.dumps(required,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'PRECHECK_FINDINGS.txt').write_text('\n'.join(findings)+'\n',encoding='utf-8')
    print(json.dumps({'files_scanned':len(inventory),'required_files':len(required),'findings':len(findings),'status':'REVIEW' if findings else 'PASS','out_dir':str(out)},ensure_ascii=False))
    if not inventory or any(x.startswith(('MISSING_DIRECTORY','REQUIRED_MISSING','DUPLICATE_NAME_REQUIRES_SHA_RESOLUTION','UNREADABLE','SCHEMA_ERROR')) for x in findings):return 2
    return 0
if __name__=='__main__':sys.exit(main())
