"""Opt-in working-copy probe for structural matching and viewport invariance."""
import argparse
import json
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import pythoncom
from win32com.client import VARIANT
from dwg_to_pdf.gstarcad.com_session import GstarSession, _gstar_pids
from dwg_to_pdf.gstarcad.template_detector import _bounded_text_and_insert_snapshots, DetectionLimits, verify_rotation
from dwg_to_pdf.domain import Point, ScaleCandidate
from dwg_to_pdf.templates.plot_window_transform import compute_candidate
from dwg_to_pdf.templates.profile_store import ProfileStore
from dwg_to_pdf.temp_workspace import SourceWorkspace, sha256


def main():
    p = argparse.ArgumentParser()
    p.add_argument('source', type=Path)
    p.add_argument('--source-root', type=Path, required=True)
    p.add_argument('--result', type=Path, required=True)
    p.add_argument('--view-probe', action='store_true')
    p.add_argument('--layout-probe', action='store_true')
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    store = ProfileStore(root / 'template_profiles', source_root=args.source_root)
    store.load_all()
    before = (sha256(args.source), args.source.stat().st_mtime_ns)
    pids = _gstar_pids()
    result = {'states': []}
    with GstarSession('GStarCAD.Application.26') as session:
        result['owned_pid'] = session.owned_pid
        with SourceWorkspace(args.source) as ws:
            with session.working_document(ws) as doc:
                states = ['original', 'shifted-ucs-offscreen'] if args.view_probe else ['original']
                if args.layout_probe:
                    states.insert(1, 'foreign-layout')
                for state in states:
                    point = lambda xyz: VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, xyz)
                    if state == 'foreign-layout':
                        active = doc.raw.ActiveLayout
                        foreign = doc.raw.Layouts.Add('DWGP_FOREIGN')
                        foreign.Block.AddText('Scale', point((anchor.x,anchor.y,0.)), 1.)
                        for a,b in best_signature:
                            foreign.Block.AddLine(point((a.x,a.y,0.)),point((b.x,b.y,0.)))
                        doc.raw.ActiveLayout = active
                    if state == 'shifted-ucs-offscreen':
                        ucs = doc.raw.UserCoordinateSystems.Add(point((123456.,654321.,0.)),
                            point((123456.,654322.,0.)), point((123455.,654321.,0.)), 'DWGP_PROBE')
                        doc.raw.ActiveUCS = ucs
                        session.app.ZoomWindow(point((1e8,1e8,0.)), point((1e8+100,1e8+100,0.)))
                    doc._geometry_cache.clear()
                    doc._bulk_raw = None
                    items = _bounded_text_and_insert_snapshots(doc, DetectionLimits(64,5000))
                    label = next(v for v in items if str(v.get('text','')).strip().casefold() == 'scale')
                    anchor = Point(*label['point'])
                    scores = []
                    for profile in store.all():
                        for rotation in (0,90,180,270):
                            candidate = compute_candidate(profile, ScaleCandidate(anchor,'',label['handle']),rotation)
                            score = verify_rotation(doc,profile,candidate)
                            expected = profile.structural_signature.transformed(anchor,profile.scale_anchor,rotation)
                            observed = [(Point(*v['start']),Point(*v['end'])) for v in doc.filtered_geometry_snapshots(candidate.frame)]
                            robust = sum(any(min(max(math.dist((a.x,a.y),(c.x,c.y)),math.dist((b.x,b.y),(d.x,d.y))),
                                max(math.dist((a.x,a.y),(d.x,d.y)),math.dist((b.x,b.y),(c.x,c.y)))) <= profile.position_tolerance
                                for c,d in observed) for a,b in expected)/len(expected)
                            scores.append({'profile':profile.profile_id,'rotation':rotation,'score':score,
                                           'undirected_score':robust,'segments':len(observed)})
                    ranked = sorted(scores,key=lambda r:-r['undirected_score'])
                    best = next(p for p in store.all() if p.profile_id == ranked[0]['profile'])
                    best_signature = best.structural_signature.transformed(anchor,best.scale_anchor,ranked[0]['rotation'])
                    result['states'].append({'state':state,'scores':ranked,
                        'scale_labels':sum(str(v.get('text','')).strip().casefold()=='scale' for v in items)})
    result['source_unchanged'] = before == (sha256(args.source),args.source.stat().st_mtime_ns)
    result['owned_closed'] = result['owned_pid'] not in _gstar_pids()
    result['user_pids_preserved'] = pids <= _gstar_pids()
    result['invariant'] = all(s['scores'] == result['states'][0]['scores']
                             and s['scale_labels'] == 1 for s in result['states'])
    args.result.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({**result,'states':[{'state':s['state'],'best':s['scores'][:3]} for s in result['states']]}))
    return int(not all(result[k] for k in ('invariant','source_unchanged','owned_closed','user_pids_preserved')))


if __name__ == '__main__':
    raise SystemExit(main())
