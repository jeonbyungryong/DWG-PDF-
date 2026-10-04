"""Post-run GstarCAD output audit; run after the three live tests succeed."""
import argparse,json
from pathlib import Path
import pypdfium2 as pdfium
from pypdf import PdfReader
from PIL import ImageChops

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('run',type=Path)
    args=parser.parse_args()
    records=list((args.run/'temporary').rglob('matrix-decisions.json'))
    assert len(records)==1,'Exactly one completed live matrix is required'
    matrix=json.loads(records[0].read_text(encoding='utf-8'))
    golden=json.loads((Path(__file__).parent/'inputs-manifest.json').read_text(encoding='utf-8'))['cases']
    expected={c['file']:c for c in golden}
    assert len(expected)==len(matrix['off'])==len(matrix['on'])==43
    rows=[];renders={}
    for mode in ('off','on'):
        assert {Path(d['source']).name for d in matrix[mode]}==set(expected)
        for d in matrix[mode]:
            name=Path(d['source']).name;case=expected[name];path=Path(d['output'])
            assert d['sha256'].upper()==case['sha256'].upper()
            assert (d['numerator'],d['denominator'],d['rotation'])==(case['scale']['numerator'],case['scale']['denominator'],case['rotation'])
            assert max(abs(a-b) for a,b in zip(d['window'],case['window']))<0.001
            reader=PdfReader(path,strict=True)
            assert not reader.is_encrypted and len(reader.pages)==1
            page=reader.pages[0];w,h=float(page.mediabox.width)*25.4/72,float(page.mediabox.height)*25.4/72
            assert abs(w-297)<0.2 and abs(h-210)<0.2 and page.rotation==0
            with pdfium.PdfDocument(path.read_bytes()) as doc:
                p=doc[0];bitmap=p.render(scale=2);image=bitmap.to_pil().convert('RGB').copy()
                bitmap.close();p.close()
            r,g,b=image.split();rg=ImageChops.difference(r,g);rb=ImageChops.difference(r,b)
            chroma=max(rg.getextrema()[1],rb.getextrema()[1])
            gray=image.convert('L');dark=sum(gray.histogram()[:246])
            assert chroma==0 and dark>=8 and image.width>image.height,(name,mode,chroma,dark)
            for obj in (r,g,b,rg,rb,gray):obj.close()
            if mode=='off':renders[name]=image
            else:
                before=renders.pop(name);assert image.size==before.size
                diff=ImageChops.difference(before,image)
                assert diff.getbbox() is None,(name,'OFF/ON pixel difference')
                diff.close();before.close();image.close()
            rows.append({'mode':mode,'file':name,'width_mm':w,'height_mm':h,'chroma':chroma,'dark_pixels':dark})
    assert len(rows)==86 and not renders
    (args.run/'output-audit.json').write_text(json.dumps({'pdfs':86,'golden_decisions':86,'same_pixel_pairs_144dpi':43,'rows':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    print('GSTAR_OUTPUT_AUDIT_PASS: PDFs86 / golden86 / monochrome86 / pixel_pairs43')

if __name__=='__main__':main()
