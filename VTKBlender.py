# $Id: VTKBlender.py,v 1.19 2008-07-03 15:13:21 cwant Exp $
#
# Copyright (c) 2005, Chris Want, Research Support Group,
# AICT, University of Alberta. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without 
# modification, are permitted provided that the following conditions are met:
#
# 1) Redistributions of source code must retain the above copyright 
#    notice, this list of conditions and the following disclaimer.
# 2) Redistributions in binary form must reproduce the above copyright 
#    notice, this list of conditions and the following disclaimer in the 
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE 
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE 
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE 
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR 
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF 
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS 
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN 
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) 
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF 
# THE POSSIBILITY OF SUCH DAMAGE.
#
# Contributors: Chris Want (University of Alberta),
#               Fritz Mielert (University of Stuttgart)
"""
VTK inside Blender module.

    This module provides code so that polydata from vtk can
    be used inside of blender.

    Python needs to find the vtk stuff and this module in order
    for this to work, and you can either a) set your PYTHONPATH
    in your environment, or you can b) hardcode your vtk path's
    in your script, e.g.,

    a) at the prompt, before starting blender, type:
       PYTHONPATH=$VTK_ROOT/Wrapping/Python:${LIBRARY_OUTPUT_PATH}
	   PYTHONPATH=$PYTHONPATH:${PATH_TO_THIS_MODULE}
	   export PYTHONPATH

    b) add the following to your script near the beginning, before
	   importing vtk or VTKBlender:
	   
       import sys
       sys.path.append($VTK_ROOT/Wrapping/Python)
       sys.path.append(${LIBRARY_OUTPUT_PATH})
       sys.path.append(${PATH_TO_VTKBlender_MODULE})

    Be sure to replace $VTK_ROOT and ${LIBRARY_OUTPUT_PATH} with
    values that are relevant to your system. These values can be
    found by starting vtkpython with no arguments and typing:

    import sys
    print sys.path

	Usually the first two items reported are the ones you want.

	Also replace ${PATH_TO_VTKBlender_MODULE} with wherever you have
	put the VTKBlender module.
"""

import vtk
import time, string

try:
	import Blender
	from Blender import Mesh, Object, Material

except:
	print "No Blender module found!"

__versiontag__ = "$Revision: 1.19 $"
__version__    = string.split(__versiontag__)[1]

# some flags to alter behavior
flags = 0
TRIS_TO_QUADS = 0x01
SMOOTH_FACES  = 0x02

# What is this 'tri to quad' stuff? Well, sometimes it's best to
# try to read in pairs of consecutive triangles in as quad faces.
# An example: you extrude a tube along a polyline in vtk, and if 
# you can get it into Blender as a bunch of quads, you can use a 
# Catmull-Clark subdivision surface to smooth the tube out, with
# fewer creases.

def SetTrisToQuads():
	global flags
	flags = flags | TRIS_TO_QUADS
	
def SetTrisToTris():
	global flags
	flags = flags & ~TRIS_TO_QUADS

def SetFacesToSmooth():
	global flags
	flags = flags | SMOOTH_FACES

def SetFacesToFaceted():
	global flags
	flags = flags & ~SMOOTH_FACES

def BlenderToPolyData(me, uvlayer=None):

	pcoords = vtk.vtkFloatArray()
	pcoords.SetNumberOfComponents(3)
	pcoords.SetNumberOfTuples(len(me.verts))
	for i in range(len(me.verts)):
		p0 = me.verts[i].co[0]
		p1 = me.verts[i].co[1]
		p2 = me.verts[i].co[2]
		pcoords.SetTuple3(i, p0, p1, p2)

	points = vtk.vtkPoints()
	points.SetData(pcoords)

	polys = vtk.vtkCellArray()
	lines = vtk.vtkCellArray()
	for face in me.faces:
		if len(face.v) == 4:
			polys.InsertNextCell(4)
			polys.InsertCellPoint(face.v[0].index)
			polys.InsertCellPoint(face.v[1].index)
			polys.InsertCellPoint(face.v[2].index)
			polys.InsertCellPoint(face.v[3].index)
		elif len(face.v) == 3:
			polys.InsertNextCell(3)
			polys.InsertCellPoint(face.v[0].index)
			polys.InsertCellPoint(face.v[1].index)
			polys.InsertCellPoint(face.v[2].index)
		elif len(face.v) == 2:
			lines.InsertNextCell(2)
			lines.InsertCellPoint(face.v[0].index)
			lines.InsertCellPoint(face.v[1].index)

	for edge in me.edges:
		lines.InsertNextCell(2)
		lines.InsertCellPoint(edge.v1.index)
		lines.InsertCellPoint(edge.v2.index)

	pdata =vtk.vtkPolyData()
	pdata.SetPoints(points)
	pdata.SetPolys(polys)
	pdata.SetLines(lines)

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

	pdata.Update()

	return pdata
	
def PolyDataMapperToBlender(pmapper, me=None):
	global flags
	faces   = []
	edges   = []
	oldmats = None

	newmesh = 0
	if (me == None):
		me = Mesh.New()
		newmesh = 1
	else:
		if me.materials:
			oldmats = me.materials

		me.verts = None # this kills the faces/edges tooo

	pmapper.Update()

	pdata = pmapper.GetInput()
	plut  = pmapper.GetLookupTable()
	#print pdata.GetNumberOfCells()

	scalars  = pdata.GetPointData().GetScalars()

	verts = []
	for i in range(pdata.GetNumberOfPoints()):
		point = pdata.GetPoint(i)
		verts.append([point[0],point[1],point[2]])

	me.verts.extend(verts)
	# I think we can free some memory by killing the reference
	# from vert to the list it points at (not sure though)
	verts = []

	colors = None

	if ( (scalars != None) and (plut != None) ):
		colors = []

		# Have to be a bit careful since VTK 5.0 changed the
		# prototype of vtkLookupTable.GetColor()
		try:
			# VTK 5.x
			scolor = [0,0,0]
			for i in range(scalars.GetNumberOfTuples()):
				plut.GetColor(scalars.GetTuple1(i), scolor)
				color = map(VTKToBlenderColor, scolor)
				alpha = int(plut.GetOpacity(scalars.GetTuple1(i))*255)
				colors.append([color[0], color[1], color[2], alpha])

		except:
			# VTK 4.x
			for i in range(scalars.GetNumberOfTuples()):
				color = map(VTKToBlenderColor, \
							plut.GetColor(scalars.GetTuple1(i)))
				alpha = int(plut.GetOpacity(scalars.GetTuple1(i))*255)
				colors.append([color[0], color[1], color[2], alpha])

	skiptriangle = False
	for i in range(pdata.GetNumberOfCells()):

		cell = pdata.GetCell(i)

		#print i, pdata.GetCellType(i)

		# Do lines
		if pdata.GetCellType(i)==3:

			n1 = cell.GetPointId(0)
			n2 = cell.GetPointId(1)

			BlenderAddEdge(me, edges, n1, n2)

		# Do poly lines
		if pdata.GetCellType(i)==4:
			for j in range(cell.GetNumberOfPoints()-1):

				n1 = cell.GetPointId(j)
				n2 = cell.GetPointId(j+1)
				
				BlenderAddEdge(me, edges, n1, n2)

		# Do triangles
		if pdata.GetCellType(i)==5:
			if skiptriangle==True:
				skiptriangle = False
			elif ( (flags & TRIS_TO_QUADS) and
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
					BlenderAddFace(me, faces, n1, n2, m1, n3)
					skiptriangle = True
				else:
					BlenderAddFace(me, faces, n1, n2, n3)

			else:
				n1 = cell.GetPointId(0)
				n2 = cell.GetPointId(1)
				n3 = cell.GetPointId(2)

				BlenderAddFace(me, faces, n1, n2, n3)

		# Do triangle strips
		if pdata.GetCellType(i)==6:
			numpoints = cell.GetNumberOfPoints()
			if ( (flags & TRIS_TO_QUADS) and (numpoints % 2 == 0) ):
				for j in range(cell.GetNumberOfPoints()-3):
					if (j % 2 == 0):
						n1 = cell.GetPointId(j)
						n2 = cell.GetPointId(j+1)
						n3 = cell.GetPointId(j+2)
						n4 = cell.GetPointId(j+3)

						BlenderAddFace(me, faces, n1, n2, n4, n3)
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

					BlenderAddFace(me, faces, n1, n2, n3)
		# Do polygon
		if pdata.GetCellType(i)==7:
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
			x    = x / N
			y    = y / N
			z    = z / N
			scal = scal / N

			newidx = len(me.verts)
			me.verts.extend(x,y,z)

			if (scalars != None):
				try:
					# VTK 5.x
					scolor = [0,0,0]
					plut.GetColor(scal, scolor)
					color = map(VTKToBlenderColor, scolor)
				except:
					color = map(VTKToBlenderColor, plut.GetColor(scal))
				alpha = int(plut.GetOpacity(scalars.GetTuple1(i))*255)

				colors.append([color[0], color[1], color[2], alpha])

			# Add triangles connecting polynomial sides to new vert
			for j in range(N):
				n1 = cell.GetPointId(j)
				n2 = cell.GetPointId( (j+1) % N )
				n3 = newidx
				BlenderAddFace(me, faces, n1, n2, n3)

		# Do pixel
		if pdata.GetCellType(i)==8:
			n1 = cell.GetPointId(0)
			n2 = cell.GetPointId(1)
			n3 = cell.GetPointId(2)
			n4 = cell.GetPointId(3)

			BlenderAddFace(me, faces, n1, n2, n3, n4)
		# Do quad
		if pdata.GetCellType(i)==9:
			n1 = cell.GetPointId(0)
			n2 = cell.GetPointId(1)
			n3 = cell.GetPointId(2)
			n4 = cell.GetPointId(3)

			BlenderAddFace(me, faces, n1, n2, n3, n4)

	if len(edges) > 0:
		me.edges.extend(edges)
	if len(faces) > 0:
		me.faces.extend(faces)

		if ( flags & SMOOTH_FACES):
			for f in me.faces:
				f.smooth = 1

	# Some faces in me.faces may have been discarded from our
	# list, so best to compute the vertex colors after the faces
	# have been added to the mesh
	if (colors != None):
		me.vertexColors = 1
		for f in me.faces:
			f_col = []
			for v in f.v:
				f_col.append(colors[v.index])

			SetVColors(f.col, f_col)

	if not me.materials:
		if oldmats:
			me.materials = oldmats
		else:
			newmat = Material.New()
			if (colors != None):
				newmat.mode |= Material.Modes.VCOL_PAINT
			me.materials = [newmat]

	if (newmesh==0):
		me.update()

	return me

def VTKToBlenderColor(x):
	return int(255*float(x)+0.5)

def BlenderAddFace(me, faces, n1, n2, n3, n4=None):

	if (n4 != None):
		faces.append([me.verts[n1], me.verts[n2], \
						 me.verts[n3], me.verts[n4]])
	else:
		faces.append([me.verts[n1], me.verts[n2], me.verts[n3]])
	
def BlenderAddEdge(me, edges, n1, n2):
	edges.append([me.verts[n1], me.verts[n2]])

	
def	SetVColors(col, vcols):
	for j in range(len(col)):

		col[j].r = vcols[j][0]
		col[j].g = vcols[j][1]
		col[j].b = vcols[j][2]
		if len(vcols[j]) == 3:
			col[j].a = 255
		else:
			col[j].a = vcols[j][3]	
	
