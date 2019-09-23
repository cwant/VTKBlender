# Copyright (c) 2005, Chris Want
"""
VTK inside Blender module.

Please see LICENSE and README.md for information about this software.
"""

import vtk

try:
    import bpy
    import bmesh
except:
    print("No Blender module found!")


class BlenderToPolyData:
    # Below is the public interface of this class
    def __init__(self, me, uvlayer=None):
        self.uvlayer = uvlayer
        self.mesh = me
        self.points = vtk.vtkPoints()
        self.polys = vtk.vtkCellArray()
        self.lines = vtk.vtkCellArray()
        self.pdata = vtk.vtkPolyData()

    def convert_data(self):
        self.__create_point_data()
        self.__process_faces()
        self.__process_edges()
        self.__create_pdata()
        # self.process_uvcoords(self.uvlayer)
        # self.pdata.Update()
        return self.pdata

    @classmethod
    def convert(cls, me, uvlayer=None):
        ob = cls(me, uvlayer)
        return ob.convert_data()

    # Below should be regarded 'private' ...
    def __create_pdata(self):
        self.pdata.SetPoints(self.points)
        self.pdata.SetPolys(self.polys)
        self.pdata.SetLines(self.lines)

    def __create_point_data(self):
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

    def __process_faces(self):
        for face in self.mesh.polygons:
            self.polys.InsertNextCell(len(face.vertices))
            for i in range(len(face.vertices)):
                self.polys.InsertCellPoint(face.vertices[i])

    def __process_edges(self):
        for edge in self.mesh.edges:
            self.lines.InsertNextCell(len(edge.vertices))
            for i in range(len(edge.vertices)):
                self.lines.InsertCellPoint(edge.vertices[i])

    # def __process_uvcoords(self):
    #     if me.faceUV:
    #         if uvlayer:
    #             uvnames = me.getUVLayerNames()
    #             if uvlayer in uvnames:
    #                 me.activeUVLayer = uvlayer
    #                 tcoords = vtk.vtkFloatArray()
    #                 tcoords.SetNumberOfComponents(2)
    #                 tcoords.SetNumberOfTuples(len(me.verts))
    #                 for face in me.faces:
    #                     for i in range(len(face.verts)):
    #                         uv = face.uv[i]
    #                         tcoords.SetTuple2(face.v[i].index, uv[0], uv[1])
    #                         pdata.GetPointData().SetTCoords(tcoords);


class PolyDataMapperToBlender:
    # some flags to alter behavior
    TRIS_TO_QUADS = 0x01
    SMOOTH_FACES = 0x02

    # Below is the public interface for this class
    def __init__(self, pmapper, me=None):
        self.__initialize_work_data()
        self.__initialize_mesh(me)
        self.pmapper = pmapper
        self.flags = 0

    def convert_data(self):
        self.__initialize_work_data()
        self.pmapper.Update()

        pdata = self.pmapper.GetInput()
        plut = self.pmapper.GetLookupTable()
        scalars = pdata.GetPointData().GetScalars()

        # print(pdata.GetNumberOfCells())

        self.__point_data_to_verts(pdata)
        self.__read_colors(scalars, plut)
        self.__process_topology(pdata, scalars)

        self.mesh.from_pydata(self.verts, self.edges, self.faces)

        self.__set_smooth()
        self.__apply_vertex_colors()

        if not self.newmesh:
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
        self.flags = self.flags | self.TRIS_TO_QUADS

    def set_tris_to_tris(self):
        self.flags = self.flags & ~self.TRIS_TO_QUADS

    def set_faces_to_smooth(self):
        self.flags = self.flags | self.SMOOTH_FACES

    def set_faces_to_faceted(self):
        self.flags = self.flags & ~self.SMOOTH_FACES

    # Below should be considered private to this class

    def __initialize_work_data(self):
        self.verts = []
        self.faces = []
        self.edges = []
        self.oldmats = None
        self.colors = None
        self.flags = 0

    def __initialize_mesh(self, me=None):
        self.newmesh = False
        if me is None:
            self.mesh = bpy.data.meshes.new("VTKBlender")
            self.newmesh = True
        else:
            self.mesh = me
            self.__remove_mesh_data()
            if me.materials:
                self.oldmats = me.materials

    def __remove_mesh_data(self):
        bm = bmesh.new()
        bm.from_mesh(self.mesh)
        all_verts = [v for v in bm.verts]
        bmesh.ops.delete(bm, geom=all_verts, context='VERTS')
        bm.to_mesh(self.mesh)

    def __point_data_to_verts(self, pdata):
        self.verts = []
        for i in range(pdata.GetNumberOfPoints()):
            point = pdata.GetPoint(i)
            self.__add_vert(point[0], point[1], point[2])

    def __add_vert(self, x, y, z):
        self.verts.append([x, y, z])

    def __read_colors(self, scalars, plut):
        if (scalars is not None) and (plut is not None):
            self.colors = []

            scolor = [0, 0, 0]
            for i in range(scalars.GetNumberOfTuples()):
                plut.GetColor(scalars.GetTuple1(i), scolor)

                color = scolor
                alpha = plut.GetOpacity(scalars.GetTuple1(i))
                self.colors.append([scolor[0], scolor[1], scolor[2], alpha])

    def __set_smooth(self):
        if self.flags & self.SMOOTH_FACES:
            for f in me.faces:
                f.smooth = 1

    def __apply_vertex_colors(self):
        # Some faces in me.faces may have been discarded from our
        # list, so best to compute the vertex colors after the faces
        # have been added to the mesh
        if self.colors is not None:
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

    # def __set_materials(self):
    #     if not self.mesh.materials:
    #         if self.oldmats:
    #             self.mesh.materials = self.oldmats
    #         else:
    #             newmat = Material.New()
    #             if colors is not None:
    #                 newmat.mode |= Material.Modes.VCOL_PAINT
    #                 self.mesh.materials = [newmat]

    def __process_line(self, cell):
        n1 = cell.GetPointId(0)
        n2 = cell.GetPointId(1)
        self.__add_edge(n1, n2)

    def __process_polyline(self, cell):
        for j in range(cell.GetNumberOfPoints() - 1):
            n1 = cell.GetPointId(j)
            n2 = cell.GetPointId(j + 1)
            self.__add_edge(n1, n2)

    def __process_triangle(self, cell, skiptriangle):
        if skiptriangle:
            skiptriangle = False
            return

        if ((self.flags & self.TRIS_TO_QUADS) and
                (i < pdata.GetNumberOfCells() - 1) and
                (pdata.GetCellType(i + 1) == 5)):
            n1 = cell.GetPointId(0)
            n2 = cell.GetPointId(1)
            n3 = cell.GetPointId(2)
            nextcell = pdata.GetCell(i + 1)
            m1 = nextcell.GetPointId(0)
            m2 = nextcell.GetPointId(1)
            m3 = nextcell.GetPointId(2)
            if (n2 == m3) and (n3 == m2):
                self.__add_face(n1, n2, m1, n3)
                skiptriangle = True
            else:
                self.__add_face(n1, n2, n3)

        else:
            n1 = cell.GetPointId(0)
            n2 = cell.GetPointId(1)
            n3 = cell.GetPointId(2)

            self.__add_face(n1, n2, n3)

    def __process_triangle_strip(self, cell):
        numpoints = cell.GetNumberOfPoints()
        if (self.flags & self.TRIS_TO_QUADS) and (numpoints % 2 == 0):
            for j in range(cell.GetNumberOfPoints() - 3):
                if j % 2 == 0:
                    n1 = cell.GetPointId(j)
                    n2 = cell.GetPointId(j + 1)
                    n3 = cell.GetPointId(j + 2)
                    n4 = cell.GetPointId(j + 3)

                    self.__add_face(n1, n2, n4, n3)
        else:
            for j in range(cell.GetNumberOfPoints() - 2):
                if j % 2 == 0:
                    n1 = cell.GetPointId(j)
                    n2 = cell.GetPointId(j + 1)
                    n3 = cell.GetPointId(j + 2)
                else:
                    n1 = cell.GetPointId(j)
                    n2 = cell.GetPointId(j + 2)
                    n3 = cell.GetPointId(j + 1)

                self.__add_face(n1, n2, n3)

    def __process_polygon(self, cell, pdata, scalars):
        # Add a vert at the center of the polygon,
        # and break into triangles
        x = 0.0
        y = 0.0
        z = 0.0
        scal = 0.0
        N = cell.GetNumberOfPoints()
        for j in range(N):
            point = pdata.GetPoint(cell.GetPointId(j))
            x = x + point[0]
            y = y + point[1]
            z = z + point[2]
            if scalars is not None:
                scal = scal + scalars.GetTuple1(j)

        x = x / N
        y = y / N
        z = z / N
        scal = scal / N

        newidx = len(self.verts)
        self.__add_vert(x, y, z)

        if scalars is not None:
            scolor = [0, 0, 0]
            plut.GetColor(scal, scolor)
            color = map(self.__vtk_to_blender_color, scolor)
            alpha = int(plut.GetOpacity(scalars.GetTuple1(i)) * 255)
            colors.append([color[0], color[1], color[2], alpha])

        # Add triangles connecting polynomial sides to new vert
        for j in range(N):
            n1 = cell.GetPointId(j)
            n2 = cell.GetPointId((j + 1) % N)
            n3 = newidx
            self.__add_face(n1, n2, n3)

    def __process_pixel(self, cell):
        n1 = cell.GetPointId(0)
        n2 = cell.GetPointId(1)
        n3 = cell.GetPointId(2)
        n4 = cell.GetPointId(3)

        self.__add_face(n1, n2, n3, n4)

    def __process_quad(self, cell):
        n1 = cell.GetPointId(0)
        n2 = cell.GetPointId(1)
        n3 = cell.GetPointId(2)
        n4 = cell.GetPointId(3)

        self.__add_face(n1, n2, n3, n4)

    def __process_topology(self, pdata, scalars):
        skiptriangle = False

        for i in range(pdata.GetNumberOfCells()):
            cell = pdata.GetCell(i)

            print(i, pdata.GetCellType(i))

            # Do line
            if pdata.GetCellType(i) == 3:
                self.__process_line(cell)

            # Do poly lines
            if pdata.GetCellType(i) == 4:
                self.__process_polyline(cell)

            # Do triangles
            if pdata.GetCellType(i) == 5:
                self.__process_triangle(cell, skiptriangle)

            # Do triangle strips
            if pdata.GetCellType(i) == 6:
                self.__process_triangle_strip(cell)

            # Do polygon
            if pdata.GetCellType(i) == 7:
                self.__process_polygon(cell, pdata, scalars)

            # Do pixel
            if pdata.GetCellType(i) == 8:
                self.__process_pixel(cell)

            # Do quad
            if pdata.GetCellType(i) == 9:
                self.__process_quad(cell)

    def __vtk_to_blender_color(self, x):
        return int(255 * float(x) + 0.5)

    def __add_face(self, n1, n2, n3, n4=None):
        if n4 is not None:
            self.faces.append([n1, n2, n3, n4])
        else:
            self.faces.append([n1, n2, n3])

    def __add_edge(self, n1, n2):
        self.edges.append([n1, n2])
