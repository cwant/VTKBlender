# Copyright (c) 2005, Chris Want
"""
VTK inside Blender module.

Please see LICENSE and README.md for information about this software.
"""

import vtk
import time, string

try:
    import bpy, bmesh

except:
    print("No Blender module found!")

class BlenderToPolyData:
    ### Below is the public interface of this class

    def __init__(self, me, uvlayer=None):
        self.mesh = me
        self.points = vtk.vtkPoints()
        self.polys = vtk.vtkCellArray()
        self.lines = vtk.vtkCellArray()
        self.pdata = vtk.vtkPolyData()

    def convert_data(self):
        self.create_point_data()
        self.process_faces()
        self.process_edges()
        self.create_pdata()
        #self.process_uvcoords()
        #self.pdata.Update()
        return self.pdata

    @classmethod
    def convert(cls, me, uvlayer=None):
        ob = cls(me, uvlayer)
        return ob.convert_data()

    ## Below should be regarded 'private' ...
    def create_pdata(self):
        self.pdata.SetPoints(self.points)
        self.pdata.SetPolys(self.polys)
        self.pdata.SetLines(self.lines)

    def create_point_data(self):
        pcoords = vtk.vtkFloatArray()
        pcoords.SetNumberOfComponents(3)
        pcoords.SetNumberOfTuples(len(self.mesh.vertices))
        for i in range(len(self.mesh.vertices)):
            v = self.mesh.vertices[i]
            p0 = v.co[0]
            p1 = v.co[1]
            p2 = v.co[2]
            pcoords.SetTuple3(i, p0, p1, p2)

        self.points.SetData(pcoords)

    def process_faces(self):
        for face in self.mesh.polygons:
            self.polys.InsertNextCell(len(face.vertices))
            for i in range(len(face.vertices)):
                self.polys.InsertCellPoint(face.vertices[i])

    def process_edges(self):
        for edge in self.mesh.edges:
            self.lines.InsertNextCell(len(edge.vertices))
            for i in range(len(edge.vertices)):
                self.lines.InsertCellPoint(edge.vertices[i])

    def process_uvcoords(self):
        if me.faceUV:
            if uvlayer:
                uvnames = me.getUVLayerNames()
                if uvlayer in uvnames:
                    me.activeUVLayer = uvlayer
                    tcoords = vtk.vtkFloatArray()
                    tcoords.SetNumberOfComponents(2)
                    tcoords.SetNumberOfTuples(len(me.verts))
                    for face in me.faces:
                        for i in range(len(face.verts)):
                            uv = face.uv[i]
                            tcoords.SetTuple2(face.v[i].index, uv[0], uv[1])
                            pdata.GetPointData().SetTCoords(tcoords);

    
class PolyDataMapperToBlender:
    # some flags to alter behavior
    TRIS_TO_QUADS = 0x01
    SMOOTH_FACES  = 0x02

    ### Below is the public interface for this class
    def __init__(self, pmapper, me=None):
        self.initialize_work_data()
        self.initialize_mesh(me)
        self.pmapper = pmapper

    def convert_data(self):
        self.initialize_work_data()
        self.pmapper.Update()

        pdata = self.pmapper.GetInput()
        plut = self.pmapper.GetLookupTable()
        scalars  = pdata.GetPointData().GetScalars()

        #print(pdata.GetNumberOfCells())

        self.point_data_to_verts(pdata)
        self.read_colors(scalars, plut)
        self.process_topology(pdata, scalars)

        self.mesh.from_pydata(self.verts, self.edges, self.faces)

        self.set_smooth()
        self.apply_vertex_colors()
        #self.set_materials()
        if (not self.newmesh):
            self.mesh.update()

        return self.mesh

    @classmethod
    def convert(cls, pmapper, me=None):
        ob = cls(pmapper, me)
        return ob.convert_data()

    # What is this 'tri to quad' stuff? Well, sometimes it's best to
    # try to read in pairs of consecutive triangles in as quad faces.
    # An example: you extrude a tube along a polyline in vtk, and if 
    # you can get it into Blender as a bunch of quads, you can use a 
    # Catmull-Clark subdivision surface to smooth the tube out, with
    # fewer creases.

    def set_tris_to_quads(self):
        self.flags = flags | self.TRIS_TO_QUADS
    
    def set_tris_to_tris(self):
        self.flags = flags & ~self.TRIS_TO_QUADS

    def set_faces_to_smooth(self):
        self.flags = flags | self.SMOOTH_FACES

    def set_faces_to_faceted(self):
        self.flags = flags & ~self.SMOOTH_FACES

    ### Below should be considered private to this class

    def initialize_work_data(self):
        self.verts = []
        self.faces = []
        self.edges = []
        self.oldmats = None
        self.colors = None
        self.flags = 0

    def initialize_mesh(self, me=None):
        self.newmesh = False
        if (me == None):
            self.mesh = bpy.data.meshes.new("VTKBlender")
            self.newmesh = True
        else:
            self.mesh = me
            self.remove_mesh_data()
            if me.materials:
                self.oldmats = me.materials

    def remove_mesh_data(self):
        bm = bmesh.new()
        bm.from_mesh(self.mesh)
        all_verts = [v for v in bm.verts]
        DEL_VERTS = 1
        bmesh.ops.delete(bm, geom=all_verts, context=DEL_VERTS)
        bm.to_mesh(self.mesh)

    def point_data_to_verts(self, pdata):
        self.verts = []
        for i in range(pdata.GetNumberOfPoints()):
            point = pdata.GetPoint(i)
            self.add_vert(point[0],point[1],point[2])

    def add_vert(self, x, y, z):
        self.verts.append([x, y, z])

    def read_colors(self, scalars, plut):
        if ( (scalars != None) and (plut != None) ):
            self.colors = []

            scolor = [0,0,0]
            for i in range(scalars.GetNumberOfTuples()):
                plut.GetColor(scalars.GetTuple1(i), scolor)

                color = scolor
                alpha = plut.GetOpacity(scalars.GetTuple1(i))
                self.colors.append([scolor[0], scolor[1], scolor[2], alpha])

    def set_smooth(self):
        if ( self.flags & self.SMOOTH_FACES):
            for f in me.faces:
                f.smooth = 1

    def apply_vertex_colors(self):
        # Some faces in me.faces may have been discarded from our
        # list, so best to compute the vertex colors after the faces
        # have been added to the mesh
        if (self.colors != None):
            if not self.mesh.vertex_colors:
                self.mesh.vertex_colors.new()
            color_layer = self.mesh.vertex_colors.active
            i = 0
            for poly in self.mesh.polygons:
                for idx in poly.vertices:
                  rgb = self.colors[idx]
                  # No alpha? Why Blender, why?
                  color_layer.data[i].color = rgb[0:3]
                  i += 1

    def set_materials(self):
        if not self.mesh.materials:
            if self.oldmats:
                self.mesh.materials = oldmats
            else:
                newmat = Material.New()
                if (colors != None):
                    newmat.mode |= Material.Modes.VCOL_PAINT
                    self.mesh.materials = [newmat]

    def process_line(self, cell):
        n1 = cell.GetPointId(0)
        n2 = cell.GetPointId(1)
        self.add_edge(n1, n2)

    def process_polyline(self, cell):
        for j in range(cell.GetNumberOfPoints()-1):
            n1 = cell.GetPointId(j)
            n2 = cell.GetPointId(j+1)
            self.add_edge(n1, n2)

    def process_triangle(self, cell, skiptriangle):
        if skiptriangle:
            skiptriangle = False
            return

        if ( (self.flags & self.TRIS_TO_QUADS) and
               (i < pdata.GetNumberOfCells()-1) and
               (pdata.GetCellType(i+1)==5) ):
            n1 = cell.GetPointId(0)
            n2 = cell.GetPointId(1)
            n3 = cell.GetPointId(2)
            nextcell = pdata.GetCell(i+1)
            m1 = nextcell.GetPointId(0)
            m2 = nextcell.GetPointId(1)
            m3 = nextcell.GetPointId(2)
            if ( (n2 == m3) and (n3 == m2) ):
                self.add_face(n1, n2, m1, n3)
                skiptriangle = True
            else:
                self.add_face(n1, n2, n3)

        else:
            n1 = cell.GetPointId(0)
            n2 = cell.GetPointId(1)
            n3 = cell.GetPointId(2)

            self.add_face(n1, n2, n3)

    def process_triangle_strip(self, cell):
        numpoints = cell.GetNumberOfPoints()
        if ( (self.flags & self.TRIS_TO_QUADS) and (numpoints % 2 == 0) ):
            for j in range(cell.GetNumberOfPoints()-3):
                if (j % 2 == 0):
                    n1 = cell.GetPointId(j)
                    n2 = cell.GetPointId(j+1)
                    n3 = cell.GetPointId(j+2)
                    n4 = cell.GetPointId(j+3)

                    self.add_face(n1, n2, n4, n3)
        else:
            for j in range(cell.GetNumberOfPoints()-2):
                if (j % 2 == 0):
                    n1 = cell.GetPointId(j)
                    n2 = cell.GetPointId(j+1)
                    n3 = cell.GetPointId(j+2)
                else:
                    n1 = cell.GetPointId(j)
                    n2 = cell.GetPointId(j+2)
                    n3 = cell.GetPointId(j+1)

                self.add_face(n1, n2, n3)

    def process_polygon(self, cell, pdata, scalars):
        # Add a vert at the center of the polygon,
        # and break into triangles
        x    = 0.0
        y    = 0.0
        z    = 0.0
        scal = 0.0
        N = cell.GetNumberOfPoints()
        for j in range(N):
            point = pdata.GetPoint(cell.GetPointId(j))
            x = x + point[0]
            y = y + point[1]
            z = z + point[2]
            if (scalars != None):
                scal = scal + scalars.GetTuple1(j)

        x = x / N
        y = y / N
        z = z / N
        scal = scal / N

        newidx = len(self.verts)
        self.add_vert(x, y, z)

        if (scalars != None):
            scolor = [0,0,0]
            plut.GetColor(scal, scolor)
            color = map(vtk_to_blender_color, scolor)
            alpha = int(plut.GetOpacity(scalars.GetTuple1(i))*255)
            colors.append([color[0], color[1], color[2], alpha])

        # Add triangles connecting polynomial sides to new vert
        for j in range(N):
            n1 = cell.GetPointId(j)
            n2 = cell.GetPointId( (j+1) % N )
            n3 = newidx
            self.add_face(n1, n2, n3)

    def process_pixel(self, cell):
        n1 = cell.GetPointId(0)
        n2 = cell.GetPointId(1)
        n3 = cell.GetPointId(2)
        n4 = cell.GetPointId(3)

        self.add_face(n1, n2, n3, n4)

    def process_quad(self, cell):
        n1 = cell.GetPointId(0)
        n2 = cell.GetPointId(1)
        n3 = cell.GetPointId(2)
        n4 = cell.GetPointId(3)

        self.add_face(n1, n2, n3, n4)

    def process_topology(self, pdata, scalars):
        skiptriangle = False

        for i in range(pdata.GetNumberOfCells()):
            cell = pdata.GetCell(i)

            # print(i, pdata.GetCellType(i))

            # Do line
            if pdata.GetCellType(i)==3:
                self.process_line(cell)

            # Do poly lines
            if pdata.GetCellType(i)==4:
                self.process_polyline(cell)

            # Do triangles
            if pdata.GetCellType(i)==5:
                self.process_triangle(cell, skiptriangle)

            # Do triangle strips
            if pdata.GetCellType(i)==6:
                self.process_triangle_strip(cell)

            # Do polygon
            if pdata.GetCellType(i)==7:
                self.process_polygon(cell, pdata, scalars)

            # Do pixel
            if pdata.GetCellType(i)==8:
                self.process_pixel(cell)

            # Do quad
            if pdata.GetCellType(i)==9:
                self.process_quad(cell)


    def vtk_to_blender_color(self, x):
        return int(255*float(x)+0.5)

    def add_face(self, n1, n2, n3, n4=None):
        if (n4 != None):
            self.faces.append([n1, n2, n3, n4])
        else:
            self.faces.append([n1, n2, n3])
    
    def add_edge(self, n1, n2):
        self.edges.append([n1, n2])
