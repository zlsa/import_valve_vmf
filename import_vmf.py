
import traceback
import mathutils
import math
import bpy
import bmesh 

# plane is a list with four elements:
# [a, b, c, d]
# where ax+by+cz=d

def distanceToPlane(point, plane):
    return point.dot(plane[0]) - plane[1]

def cutPolygonByPlane(polygon, plane):
    newPolygon = []

    # polygon[1:] + [polygon[0]] rotates the whole array
    edges = list(zip(polygon, polygon[1:] + [polygon[0]]))
    for edge in edges:
        distances = [distanceToPlane(edge[0], plane),
                     distanceToPlane(edge[1], plane)]

        if distances[0] < 0 and distances[1] < 0:
            newPolygon.append(edge[0])
        elif distances[0] >= 0 and distances[1] >= 0:
            continue
        else:
            ratio = distances[0] / (distances[0] - distances[1])
            intersection = edge[0] * (1 - ratio) + edge[1] * ratio
            if distances[0] < 0:
                newPolygon.append(edge[0])
            newPolygon.append(intersection)
    return newPolygon

def brushToFaces(planes):
    polygons = []
    for plane in planes:
        # 'up' is just a vector which is not perpendicular to the plane
        up = mathutils.Vector((0, 0, 1))
        if abs(plane[0].dot(up)) > 0.9:
            up = mathutils.Vector((1, 0, 0))
        # two axes that are parallel to the plane (and each other); we don't care which
        right = plane[0].cross(up).normalized()
        forward = plane[0].cross(right).normalized()

        # 16 million
        # this is the largest a map can be without "issues" (i.e. planes that are randomly cut off in one axis)
        size = 2 ** 24
        
        polygon = [
            right * -size + forward * -size + plane[0] * plane[1],
            right * -size + forward * +size + plane[0] * plane[1],
            right * +size + forward * +size + plane[0] * plane[1],
            right * +size + forward * -size + plane[0] * plane[1],
        ]

        if len(polygon) == 0:
            continue
        
        for otherPlane in planes:
            if otherPlane != plane:
                if len(polygon) != 4:
                    continue
                polygon = cutPolygonByPlane(polygon, otherPlane)
                
        polygons.append(polygon)
        
    return polygons

def triangleToPlaneDistance(triangle):
    normal = ((triangle[2] - triangle[0]).cross(triangle[1] - triangle[0])).normalized()
    distance = triangle[0].dot(normal)
    return [normal, distance]

class Parser:

    def __init__(self, operator, context, filename, options):
        self.operator = operator
        self.context = context
        self.filename = filename

        self.options = options

        self.contents = ''
        self.pointer = 0
        self.line = 1

    def parse(self):
        print("Parsing VMF file '{}'".format(self.filename))
        
        with open(self.filename, 'r') as f:
            self.contents = f.read()
            self.pointer = 0
            
        while True:
            if not self.parse_next_root_block():
                return

    def get_char(self):
        if self.pointer == len(self.contents):
            return ''

        character = self.contents[self.pointer]
        
        if character == '\n':
            self.line += 1
            
        self.pointer += 1
        return character

    def peek(self):
        if self.pointer == len(self.contents):
            return ''
        
        return self.contents[self.pointer]

    def unget_char(self, c):
        if self.pointer == 0:
            raise Exception("cannot unget past the start of the file")

        self.pointer -= 1
        
        if c == '\n':
            self.line -= 1
            
        return self.contents[self.pointer]

    def skip_whitespace(self):

        skipped = 0

        while True:
            c = self.get_char()

            if c == "":
                return skipped

            skipped += 1
            
            if not c.isspace():
                self.unget_char(c)
                return skipped

    def get_literal(self):
        literal = ""

        c = ""

        while True:
            c = self.get_char()
            
            if c.isspace() or c == "{" or c == "":
                self.unget_char(c)
                break
            
            literal += c

        return literal

    def get_string(self):
        string = ""

        if self.get_char() != "\"":
            raise Exception("Expected to find opening double-quote character when parsing string")

        c = ""
        escaping = False
        while True:
            c = self.get_char()
            
            if c == "":
                raise Exception("Encountered EOF while reading string '{}'".format(string))

            if escaping:
                string += c
                continue

            if c == "\\":
                escaping = true
                continue
            
            if c == "\"":
                break
            
            string += c

        return string

    def get_property(self):
        key = self.get_string()
        
        self.skip_whitespace()

        if self.peek() != "\"":
            raise Exception("Expected value to follow key '{}'".format(key))
            
        value = self.get_string()

        return (key, value)
        
    def get_block(self):
        self.skip_whitespace()
        
        name = self.get_literal()

        if name == "":
            return None

        properties = {}
        children = []

        self.skip_whitespace()

        if self.get_char() != "{":
            raise Exception("expected '{' after reading block name")
            
        while True:
            self.skip_whitespace()

            # We've gotten to the end of the block! yay!
            if self.peek() == "}":
                self.get_char()
                break
            
            elif self.peek() == "\"":
                key, value = self.get_property()
                properties[key] = value
            else:
                block = self.get_block()
                children.append(block)

        return (name, properties, children)

    # Parses the contents of a single `solid` block.
    def parse_solid_block(self, block):
        # The sides of this brush
        sides = []

        _, properties, children = block

        for child in children:
            child_name = child[0]

            if child_name == "side":
                plane = child[1]["plane"]

                # TODO: fix this to parse `(...) (...) ...` better
                plane = plane[1:-1].split(") (")

                plane = [[float(value) for value in point.split()] for point in plane]

                plane = triangleToPlaneDistance([mathutils.Vector(plane[0]), mathutils.Vector(plane[1]), mathutils.Vector(plane[2])])

                sides.append(plane)

        #print("Block sides:")
        #print(sides)
        
        faces = brushToFaces(sides)

        return faces
        
    # Parses the contents of a single `world` block.
    def parse_world_block(self, block):
        name, properties, children = block

        brushes = []

        for child in children:
            child_name = child[0]

            if child_name == "solid":
                brushes.append(self.parse_solid_block(child))
            else:
                print("Ignoring unknown world block '{}'".format(child_name))

        mesh = bpy.data.meshes.new("mesh")  # add a new mesh
        obj = bpy.data.objects.new("MyObject", mesh)  # add a new object using the mesh

        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        
        #bpy.context.collection.objects.link(obj)
        #bpy.context.active_object = obj  # set as the active object in the scene
        #obj.select = True  # select object

        bm = bmesh.new()
        bm.from_mesh(mesh)

        for brush in brushes:
            brush_vertices = []
            
            for face in brush:
                vertices = [bm.verts.new(i / self.options["scale"]) for i in face]
                brush_vertices.extend(vertices)
            
                if len(vertices) <= 2:
                    print("Warning: face has less than 3 vertices")
                    continue
            
                print(vertices)
                bm.faces.new(vertices)
                
            bmesh.ops.remove_doubles(bm, verts=brush_vertices, dist=0.001)

        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        #bm.normal_update()
        #bpy.ops.object.mode_set(mode='OBJECT')
        
        bm.to_mesh(mesh)
        bm.free()
    
    def parse_next_root_block(self):
        block = self.get_block()
        
        if block == None:
            return False

        name, properties, children = block

        print("Parsing '{}' block".format(name))

        if name == "versioninfo":
            # We just totally ignore this shit.
            return True
        elif name == "visgroups":
            pass
        elif name == "world":
            self.parse_world_block(block)
        elif name == "entity":
            pass
        elif name == "hidden":
            pass
        elif name == "cameras":
            pass
        elif name == "cordon":
            pass
        elif name == "editor":
            pass
        else:
            print("Ignoring unknown top-level block '{}'".format(name))

        return True

def load(operator, context, filename="", options={}):

    p = Parser(operator, context, filename, options)
    
    try:
        p.parse()
        return {'FINISHED'}
    except Exception as e:
        traceback.print_exc()
        
        message = "Malformed VMF file: {} on line {} of '{}'".format(str(e), p.line, p.filename)
        operator.report({"ERROR"}, message)

        return {'CANCELLED'}
