from math import sqrt
import bpy
import numpy as np


class CurveContainer:

    def __init__(self, root, curve_template, smooth_sections, recursive=True, origin_type="center"):

        self.root_hash = root.hash
        self.name = root.name
        self.smooth_sections = smooth_sections
        self.default_color = [1,1,1]

        # copy the curve template and make a new blender object out of it
        self.curve = curve_template.copy()
        self.object = bpy.data.objects.new(self.name, self.curve)

        self.linked = False
        self.material_indices = []

        # Quickly find the spline of a given section
        self.hash2spline_index = {}

        # Recursively add section splines and corresponding materials to the container
        self.add_section(root, recursive, in_top_level=True, origin_type=origin_type)

    def set_parent_object(self, parent_container):
        if not self.linked or not parent_container.linked:
            raise Exception("Cannot create parent-child relationship between Blender objects that have not "
                            "been linked to the scene: " + self.name + "->" + parent_container.name )

        child = self.object
        parent = parent_container.object

        child.parent = parent
        child.matrix_parent_inverse = parent.matrix_world.inverted()

    def remove(self):
        self.unlink()

        # materials
        for mat in self.curve.materials:
            bpy.data.materials.remove(mat)

        # curve
        bpy.data.curves.remove(self.curve)

        # object
        bpy.data.objects.remove(self.object)

    @property
    def origin(self):
        return self.object.location

    @origin.setter
    def origin(self, value):
        self.object.location = value

    def diam0version(self, start, end):
        lengths = end - start

        # Versor extension
        length = sqrt(np.power(lengths,2).sum())
        versor = lengths / length
        extended = end + versor * 0.01 # Extend in the same direction by a small amount

        return extended

    def add_spline(self, coords, radii, smooth):
        curve = self.curve

        sec_spline = curve.splines.new('BEZIER')

        # This line is necessary due to a bug in Blender
        # see: https://developer.blender.org/T54112
        curve.resolution_u = curve.resolution_u

        # Subtract the container origin (as bezier points are
        # relative to the object origin)
        coords = coords - self.origin

        # Add closed, 0-diam caps (to avoid open-ended cylinders)
        cap1 = self.diam0version(coords[1], coords[0])
        cap2 = self.diam0version(coords[-2], coords[-1])

        coords = np.concatenate(([cap1], coords, [cap2]))
        radii = np.concatenate(([0],radii,[0]))

        # Flatten the coords back (needed by the foreach_set() functions below)
        coords.shape = (-1)

        bezier_points = sec_spline.bezier_points

        # Allocate space for bezier points
        #bezier_points.clear() # can't clear the one initial point
        bezier_points.add(len(radii)-1)

        bezier_points.foreach_set('radius', radii)
        bezier_points.foreach_set('co', coords)

        if not smooth:
            # Fast
            bezier_points.foreach_set('handle_right', coords)
            bezier_points.foreach_set('handle_left', coords)

        else:
            # Slower
            for p in bezier_points:
                p.handle_right_type = p.handle_left_type = 'AUTO'

        return sec_spline


    def create_material(self, name):
        result = bpy.data.materials.new(name)

        result.diffuse_color = self.default_color

        # Ambient and back lighting
        result.ambient = 0.85
        result.translucency = 0.85

        # Raytraced reflections
        result.raytrace_mirror.use = True
        result.raytrace_mirror.reflect_factor = 0.1
        result.raytrace_mirror.fresnel = 2.0

        return result

    def add_material_to_object(self, material):
        mats = self.curve.materials
        mats.append(material)
        mat_idx = len(mats)-1
        return mat_idx

    def to_global(self, local_coords):
        """
        This function performs the fancy fast vectorized multiplication of the container object's
        world matrix (trans, rot, scale) by the local bezier curve points to obtain the global
        version of the coordinates.

        :param local_coords: Local coords as returned by bezier_points.foreach_get("co")
        :return: Global version of the local_coords
        """

        # Get the world matrix
        matrix = self.object.matrix_world

        # Reshape coords to Nx3 matrix
        local_coords.shape = (-1, 3)

        # Add an extra 1.0s column (for matrix dot prod)
        local_coords = np.c_[local_coords, np.ones(local_coords.shape[0])]

        # Dot product matrix with the coords transpose
        # Keep the first 3 rows (x,y,z)
        # Transpose result to Nx3
        # Flatten
        global_coords = np.dot(matrix, local_coords.T)[0:3].T.reshape((-1))

        return global_coords

    def update_group_section(self, root, recursive=True):
        # Find the spline that corresponds to the section
        spline_i = self.hash2spline_index[root.hash]

        try:
            spline = self.curve.splines[spline_i]

        except IndexError:
            print("Could not find spline with index " + str(spline_i) + " in " + self.name +
                  ". This can happen if a spline is deleted in Edit Mode.")
            raise

        # Get the 3d points
        bezier_points = spline.bezier_points
        num_coords = len(bezier_points)

        coords = np.zeros(num_coords * 3)
        bezier_points.foreach_get("co", coords)

        # Adjust coords for container origin and rotation
        coords = self.to_global(coords)

        # Discard the 0-radius end caps
        coords = coords[3:-3]

        root.coords = coords.tolist()

        # Get radii
        radii = np.zeros(num_coords)
        bezier_points.foreach_get("radius", radii)
        root.radii  = radii[1:-1].tolist()

        # Cleanup before recursion
        del spline, bezier_points, num_coords, coords, radii

        if recursive:
            for child in root.children:
                self.update_group_section(child, recursive=True)

    def add_section(self, root, recursive=True, in_top_level=True, origin_type="center"):
        # Reshape the coords to be n X 3 array (for xyz)
        coords = np.array(root.coords)
        coords.shape = (-1, 3)

        if in_top_level:
            self.set_origin(coords, origin_type)

        # Add section spline and material to the cell object
        spline = self.add_spline(coords, root.radii, self.smooth_sections)

        # Each section gets a material, whose emit property will be animated
        material = self.create_material(root.name)
        mat_idx = self.add_material_to_object(material)

        # Assign the material to the new spline
        spline.material_index = mat_idx

        # Save spline index for later lookup
        # Note: In Blender, using edit-mode on a curve object, results in creation of
        # new spline instances when returning to object-mode. If references to the
        # old splines are kept, Blender usually crashes. Here we retain the spline index,
        # which is preserved (if splines are not deleted in edit-mode).
        self.hash2spline_index[root.hash] = len(self.curve.splines) - 1

        # Cleanup before starting recursion
        del spline, material, mat_idx

        # Do same with the children
        if recursive:
            for child in root.children:
                self.add_section(child, recursive=True, in_top_level=False)

    def set_origin(self, coords, type = "center"):
        if type == "center":
            point_count = coords.shape[0]

            center_i = int(point_count / 2)

            # If even number of 3D points, use the mean of the
            # two points closest to the section middle
            if point_count % 2 == 0:
                center_i2 = center_i - 1
                center = (coords[center_i] + coords[center_i2]) / 2.0
            else:
                center = coords[center_i]

            self.object.location = center

        if type == "first":
            self.object.location = coords[0]

    def link(self):
        bpy.context.scene.objects.link(self.object)

        self.linked = True

    def unlink(self):
        bpy.context.scene.objects.unlink(self.object)

        self.linked = False