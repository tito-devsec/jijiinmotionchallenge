import bpy, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'common'))
import posta_lib as P
bpy.ops.wm.read_factory_settings(use_empty=True)
objs = P.link_city()
import numpy as np
for n in ('CITY_WATER','CITY_BUILDING','CITY_ROAD','CITY_TERRAIN'):
    o = objs[n]; co = np.empty(len(o.data.vertices)*3); o.data.vertices.foreach_get('co', co); co = co.reshape(-1,3)
    print(n, 'min', co.min(0).round(0), 'max', co.max(0).round(0), 'mean', co.mean(0).round(0))
# tallest building location
o = objs['CITY_BUILDING']; co = np.empty(len(o.data.vertices)*3); o.data.vertices.foreach_get('co', co); co=co.reshape(-1,3)
i = co[:,2].argmax(); print('tallest vertex at', co[i].round(0))
