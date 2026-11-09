import json, sys, math, collections
from PIL import Image, ImageDraw
LAT0,LON0=-6.81926,39.29268; R=6378137.0
def proj(lon,lat):
    # simple local equirectangular is accurate enough (<0.1 m) at this scale for a preview
    x=math.radians(lon-LON0)*R*math.cos(math.radians(LAT0)); y=math.radians(lat-LAT0)*R; return x,y
feats=[]
for p in sys.argv[1:]: feats+=json.load(open(p))['features']
names=collections.Counter(); hts=[]
for f in feats:
    t=f['properties'].get('tags',{}); n=t.get('name') or t.get('name:en')
    if n: names[(f['properties']['type'],n)]+=1
    if f['properties']['type']=='building': hts.append(f['properties'].get('height',0))
print("named features:", len(names))
for (ty,n),c in list(names.items())[:60]: print(f"  {ty:10s} {n}")
import statistics; print("building heights: min",min(hts),"max",max(hts),"median",statistics.median(hts), "n>=30m:",sum(h>=30 for h in hts))
W,H=2200,1800; S=0.6
img=Image.new('RGB',(int(W*S),int(H*S)),(9,13,22)); d=ImageDraw.Draw(img)
def tr(lon,lat): x,y=proj(lon,lat); return ((x+1100)*S,(900-y)*S)
def poly(g,fill,outline=None):
    polys=[g['coordinates']] if g['type']=='Polygon' else g['coordinates'] if g['type']=='MultiPolygon' else []
    for pp in polys:
        if len(pp[0])>=3: d.polygon([tr(*p[:2]) for p in pp[0]],fill=fill,outline=outline)
def line(g,col,w):
    ls=[g['coordinates']] if g['type']=='LineString' else g['coordinates'] if g['type']=='MultiLineString' else []
    for l in ls: d.line([tr(*p[:2]) for p in l],fill=col,width=w)
for f in feats:
    if f['properties']['type']=='water': poly(f['geometry'],(7,85,201))
for f in feats:
    if f['properties']['type']=='beach': poly(f['geometry'],(246,201,40))
for f in feats:
    if f['properties']['type']=='building':
        h=f['properties'].get('height',0); c=min(255,70+int(h*4)); poly(f['geometry'],(c,c,c+10),(40,44,55))
for f in feats:
    if f['properties']['type']=='road':
        hw=f['properties'].get('tags',{}).get('highway',''); w=3 if hw in('primary','secondary','trunk') else 1
        line(f['geometry'],(0,198,168),w)
    if f['properties']['type']=='rail': line(f['geometry'],(255,101,13),1)
    if f['properties']['type']=='pier': line(f['geometry'],(243,240,232),2) if f['geometry']['type'].endswith('LineString') else poly(f['geometry'],(243,240,232))
d.text((10,10),"Posta / Kivukoni, Dar es Salaam  (2200 x 1800 m, N up)  roads=teal buildings=grey water=blue",fill=(243,240,232))
img.save('posta_geo_preview.png'); print("saved", img.size)
