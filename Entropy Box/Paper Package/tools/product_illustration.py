"""Vector illustration based on the referenced Entropy Box product appearance.
White lid, dark base, 5x5 dice. Illustration only; no new manufacturing geometry.
"""
import math

def draw_product(shape,polygon,circle,cx,cy,scale=.42):
    def p(x,y,z):return [cx+(x-y)/math.sqrt(2)*scale,cy+((x+y)/2+.45*z)*scale]
    def face(points,fill,stroke=None,width=.15,tag='product_illustration'):
        return polygon([p(*q) for q in points],fill=fill,stroke=stroke,width=width,tag=tag)
    def plane_path(size,z,r):
        h=size/2;k=r*.5522847498
        raw=[('M',[-h+r,-h]),('L',[h-r,-h]),
             ('C',[h-r+k,-h,h,-h+r-k,h,-h+r]),('L',[h,h-r]),
             ('C',[h,h-r+k,h-r+k,h,h-r,h]),('L',[-h+r,h]),
             ('C',[-h+r-k,h,-h,h-r+k,-h,h-r]),('L',[-h,-h+r]),
             ('C',[-h,-h+r-k,-h+r-k,-h,-h+r,-h]),('Z',[])]
        out=[]
        for op,coords in raw:
            values=[]
            for i in range(0,len(coords),2):values+=p(coords[i],coords[i+1],z)
            out.append((op,values))
        return out
    def ellipse_at(x,y,z,r):
        k=.5522847498*r
        raw=[('M',[x+r,y]),('C',[x+r,y+k,x+k,y+r,x,y+r]),
             ('C',[x-k,y+r,x-r,y+k,x-r,y]),('C',[x-r,y-k,x-k,y-r,x,y-r]),
             ('C',[x+k,y-r,x+r,y-k,x+r,y]),('Z',[])]
        cmds=[]
        for op,coords in raw:
            values=[]
            for i in range(0,len(coords),2):values+=p(coords[i],coords[i+1],z)
            cmds.append((op,values))
        return shape(cmds,fill=(0,0,0,.92),tag='product_illustration_die_pip')
    def arc(center,r,start,end,count=12):
        return [(center[0]+r*math.cos(math.radians(start+(end-start)*i/count)),
                 center[1]+r*math.sin(math.radians(start+(end-start)*i/count)))
                for i in range(count+1)]
    left=arc((-25,25),4,135,180,5)+[(-29,-25)]+arc((-25,-25),4,180,225,5)[1:]
    right=arc((-25,-25),4,225,270,5)+[(25,-29)]+arc((25,-25),4,270,315,5)[1:]
    def walls():
        for path,c0,c1 in [(left,(0,0,0,.88),(0,0,0,.14)),(right,(0,0,0,.78),(0,0,0,.07))]:
            for low,high,color in [(0,5.8,c0),(5.8,15.6,c1)]:
                face([(x,y,high) for x,y in path]+[(x,y,low) for x,y in reversed(path)],color,
                     tag='product_illustration_outer_wall')
    # Subtle ground shadow, then the transparent opening and reference dice.
    ellipse=[]
    rx,ry=19.2,2.1;sy=cy-13.2
    for i in range(40):
        a=2*math.pi*i/40;ellipse.append((cx+rx*math.cos(a),sy+ry*math.sin(a)))
    polygon(ellipse,fill=(0,0,0,.055),tag='product_illustration_shadow')
    walls()
    face([(-22,-22,15.6),(22,-22,15.6),(22,22,15.6),(-22,22,15.6)],(0,0,0,.76),
         tag='product_illustration_transparent_opening')
    patterns={1:[(0,0)],2:[(-1,-1),(1,1)],3:[(-1,-1),(0,0),(1,1)],
              4:[(-1,-1),(-1,1),(1,-1),(1,1)],
              5:[(-1,-1),(-1,1),(0,0),(1,-1),(1,1)],
              6:[(-1,-1),(-1,0),(-1,1),(1,-1),(1,0),(1,1)]}
    cells=[(i,j,(i-2)*8.8,(j-2)*8.8) for j in range(5) for i in range(5)]
    for i,j,x,y in sorted(cells,key=lambda t:-(t[2]+t[3])):
        s=2.5;bottom=1.4;top=6.4
        face([(x-s,y-s,bottom),(x+s,y-s,bottom),(x+s,y-s,top),(x-s,y-s,top)],(0,0,0,.18))
        face([(x-s,y-s,bottom),(x-s,y+s,bottom),(x-s,y+s,top),(x-s,y-s,top)],(0,0,0,.28))
        face([(x-s,y-s,top),(x+s,y-s,top),(x+s,y+s,top),(x-s,y+s,top)],(0,0,0,.01),
             stroke=(0,0,0,.25),width=.12,tag='product_illustration_die_top')
        for u,v in patterns[1+(i+3*j)%6]:ellipse_at(x+u*1.05,y+v*1.05,top+.005,.29)
    # Repaint the visible walls, naturally occluding dice below the window.
    walls()
    outer=plane_path(58,15.6,4)
    inner=[('M',p(-22,-22,15.6)),('L',p(-22,22,15.6)),
           ('L',p(22,22,15.6)),('L',p(22,-22,15.6)),('Z',[])]
    shape(outer+inner,fill=(0,0,0,.025),stroke=(0,0,0,.24),width=.22,
          tag='product_illustration_white_frame')
    # Glass-edge highlight along the rear edge, kept inside the opening.
    shape([('M',p(-20.5,21.25,15.58)),('L',p(20.5,21.25,15.58))],
          stroke=(0,0,0,.38),width=.4,tag='product_illustration_glass_highlight')
    return 25
