"""Procedural irrigation robot, using Camposol's green, sun and gold palette."""
import math


def geometry_builder():
    faces = []
    def tube(start, end, radius, color):
        axis = [end[k]-start[k] for k in range(3)]
        length = math.sqrt(sum(v*v for v in axis))
        axis = [v/length for v in axis]
        ref = (0, 0, 1) if abs(axis[2]) < .9 else (0, 1, 0)
        u = [axis[1]*ref[2]-axis[2]*ref[1], axis[2]*ref[0]-axis[0]*ref[2], axis[0]*ref[1]-axis[1]*ref[0]]
        norm = math.sqrt(sum(v*v for v in u))
        u = [v/norm for v in u]
        v = [axis[1]*u[2]-axis[2]*u[1], axis[2]*u[0]-axis[0]*u[2], axis[0]*u[1]-axis[1]*u[0]]
        center = tuple((start[k]+end[k])/2 for k in range(3))
        def ring(p, j):
            angle = j*math.tau/64
            return tuple(p[k]+radius*(u[k]*math.cos(angle)+v[k]*math.sin(angle)) for k in range(3))
        for j in range(64):
            a,b,c,d=ring(start,j),ring(end,j),ring(end,j+1),ring(start,j+1)
            faces.append(([a,b,c,d], center, color))
            faces.append(([start,a,d,start], center, color))
            faces.append(([end,c,b,end], center, color))
    def body(center, size, color, power=0.35):
        def signed(v):
            return math.copysign(abs(v)**power, v)
        def point(i, j):
            a, b = math.pi*i/12-math.pi/2, math.tau*j/24
            return (center[0]+size[0]*signed(math.cos(a))*signed(math.cos(b)),
                    center[1]+size[1]*signed(math.sin(a)),
                    center[2]+size[2]*signed(math.cos(a))*signed(math.sin(b)))
        for i in range(12):
            for j in range(24):
                faces.append(([point(i,j), point(i+1,j), point(i+1,j+1), point(i,j+1)], center, color))
    return faces, tube, body


def mesh():
    faces, tube, body = geometry_builder()
    # Helmet and dark inset display; separate mechanical torso and limbs.
    body((0, .56, 0), (.76, .46, .40), (235, 239, 215), .70)
    body((0, .57, .37), (.67, .35, .085), (70, 111, 45), .43)
    body((0, .57, .45), (.60, .28, .06), (19,  40, 35), .50)
    body((0, .94, .04), (.39, .045, .30), (115, 164, 64), .5)
    for side in (-1, 1):
        body((side*.76, .54, 0), (.08, .23, .23), (86, 128, 52), .55)
        body((side*.82, .54, .03), (.035, .12, .15), (190, 173, 108), .6)
    # Filter housing as torso, with threaded pipe neck and compression rings.
    tube((0,-.10,0),(0,.14,0),.15,(112,131,116))
    tube((0,-.77,0),(0,-.12,0),.40,(221,228,213))
    for y in (-.12,-.17,-.72,-.77):
        tube((0,y-.025,0),(0,y+.025,0),.43,(58,91,62))
    body((0, -.44, .39), (.27, .25, .025), (246, 247, 239))
    for side in (-1, 1):
        # PE tube limbs, brass unions and rounded 90-degree elbows.
        tube((side*.39,-.25,0),(side*.72,-.25,0),.105,(47,64,53))
        tube((side*.49,-.25,0),(side*.59,-.25,0),.14,(188,163,100))
        body((side*.73,-.27,0),(.13,.13,.13),(64,89, 60),1)
        tube((side*.73,-.28,0),(side*.73,-.62,0),.105,(58,78,62))
        for y in (-.37,-.58):
            tube((side*.73,y-.035,0),(side*.73,y+.035,0),.13,(125,156, 90))
        tube((side*.23,-.75,0),(side*.23,-1.0,0),.095,(69,85,72))
        tube((side*.23,-.89,0),(side*.23,-.84,0),.14,(175,160,109))
        body((side*.24, -1.03, .07), (.20, .10, .26), (49, 79, 54))
    tube((-.73,-.62,0),(-.93,-.62,.04),.09,(184,158,92))
    tube((-.93,-.62,.04),(-.93,-.46,.04),.06,(184,158,92))
    body((.77, -.61, .08), (.18, .11, .15), (183, 164, 94))
    body((.98, -.58, .12), (.12, .07, .11), (76, 101, 80))
    # A brass valve wheel sits above the right-hand irrigation fitting.
    tube((.78,-.60,.06),(.78,-.40,.06),.035,(187,163,101))
    return faces


def draw_robot(c, faces, t, bounce, yaw, color, busy):
    def rotate(p):
        x,y,z=p
        return (x*math.cos(yaw)+z*math.sin(yaw), y, -x*math.sin(yaw)+z*math.cos(yaw))
    def project(p):
        x,y,z=p
        f=5/(5-z)
        return (210+x*78*f, 125-y*78*f+bounce)
    def pos(p):
        return project(rotate(p))
    c.create_oval(155, 216, 266, 229, fill="#24352b", outline="")
    # Flexible irrigation hose linking the tank to the brass quick-coupler.
    hose=[]
    for step in range(25):
        q=step/24
        hose.extend(pos((.38+.48*q, -.53-.30*math.sin(q*math.pi), -.12)))
    c.create_line(*hose,fill="#263e32",width=7)
    c.create_line(*hose,fill="#66795a",width=3)
    polygons=[]
    for vertices, origin, base in faces:
        pts=[rotate(p) for p in vertices]
        center=[sum(p[k] for p in pts)/4 for k in range(3)]
        org=rotate(origin)
        a=[pts[1][k]-pts[0][k] for k in range(3)]
        b=[pts[3][k]-pts[0][k] for k in range(3)]
        n=[a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]
        if sum(n[k]*(center[k]-org[k]) for k in range(3))<0:
            n=[-v for v in n]
        length=math.sqrt(sum(v*v for v in n)) or 1
        n=[v/length for v in n]
        if n[2]<-.1: continue
        light=max(0,-n[0]*.45+n[1]*.55+n[2]*.7)
        gloss=max(0,-n[0]*.25+n[1]*.32+n[2]*.914)**35
        rgb=tuple(min(255,int(v*(.45+.55*light)+gloss*90)) for v in base)
        polygons.append((center[2], [v for p in pts for v in project(p)], '#%02x%02x%02x'%rgb))
    for _, points, fill in sorted(polygons):
        c.create_polygon(points, fill=fill, outline=fill)
    # Compact mecha crown, echoing Camposol's sunlight accent.
    ax,ay=pos((0,1.0,0))
    c.create_polygon([ax-4,ay+2,ax-22,ay-13,ax-18,ay+4,ax,ay+11,ax+18,ay+4,ax+22,ay-13,ax+4,ay+2],fill="#c6b572",outline="")
    c.create_polygon([ax,ay-4,ax+6,ay+3,ax,ay+9,ax-6,ay+3],fill="#f2ce55",outline="")
    # Anime-inspired luminous eyes: angled lids, deep irises and double catchlights.
    for side in (-1,1):
        ex,ey=pos((side*.26,.61,.53))
        if t%4.8>4.62:
            c.create_arc(ex-10,ey-3,ex+10,ey+8,start=10,extent=160,style="arc",outline="#bde8bb",width=2.5)
        else:
            c.create_polygon([ex-12,ey-11,ex+10,ey-14,ex+12,ey+8,ex+6,ey+14,ex-7,ey+13,ex-12,ey+5],fill="#d7eee1")
            c.create_oval(ex-7,ey-10,ex+8,ey+12,fill="#5ebea0",outline="")
            c.create_oval(ex-4,ey-8,ex+5,ey+9,fill="#1c6050",outline="")
            c.create_oval(ex-3,ey-7,ex+3,ey+7,fill="#102e29",outline="")
            c.create_oval(ex-6,ey-10,ex+1,ey-3,fill="#f6fff1",outline="")
            c.create_oval(ex+3,ey+5,ex+6,ey+8,fill="#c7ffdf",outline="")
            c.create_line(ex-13,ey-11,ex+11,ey-14,fill="#83ccb1",width=2)
        cx,cy=pos((side*.48,.39,.51))
        c.create_line(cx-4,cy,cx+3,cy-1,fill="#bdad67",width=1.5)
    x,y=pos((0,.42,.53))
    c.create_arc(x-10,y-5,x+10,y+7,start=190,extent=160,style="arc",outline="#caee9d",width=2)
    # Curved glass reflection and brushed helmet trim.
    x,y=pos((0,.79,.53))
    c.create_line(x-28,y+2,x-8,y-2,x+20,y-1,fill="#6c9182",width=1)
    for side in (-1,1):
        x,y=pos((side*.62,.34,.38))
        c.create_oval(x-2,y-2,x+2,y+2,fill="#8d9277",outline="")
        x,y=pos((side*.23,-1.03,.34))
        c.create_line(x-10,y,x+10,y,fill="#93a281",width=2)
    # Exact company artwork on the service plate, not a reconstructed symbol.
    x,y=pos((0,-.44,.43))
    c.brand(x,y,38)
    # Pressure gauge is a visual design element, not a live measurement.
    gx,gy=pos((-.93,-.37,.15))
    c.create_oval(gx-12,gy-12,gx+12,gy+12,fill="#bbc3b4",outline="#4f6252",width=2)
    c.create_oval(gx-9,gy-9,gx+9,gy+9,fill="#f3f2df",outline="")
    for index in range(7):
        angle=math.radians(145+index*40)
        c.create_line(gx+math.cos(angle)*6,gy+math.sin(angle)*6,gx+math.cos(angle)*8,gy+math.sin(angle)*8,fill="#5d715b",width=.7)
    c.create_line(gx,gy,gx-4,gy-4,fill="#b79a4b",width=1.4)
    c.create_oval(gx-1,gy-1,gx+1,gy+1,fill="#465b44",outline="")
    # Quarter-turn handwheel, with a hollow hub and mechanical spokes.
    wx,wy=pos((.78,-.39,.08))
    c.create_oval(wx-10,wy-4,wx+10,wy+4,outline="#a99455",width=2)
    c.create_line(wx-8,wy,wx+8,wy,fill="#c6b372",width=1.5)
    c.create_line(wx,wy-3,wx,wy+3,fill="#c6b372",width=1.5)
    # Service screws and a compact tank-level gauge.
    for dx in (-.35,.35):
        x,y=pos((dx,-.66,.32))
        c.create_oval(x-1.4,y-1.4,x+1.4,y+1.4,fill="#89937d",outline="")
    x,y=pos((-.34,-.35,.33))
    c.create_rectangle(x-2,y-8,x+2,y+7,fill="#294739",outline="")
    for dy in (-5,0,5):
        c.create_line(x-1,y+dy,x+1,y+dy,fill="#bddb8e",width=1)
    x,y=pos((.58,.83,.38))
    c.create_oval(x-3,y-3,x+3,y+3,fill=color,outline="")
    # Nozzle perforations and animated water pulses during synchronization.
    x,y=pos((1.1,-.58,.22))
    for dy in (-3,2):
        c.create_oval(x-2,y+dy,x+1,y+dy+2,fill="#162c27",outline="")
    if busy:
        for i in range(3):
            phase=(t*1.4+i/3)%1
            dx=10+phase*30
            dy=phase*phase*30
            c.create_oval(x+dx,y+dy,x+dx+4,y+dy+7,fill="#8edcea",outline="")

