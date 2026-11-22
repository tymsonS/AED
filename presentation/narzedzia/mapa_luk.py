import json, math, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Patch
# Mapa luk po gminach do prezentacji. Najpierw: python -m ingest fetch-gminy, fetch all, build all, gaps.
import pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2]
d=json.load(open(ROOT/'ingest/data/out/mapa-luk.geojson'))
col={'publikuje dane':'#00965E','tylko dane niezweryfikowane':'#C9CED6','brak AED w danych':'#1B266B'}
k=math.cos(math.radians(52))
polys={s:[] for s in col}; pubs=[]
for f in d['features']:
    g=f['geometry']; s=f['properties']['status']
    parts=g['coordinates'] if g['type']=='MultiPolygon' else [g['coordinates']]
    for poly in parts:
        ring=poly[0]; polys[s].append([(x*k,y) for x,y in ring])
    if s=='publikuje dane':
        r=parts[0][0]; pubs.append((sum(p[0] for p in r)/len(r)*k, sum(p[1] for p in r)/len(r), f['properties']['gmina']))
fig,ax=plt.subplots(figsize=(9,8.4),dpi=200)
for s in ('tylko dane niezweryfikowane','brak AED w danych','publikuje dane'):
    ax.add_collection(PolyCollection(polys[s],facecolors=col[s],edgecolors='white',linewidths=0.15))
for x,y,n in pubs:
    ax.plot(x,y,'o',ms=11,mfc='none',mec='#00965E',mew=2.2)
    ax.annotate(n,(x,y),xytext=(10,-4),textcoords='offset points',fontsize=11,color='#00965E',fontweight='bold')
ax.autoscale(); ax.set_aspect('equal'); ax.axis('off')
ax.legend(handles=[Patch(color=col['publikuje dane'],label='publikuje dane na dane.gov.pl (3)'),
                   Patch(color=col['tylko dane niezweryfikowane'],label='tylko dane społeczne, niezweryfikowane (2 125)'),
                   Patch(color=col['brak AED w danych'],label='brak AED w danych (351)')],
          loc='lower left',frameon=False,fontsize=11)
plt.tight_layout(); plt.savefig(ROOT/'presentation/zrzuty/mapa-luk.jpg',transparent=False,facecolor='white')
