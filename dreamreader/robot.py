"""Procedural irrigation robot, using Camposol's green, sun and gold palette."""
import math


def mesh():
    faces = []
    def body(center, size, color, power=0.35):
        def signed(v):
            return math.copysign(abs(v)**power, v)
        def point(i, j):
            a, b = math.pi*i/8-math.pi/2, math.tau*j/16
            return (center[0]+size[0]*signed(math.cos(a))*signed(math.cos(b)),
                    center[1]+size[1]*signed(math.sin(a)),
                    center[2]+size[2]*signed(math.cos(a))*signed(math.sin(b)))
        for i in range(8):
            for j in range(16):
                faces.append(([point(i,j), point(i+1,j), point(i+1,j+1), point(i,j+1)], center, color))
    # Helmet and dark inset display; separate mechanical torso and limbs.
    body((0, .56, 0), (.67, .43, .36), (112, 166,  60), .30)
    body((0, .56, .365), (.55, .29, .055), (23, 60, 40), .30)
    body((0, .02, 0), (.18, .12, .21), (164, 173, 158))
    body((0, -.42, 0), (.44, .34, .30), (221, 229, 204))
    body((0, -.43, .30), (.32, .23, .035), (96, 153, 53))
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
        rgb=tuple(min(255,int(v*(.45+.55*light)+gloss*65)) for v in base)
        polygons.append((center[2], [v for p in pts for v in project(p)], '#%02x%02x%02x'%rgb))
    for _, points, fill in sorted(polygons):
        c.create_polygon(points, fill=fill, outline=fill)
    # Signal antenna with a solar-yellow beacon.
    ax,ay=pos((0,1.0,0))
    c.create_line(ax,ay,ax,ay-15,fill="#a99a62",width=4)
    c.create_oval(ax-6,ay-23,ax+6,ay-11,fill="#ffce28",outline="#ecdf96",width=2)
    for x in (-.25,.25):
        ex,ey=pos((x,.60,.44))
        if t%4.8>4.62:
            c.create_line(ex-8,ey,ex+8,ey,fill="#d7f7a9",width=3)
        else:
            c.create_rectangle(ex-7,ey-9,ex+7,ey+9,fill="#caee9d",outline="")
            c.create_rectangle(ex-3,ey-6,ex+2,ey-1,fill="#f9ffe8",outline="")
    x,y=pos((0,.40,.44))
    c.create_arc(x-10,y-5,x+10,y+7,start=190,extent=160,style="arc",outline="#caee9d",width=2)
    # Chest seal: rising sun and field lines reference the supplied identity.
    x,y=pos((0,-.40,.36))
    c.create_oval(x-13,y-14,x+13,y+12,fill="#669e3a",outline="#c3af70",width=2)
    c.create_arc(x-6,y-10,x+6,y+2,start=0,extent=180,fill="#ffce28",outline="")
    for offset in (-7,0,7):
        c.create_line(x+offset,y+8,x+offset*.3,y-1,fill="#e4efd1",width=1)
    c.create_text(x,y+23,text="RIEGO",fill="#345836",font=("Segoe UI",6,"bold"))
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

