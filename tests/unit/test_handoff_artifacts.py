import hashlib,json
from pathlib import Path

ROOT=Path(__file__).parents[2]

def test_regression_inputs_have_43_distinct_verified_approved_cases():
    kit=ROOT/'tools'/'regression'/'gstarcad'
    cases=json.loads((kit/'inputs-manifest.json').read_text(encoding='utf-8'))['cases']
    assert len(cases)==len({c['file'] for c in cases})==43
    originals=[c for c in cases if c['state']=='original']
    assert len(originals)==13
    approved={json.loads(p.read_text(encoding='utf-8'))['source']['sha256'].upper() for p in (ROOT/'template_profiles').glob('*.json')}
    assert {c['sha256'].upper() for c in originals}==approved
    for case in cases:
        assert hashlib.sha256((kit/'inputs'/case['file']).read_bytes()).hexdigest().upper()==case['sha256'].upper()
        assert len(case['window'])==4 and case['rotation'] in (0,90,180,270)

def test_public_evidence_exact_bytes_match_checksum_manifest():
    folder=ROOT/'validation'/'autocad-2021-pc-b'
    checks=json.loads((folder/'checksums.json').read_text(encoding='utf-8'))
    assert checks and len(list((folder/'pdfs').rglob('*.pdf')))==86
    for name,expected in checks.items():
        assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==expected,name
