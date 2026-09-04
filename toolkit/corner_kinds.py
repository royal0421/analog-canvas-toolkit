# -*- coding: utf-8 -*-
"""Where each corner IS: on a pin, on a bend, or on a junction.

    python corner_kinds.py <a .icproj.json> [<another> ...]

`ring_corners.py` draws the corners; this one classifies them, which is the
question that matters when the netlist lane loses to a hand-drawn figure.
Measured 2026-09-04 over the 21-figure bench: the hand-drawn answers put 8
corners on pins, this lane put 77.  A gate faces sideways and a drain faces
up, so ONE straight trunk always makes one of the two groups turn AT the
pin -- which is what the L trunk (SOP 3J) exists to avoid.

Same definition as `netlist_bench.bend_count`: a corner is a point where an
H path meets a V path, paths being route segments AND pin escape
directions; V_DD contacts and foreign-net crossings are excluded.
"""
import json, sys, pathlib
sys.path.insert(0, '.')
import icproj

def corners(path):
    doc = json.load(open(path, encoding='utf-8'))["documents"][0]
    pos = {i["id"]: (i["placement"]["position"]["x"], i["placement"]["position"]["y"],
                     i["placement"].get("mirror","none"), i["placement"].get("rotation",0),
                     i["symbolId"]) for i in doc["instances"]}
    variant = {i["id"]: i.get("symbolVariantId") for i in doc["instances"]}
    jn = {j["id"]: (j["position"]["x"], j["position"]["y"]) for j in doc["junctions"]}
    def pin_xy(iid, name):
        if iid not in pos: return None
        x,y,mir,rot,sid = pos[iid]
        for pin in icproj.sym(sid)["pins"]:
            if pin["name"]==name:
                dx,dy = icproj.xf(pin["at"]["x"], pin["at"]["y"], mir, rot)
                return (x+round(dx), y+round(dy))
        return None
    def xy(ep):
        if ep["kind"]=="junction": return jn[ep["junctionId"]]
        return pin_xy(ep["instanceId"], ep["pinName"])
    rsegs=[]
    for r in doc["routes"]:
        cur=xy(r["start"])
        for lg in r["legs"]:
            to=lg["to"]
            nxt=((to["position"]["x"],to["position"]["y"]) if to["kind"]=="bend" else xy(to["endpoint"]))
            if cur and nxt: rsegs.append((r["id"],cur,nxt))
            cur=nxt
    rnet0={r["id"]: r.get("netId") for r in doc["routes"]}
    inc, netat, why = {}, {}, {}
    for rid,a,b in rsegs:
        if a==b: continue
        d = "H" if a[1]==b[1] else ("V" if a[0]==b[0] else None)
        if d is None: continue
        for p in (a,b):
            inc.setdefault(p,set()).add(d)
            netat.setdefault(p,set()).add(rnet0.get(rid))
            why.setdefault(p,[]).append("%s:%s"%(rid,d))
    for iid,(x,y,mir,rot,sid) in pos.items():
        for pdef in icproj.sym(sid)["pins"]:
            nm,dirn = pdef["name"], pdef.get("direction")
            if not dirn or (sid in ("nmos","pmos") and nm=="B"): continue
            p=pin_xy(iid,nm)
            if p is None: continue
            vx,_vy = icproj.xf(*icproj.Schematic.DIRV[dirn], mirror=mir, rotation=rot)
            inc.setdefault(p,set()).add("H" if round(vx) else "V")
            why.setdefault(p,[]).append("PIN %s.%s(%s)"%(iid,nm,"H" if round(vx) else "V"))
    skip=set()
    supnets={r.get("netId") for r in doc["routes"] if r.get("presentation")=="power-rail"}
    for iid,(_x,_y,_m,_r,sid) in pos.items():
        if sid=="vdd-port":
            for pdef in icproj.sym(sid)["pins"]:
                p=pin_xy(iid,pdef["name"])
                if p: skip.add(p)
    for r in doc["routes"]:
        if r.get("presentation")!="power-rail" and r.get("netId") not in supnets: continue
        cur=xy(r["start"])
        for lg in r["legs"]:
            to=lg["to"]
            nxt=((to["position"]["x"],to["position"]["y"]) if to["kind"]=="bend" else xy(to["endpoint"]))
            if cur: skip.add(cur)
            if nxt: skip.add(nxt)
            cur=nxt
    netof={}
    for n in doc.get("nets",()):
        for t in n["terminals"]: netof[(t["instanceId"],t["pinName"])]=n["id"]
    for iid,(_x,_y,_m,_r,sid) in pos.items():
        for pdef in icproj.sym(sid)["pins"]:
            key=(iid,pdef["name"]); p=pin_xy(iid,pdef["name"])
            if p is not None and key in netof: netat.setdefault(p,set()).add(netof[key])
    jpts=set(jn.values())
    out=[]
    for p,ds in sorted(inc.items()):
        if "H" not in ds or "V" not in ds or p in skip: continue
        nets={x for x in netat.get(p,()) if x}
        if len(nets)>1 and p not in jpts: continue
        kind = "JUNC" if p in jpts else ("PIN" if any(w.startswith("PIN") for w in why[p]) else "BEND")
        out.append((p,kind,why[p]))
    return out

for path in sys.argv[1:]:
    cs = corners(path)
    print("=====", path, len(cs))
    for p,kind,w in cs:
        print("   %-12s %-5s %s" % (p,kind,w))
