from pathlib import Path
import numpy as np
import trimesh
import vtk
from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
from PIL import Image, ImageDraw, ImageFont
P=Path(__file__).resolve().parent

def render(variant,camera,focus,scale,width,height,filename):
    sc=trimesh.load(P/f'AFP_FE_Node_Rev0_2_{variant}.glb',force='scene')
    ren=vtk.vtkRenderer(); ren.SetBackground(.955,.967,.977);ren.SetAmbient(.22,.22,.22)
    # Use CAD axes: x width, y length, z toward cover (convert glTF back to Z-up).
    conv=np.array([[1,0,0,0],[0,0,-1,0],[0,1,0,0],[0,0,0,1]])
    for node in sc.graph.nodes_geometry:
        trans,key=sc.graph[node]; mesh=sc.geometry[key]; v=trimesh.transform_points(mesh.vertices,conv@trans)*1000
        pd=vtk.vtkPolyData(); pts=vtk.vtkPoints();pts.SetData(numpy_to_vtk(np.ascontiguousarray(v),deep=True));pd.SetPoints(pts)
        a=np.column_stack([np.full(len(mesh.faces),3),mesh.faces]).astype(np.int64).ravel(); ca=vtk.vtkCellArray();ca.SetCells(len(mesh.faces),numpy_to_vtkIdTypeArray(a,deep=True));pd.SetPolys(ca)
        normals=vtk.vtkPolyDataNormals();normals.SetInputData(pd);normals.ComputePointNormalsOff();normals.ComputeCellNormalsOn();normals.Update()
        mapper=vtk.vtkPolyDataMapper();mapper.SetInputConnection(normals.GetOutputPort());act=vtk.vtkActor();act.SetMapper(mapper)
        mat=mesh.visual.material;c=np.asarray(mat.baseColorFactor)/255.0
        act.GetProperty().SetColor(*c[:3]);act.GetProperty().SetOpacity(float(c[3]));act.GetProperty().SetAmbient(.28);act.GetProperty().SetDiffuse(.72);act.GetProperty().SetSpecular(.14);act.GetProperty().SetSpecularPower(18)
        if 'Transparent_PC' in node:act.GetProperty().SetOpacity(.11 if 'face' in node else .26)
        ren.AddActor(act)
    cam=ren.GetActiveCamera();cam.SetPosition(*camera);cam.SetFocalPoint(*focus);cam.SetViewUp(0,1,0);cam.ParallelProjectionOn();cam.SetParallelScale(scale);ren.ResetCameraClippingRange()
    for pos,intensity in [((200,-400,700),.95),((-500,400,500),.42),((200,500,100),.35)]:
        l=vtk.vtkLight();l.SetPosition(*pos);l.SetFocalPoint(*focus);l.SetIntensity(intensity);ren.AddLight(l)
    win=vtk.vtkRenderWindow();win.SetOffScreenRendering(1);win.AddRenderer(ren);win.SetSize(width,height);win.SetMultiSamples(4);ren.UseDepthPeelingOn();ren.SetMaximumNumberOfPeels(40);ren.SetOcclusionRatio(.05);win.SetAlphaBitPlanes(1);win.Render()
    w=vtk.vtkWindowToImageFilter();w.SetInput(win);w.Update();writer=vtk.vtkPNGWriter();writer.SetFileName(str(P/filename));writer.SetInputConnection(w.GetOutputPort());writer.Write();win.Finalize()

render('inspection',(465,-460,1100),(140,0,40),245,1550,1000,'preview_inspection_raw.png')
render('backplate',(140,-240,780),(0,0,20),193,1050,1050,'preview_backplate_raw.png')
render('tray',(5,15,240),(-36,83,27),57,1350,940,'preview_tray_raw.png')
# Compose a clean overview with actual geometry renders; labels kept English for portable font.
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def F(n,b=False):return ImageFont.truetype(bold if b else font,n)
canvas=Image.new('RGB',(1800,1500),'#f4f7fa');d=ImageDraw.Draw(canvas)
d.rectangle((0,0,1800,120),fill='#20354d');d.text((48,23),'AFP LAB  /  FIELD ENGINEERING',font=F(28,True),fill='#cfe0ef');d.text((48,58),'FE-NODE-001   |   Rev. 0.2  /  Assembly concept',font=F(38,True),fill='white')
d.text((48,141),'01   INSPECTION VIEW',font=F(24,True),fill='#20354d');d.text((48,176),'BCAP253515T + BMP2535P   •   2 × SY-M2W / 4 W option',font=F(22),fill='#4b5c70')
im=Image.open(P/'preview_inspection_raw.png').convert('RGB');im.thumbnail((1150,790));canvas.paste(im,(32,210))
d.text((1190,141),'02   BACKPLATE',font=F(24,True),fill='#20354d');d.text((1190,176),'215.5 × 315 × 4 mm',font=F(22),fill='#4b5c70');im=Image.open(P/'preview_backplate_raw.png').convert('RGB');im.thumbnail((600,670));canvas.paste(im,(1195,210))
d.line((45,980,1755,980),fill='#a8b8c6',width=2);d.text((48,1001),'03   POWER TRAY  /  126 × 76 mm floor',font=F(26,True),fill='#20354d');d.text((48,1037),'Sensor head sits on cell surface. Tape is the first-test fixing method.',font=F(21),fill='#4b5c70')
im=Image.open(P/'preview_tray_raw.png').convert('RGB');im.thumbnail((800,420));canvas.paste(im,(80,1072))
d.text((920,1104),'Independent modules',font=F(24,True),fill='#20354d');
for i,t in enumerate(['•  18650 holder / JT100 surface thermistor','•  BQ25185 charger / MiniBoost converter','•  Inline fuse / PC removable tray','•  ATOM Lite / E220 radio / stock antenna']):d.text((920,1142+i*39),t,font=F(22),fill='#35495c')
d.text((920,1330),'Dimensioned proxies; not production CAD.',font=F(21,True),fill='#985f20');d.text((920,1365),'Connector locations, mounting details and actual fit TBD.',font=F(18),fill='#4b5c70');
canvas.save(P/'AFP_FE_Node_Rev0_2_preview.png')
