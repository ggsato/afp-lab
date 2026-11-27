"""AFP Lab FE-NODE-001 Rev 0.2 concept, parametric assembly in mm.
Requires cadquery, trimesh, numpy. Outputs GLB in metre units (glTF Y-up),
STEP solids in mm. Models are independent dimensional proxies, not vendor CAD.
"""
from pathlib import Path
import math, json, csv
import numpy as np
import cadquery as cq
import trimesh as tm
from trimesh.visual.material import PBRMaterial
from trimesh.visual import TextureVisuals
from collections import defaultdict
OUT=Path(__file__).resolve().parent
PARTS=[]
GROUPS={}
# coordinate system: X=width, Y=installed vertical, Z=backplate to front cover
ABS=(.78,.81,.82,1); PC=(.66,.70,.73,1); BLACK=(.075,.085,.10,1); STEEL=(.67,.70,.73,1); GOLD=(.74,.53,.22,1); BAT=(.27,.45,.67,1); RED=(.82,.13,.14,1); DARK=(.12,.14,.16,1); WHITE=(.91,.90,.85,1); PCB=(.07,.10,.105,1); PURPLE=(.36,.20,.52,1); BLUE=(.055,.12,.24,1); AMBER=(.95,.64,.14,1); CLEAR=(.63,.82,.91,.17); TAPE=(.95,.78,.20,.50); FLEX=(.80,.67,.28,1)

def group(name,origin=(0,0,0),parent=None,desc=''):
    GROUPS[name]={'origin':np.array(origin,float),'parent':parent,'description':desc}; return name

def add(name,shape,g,col,kind='proxy'):
    if isinstance(shape,cq.Workplane): shape=shape.val()
    PARTS.append(dict(name=name,shape=shape,g=g,col=col,kind=kind));return shape

def box(w,l,h,x=0,y=0,z=0,r=0):
    s=cq.Workplane('XY').box(w,l,h,centered=(True,True,False))
    if r: s=s.edges('|Z').fillet(r)
    return s.translate((x,y,z)).val()

def cyl(r,h,x=0,y=0,z=0,axis=(0,0,1)):
    return cq.Solid.makeCylinder(r,h,cq.Vector(x,y,z),cq.Vector(*axis))

def ring(ro,ri,h,x,y,z): return cyl(ro,h,x,y,z).cut(cyl(ri,h+2,x,y,z-1))

def compound(shapes): return cq.Compound.makeCompound(shapes)

def drilled(w,l,h,x,y,z,holes,r=0):
    s=box(w,l,h,x,y,z,r)
    for hx,hy,diam in holes: s=s.cut(cyl(diam/2,h+2,hx,hy,z-1))
    return s

def frame(w,l,wi,li,h,x,y,z,r=2):
    return box(w,l,h,x,y,z,r).cut(box(wi,li,h+2,x,y,z-1,max(.2,r-1)))

def wire(name,points,r,g,col):
    # round segments + small spheres; route is schematic and adjustable
    ss=[]; pts=np.asarray(points,float)
    for a,b in zip(pts[:-1],pts[1:]):
        d=b-a; n=np.linalg.norm(d)
        if n>1e-5: ss.append(cyl(r,n,*a,tuple(d/n)))
    for p in pts[1:-1]: ss.append(cq.Solid.makeSphere(r,cq.Vector(*p)))
    return add(name,compound(ss),g,col,'routing_proxy')

def screw(name,x,y,z,g,d=3,h=2):
    add(name,compound([cyl(d*.8,h,x,y,z),cyl(d*.35,2,x,y,z-2)]),g,STEEL,'fastener_proxy')

# 01: enclosure, prior generation BCAP253515T. External 250 x 350 x 150
# (latch / rear projections omitted from nominal envelope).
group('01_Enclosure_BASE',(0,0,0),desc='BCAP253515T simplified; no gasket/hinge exact fit')
G='01_Enclosure_BASE'
# tapered body represented by straight shell; internal clear footprint max 223.5 x 323.5
outer=box(231.8,331.8,120,0,0,0,6)
inner=box(223.5,323.5,118,0,0,4,4)
add('ABS_base_shell',outer.cut(inner),G,ABS)
add('ABS_rim',frame(250,350,223.5,323.5,5,0,0,115,7),G,ABS)
# bosses under plate; exact molding not modeled
for x in (-90,90):
 for y in (-134.25,134.25): add(f'M5_insert_boss_{x}_{y}',ring(6,2.5,8,x,y,4),G,ABS)
# simple latch and hinge envelopes, no external drilled openings
for y in (-134,134):
 add(f'Stainless_latch_{y}',box(4,25,20,124,y,101,1),G,STEEL)
 add(f'Hinge_envelope_{y}',box(5,24,12,-124,y,112,1),G,ABS)
# 02 backplate 215.5 x 315, 4 mm thick; four 8 mm holes; rib outline 127 x 212 x 6
BP='02_Backplate_BMP2535P';group(BP,(0,0,12),desc='Manufacturer dimensions; corner profile simplified')
plate=drilled(215.5,315,4,0,0,12,[(x,y,8) for x in (-90,90) for y in (-134.25,134.25)],r=5)
add('Backplate_ABS_215p5x315x4',plate,BP,ABS,'dimensioned_proxy')
add('Rear_rib_outline_127x212',frame(127,212,121,206,6,0,0,6,2),BP,ABS,'dimensioned_proxy')
for x in (-90,90):
 for y in (-134.25,134.25): screw(f'M5_plate_screw_{x}_{y}',x,y,16,BP,5,2)
# 03 removable tray: layout proposal on base plate, not print released
TR='03_Power_tray';group(TR,(-36,83,16),desc='Proposed PC tray 126 x 76; hole layout provisional')
trayx,trayy=-36,83; tz=20
base=drilled(126,76,2.5,trayx,trayy,tz,[(x,y,3.4) for x in (-92,20) for y in (51,115)],r=3)
add('PC_tray_floor',base,TR,PC,'concept')
# Rails are separate from the moving tray; 0.5 mm vertical clearance above floor.
RA='03a_Tray_fixed_rails';group(RA,(trayx,trayy,16),BP,'Proposed fixed rails; retention stop, actual drilling and screw lengths TBD')
for x in (-101,29):
 dx=(1 if x<0 else -1)
 add(f'PC_slide_rail_{x}',box(4,76,7,x,trayy,16,.6),RA,PC,'concept')
 add(f'PC_slide_support_{x}',box(6,76,2,x+dx,trayy,18,.6),RA,PC,'concept')
 add(f'PC_slide_lip_{x}',box(6,76,2,x+dx,trayy,23,.6),RA,PC,'concept')
for y in (46.5,119.5): add(f'Tray_end_wall_{y}',box(119,2.5,5,trayx,y,22.5,1),TR,PC,'concept')
# Tray floor holes retained as alternate screw-fixing option; do not use in sliding configuration.
# battery holder and cell
HO='04_18650_holder';group(HO,(-49,101,22.5),TR,'75 mm molded holder; total product envelope 80 x 21 x 18.6; side profile approximated')
hx,hy,hz=-49,101,22.5
# base and walls with open top, modest cutouts for cell access
bottom=box(75,20.6,1.5,hx,hy,hz,1)
# hole x +/-17.3; lateral centers from drawing not explicitly dimensioned: omit drill in holder model
add('PP_holder_floor',bottom,HO,BLACK,'dimensioned_proxy')
for yy in (hy-9.55,hy+9.55):
 side=box(72,1.5,11.0,hx,yy,hz+1.5,.4)
 # center finger recess; open trough, not exact extrusion
 side=side.cut(cyl(24,3,hx,yy-1.5,hz+32,(0,1,0)))
 add(f'PP_holder_side_{yy}',side,HO,BLACK)
for xx in (hx-35.75,hx+35.75): add(f'Holder_endwall_{xx}',box(3.5,20.6,17.1,xx,hy,hz+1.5,.8),HO,BLACK)
add('PCM_end_envelope',box(5,20.6,15,hx-40,hy,hz+1,.6),HO,BLACK)
# contact positions approximate; no conductive geometry to touch the cell sleeve
add('Positive_contact',cyl(3.1,1.3,hx+33,hy,hz+10.6,(1,0,0)),HO,STEEL)
add('Negative_contact',cyl(3.5,2.5,hx-35,hy,hz+10.6,(1,0,0)),HO,STEEL)
# retaining side stops, no screws through holder into cell space
for xx in (hx-38.8,hx+38.8):
 add(f'PC_holder_stop_{xx}',box(3,25,4,xx,hy,hz,.6),TR,PC,'concept')
CELL='05_18650_cell';group(CELL,(hx,hy,hz+10.7),HO,'Nominal 18.2 x 65 mm cell; measure chosen cell')
cz=hz+10.7
add('LiIon_cell_sleeved',cyl(9.1,64,hx-32.5,hy,cz,(1,0,0)),CELL,BAT,'dimensioned_proxy')
add('Cell_positive_end',cyl(3.2,1,hx+31.5,hy,cz,(1,0,0)),CELL,STEEL)
# thin JT thermistor at cell midpoint, tape first. 3.6 x 0.5 nominal film width/thickness.
NT='06_JT100_surface_NTC';group(NT,(hx,hy,cz+9.1),HO,'Taped sensor head; lead path illustrative; no applied clamp pressure')
# sensor head tangential at cell top, narrow width; tape is model of tape contact, not a clamp
head=cyl(9.6,5,hx-2.5,hy,cz,(1,0,0)).cut(cyl(9.1,7,hx-3.5,hy,cz,(1,0,0)))
head=head.intersect(box(5,3.6,2,hx,hy,cz+8,0))
add('JT100_sensor_head_5x3p6x0p5',head,NT,FLEX,'dimensioned_proxy')
add('NTC_sensor_element',box(1.3,1.0,.10,hx-1,hy,cz+9.6,.1),NT,DARK)
# tape cap over sensor not contacting cell terminals; thin conceptual patch
add('Polyimide_tape_patch',box(12,10,.09,hx,hy,cz+9.61,1),NT,TAPE,'concept')
# flex tail as simplified route: thin flat segments (not an exact formed part)
# route along cell top then out around end; route stays away from terminal, adjust after real measurement
add('JT100_flex_tail_visible',box(26,3.6,.25,hx+15.5,hy,cz+9.15,.2),NT,FLEX,'routing_proxy')
# flexible tail exits laterally; generic path for remaining ribbon/leads
wire('JT100_tail_route_A',[(hx+28,hy,cz+9.3),(-19,hy,cz+9.3),(-13,hy-5,cz+8),(-13,87,38),(-13,81,33),(-10,78,28)],.35,NT,FLEX)
wire('JT100_tail_route_B',[(hx+28,hy-1.2,cz+9.3),(-20,hy-1.2,cz+9.3),(-14,hy-5,cz+8),(-14,87,38),(-14,81,33),(-11,78,28)],.35,NT,FLEX)
# charger outline and indicative ports, not an official CAD model
CH='07_BQ25185_6091';group(CH,(-18,67,25.5),TR,'32 x 26.3 x 7.2 mm envelope; connector positions approximate')
chx,chy,zc=-18,67,25.5
add('PCB_6091_32x26p3',box(32,26.3,1.6,chx,chy,zc,2),CH,PCB,'dimensioned_proxy')
# edge support, no invented holes
for dx in (-14,14):
 add(f'Charger_PC_support_{dx}',box(3,19,3,chx+dx,chy,22.5,.5),TR,PC,'concept')
# USB-C along lower edge, 2 JST-PH and DC terminal block indicative only
add('USB_C_shell_proxy',box(8.9,7.2,3.2,chx,chy-10,zc+1.6,.7),CH,STEEL)
for yy,label in [(chy+8.5,'BATT'),(chy-1,'LOAD')]:
 add(f'JST_PH_{label}_proxy',box(7.8,6.2,5.6,chx+10.5,yy,zc+1.6,.4),CH,WHITE)
 add(f'JST_{label}_contacts',box(4.6,2.2,.8,chx+10.5,yy,zc+6.2),CH,GOLD)
add('DCIN_terminal_proxy',box(6.5,7,5.6,chx-11,chy+8.5,zc+1.6,.3),CH,DARK)
add('BQ25185_IC',box(3.2,3.2,.9,chx-2,chy+1,zc+1.6,.15),CH,DARK)
for i,(dx,dy) in enumerate([(-7,-3),(-6,3),(4,4),(4,-5),(-9,0),(-4,-7),(1,7)]):
 add(f'Passive_proxy_{i}',box(2.0,1.1,.8,chx+dx,chy+dy,zc+1.6,.12),CH,(.66,.60,.42,1))
# MiniBoost Eagle layout: X 0..11.43 Y 0..17.78, hole (2.54,15.24), pin row y2.54
MB='08_MiniBoost_4654';group(MB,(12,67,25.5),TR,'Board outline and XY component centers from official Eagle; component Z proxies')
mx,my,mz=12,67,25.5; ox,oy=mx-11.43/2,my-17.78/2
holes=[(ox+2.54,oy+15.24,2.5)]+[(ox+i,oy+2.54,1.0) for i in (1.905,4.445,6.985,9.525)]
# rounded top corners only, per Eagle arc radius 2.54
s=cq.Workplane('XY').moveTo(ox,oy).lineTo(ox,oy+15.24).radiusArc((ox+2.54,oy+17.78),2.54).lineTo(ox+8.89,oy+17.78).radiusArc((ox+11.43,oy+15.24),2.54).lineTo(ox+11.43,oy).close().extrude(1.6).translate((0,0,mz)).val()
for a,b,d in holes:s=s.cut(cyl(d/2,3.6,a,b,mz-1))
add('PCB_4654_Eagle_outline',s,MB,PCB,'Eagle_xy_proxy')
for i,(a,b,d) in enumerate(holes):add(f'Plated_ring_{i}',ring(2 if i==0 else .889,d/2,.07,a,b,mz+1.6),MB,GOLD,'Eagle_xy_proxy')
add('L1_inductor_5x5',box(5,5,4,ox+3.683,oy+8.763,mz+1.6,.5),MB,DARK,'Eagle_xy_proxy')
add('IC1_TPS61023',box(1.6,1.6,.7,ox+7.874,oy+8.763,mz+1.6,.1),MB,DARK,'Eagle_xy_proxy')
for i,(a,b) in enumerate([(8.255,6.604),(3.175,4.699),(8.255,4.7244),(8.128,11.557),(9.652,8.9916),(9.652,12.065)]):
 add(f'SMD_{i}',box(1.8 if i<3 else .9,1.0 if i<3 else 1.5,.7,ox+a,oy+b,mz+1.6,.1),MB,(.66,.60,.42,1),'Eagle_xy_proxy')
add('Boost_PC_standoff',ring(2.9,1.25,3,ox+2.54,oy+15.24,22.5),TR,PC,'concept')
add('Boost_anti_rotation_support',box(3,4,3,ox+8,oy+2,22.5,.4),TR,PC,'concept')
screw('M2_boost_screw_candidate',ox+2.54,oy+15.24,mz+1.67,MB,2,1.3)
# fuse holder inline envelope; no exact external CAD retrieved; 45 x 13 nominal reservation
FU='09_Inline_fuse_8601';group(FU,(-70,65,29),TR,'SCHURTER 8601.2000 approximate reserved envelope; confirm exact length')
fx,fy,fz=-70,65,29
add('FDI_fuseholder_body_proxy',cyl(6.5,42,fx-21,fy,fz,(1,0,0)),FU,BLACK)
add('Fuseholder_cap_proxy',cyl(6.7,12,fx+9,fy,fz,(1,0,0)),FU,DARK)
for xx in (fx-16,fx+16):add(f'Fuse_cradle_{xx}',box(8,17,3,xx,fy,22.5,1),TR,PC,'concept')
# wiring paths, no claim final wiring layout
WI='10_Power_wiring';group(WI,(-36,83,22.5),TR,'Illustrative wire routing; polarity and gauge verified separately')
wire('BAT_plus_to_fuse',[(-89,101,31),(-96,101,29),(-96,75,29),(-91,65,29)],.85,WI,RED)
wire('Fuse_to_BATT_plus',[(-49,65,29),(-43,65,29),(-41,79,30),(-10,80,33),(-7.5,75.5,32)],.85,WI,RED)
wire('BAT_minus',[(-89,98,29),(-96,93,25),(-96,85,25),(-31,85,25),(-9,78,32)],.85,WI,BLACK)
wire('LOAD_to_boost_plus',[(-7.5,66,31),(0,64,29),(ox+1.905,oy+2.54,29)],.55,WI,RED)
wire('LOAD_to_boost_GND',[(-7.5,64,31),(-1,58,28),(ox+4.445,oy+2.54,29)],.55,WI,BLACK)
# Atom and LoRa separately mounted to plate
AT='11_ATOM_Lite_C008';group(AT,(34,-44,22),desc='24 x 24 x 9.5 mm; screw and port locations approximated')
ax,ay,az=34,-44,22
add('Atom_PC_mount_bracket',drilled(36,32,3,ax,ay,16,[(ax-14,ay,3.4),(ax+14,ay,3.4)],3),AT,PC,'concept')
add('Atom_standoff',ring(4,1.1,3,ax,ay,19),AT,PC,'concept')
add('Atom_body',box(24,24,9.5,ax,ay,az,3),AT,BLACK,'dimensioned_proxy')
add('Atom_front_button',box(19.6,19.6,.55,ax,ay,az+9.0,2.4),AT,(.20,.22,.25,1))
add('Atom_RGB_indicator_proxy',box(3.5,3.5,.3,ax,ay,az+9.55,.5),AT,(.30,.78,.52,1))
add('Atom_USB_C_proxy',box(8.6,2,3,ax,ay-11.9,az+2.8,.4),AT,STEEL)
add('Atom_Grove_proxy',box(10,2,5,ax,ay+11.9,az+2,.4),AT,WHITE)
LO='12_LoRa_E220_U170';group(LO,(79,-8,20),desc='71.4 x 24 x 8 mm; shell/connector details approximated')
lx,ly,lz=79,-8,20
# support bracket separate body, fasteners through plate not hole drilled until measured
add('LoRa_PC_mount_base',drilled(35,79,3,lx,ly,16,[(lx,ly-37,3.4),(lx,ly+37,3.4)],2),LO,PC,'concept')
add('LoRa_unit_body_71p4x24x8',box(24,71.4,8,lx,ly,lz,2),LO,WHITE,'dimensioned_proxy')
add('LoRa_label_window_proxy',box(19,28,.25,lx,ly+9,lz+8,1),LO,(.22,.27,.30,1))
add('LoRa_DIP_switch_proxy',box(12,5,1,lx,ly-13,lz+8,.4),LO,DARK)
for xx in (lx-3,lx+3):add(f'DIP_switch_{xx}',box(1.5,2,.5,xx,ly-13,lz+9),LO,WHITE)
add('LoRa_Grove_proxy',box(10,2,5,lx,ly-35.4,lz+1.5,.5),LO,WHITE)
AN='13_Stock_antenna_110mm';group(AN,(lx,ly+35.7,lz+4),LO,'110 mm total manufacturer length; diameter and SMA geometry proxies')
a0=ly+35.7;az2=lz+4
add('SMA_collar_proxy',cyl(4.5,8,lx,a0,az2,(0,1,0)),AN,GOLD)
add('Antenna_rod_proxy',cyl(4,102,lx,a0+8,az2,(0,1,0)),AN,BLACK,'dimensioned_proxy')
# groove free route no exact harness design
SI='14_Node_wiring';group(SI,(0,0,20),desc='Illustrative wiring paths; 200mm Grove cable with service slack')
wire('5V_out_plus',[(ox+6.985,oy+2.54,29),(24,56,27),(24,36,24),(14,17,21),(14,-15,21),(ax-10,ay-12,25)],.65,SI,RED)
wire('5V_out_GND',[(ox+4.445,oy+2.54,29),(21,53,27),(21,34,24),(11,16,21),(11,-16,21),(ax-8,ay-12,25)],.65,SI,BLACK)
for i,c in enumerate([BLACK,RED,AMBER,WHITE]):
 o=(i-1.5)*1.0
 wire(f'Grove_{i+1}',[(ax+o,ay+12,25),(ax+o,ay+17,24),(ax+7+o,ay+22,22),(lx-17+o,ly-49,22),(lx+o,ly-49,23),(lx+o,ly-35.7,24)],.42,SI,c)
# solar cover with 2 panels. nominal overall depth 150. clear face separately toggleable
CV='15_Cover_PC';group(CV,(0,0,120),desc='Transparent top cover nominal 250 x 350 x 30; geometry simplified')
add('Transparent_PC_frame',frame(250,350,235,335,30,0,0,120,7),CV,CLEAR)
add('Transparent_PC_face',box(250,350,3,0,0,147,7),CV,CLEAR)
add('Gasket_outline_proxy',frame(240,340,234,334,1.5,0,0,119,5),CV,BLACK)
for n,py in [(1,66),(2,-58)]:
 pg=f'16_PV_{n}_SY_M2W'; group(pg,(-43,py,143),CV,('Primary panel' if n==1 else 'Optional second panel (hide for 2W)')+'; 116 x 116 x 3 mm')
 px=-43;pz=143
 add(f'PV{n}_substrate',box(116,116,2.7,px,py,pz,.4),pg,BLACK,'dimensioned_proxy')
 # actual 2 x 6 cell grid, borders approximate, total stack 3mm
 for col in range(2):
  for row in range(6):
   xx=px+(col-.5)*54; yy=py+(row-2.5)*18
   add(f'PV{n}_cell_{col}_{row}',box(52.8,17.4,.25,xx,yy,pz+2.7,.12),pg,BLUE,'dimensioned_proxy')
 for xx in (px-27,px+27):add(f'PV{n}_busbar_{xx}',box(.65,107,.04,xx,py,pz+2.95),pg,STEEL)
 for xx in (px-51,px+51):
  for yy in (py-51,py+51):add(f'PV{n}_adhesive_pad_{xx}_{yy}',box(8,8,1,xx,yy,146,.5),pg,(.82,.85,.86,.6),'concept')
 # backside terminal pads only, no cable to moving lid modeled
 for dx in (-5,5):add(f'PV{n}_rear_contact_{dx}',box(3,3,.3,px+dx,py-5,pz-.3),pg,GOLD)
# Reserved area shown in README, not as solid. Solar cable service loop to be designed after actual hinge measurement.

# ---------- exports ----------
# CAD geometry mm => GLB metres, root transformation from Z-up to glTF Y-up.
ROT=np.array([[1,0,0,0],[0,0,1,0],[0,-1,0,0],[0,0,0,1]],float)

def descendants(g):
    out=[g]; p=GROUPS[g]['parent']
    while p is not None:out.append(p);p=GROUPS[p]['parent']
    return out

def shifts(g,variant):
    if CV in descendants(g) and variant=='inspection':return np.array([280.,0.,-119.])
    if CV in descendants(g) and variant=='exploded':return np.array([0.,0.,65.])
    if variant=='exploded' and g!=G:return np.array([0.,0.,38.])
    return np.zeros(3)

def allowed(g,variant):
    if variant=='backplate':return CV not in descendants(g) and g!=G
    if variant=='tray':return TR in descendants(g) or g==RA
    return True

def mesh_for(s,origin,col):
    vs,fs=s.tessellate(.12,.15)
    v=np.array([[p.x,p.y,p.z] for p in vs],dtype=float)-origin
    m=tm.Trimesh(vertices=v*.001,faces=np.asarray(fs),process=False)
    c=np.array(col)*255
    m.visual=TextureVisuals(material=PBRMaterial(baseColorFactor=c.astype(np.uint8), metallicFactor=.25 if col in (STEEL,GOLD) else 0.,roughnessFactor=.52,alphaMode='BLEND' if col[3]<.99 else 'OPAQUE',doubleSided=True))
    return m

def export_scene(variant):
    sc=tm.Scene(base_frame='world'); sc.graph.update(frame_to='AFP_FE_Node_Rev0_2',frame_from='world',matrix=ROT)
    for g,info in GROUPS.items():
        if not allowed(g,variant):continue
        parent=info['parent']; parent=parent if parent and allowed(parent,variant) else None
        po=GROUPS[parent]['origin']+shifts(parent,variant) if parent else np.zeros(3)
        t=np.eye(4);t[:3,3]=(info['origin']+shifts(g,variant)-po)*.001
        sc.graph.update(frame_to=g,frame_from=parent or 'AFP_FE_Node_Rev0_2',matrix=t)
    for p in PARTS:
        if not allowed(p['g'],variant):continue
        m=mesh_for(p['shape'],GROUPS[p['g']]['origin'],p['col']);sc.add_geometry(m,node_name=p['name'],geom_name=p['name'],parent_node_name=p['g'])
    name=f'AFP_FE_Node_Rev0_2_{variant}.glb'
    (OUT/name).write_bytes(sc.export(file_type='glb'))
    print(name,len(sc.geometry),sc.bounds,flush=True)
    return sc

if __name__=='__main__':
    for variant in ['assembled','inspection','backplate','tray']:export_scene(variant)
    # Mechanical-only STEP, omit flexible routing, tape, adhesive, and small electronic cosmetic proxies.
    asm=cq.Assembly(name='AFP_FE_Node_Rev0_2_mechanical_concept')
    for p in PARTS:
        if p['kind']=='routing_proxy' or p['name'].startswith(('Passive_proxy','SMD_','PV1_cell','PV2_cell','PV1_busbar','PV2_busbar','Plated_ring','PV1_adhesive','PV2_adhesive')):continue
        asm.add(p['shape'],name=p['name'],color=cq.Color(*p['col']))
    asm.save(str(OUT/'AFP_FE_Node_Rev0_2_mechanical.step'),exportType='STEP')
    with open(OUT/'component_register.csv','w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f); w.writerow(['group','parent','origin_x_mm','origin_y_mm','origin_z_mm','fidelity_and_limitations'])
        for k,v in GROUPS.items(): w.writerow([k,v['parent'] or '',*v['origin'],v['description']])
    # Dimension checks on closed assembly in global mm; major envelopes only
    print('Nominal plate:',215.5,315,4,'mm; nominal body:',250,350,150,'mm')
    print('Panel clear edge to antenna rod:',79-4-(-43+58),'mm (projected)')
