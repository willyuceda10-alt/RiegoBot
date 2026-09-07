"""A miniature irrigation headworks, without anthropomorphic features."""
import math
from .robot import geometry_builder


def mesh():
    faces, tube, body = geometry_builder()
    graphite = (55, 69,  60)
    green = (92, 135,  64)
    brass = (190, 167, 107)
    pearl = (223, 229, 215)
    # Continuous inlet/outlet manifold with flange and compression joints.
    tube((-1.47,.12,0),(1.43,.12,0),.14,graphite)
    for x in (-1.29,-.94,.55,1.10,1.30):
        tube((x-.055,.12,0),(x+.055,.12,0),.20,green)
    for x in (-1.30,1.31):
        for offset in (-.04,0,.04):
            tube((x+offset-.01,.12,0),(x+offset+.01,.12,0),.208,(126,151,100))
    # Vertical disc filter with a service cap and drain at the base.
    tube((-.42,-.79,0),(-.42,.51,0),.35,pearl)
    tube((-.42,.41,0),(-.42,.52,0),.40,green)
    for y in (-.71,-.76,.41,.48):
        tube((-.42,y-.025,0),(-.42,y+.025,0),.37,graphite)
    tube((-.42,-.94,0),(-.42,-.76,0),.08,brass)
    tube((-.53,-.94,0),(-.30,-.94,0),.055,green)
    body((-.42,-.16,.35),(.28,.31,.035),(245,246,239),.3)
    # Stainless pressure port above inlet.
    tube((-1.03,.12,0),(-1.03,.57,0),.045,brass)
    tube((-1.03,.62,0),(-1.03,.62,.12),.18,(157,168,151))
    # Solenoid valve and cable connector on outlet.
    body((.79,.15,0),(.22,.21,.22),brass,.6)
    tube((.79,.25,0),(.79,.65,0),.12,graphite)
    tube((.79,.51,0),(.79,.64,0),.16,green)
    body((.96,.55,-.02),(.10,.065,.08),graphite)
    # Low enclosure: the actual digital collector is visually the focal point.
    body((.43,-.57,.04),(.47,.33,.21),graphite,.35)
    body((.43,-.56,.26),(.42,.27,.035),pearl,.3)
    body((.43,-.48,.30),(.33,.12,.025),(23,44,35),.35)
    # Bracket keeps a grounded equipment silhouette.
    body((0,-1.01,-.05),(1.19,.04,.26),(88,102, 80),.3)
    return faces


def draw_station(c, faces, t, bounce, yaw, color, busy):
    def rotate(p):
        x,y,z=p
        return (x*math.cos(yaw)+z*math.sin(yaw), y, -x*math.sin(yaw)+z*math.cos(yaw))
    def project(p):
        x,y,z=p
        # Slight elevated camera exposes pipe caps and the equipment's depth.
        y,z=y*.985-z*.17,y*.17+z*.985
        f=5/(5-z)
        return (210+x*83*f, 130-y*83*f)
    def pos(p):
        return project(rotate(p))
    c.create_oval(105,214,316,230,fill="#2d3c31",outline="")
    # Electrical harness, placed behind the body.
    points=[]
    for i in range(30):
        q=i/29
        points.extend(pos((.97+.22*math.sin(q*math.pi),.54-1.1*q,-.13)))
    c.create_line(*points,fill="#253a2e",width=3)
    polygons=[]
    for vertices,origin,base in faces:
        pts=[rotate(p) for p in vertices]
        center=[sum(p[k] for p in pts)/4 for k in range(3)]
        org=rotate(origin)
        a=[pts[1][k]-pts[0][k] for k in range(3)]
        b=[pts[3][k]-pts[0][k] for k in range(3)]
        n=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
        if sum(n[k]*(center[k]-org[k]) for k in range(3))<0:
            n=[-v for v in n]
        length=math.sqrt(sum(v*v for v in n)) or 1
        n=[v/length for v in n]
        if n[2]*.985+n[1]*.17 < -.1: continue
        light=max(0,-n[0]*.45+n[1]*.55+n[2]*.7)
        gloss=max(0,-n[0]*.25+n[1]*.32+n[2]*.914)**40
        rgb=tuple(min(255,int(v*(.42+.58*light)+gloss*70)) for v in base)
        polygons.append((center[2]*.985+center[1]*.17,[v for p in pts for v in project(p)],'#%02x%02x%02x'%rgb))
    for _,points,fill in sorted(polygons):
        c.create_polygon(points,fill=fill)
    x,y=pos((-.42,-.16,.40))
    c.brand(x,y,43)
    # The gauge is an illustration: intentionally no numeric pressure reading.
    gx,gy=pos((-1.03,.62,.16))
    c.create_oval(gx-14,gy-14,gx+14,gy+14,fill="#c6ccbd",outline="#53654e",width=1)
    c.create_oval(gx-11,gy-11,gx+11,gy+11,fill="#f5f4e7",outline="")
    for i in range(9):
        angle=math.radians(140+i*35)
        c.create_line(gx+math.cos(angle)*8,gy+math.sin(angle)*8,gx+math.cos(angle)*10,gy+math.sin(angle)*10,fill="#6d7d62",width=.7)
    c.create_line(gx,gy,gx-5,gy-5,fill="#ad9659",width=1.3)
    c.create_oval(gx-1.5,gy-1.5,gx+1.5,gy+1.5,fill="#566948",outline="")
    x,y=pos((.43,-.48,.34))
    c.create_text(x,y,text="SYNC" if busy else "DREAM",fill="#d4e4bb",font=("Segoe UI",7,"bold"))
    x,y=pos((.43,-.72,.32))
    c.create_text(x-4,y,text="RIEGOBOT",fill="#526648",font=("Segoe UI",6,"bold"))
    c.create_oval(x+25,y-2,x+29,y+2,fill=color,outline="")
    if busy:
        for i in range(3):
            c.create_rectangle(x-12+i*8,y+10,x-8+i*8,y+12,fill="#bad583" if i==int(t*4)%3 else "#86977b",outline="")
    for dx in (.06,.80):
        for dy in (-.33,-.78):
            sx,sy=pos((dx,dy,.31))
            c.create_oval(sx-1,sy-1,sx+1,sy+1,fill="#7b8a70",outline="")
