"""Procedural irrigation robot, using Camposol's green, sun and gold palette."""
import math


def mesh():
    faces = []
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
    # Helmet and dark inset display; separate mechanical torso and limbs.
    body((0, .56, 0), (.72, .43, .39), (235, 239, 215), .46)
    body((0, .57, .37), (.63, .34, .085), (70, 111, 45), .43)
    body((0, .57, .45), (.56, .265, .06), (19,  40, 35), .50)
    body((0, .94, .04), (.39, .045, .30), (115, 164, 64), .5)
    for side in (-1, 1):
        body((side*.76, .54, 0), (.08, .23, .23), (86, 128, 52), .55)
        body((side*.82, .54, .03), (.035, .12, .15), (190, 173, 108), .6)
    body((0, .02, 0), (.18, .12, .21), (164, 173, 158))
    body((0, -.42, 0), (.43, .34, .30), (231, 236, 219))
    body((0, -.43, .30), (.30, .23, .035), (91, 139, 51))
    for side in (-1, 1):
        body((side*.59, -.23, 0), (.12, .14, .17), (180, 162, 92), 1)
        body((side*.71, -.42, 0), (.12, .21, .12), (109, 153, 60))
        body((side*.23, -.87, 0), (.12, .11, .14), (119, 133, 117))
        body((side*.24, -1.03, .07), (.20, .10, .26), (49, 79, 54))
    body((-.73, -.67, .04), (.15, .10, .16), (211, 224, 201))
    body((.77, -.61, .08), (.18, .11, .15), (183, 164, 94))
    body((.98, -.58, .12), (.12, .07, .11), (76, 101, 80))
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
    # Signal antenna with a solar-yellow beacon.
    ax,ay=pos((0,1.0,0))
    c.create_line(ax,ay,ax,ay-15,fill="#a99a62",width=4)
    c.create_oval(ax-6,ay-23,ax+6,ay-11,fill="#ffce28",outline="#ecdf96",width=2)
    for x in (-.25,.25):
        ex,ey=pos((x,.61,.53))
        if t%4.8>4.62:
            c.create_line(ex-8,ey,ex+8,ey,fill="#d7f7a9",width=3)
        else:
            c.create_rectangle(ex-8,ey-9,ex+8,ey+9,fill="#caee9d",outline="")
            c.create_rectangle(ex-3,ey-6,ex+2,ey-1,fill="#f9ffe8",outline="")
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
    # Chest seal: rising sun and field lines reference the supplied identity.
    x,y=pos((0,-.40,.36))
    c.create_oval(x-13,y-14,x+13,y+12,fill="#669e3a",outline="#c3af70",width=2)
    c.create_arc(x-6,y-10,x+6,y+2,start=0,extent=180,fill="#ffce28",outline="")
    for offset in (-7,0,7):
        c.create_line(x+offset,y+8,x+offset*.3,y-1,fill="#e4efd1",width=1)
    c.create_text(x,y+23,text="RIEGO",fill="#345836",font=("Segoe UI",6,"bold"))
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

