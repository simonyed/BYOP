from pathlib import Path
import hashlib,json,zipfile,shutil
R=Path(__file__).resolve().parent
entries={
'Native_Load_2025.zip':('https://www.ercot.com/files/docs/2025/02/11/Native_Load_2025.zip','2025 actual hourly load; published/revised 2026-02-04'),
'Native_Load_2025.xlsx':('https://www.ercot.com/files/docs/2025/02/11/Native_Load_2025.zip','Unmodified XLSX extracted from ZIP; identical SHA to repository input'),
'ERCOT_2025_Annual_Report.pdf':('https://www.ercot.com/files/docs/2026/03/19/2025-ERCOT-Annual-Report-Final-Single-Pages-March-19-2026.pdf','2025 retrospective; broad installed ratings, printed page 6'),
'Capacity_December2025.xlsx':('https://www.ercot.com/files/docs/2026/01/08/Capacity-Changes-by-Fuel-Type-Charts_December_2025.xlsx','December 2025 snapshot, published January 2026'),
'Capacity_November2025.xlsx':('https://www.ercot.com/files/docs/2025/12/04/Capacity-Changes-by-Fuel-Type-Charts_November_2025.xlsx','November snapshot; not year-end'),
'CDR_December2025.xlsx':('https://www.ercot.com/files/docs/2025/12/19/CapacityDemandandReservesReport_December2025.xlsx','December CDR; includes planned units and future seasonal capabilities'),
'IntGenbyFuel2025.xlsx':('https://www.ercot.com/files/docs/2025/02/07/IntGenbyFuel2025.xlsx','2025 settlement fuel mix; archive page update 2026-03-09'),
'MORA_August2025.xlsx':('https://www.ercot.com/files/docs/2025/06/05/MORA_August2025.xlsx','Ex-ante August forecast, not actual annual reliability'),
'ERCOT_Monthly_December2025.pdf':('https://www.ercot.com/files/docs/2026/01/20/ERCOT-Monthly-December-2025-FINAL.pdf','December issue with November lookback; supporting only'),
'ERCOT_Constraints_Needs_2025.pdf':('https://www.ercot.com/files/docs/2025/12/23/2025-Report-on-Existing-and-Potential-Electric-System-Constraints-and-Needs.pdf','2025 report; historical constraints Oct 2024 to Sep 2025')}
sources=[]
for n,(u,note) in entries.items():
 p=R/'raw'/n
 assert p.is_file(),n
 sources.append(dict(file='raw/'+n,url=u,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size,notes=note,retrieved_on='2026-10-22'))
(R/'SOURCE_MANIFEST.json').write_text(json.dumps(dict(repo_sha='7a7eb2683a1d91840060616ecb31b76623223ed7',sources=sources),indent=2)+'\n')
paths=[p for p in R.rglob('*') if p.is_file() and p.name!='CHECKSUMS.sha256']
(R/'CHECKSUMS.sha256').write_text('\n'.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(R)}' for p in sorted(paths))+'\n')
out=R.parent/'deliverables';out.mkdir(exist_ok=True)
md=out/'ERCOT_2025_Official_Anchor_Evidence_and_Execution_v1.3.md'
shutil.copyfile(R/'README_AND_EXECUTION_PROMPT_v1.3.md',md)
z=out/'ERCOT_2025_Official_Anchor_Evidence_Package_v1.3.zip'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as archive:
 for p in sorted(R.rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts:archive.write(p,'ERCOT_2025_Official_Anchor_v1.3/'+str(p.relative_to(R)))
with zipfile.ZipFile(z) as archive:
 assert archive.testzip() is None
 print(json.dumps(dict(zip=str(z),bytes=z.stat().st_size,files=len(archive.namelist()),md=str(md)),indent=2))
