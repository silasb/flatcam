############################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
# http://caram.cl/software/flatcam                         #
# Author: Juan Pablo Caram (c)                             #
# Date: 2/5/2014                                           #
# MIT Licence                                              #
############################################################

from numpy import arctan2, Inf, array, sqrt, pi, ceil, sin, cos
from matplotlib.figure import Figure
import re

# See: http://toblerity.org/shapely/manual.html
from shapely.geometry import Polygon, LineString, Point, LinearRing
from shapely.geometry import MultiPoint, MultiPolygon
from shapely.geometry import box as shply_box
from shapely.ops import cascaded_union
import shapely.affinity as affinity
from shapely.wkt import loads as sloads
from shapely.wkt import dumps as sdumps
from shapely.geometry.base import BaseGeometry

# Used for solid polygons in Matplotlib
from descartes.patch import PolygonPatch

import simplejson as json
# TODO: Commented for FlatCAM packaging with cx_freeze
#from matplotlib.pyplot import plot

import logging

log = logging.getLogger('base2')
#log.setLevel(logging.DEBUG)
log.setLevel(logging.WARNING)
formatter = logging.Formatter('[%(levelname)s] %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
log.addHandler(handler)


class Geometry(object):
    def __init__(self):
        # Units (in or mm)
        self.units = 'in'
        
        # Final geometry: MultiPolygon
        self.solid_geometry = None

        # Attributes to be included in serialization
        self.ser_attrs = ['units', 'solid_geometry']
        
    def isolation_geometry(self, offset):
        """
        Creates contours around geometry at a given
        offset distance.

        :param offset: Offset distance.
        :type offset: float
        :return: The buffered geometry.
        :rtype: Shapely.MultiPolygon or Shapely.Polygon
        """
        return self.solid_geometry.buffer(offset)
        
    def bounds(self):
        """
        Returns coordinates of rectangular bounds
        of geometry: (xmin, ymin, xmax, ymax).
        """
        if self.solid_geometry is None:
            log.warning("solid_geometry not computed yet.")
            return (0, 0, 0, 0)
            
        if type(self.solid_geometry) == list:
            # TODO: This can be done faster. See comment from Shapely mailing lists.
            return cascaded_union(self.solid_geometry).bounds
        else:
            return self.solid_geometry.bounds
        
    def size(self):
        """
        Returns (width, height) of rectangular
        bounds of geometry.
        """
        if self.solid_geometry is None:
            log.warning("Solid_geometry not computed yet.")
            return 0
        bounds = self.bounds()
        return (bounds[2]-bounds[0], bounds[3]-bounds[1])
        
    def get_empty_area(self, boundary=None):
        """
        Returns the complement of self.solid_geometry within
        the given boundary polygon. If not specified, it defaults to
        the rectangular bounding box of self.solid_geometry.
        """
        if boundary is None:
            boundary = self.solid_geometry.envelope
        return boundary.difference(self.solid_geometry)
        
    def clear_polygon(self, polygon, tooldia, overlap=0.15):
        """
        Creates geometry inside a polygon for a tool to cover
        the whole area.
        """
        poly_cuts = [polygon.buffer(-tooldia/2.0)]
        while True:
            polygon = poly_cuts[-1].buffer(-tooldia*(1-overlap))
            if polygon.area > 0:
                poly_cuts.append(polygon)
            else:
                break
        return poly_cuts

    def scale(self, factor):
        """
        Scales all of the object's geometry by a given factor. Override
        this method.
        :param factor: Number by which to scale.
        :type factor: float
        :return: None
        :rtype: None
        """
        return

    def offset(self, vect):
        """
        Offset the geometry by the given vector. Override this method.

        :param vect: (x, y) vector by which to offset the object.
        :type vect: tuple
        :return: None
        """
        return

    def convert_units(self, units):
        """
        Converts the units of the object to ``units`` by scaling all
        the geometry appropriately. This call ``scale()``. Don't call
        it again in descendents.

        :param units: "IN" or "MM"
        :type units: str
        :return: Scaling factor resulting from unit change.
        :rtype: float
        """
        log.debug("Geometry.convert_units()")

        if units.upper() == self.units.upper():
            return 1.0

        if units.upper() == "MM":
            factor = 25.4
        elif units.upper() == "IN":
            factor = 1/25.4
        else:
            log.error("Unsupported units: %s" % str(units))
            return 1.0

        self.units = units
        self.scale(factor)
        return factor

    def to_dict(self):
        """
        Returns a respresentation of the object as a dictionary.
        Attributes to include are listed in ``self.ser_attrs``.

        :return: A dictionary-encoded copy of the object.
        :rtype: dict
        """
        d = {}
        for attr in self.ser_attrs:
            d[attr] = getattr(self, attr)
        return d

    def from_dict(self, d):
        """
        Sets object's attributes from a dictionary.
        Attributes to include are listed in ``self.ser_attrs``.
        This method will look only for only and all the
        attributes in ``self.ser_attrs``. They must all
        be present. Use only for deserializing saved
        objects.

        :param d: Dictionary of attributes to set in the object.
        :type d: dict
        :return: None
        """
        for attr in self.ser_attrs:
            setattr(self, attr, d[attr])


class ApertureMacro:

    ## Regular expressions
    am1_re = re.compile(r'^%AM([^\*]+)\*(.+)?(%)?$')
    am2_re = re.compile(r'(.*)%$')
    amcomm_re = re.compile(r'^0(.*)')
    amprim_re = re.compile(r'^[1-9].*')
    amvar_re = re.compile(r'^\$([0-9a-zA-z]+)=(.*)')

    def __init__(self, name=None):
        self.name = name
        self.raw = ""

        ## These below are recomputed for every aperture
        ## definition, in other words, are temporary variables.
        self.primitives = []
        self.locvars = {}
        self.geometry = None

    def to_dict(self):
        """
        Returns the object in a serializable form. Only the name and
        raw are required.

        :return: Dictionary representing the object. JSON ready.
        :rtype: dict
        """

        return {
            'name': self.name,
            'raw': self.raw
        }

    def from_dict(self, d):
        """
        Populates the object from a serial representation created
        with ``self.to_dict()``.

        :param d: Serial representation of an ApertureMacro object.
        :return: None
        """
        for attr in ['name', 'raw']:
            setattr(self, attr, d[attr])

    def parse_content(self):
        """
        Creates numerical lists for all primitives in the aperture
        macro (in ``self.raw``) by replacing all variables by their
        values iteratively and evaluating expressions. Results
        are stored in ``self.primitives``.

        :return: None
        """
        # Cleanup
        self.raw = self.raw.replace('\n', '').replace('\r', '').strip(" *")
        self.primitives = []

        # Separate parts
        parts = self.raw.split('*')

        #### Every part in the macro ####
        for part in parts:
            ### Comments. Ignored.
            match = ApertureMacro.amcomm_re.search(part)
            if match:
                continue

            ### Variables
            # These are variables defined locally inside the macro. They can be
            # numerical constant or defind in terms of previously define
            # variables, which can be defined locally or in an aperture
            # definition. All replacements ocurr here.
            match = ApertureMacro.amvar_re.search(part)
            if match:
                var = match.group(1)
                val = match.group(2)

                # Replace variables in value
                for v in self.locvars:
                    val = re.sub(r'\$'+str(v)+r'(?![0-9a-zA-Z])', str(self.locvars[v]), val)

                # Make all others 0
                val = re.sub(r'\$[0-9a-zA-Z](?![0-9a-zA-Z])', "0", val)

                # Change x with *
                val = re.sub(r'[xX]', "*", val)

                # Eval() and store.
                self.locvars[var] = eval(val)
                continue

            ### Primitives
            # Each is an array. The first identifies the primitive, while the
            # rest depend on the primitive. All are strings representing a
            # number and may contain variable definition. The values of these
            # variables are defined in an aperture definition.
            match = ApertureMacro.amprim_re.search(part)
            if match:
                ## Replace all variables
                for v in self.locvars:
                    part = re.sub(r'\$'+str(v)+r'(?![0-9a-zA-Z])', str(self.locvars[v]), part)

                # Make all others 0
                part = re.sub(r'\$[0-9a-zA-Z](?![0-9a-zA-Z])', "0", part)

                # Change x with *
                part = re.sub(r'[xX]', "*", part)

                ## Store
                elements = part.split(",")
                self.primitives.append([eval(x) for x in elements])
                continue

            log.warning("Unknown syntax of aperture macro part: %s" % str(part))

    def append(self, data):
        """
        Appends a string to the raw macro.

        :param data: Part of the macro.
        :type data: str
        :return: None
        """
        self.raw += data

    @staticmethod
    def default2zero(n, mods):
        """
        Pads the ``mods`` list with zeros resulting in an
        list of length n.

        :param n: Length of the resulting list.
        :type n: int
        :param mods: List to be padded.
        :type mods: list
        :return: Zero-padded list.
        :rtype: list
        """
        x = [0.0]*n
        na = len(mods)
        x[0:na] = mods
        return x

    @staticmethod
    def make_circle(mods):
        """

        :param mods: (Exposure 0/1, Diameter >=0, X-coord, Y-coord)
        :return:
        """

        pol, dia, x, y = ApertureMacro.default2zero(4, mods)

        return {"pol": int(pol), "geometry": Point(x, y).buffer(dia/2)}

    @staticmethod
    def make_vectorline(mods):
        """

        :param mods: (Exposure 0/1, Line width >= 0, X-start, Y-start, X-end, Y-end,
            rotation angle around origin in degrees)
        :return:
        """
        pol, width, xs, ys, xe, ye, angle = ApertureMacro.default2zero(7, mods)

        line = LineString([(xs, ys), (xe, ye)])
        box = line.buffer(width/2, cap_style=2)
        box_rotated = affinity.rotate(box, angle, origin=(0, 0))

        return {"pol": int(pol), "geometry": box_rotated}

    @staticmethod
    def make_centerline(mods):
        """

        :param mods: (Exposure 0/1, width >=0, height >=0, x-center, y-center,
            rotation angle around origin in degrees)
        :return:
        """

        pol, width, height, x, y, angle = ApertureMacro.default2zero(6, mods)

        box = shply_box(x-width/2, y-height/2, x+width/2, y+height/2)
        box_rotated = affinity.rotate(box, angle, origin=(0, 0))

        return {"pol": int(pol), "geometry": box_rotated}

    @staticmethod
    def make_lowerleftline(mods):
        """

        :param mods: (exposure 0/1, width >=0, height >=0, x-lowerleft, y-lowerleft,
            rotation angle around origin in degrees)
        :return:
        """

        pol, width, height, x, y, angle = ApertureMacro.default2zero(6, mods)

        box = shply_box(x, y, x+width, y+height)
        box_rotated = affinity.rotate(box, angle, origin=(0, 0))

        return {"pol": int(pol), "geometry": box_rotated}

    @staticmethod
    def make_outline(mods):
        """

        :param mods:
        :return:
        """

        pol = mods[0]
        n = mods[1]
        points = [(0, 0)]*(n+1)

        for i in range(n+1):
            points[i] = mods[2*i + 2:2*i + 4]

        angle = mods[2*n + 4]

        poly = Polygon(points)
        poly_rotated = affinity.rotate(poly, angle, origin=(0, 0))

        return {"pol": int(pol), "geometry": poly_rotated}

    @staticmethod
    def make_polygon(mods):
        """
        Note: Specs indicate that rotation is only allowed if the center
        (x, y) == (0, 0). I will tolerate breaking this rule.

        :param mods: (exposure 0/1, n_verts 3<=n<=12, x-center, y-center,
            diameter of circumscribed circle >=0, rotation angle around origin)
        :return:
        """

        pol, nverts, x, y, dia, angle = ApertureMacro.default2zero(6, mods)
        points = [(0, 0)]*nverts

        for i in range(nverts):
            points[i] = (x + 0.5 * dia * cos(2*pi * i/nverts),
                         y + 0.5 * dia * sin(2*pi * i/nverts))

        poly = Polygon(points)
        poly_rotated = affinity.rotate(poly, angle, origin=(0, 0))

        return {"pol": int(pol), "geometry": poly_rotated}

    @staticmethod
    def make_moire(mods):
        """
        Note: Specs indicate that rotation is only allowed if the center
        (x, y) == (0, 0). I will tolerate breaking this rule.

        :param mods: (x-center, y-center, outer_dia_outer_ring, ring thickness,
            gap, max_rings, crosshair_thickness, crosshair_len, rotation
            angle around origin in degrees)
        :return:
        """

        x, y, dia, thickness, gap, nrings, cross_th, cross_len, angle = ApertureMacro.default2zero(9, mods)

        r = dia/2 - thickness/2
        result = Point((x, y)).buffer(r).exterior.buffer(thickness/2.0)
        ring = Point((x, y)).buffer(r).exterior.buffer(thickness/2.0)  # Need a copy!

        i = 1  # Number of rings created so far

        ## If the ring does not have an interior it means that it is
        ## a disk. Then stop.
        while len(ring.interiors) > 0 and i < nrings:
            r -= thickness + gap
            if r <= 0:
                break
            ring = Point((x, y)).buffer(r).exterior.buffer(thickness/2.0)
            result = cascaded_union([result, ring])
            i += 1

        ## Crosshair
        hor = LineString([(x - cross_len, y), (x + cross_len, y)]).buffer(cross_th/2.0, cap_style=2)
        ver = LineString([(x, y-cross_len), (x, y + cross_len)]).buffer(cross_th/2.0, cap_style=2)
        result = cascaded_union([result, hor, ver])

        return {"pol": 1, "geometry": result}

    @staticmethod
    def make_thermal(mods):
        """
        Note: Specs indicate that rotation is only allowed if the center
        (x, y) == (0, 0). I will tolerate breaking this rule.

        :param mods: [x-center, y-center, diameter-outside, diameter-inside,
            gap-thickness, rotation angle around origin]
        :return:
        """

        x, y, dout, din, t, angle = ApertureMacro.default2zero(6, mods)

        ring = Point((x, y)).buffer(dout/2.0).difference(Point((x, y)).buffer(din/2.0))
        hline = LineString([(x - dout/2.0, y), (x + dout/2.0, y)]).buffer(t/2.0, cap_style=3)
        vline = LineString([(x, y - dout/2.0), (x, y + dout/2.0)]).buffer(t/2.0, cap_style=3)
        thermal = ring.difference(hline.union(vline))

        return {"pol": 1, "geometry": thermal}

    def make_geometry(self, modifiers):
        """
        Runs the macro for the given modifiers and generates
        the corresponding geometry.

        :param modifiers: Modifiers (parameters) for this macro
        :type modifiers: list
        """

        ## Primitive makers
        makers = {
            "1": ApertureMacro.make_circle,
            "2": ApertureMacro.make_vectorline,
            "20": ApertureMacro.make_vectorline,
            "21": ApertureMacro.make_centerline,
            "22": ApertureMacro.make_lowerleftline,
            "4": ApertureMacro.make_outline,
            "5": ApertureMacro.make_polygon,
            "6": ApertureMacro.make_moire,
            "7": ApertureMacro.make_thermal
        }

        ## Store modifiers as local variables
        modifiers = modifiers or []
        modifiers = [float(m) for m in modifiers]
        self.locvars = {}
        for i in range(0, len(modifiers)):
            self.locvars[str(i+1)] = modifiers[i]

        ## Parse
        self.primitives = []  # Cleanup
        self.geometry = None
        self.parse_content()

        ## Make the geometry
        for primitive in self.primitives:
            # Make the primitive
            prim_geo = makers[str(int(primitive[0]))](primitive[1:])

            # Add it (according to polarity)
            if self.geometry is None and prim_geo['pol'] == 1:
                self.geometry = prim_geo['geometry']
                continue
            if prim_geo['pol'] == 1:
                self.geometry = self.geometry.union(prim_geo['geometry'])
                continue
            if prim_geo['pol'] == 0:
                self.geometry = self.geometry.difference(prim_geo['geometry'])
                continue

        return self.geometry


class Gerber (Geometry):
    """
    **ATTRIBUTES**

    * ``apertures`` (dict): The keys are names/identifiers of each aperture.
      The values are dictionaries key/value pairs which describe the aperture. The
      type key is always present and the rest depend on the key:

    +-----------+-----------------------------------+
    | Key       | Value                             |
    +===========+===================================+
    | type      | (str) "C", "R", "O", "P", or "AP" |
    +-----------+-----------------------------------+
    | others    | Depend on ``type``                |
    +-----------+-----------------------------------+

    * ``aperture_macros`` (dictionary): Are predefined geometrical structures
      that can be instanciated with different parameters in an aperture
      definition. See ``apertures`` above. The key is the name of the macro,
      and the macro itself, the value, is a ``Aperture_Macro`` object.

    * ``flash_geometry`` (list): List of (Shapely) geometric object resulting
      from ``flashes``. These are generated from ``flashes`` in ``do_flashes()``.

    * ``buffered_paths`` (list): List of (Shapely) polygons resulting from
      *buffering* (or thickening) the ``paths`` with the aperture. These are
      generated from ``paths`` in ``buffer_paths()``.

    **USAGE**::

        g = Gerber()
        g.parse_file(filename)
        g.create_geometry()
        do_something(s.solid_geometry)

    """

    def __init__(self):
        """
        The constructor takes no parameters. Use ``gerber.parse_files()``
        or ``gerber.parse_lines()`` to populate the object from Gerber source.

        :return: Gerber object
        :rtype: Gerber
        """

        # Initialize parent
        Geometry.__init__(self)        

        self.solid_geometry = Polygon()

        # Number format
        self.int_digits = 3
        """Number of integer digits in Gerber numbers. Used during parsing."""

        self.frac_digits = 4
        """Number of fraction digits in Gerber numbers. Used during parsing."""
        
        ## Gerber elements ##
        # Apertures {'id':{'type':chr, 
        #             ['size':float], ['width':float],
        #             ['height':float]}, ...}
        self.apertures = {}

        # Aperture Macros
        self.aperture_macros = {}

        # Attributes to be included in serialization
        # Always append to it because it carries contents
        # from Geometry.
        self.ser_attrs += ['int_digits', 'frac_digits', 'apertures',
                           'aperture_macros', 'solid_geometry']

        #### Parser patterns ####
        # FS - Format Specification
        # The format of X and Y must be the same!
        # L-omit leading zeros, T-omit trailing zeros
        # A-absolute notation, I-incremental notation
        self.fmt_re = re.compile(r'%FS([LT])([AI])X(\d)(\d)Y\d\d\*%$')

        # Mode (IN/MM)
        self.mode_re = re.compile(r'^%MO(IN|MM)\*%$')

        # Comment G04|G4
        self.comm_re = re.compile(r'^G0?4(.*)$')

        # AD - Aperture definition
        self.ad_re = re.compile(r'^%ADD(\d\d+)([a-zA-Z0-9]*)(?:,(.*))?\*%$')

        # AM - Aperture Macro
        # Beginning of macro (Ends with *%):
        self.am_re = re.compile(r'^%AM([a-zA-Z0-9]*)\*')

        # Tool change
        # May begin with G54 but that is deprecated
        self.tool_re = re.compile(r'^(?:G54)?D(\d\d+)\*$')

        # G01... - Linear interpolation plus flashes with coordinates
        # Operation code (D0x) missing is deprecated... oh well I will support it.
        self.lin_re = re.compile(r'^(?:G0?(1))?(?=.*X(-?\d+))?(?=.*Y(-?\d+))?[XY][^DIJ]*(?:D0?([123]))?\*$')

        # Operation code alone, usually just D03 (Flash)
        self.opcode_re = re.compile(r'^D0?([123])\*$')

        # G02/3... - Circular interpolation with coordinates
        # 2-clockwise, 3-counterclockwise
        # Operation code (D0x) missing is deprecated... oh well I will support it.
        # Optional start with G02 or G03, optional end with D01 or D02 with
        # optional coordinates but at least one in any order.
        self.circ_re = re.compile(r'^(?:G0?([23]))?(?=.*X(-?\d+))?(?=.*Y(-?\d+))' +
                                  '?(?=.*I(-?\d+))?(?=.*J(-?\d+))?[XYIJ][^D]*(?:D0([12]))?\*$')

        # G01/2/3 Occurring without coordinates
        self.interp_re = re.compile(r'^(?:G0?([123]))\*')

        # Single D74 or multi D75 quadrant for circular interpolation
        self.quad_re = re.compile(r'^G7([45])\*$')

        # Region mode on
        # In region mode, D01 starts a region
        # and D02 ends it. A new region can be started again
        # with D01. All contours must be closed before
        # D02 or G37.
        self.regionon_re = re.compile(r'^G36\*$')

        # Region mode off
        # Will end a region and come off region mode.
        # All contours must be closed before D02 or G37.
        self.regionoff_re = re.compile(r'^G37\*$')

        # End of file
        self.eof_re = re.compile(r'^M02\*')

        # IP - Image polarity
        self.pol_re = re.compile(r'^%IP(POS|NEG)\*%$')

        # LP - Level polarity
        self.lpol_re = re.compile(r'^%LP([DC])\*%$')

        # Units (OBSOLETE)
        self.units_re = re.compile(r'^G7([01])\*$')

        # Absolute/Relative G90/1 (OBSOLETE)
        self.absrel_re = re.compile(r'^G9([01])\*$')

        # Aperture macros
        self.am1_re = re.compile(r'^%AM([^\*]+)\*(.+)?(%)?$')
        self.am2_re = re.compile(r'(.*)%$')

        # TODO: This is bad.
        self.steps_per_circ = 40

    def scale(self, factor):
        """
        Scales the objects' geometry on the XY plane by a given factor.
        These are:

        * ``buffered_paths``
        * ``flash_geometry``
        * ``solid_geometry``
        * ``regions``

        NOTE:
        Does not modify the data used to create these elements. If these
        are recreated, the scaling will be lost. This behavior was modified
        because of the complexity reached in this class.

        :param factor: Number by which to scale.
        :type factor: float
        :rtype : None
        """

        ## solid_geometry ???
        #  It's a cascaded union of objects.
        self.solid_geometry = affinity.scale(self.solid_geometry, factor,
                                             factor, origin=(0, 0))

        # # Now buffered_paths, flash_geometry and solid_geometry
        # self.create_geometry()

    def offset(self, vect):
        """
        Offsets the objects' geometry on the XY plane by a given vector.
        These are:

        * ``buffered_paths``
        * ``flash_geometry``
        * ``solid_geometry``
        * ``regions``

        NOTE:
        Does not modify the data used to create these elements. If these
        are recreated, the scaling will be lost. This behavior was modified
        because of the complexity reached in this class.

        :param vect: (x, y) offset vector.
        :type vect: tuple
        :return: None
        """

        dx, dy = vect

        ## Solid geometry
        self.solid_geometry = affinity.translate(self.solid_geometry, xoff=dx, yoff=dy)

    def mirror(self, axis, point):
        """
        Mirrors the object around a specified axis passign through
        the given point. What is affected:

        * ``buffered_paths``
        * ``flash_geometry``
        * ``solid_geometry``
        * ``regions``

        NOTE:
        Does not modify the data used to create these elements. If these
        are recreated, the scaling will be lost. This behavior was modified
        because of the complexity reached in this class.

        :param axis: "X" or "Y" indicates around which axis to mirror.
        :type axis: str
        :param point: [x, y] point belonging to the mirror axis.
        :type point: list
        :return: None
        """

        px, py = point
        xscale, yscale = {"X": (1.0, -1.0), "Y": (-1.0, 1.0)}[axis]

        ## solid_geometry ???
        #  It's a cascaded union of objects.
        self.solid_geometry = affinity.scale(self.solid_geometry,
                                             xscale, yscale, origin=(px, py))

    def aperture_parse(self, apertureId, apertureType, apParameters):
        """
        Parse gerber aperture definition into dictionary of apertures.
        The following kinds and their attributes are supported:

        * *Circular (C)*: size (float)
        * *Rectangle (R)*: width (float), height (float)
        * *Obround (O)*: width (float), height (float).
        * *Polygon (P)*: diameter(float), vertices(int), [rotation(float)]
        * *Aperture Macro (AM)*: macro (ApertureMacro), modifiers (list)

        :param apertureId: Id of the aperture being defined.
        :param apertureType: Type of the aperture.
        :param apParameters: Parameters of the aperture.
        :type apertureId: str
        :type apertureType: str
        :type apParameters: str
        :return: Identifier of the aperture.
        :rtype: str
        """

        # Found some Gerber with a leading zero in the aperture id and the
        # referenced it without the zero, so this is a hack to handle that.
        apid = str(int(apertureId))

        try:  # Could be empty for aperture macros
            paramList = apParameters.split('X')
        except:
            paramList = None

        if apertureType == "C":  # Circle, example: %ADD11C,0.1*%
            self.apertures[apid] = {"type": "C",
                                    "size": float(paramList[0])}
            return apid
        
        if apertureType == "R":  # Rectangle, example: %ADD15R,0.05X0.12*%
            self.apertures[apid] = {"type": "R",
                                    "width": float(paramList[0]),
                                    "height": float(paramList[1])}
            return apid

        if apertureType == "O":  # Obround
            self.apertures[apid] = {"type": "O",
                                    "width": float(paramList[0]),
                                    "height": float(paramList[1])}
            return apid
        
        if apertureType == "P":  # Polygon (regular)
            self.apertures[apid] = {"type": "P",
                                    "diam": float(paramList[0]),
                                    "nVertices": int(paramList[1])}
            if len(paramList) >= 3:
                self.apertures[apid]["rotation"] = float(paramList[2])
            return apid

        if apertureType in self.aperture_macros:
            self.apertures[apid] = {"type": "AM",
                                    "macro": self.aperture_macros[apertureType],
                                    "modifiers": paramList}
            return apid

        log.warning("Aperture not implemented: %s" % str(apertureType))
        return None
        
    def parse_file(self, filename):
        """
        Calls Gerber.parse_lines() with array of lines
        read from the given file.

        :param filename: Gerber file to parse.
        :type filename: str
        :return: None
        """
        gfile = open(filename, 'r')
        gstr = gfile.readlines()
        gfile.close()
        self.parse_lines(gstr)

    def parse_lines(self, glines):
        """
        Main Gerber parser. Reads Gerber and populates ``self.paths``, ``self.apertures``,
        ``self.flashes``, ``self.regions`` and ``self.units``.

        :param glines: Gerber code as list of strings, each element being
            one line of the source file.
        :type glines: list
        :return: None
        :rtype: None
        """

        # Coordinates of the current path, each is [x, y]
        path = []

        # Polygons are stored here until there is a change in polarity.
        # Only then they are combined via cascaded_union and added or
        # subtracted from solid_geometry. This is ~100 times faster than
        # applyng a union for every new polygon.
        poly_buffer = []

        last_path_aperture = None
        current_aperture = None

        # 1,2 or 3 from "G01", "G02" or "G03"
        current_interpolation_mode = None

        # 1 or 2 from "D01" or "D02"
        # Note this is to support deprecated Gerber not putting
        # an operation code at the end of every coordinate line.
        current_operation_code = None

        # Current coordinates
        current_x = None
        current_y = None

        # Absolute or Relative/Incremental coordinates
        # Not implemented
        absolute = True

        # How to interpret circular interpolation: SINGLE or MULTI
        quadrant_mode = None

        # Indicates we are parsing an aperture macro
        current_macro = None

        # Indicates the current polarity: D-Dark, C-Clear
        current_polarity = 'D'

        # If a region is being defined
        making_region = False

        #### Parsing starts here ####
        line_num = 0
        for gline in glines:
            line_num += 1

            ### Cleanup
            gline = gline.strip(' \r\n')

            ### Aperture Macros
            # Having this at the beggining will slow things down
            # but macros can have complicated statements than could
            # be caught by other ptterns.
            if current_macro is None:  # No macro started yet
                match = self.am1_re.search(gline)
                # Start macro if match, else not an AM, carry on.
                if match:
                    current_macro = match.group(1)
                    self.aperture_macros[current_macro] = ApertureMacro(name=current_macro)
                    if match.group(2):  # Append
                        self.aperture_macros[current_macro].append(match.group(2))
                    if match.group(3):  # Finish macro
                        #self.aperture_macros[current_macro].parse_content()
                        current_macro = None
                    continue
            else:  # Continue macro
                match = self.am2_re.search(gline)
                if match:  # Finish macro
                    self.aperture_macros[current_macro].append(match.group(1))
                    #self.aperture_macros[current_macro].parse_content()
                    current_macro = None
                else:  # Append
                    self.aperture_macros[current_macro].append(gline)
                continue

            ### G01 - Linear interpolation plus flashes
            # Operation code (D0x) missing is deprecated... oh well I will support it.
            # REGEX: r'^(?:G0?(1))?(?:X(-?\d+))?(?:Y(-?\d+))?(?:D0([123]))?\*$'
            match = self.lin_re.search(gline)
            if match:
                # Dxx alone?
                # if match.group(1) is None and match.group(2) is None and match.group(3) is None:
                #     try:
                #         current_operation_code = int(match.group(4))
                #     except:
                #         pass  # A line with just * will match too.
                #     continue
                # NOTE: Letting it continue allows it to react to the
                #       operation code.

                # Parse coordinates
                if match.group(2) is not None:
                    current_x = parse_gerber_number(match.group(2), self.frac_digits)
                if match.group(3) is not None:
                    current_y = parse_gerber_number(match.group(3), self.frac_digits)

                # Parse operation code
                if match.group(4) is not None:
                    current_operation_code = int(match.group(4))

                # Pen down: add segment
                if current_operation_code == 1:
                    path.append([current_x, current_y])
                    last_path_aperture = current_aperture

                elif current_operation_code == 2:
                    if len(path) > 1:

                        ## --- BUFFERED ---
                        if making_region:
                            geo = Polygon(path)
                        else:
                            if last_path_aperture is None:
                                log.warning("No aperture defined for curent path. (%d)" % line_num)
                            width = self.apertures[last_path_aperture]["size"]
                            geo = LineString(path).buffer(width/2)
                        poly_buffer.append(geo)

                    path = [[current_x, current_y]]  # Start new path

                # Flash
                elif current_operation_code == 3:

                    # --- BUFFERED ---
                    flash = Gerber.create_flash_geometry(Point([current_x, current_y]),
                                                         self.apertures[current_aperture])
                    poly_buffer.append(flash)

                continue

            ### G02/3 - Circular interpolation
            # 2-clockwise, 3-counterclockwise
            match = self.circ_re.search(gline)
            if match:

                mode, x, y, i, j, d = match.groups()
                try:
                    x = parse_gerber_number(x, self.frac_digits)
                except:
                    x = current_x
                try:
                    y = parse_gerber_number(y, self.frac_digits)
                except:
                    y = current_y
                try:
                    i = parse_gerber_number(i, self.frac_digits)
                except:
                    i = 0
                try:
                    j = parse_gerber_number(j, self.frac_digits)
                except:
                    j = 0

                if quadrant_mode is None:
                    log.error("Found arc without preceding quadrant specification G74 or G75. (%d)" % line_num)
                    log.error(gline)
                    continue

                if mode is None and current_interpolation_mode not in [2, 3]:
                    log.error("Found arc without circular interpolation mode defined. (%d)" % line_num)
                    log.error(gline)
                    continue
                elif mode is not None:
                    current_interpolation_mode = int(mode)

                # Set operation code if provided
                if d is not None:
                    current_operation_code = int(d)

                # Nothing created! Pen Up.
                if current_operation_code == 2:
                    log.warning("Arc with D2. (%d)" % line_num)
                    if len(path) > 1:
                        if last_path_aperture is None:
                            log.warning("No aperture defined for curent path. (%d)" % line_num)

                        # --- BUFFERED ---
                        width = self.apertures[last_path_aperture]["size"]
                        buffered = LineString(path).buffer(width/2)
                        poly_buffer.append(buffered)

                    current_x = x
                    current_y = y
                    path = [[current_x, current_y]]  # Start new path
                    continue

                # Flash should not happen here
                if current_operation_code == 3:
                    log.error("Trying to flash within arc. (%d)" % line_num)
                    continue

                if quadrant_mode == 'MULTI':
                    center = [i + current_x, j + current_y]
                    radius = sqrt(i**2 + j**2)
                    start = arctan2(-j, -i)
                    stop = arctan2(-center[1] + y, -center[0] + x)
                    arcdir = [None, None, "cw", "ccw"]
                    this_arc = arc(center, radius, start, stop,
                                   arcdir[current_interpolation_mode],
                                   self.steps_per_circ)

                    # Last point in path is current point
                    current_x = this_arc[-1][0]
                    current_y = this_arc[-1][1]

                    # Append
                    path += this_arc

                    last_path_aperture = current_aperture

                    continue

                if quadrant_mode == 'SINGLE':
                    log.warning("Single quadrant arc are not implemented yet. (%d)" % line_num)

            ### Operation code alone
            match = self.opcode_re.search(gline)
            if match:
                current_operation_code = int(match.group(1))
                if current_operation_code == 3:

                    ## --- Buffered ---
                    flash = Gerber.create_flash_geometry(Point(path[-1]),
                                                         self.apertures[current_aperture])
                    poly_buffer.append(flash)

                continue

            ### G74/75* - Single or multiple quadrant arcs
            match = self.quad_re.search(gline)
            if match:
                if match.group(1) == '4':
                    quadrant_mode = 'SINGLE'
                else:
                    quadrant_mode = 'MULTI'
                continue

            ### G36* - Begin region
            if self.regionon_re.search(gline):
                if len(path) > 1:
                    # Take care of what is left in the path

                    ## --- Buffered ---
                    width = self.apertures[last_path_aperture]["size"]
                    geo = LineString(path).buffer(width/2)
                    poly_buffer.append(geo)

                    path = [path[-1]]

                making_region = True
                continue

            ### G37* - End region
            if self.regionoff_re.search(gline):
                making_region = False

                # Only one path defines region?
                # This can happen if D02 happened before G37 and
                # is not and error.
                if len(path) < 3:
                    # print "ERROR: Path contains less than 3 points:"
                    # print path
                    # print "Line (%d): " % line_num, gline
                    # path = []
                    #path = [[current_x, current_y]]
                    continue

                # For regions we may ignore an aperture that is None
                # self.regions.append({"polygon": Polygon(path),
                #                      "aperture": last_path_aperture})

                # --- Buffered ---
                region = Polygon(path)
                if not region.is_valid:
                    region = region.buffer(0)
                poly_buffer.append(region)

                path = [[current_x, current_y]]  # Start new path
                continue
            
            ### Aperture definitions %ADD...
            match = self.ad_re.search(gline)
            if match:
                self.aperture_parse(match.group(1), match.group(2), match.group(3))
                continue

            ### G01/2/3* - Interpolation mode change
            # Can occur along with coordinates and operation code but
            # sometimes by itself (handled here).
            # Example: G01*
            match = self.interp_re.search(gline)
            if match:
                current_interpolation_mode = int(match.group(1))
                continue

            ### Tool/aperture change
            # Example: D12*
            match = self.tool_re.search(gline)
            if match:
                current_aperture = match.group(1)
                continue

            ### Polarity change
            # Example: %LPD*% or %LPC*%
            match = self.lpol_re.search(gline)
            if match:
                if len(path) > 1 and current_polarity != match.group(1):

                    # --- Buffered ----
                    width = self.apertures[last_path_aperture]["size"]
                    geo = LineString(path).buffer(width/2)
                    poly_buffer.append(geo)

                    path = [path[-1]]

                # --- Apply buffer ---
                if current_polarity == 'D':
                    self.solid_geometry = self.solid_geometry.union(cascaded_union(poly_buffer))
                else:
                    self.solid_geometry = self.solid_geometry.difference(cascaded_union(poly_buffer))
                poly_buffer = []

                current_polarity = match.group(1)
                continue

            ### Number format
            # Example: %FSLAX24Y24*%
            # TODO: This is ignoring most of the format. Implement the rest.
            match = self.fmt_re.search(gline)
            if match:
                absolute = {'A': True, 'I': False}
                self.int_digits = int(match.group(3))
                self.frac_digits = int(match.group(4))
                continue

            ### Mode (IN/MM)
            # Example: %MOIN*%
            match = self.mode_re.search(gline)
            if match:
                self.units = match.group(1)
                continue

            ### Units (G70/1) OBSOLETE
            match = self.units_re.search(gline)
            if match:
                self.units = {'0': 'IN', '1': 'MM'}[match.group(1)]
                continue

            ### Absolute/relative coordinates G90/1 OBSOLETE
            match = self.absrel_re.search(gline)
            if match:
                absolute = {'0': True, '1': False}[match.group(1)]
                continue

            #### Ignored lines
            ## Comments
            match = self.comm_re.search(gline)
            if match:
                continue

            ## EOF
            match = self.eof_re.search(gline)
            if match:
                continue

            ### Line did not match any pattern. Warn user.
            log.warning("Line ignored (%d): %s" % (line_num, gline))
        
        if len(path) > 1:
            # EOF, create shapely LineString if something still in path

            ## --- Buffered ---
            width = self.apertures[last_path_aperture]["size"]
            geo = LineString(path).buffer(width/2)
            poly_buffer.append(geo)

        # --- Apply buffer ---
        if current_polarity == 'D':
            self.solid_geometry = self.solid_geometry.union(cascaded_union(poly_buffer))
        else:
            self.solid_geometry = self.solid_geometry.difference(cascaded_union(poly_buffer))

    @staticmethod
    def create_flash_geometry(location, aperture):

        if type(location) == list:
            location = Point(location)

        if aperture['type'] == 'C':  # Circles
            return location.buffer(aperture['size']/2)

        if aperture['type'] == 'R':  # Rectangles
            loc = location.coords[0]
            width = aperture['width']
            height = aperture['height']
            minx = loc[0] - width/2
            maxx = loc[0] + width/2
            miny = loc[1] - height/2
            maxy = loc[1] + height/2
            return shply_box(minx, miny, maxx, maxy)

        if aperture['type'] == 'O':  # Obround
            loc = location.coords[0]
            width = aperture['width']
            height = aperture['height']
            if width > height:
                p1 = Point(loc[0] + 0.5*(width-height), loc[1])
                p2 = Point(loc[0] - 0.5*(width-height), loc[1])
                c1 = p1.buffer(height*0.5)
                c2 = p2.buffer(height*0.5)
            else:
                p1 = Point(loc[0], loc[1] + 0.5*(height-width))
                p2 = Point(loc[0], loc[1] - 0.5*(height-width))
                c1 = p1.buffer(width*0.5)
                c2 = p2.buffer(width*0.5)
            return cascaded_union([c1, c2]).convex_hull

        if aperture['type'] == 'P':  # Regular polygon
            loc = location.coords[0]
            diam = aperture['diam']
            n_vertices = aperture['nVertices']
            points = []
            for i in range(0, n_vertices):
                x = loc[0] + diam * (cos(2 * pi * i / n_vertices))
                y = loc[1] + diam * (sin(2 * pi * i / n_vertices))
                points.append((x, y))
            ply = Polygon(points)
            if 'rotation' in aperture:
                ply = affinity.rotate(ply, aperture['rotation'])
            return ply

        if aperture['type'] == 'AM':  # Aperture Macro
            loc = location.coords[0]
            flash_geo = aperture['macro'].make_geometry(aperture['modifiers'])
            return affinity.translate(flash_geo, xoff=loc[0], yoff=loc[1])

        return None
    
    def create_geometry(self):
        """
        Geometry from a Gerber file is made up entirely of polygons.
        Every stroke (linear or circular) has an aperture which gives
        it thickness. Additionally, aperture strokes have non-zero area,
        and regions naturally do as well.

        :rtype : None
        :return: None
        """

        # self.buffer_paths()
        #
        # self.fix_regions()
        #
        # self.do_flashes()
        #
        # self.solid_geometry = cascaded_union(self.buffered_paths +
        #                                      [poly['polygon'] for poly in self.regions] +
        #                                      self.flash_geometry)

    def get_bounding_box(self, margin=0.0, rounded=False):
        """
        Creates and returns a rectangular polygon bounding at a distance of
        margin from the object's ``solid_geometry``. If margin > 0, the polygon
        can optionally have rounded corners of radius equal to margin.

        :param margin: Distance to enlarge the rectangular bounding
         box in both positive and negative, x and y axes.
        :type margin: float
        :param rounded: Wether or not to have rounded corners.
        :type rounded: bool
        :return: The bounding box.
        :rtype: Shapely.Polygon
        """

        bbox = self.solid_geometry.envelope.buffer(margin)
        if not rounded:
            bbox = bbox.envelope
        return bbox


class Excellon(Geometry):
    """
    *ATTRIBUTES*

    * ``tools`` (dict): The key is the tool name and the value is
      a dictionary specifying the tool:

    ================  ====================================
    Key               Value
    ================  ====================================
    C                 Diameter of the tool
    Others            Not supported (Ignored).
    ================  ====================================

    * ``drills`` (list): Each is a dictionary:

    ================  ====================================
    Key               Value
    ================  ====================================
    point             (Shapely.Point) Where to drill
    tool              (str) A key in ``tools``
    ================  ====================================
    """

    def __init__(self):
        """
        The constructor takes no parameters.

        :return: Excellon object.
        :rtype: Excellon
        """

        Geometry.__init__(self)
        
        self.tools = {}
        
        self.drills = []

        # Trailing "T" or leading "L" (default)
        self.zeros = "L"

        # Attributes to be included in serialization
        # Always append to it because it carries contents
        # from Geometry.
        self.ser_attrs += ['tools', 'drills', 'zeros']

        #### Patterns ####
        # Regex basics:
        # ^ - beginning
        # $ - end
        # *: 0 or more, +: 1 or more, ?: 0 or 1

        # M48 - Beggining of Part Program Header
        self.hbegin_re = re.compile(r'^M48$')

        # M95 or % - End of Part Program Header
        # NOTE: % has different meaning in the body
        self.hend_re = re.compile(r'^(?:M95|%)$')

        # FMAT Excellon format
        self.fmat_re = re.compile(r'^FMAT,([12])$')

        # Number format and units
        # INCH uses 6 digits
        # METRIC uses 5/6
        self.units_re = re.compile(r'^(INCH|METRIC)(?:,([TL])Z)?$')

        # Tool definition/parameters (?= is look-ahead
        # NOTE: This might be an overkill!
        # self.toolset_re = re.compile(r'^T(0?\d|\d\d)(?=.*C(\d*\.?\d*))?' +
        #                              r'(?=.*F(\d*\.?\d*))?(?=.*S(\d*\.?\d*))?' +
        #                              r'(?=.*B(\d*\.?\d*))?(?=.*H(\d*\.?\d*))?' +
        #                              r'(?=.*Z([-\+]?\d*\.?\d*))?[CFSBHT]')
        self.toolset_re = re.compile(r'^T(\d+)(?=.*C(\d*\.?\d*))?' +
                                     r'(?=.*F(\d*\.?\d*))?(?=.*S(\d*\.?\d*))?' +
                                     r'(?=.*B(\d*\.?\d*))?(?=.*H(\d*\.?\d*))?' +
                                     r'(?=.*Z([-\+]?\d*\.?\d*))?[CFSBHT]')

        # Tool select
        # Can have additional data after tool number but
        # is ignored if present in the header.
        # Warning: This will match toolset_re too.
        # self.toolsel_re = re.compile(r'^T((?:\d\d)|(?:\d))')
        self.toolsel_re = re.compile(r'^T(\d+)')

        # Comment
        self.comm_re = re.compile(r'^;(.*)$')

        # Absolute/Incremental G90/G91
        self.absinc_re = re.compile(r'^G9([01])$')

        # Modes of operation
        # 1-linear, 2-circCW, 3-cirCCW, 4-vardwell, 5-Drill
        self.modes_re = re.compile(r'^G0([012345])')

        # Measuring mode
        # 1-metric, 2-inch
        self.meas_re = re.compile(r'^M7([12])$')

        # Coordinates
        #self.xcoord_re = re.compile(r'^X(\d*\.?\d*)(?:Y\d*\.?\d*)?$')
        #self.ycoord_re = re.compile(r'^(?:X\d*\.?\d*)?Y(\d*\.?\d*)$')
        self.coordsperiod_re = re.compile(r'(?=.*X([-\+]?\d*\.\d*))?(?=.*Y([-\+]?\d*\.\d*))?[XY]')
        self.coordsnoperiod_re = re.compile(r'(?!.*\.)(?=.*X([-\+]?\d*))?(?=.*Y([-\+]?\d*))?[XY]')

        # R - Repeat hole (# times, X offset, Y offset)
        self.rep_re = re.compile(r'^R(\d+)(?=.*[XY])+(?:X([-\+]?\d*\.?\d*))?(?:Y([-\+]?\d*\.?\d*))?$')

        # Various stop/pause commands
        self.stop_re = re.compile(r'^((G04)|(M09)|(M06)|(M00)|(M30))')

        # Parse coordinates
        self.leadingzeros_re = re.compile(r'^(0*)(\d*)')
        
    def parse_file(self, filename):
        """
        Reads the specified file as array of lines as
        passes it to ``parse_lines()``.

        :param filename: The file to be read and parsed.
        :type filename: str
        :return: None
        """
        efile = open(filename, 'r')
        estr = efile.readlines()
        efile.close()
        self.parse_lines(estr)

    def parse_lines(self, elines):
        """
        Main Excellon parser.

        :param elines: List of strings, each being a line of Excellon code.
        :type elines: list
        :return: None
        """

        # State variables
        current_tool = ""
        in_header = False
        current_x = None
        current_y = None

        line_num = 0  # Line number
        for eline in elines:
            line_num += 1

            ### Cleanup lines
            eline = eline.strip(' \r\n')

            ## Header Begin/End ##
            if self.hbegin_re.search(eline):
                in_header = True
                continue

            if self.hend_re.search(eline):
                in_header = False
                continue

            #### Body ####
            if not in_header:

                ## Tool change ##
                match = self.toolsel_re.search(eline)
                if match:
                    current_tool = str(int(match.group(1)))
                    continue

                ## Coordinates without period ##
                match = self.coordsnoperiod_re.search(eline)
                if match:
                    try:
                        #x = float(match.group(1))/10000
                        x = self.parse_number(match.group(1))
                        current_x = x
                    except TypeError:
                        x = current_x

                    try:
                        #y = float(match.group(2))/10000
                        y = self.parse_number(match.group(2))
                        current_y = y
                    except TypeError:
                        y = current_y

                    if x is None or y is None:
                        log.error("Missing coordinates")
                        continue

                    self.drills.append({'point': Point((x, y)), 'tool': current_tool})
                    continue

                ## Coordinates with period: Use literally. ##
                match = self.coordsperiod_re.search(eline)
                if match:
                    try:
                        x = float(match.group(1))
                        current_x = x
                    except TypeError:
                        x = current_x

                    try:
                        y = float(match.group(2))
                        current_y = y
                    except TypeError:
                        y = current_y

                    if x is None or y is None:
                        log.error("Missing coordinates")
                        continue

                    self.drills.append({'point': Point((x, y)), 'tool': current_tool})
                    continue

            #### Header ####
            if in_header:

                ## Tool definitions ##
                match = self.toolset_re.search(eline)
                if match:
                    name = str(int(match.group(1)))
                    spec = {
                        "C": float(match.group(2)),
                        # "F": float(match.group(3)),
                        # "S": float(match.group(4)),
                        # "B": float(match.group(5)),
                        # "H": float(match.group(6)),
                        # "Z": float(match.group(7))
                    }
                    self.tools[name] = spec
                    continue

                ## Units and number format ##
                match = self.units_re.match(eline)
                if match:
                    self.zeros = match.group(2)  # "T" or "L"
                    self.units = {"INCH": "IN", "METRIC": "MM"}[match.group(1)]
                    continue

            log.warning("Line ignored: %s" % eline)
        
    def parse_number(self, number_str):
        """
        Parses coordinate numbers without period.

        :param number_str: String representing the numerical value.
        :type number_str: str
        :return: Floating point representation of the number
        :rtype: foat
        """
        if self.zeros == "L":
            match = self.leadingzeros_re.search(number_str)
            return float(number_str)/(10**(len(match.group(2))-2+len(match.group(1))))
        else:  # Trailing
            return float(number_str)/10000

    def create_geometry(self):
        """
        Creates circles of the tool diameter at every point
        specified in ``self.drills``.

        :return: None
        """
        self.solid_geometry = []

        for drill in self.drills:
            #poly = drill['point'].buffer(self.tools[drill['tool']]["C"]/2.0)
            tooldia = self.tools[drill['tool']]['C']
            poly = drill['point'].buffer(tooldia/2.0)
            self.solid_geometry.append(poly)

    def scale(self, factor):
        """
        Scales geometry on the XY plane in the object by a given factor.
        Tool sizes, feedrates an Z-plane dimensions are untouched.

        :param factor: Number by which to scale the object.
        :type factor: float
        :return: None
        :rtype: NOne
        """

        # Drills
        for drill in self.drills:
            drill['point'] = affinity.scale(drill['point'], factor, factor, origin=(0, 0))

        self.create_geometry()

    def offset(self, vect):
        """
        Offsets geometry on the XY plane in the object by a given vector.

        :param vect: (x, y) offset vector.
        :type vect: tuple
        :return: None
        """

        dx, dy = vect

        # Drills
        for drill in self.drills:
            drill['point'] = affinity.translate(drill['point'], xoff=dx, yoff=dy)

        # Recreate geometry
        self.create_geometry()

    def mirror(self, axis, point):
        """

        :param axis: "X" or "Y" indicates around which axis to mirror.
        :type axis: str
        :param point: [x, y] point belonging to the mirror axis.
        :type point: list
        :return: None
        """

        px, py = point
        xscale, yscale = {"X": (1.0, -1.0), "Y": (-1.0, 1.0)}[axis]

        # Modify data
        for drill in self.drills:
            drill['point'] = affinity.scale(drill['point'], xscale, yscale, origin=(px, py))

        # Recreate geometry
        self.create_geometry()

    def convert_units(self, units):
        factor = Geometry.convert_units(self, units)

        # Tools
        for tname in self.tools:
            self.tools[tname]["C"] *= factor

        self.create_geometry()

        return factor


class CNCjob(Geometry):
    """
    Represents work to be done by a CNC machine.

    *ATTRIBUTES*

    * ``gcode_parsed`` (list): Each is a dictionary:

    =====================  =========================================
    Key                    Value
    =====================  =========================================
    geom                   (Shapely.LineString) Tool path (XY plane)
    kind                   (string) "AB", A is "T" (travel) or
                           "C" (cut). B is "F" (fast) or "S" (slow).
    =====================  =========================================
    """
    def __init__(self, units="in", kind="generic", z_move=0.1,
                 feedrate=3.0, z_cut=-0.002, tooldia=0.0):

        Geometry.__init__(self)
        self.kind = kind
        self.units = units
        self.z_cut = z_cut
        self.z_move = z_move
        self.feedrate = feedrate
        self.tooldia = tooldia
        self.unitcode = {"IN": "G20", "MM": "G21"}
        self.pausecode = "G04 P1"
        self.feedminutecode = "G94"
        self.absolutecode = "G90"
        self.gcode = ""
        self.input_geometry_bounds = None
        self.gcode_parsed = None
        self.steps_per_circ = 20  # Used when parsing G-code arcs

        # Attributes to be included in serialization
        # Always append to it because it carries contents
        # from Geometry.
        self.ser_attrs += ['kind', 'z_cut', 'z_move', 'feedrate', 'tooldia',
                           'gcode', 'input_geometry_bounds', 'gcode_parsed',
                           'steps_per_circ']

    def convert_units(self, units):
        factor = Geometry.convert_units(self, units)
        log.debug("CNCjob.convert_units()")

        self.z_cut *= factor
        self.z_move *= factor
        self.feedrate *= factor
        self.tooldia *= factor

        return factor

    def generate_from_excellon(self, exobj):
        """
        Generates G-code for drilling from Excellon object.
        self.gcode becomes a list, each element is a
        different job for each tool in the excellon code.
        """
        self.kind = "drill"
        self.gcode = []
        
        t = "G00 X%.4fY%.4f\n"
        down = "G01 Z%.4f\n" % self.z_cut
        up = "G01 Z%.4f\n" % self.z_move

        for tool in exobj.tools:
            
            points = []
            
            for drill in exobj.drill:
                if drill['tool'] == tool:
                    points.append(drill['point'])
            
            gcode = self.unitcode[self.units.upper()] + "\n"
            gcode += self.absolutecode + "\n"
            gcode += self.feedminutecode + "\n"
            gcode += "F%.2f\n" % self.feedrate
            gcode += "G00 Z%.4f\n" % self.z_move  # Move to travel height
            gcode += "M03\n"  # Spindle start
            gcode += self.pausecode + "\n"
            
            for point in points:
                gcode += t % point
                gcode += down + up
            
            gcode += t % (0, 0)
            gcode += "M05\n"  # Spindle stop
            
            self.gcode.append(gcode)

    def generate_from_excellon_by_tool(self, exobj, tools="all"):
        """
        Creates gcode for this object from an Excellon object
        for the specified tools.

        :param exobj: Excellon object to process
        :type exobj: Excellon
        :param tools: Comma separated tool names
        :type: tools: str
        :return: None
        :rtype: None
        """
        log.debug("Creating CNC Job from Excellon...")
        if tools == "all":
            tools = [tool for tool in exobj.tools]
        else:
            tools = [x.strip() for x in tools.split(",")]
            tools = filter(lambda i: i in exobj.tools, tools)
        log.debug("Tools are: %s" % str(tools))

        points = []
        for drill in exobj.drills:
            if drill['tool'] in tools:
                points.append(drill['point'])

        log.debug("Found %d drills." % len(points))
        #self.kind = "drill"
        self.gcode = []

        t = "G00 X%.4fY%.4f\n"
        down = "G01 Z%.4f\n" % self.z_cut
        up = "G01 Z%.4f\n" % self.z_move

        gcode = self.unitcode[self.units.upper()] + "\n"
        gcode += self.absolutecode + "\n"
        gcode += self.feedminutecode + "\n"
        gcode += "F%.2f\n" % self.feedrate
        gcode += "G00 Z%.4f\n" % self.z_move  # Move to travel height
        gcode += "M03\n"  # Spindle start
        gcode += self.pausecode + "\n"

        for point in points:
            x, y = point.coords.xy
            gcode += t % (x[0], y[0])
            gcode += down + up

        gcode += t % (0, 0)
        gcode += "M05\n"  # Spindle stop

        self.gcode = gcode

    def generate_from_geometry(self, geometry, append=True, tooldia=None, tolerance=0):
        """
        Generates G-Code from a Geometry object. Stores in ``self.gcode``.

        :param geometry: Geometry defining the toolpath
        :type geometry: Geometry
        :param append: Wether to append to self.gcode or re-write it.
        :type append: bool
        :param tooldia: If given, sets the tooldia property but does
            not affect the process in any other way.
        :type tooldia: bool
        :param tolerance: All points in the simplified object will be within the
            tolerance distance of the original geometry.
        :return: None
        :rtype: None
        """
        if tooldia is not None:
            self.tooldia = tooldia
            
        self.input_geometry_bounds = geometry.bounds()
        
        if not append:
            self.gcode = ""

        self.gcode = self.unitcode[self.units.upper()] + "\n"
        self.gcode += self.absolutecode + "\n"
        self.gcode += self.feedminutecode + "\n"
        self.gcode += "F%.2f\n" % self.feedrate
        self.gcode += "G00 Z%.4f\n" % self.z_move  # Move to travel height
        self.gcode += "M03\n"  # Spindle start
        self.gcode += self.pausecode + "\n"
        
        for geo in geometry.solid_geometry:
            
            if type(geo) == Polygon:
                self.gcode += self.polygon2gcode(geo, tolerance=tolerance)
                continue
            
            if type(geo) == LineString or type(geo) == LinearRing:
                self.gcode += self.linear2gcode(geo, tolerance=tolerance)
                continue
            
            if type(geo) == Point:
                self.gcode += self.point2gcode(geo)
                continue

            if type(geo) == MultiPolygon:
                for poly in geo:
                    self.gcode += self.polygon2gcode(poly, tolerance=tolerance)
                continue

            log.warning("G-code generation not implemented for %s" % (str(type(geo))))

        self.gcode += "G00 Z%.4f\n" % self.z_move  # Stop cutting
        self.gcode += "G00 X0Y0\n"
        self.gcode += "M05\n"  # Spindle stop

    def pre_parse(self, gtext):
        """
        Separates parts of the G-Code text into a list of dictionaries.
        Used by ``self.gcode_parse()``.

        :param gtext: A single string with g-code
        """

        # Units: G20-inches, G21-mm
        units_re = re.compile(r'^G2([01])')

        # TODO: This has to be re-done
        gcmds = []
        lines = gtext.split("\n")  # TODO: This is probably a lot of work!
        for line in lines:
            # Clean up
            line = line.strip()

            # Remove comments
            # NOTE: Limited to 1 bracket pair
            op = line.find("(")
            cl = line.find(")")
            #if op > -1 and  cl > op:
            if cl > op > -1:
                #comment = line[op+1:cl]
                line = line[:op] + line[(cl+1):]

            # Units
            match = units_re.match(line)
            if match:
                self.units = {'0': "IN", '1': "MM"}[match.group(1)]

            # Parse GCode
            # 0   4       12
            # G01 X-0.007 Y-0.057
            # --> codes_idx = [0, 4, 12]
            codes = "NMGXYZIJFP"
            codes_idx = []
            i = 0
            for ch in line:
                if ch in codes:
                    codes_idx.append(i)
                i += 1
            n_codes = len(codes_idx)
            if n_codes == 0:
                continue

            # Separate codes in line
            parts = []
            for p in range(n_codes-1):
                parts.append(line[codes_idx[p]:codes_idx[p+1]].strip())
            parts.append(line[codes_idx[-1]:].strip())

            # Separate codes from values
            cmds = {}
            for part in parts:
                cmds[part[0]] = float(part[1:])
            gcmds.append(cmds)
        return gcmds

    def gcode_parse(self):
        """
        G-Code parser (from self.gcode). Generates dictionary with
        single-segment LineString's and "kind" indicating cut or travel,
        fast or feedrate speed.
        """

        kind = ["C", "F"]  # T=travel, C=cut, F=fast, S=slow

        # Results go here
        geometry = []        
        
        # TODO: Merge into single parser?
        gobjs = self.pre_parse(self.gcode)
        
        # Last known instruction
        current = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'G': 0}

        # Current path: temporary storage until tool is
        # lifted or lowered.
        path = [(0, 0)]

        # Process every instruction
        for gobj in gobjs:

            ## Changing height
            if 'Z' in gobj:
                if ('X' in gobj or 'Y' in gobj) and gobj['Z'] != current['Z']:
                    log.warning("Non-orthogonal motion: From %s" % str(current))
                    log.warning("  To: %s" % str(gobj))
                current['Z'] = gobj['Z']
                # Store the path into geometry and reset path
                if len(path) > 1:
                    geometry.append({"geom": LineString(path),
                                     "kind": kind})
                    path = [path[-1]]  # Start with the last point of last path.

            if 'G' in gobj:
                current['G'] = int(gobj['G'])
                
            if 'X' in gobj or 'Y' in gobj:
                
                if 'X' in gobj:
                    x = gobj['X']
                else:
                    x = current['X']
                
                if 'Y' in gobj:
                    y = gobj['Y']
                else:
                    y = current['Y']

                kind = ["C", "F"]  # T=travel, C=cut, F=fast, S=slow

                if current['Z'] > 0:
                    kind[0] = 'T'
                if current['G'] > 0:
                    kind[1] = 'S'
                   
                arcdir = [None, None, "cw", "ccw"]
                if current['G'] in [0, 1]:  # line
                    path.append((x, y))

                if current['G'] in [2, 3]:  # arc
                    center = [gobj['I'] + current['X'], gobj['J'] + current['Y']]
                    radius = sqrt(gobj['I']**2 + gobj['J']**2)
                    start = arctan2(-gobj['J'], -gobj['I'])
                    stop = arctan2(-center[1]+y, -center[0]+x)
                    path += arc(center, radius, start, stop,
                                arcdir[current['G']],
                                self.steps_per_circ)

            # Update current instruction
            for code in gobj:
                current[code] = gobj[code]

        # There might not be a change in height at the
        # end, therefore, see here too if there is
        # a final path.
        if len(path) > 1:
            geometry.append({"geom": LineString(path),
                             "kind": kind})

        self.gcode_parsed = geometry
        return geometry
        
    # def plot(self, tooldia=None, dpi=75, margin=0.1,
    #          color={"T": ["#F0E24D", "#B5AB3A"], "C": ["#5E6CFF", "#4650BD"]},
    #          alpha={"T": 0.3, "C": 1.0}):
    #     """
    #     Creates a Matplotlib figure with a plot of the
    #     G-code job.
    #     """
    #     if tooldia is None:
    #         tooldia = self.tooldia
    #
    #     fig = Figure(dpi=dpi)
    #     ax = fig.add_subplot(111)
    #     ax.set_aspect(1)
    #     xmin, ymin, xmax, ymax = self.input_geometry_bounds
    #     ax.set_xlim(xmin-margin, xmax+margin)
    #     ax.set_ylim(ymin-margin, ymax+margin)
    #
    #     if tooldia == 0:
    #         for geo in self.gcode_parsed:
    #             linespec = '--'
    #             linecolor = color[geo['kind'][0]][1]
    #             if geo['kind'][0] == 'C':
    #                 linespec = 'k-'
    #             x, y = geo['geom'].coords.xy
    #             ax.plot(x, y, linespec, color=linecolor)
    #     else:
    #         for geo in self.gcode_parsed:
    #             poly = geo['geom'].buffer(tooldia/2.0)
    #             patch = PolygonPatch(poly, facecolor=color[geo['kind'][0]][0],
    #                                  edgecolor=color[geo['kind'][0]][1],
    #                                  alpha=alpha[geo['kind'][0]], zorder=2)
    #             ax.add_patch(patch)
    #
    #     return fig
        
    def plot2(self, axes, tooldia=None, dpi=75, margin=0.1,
             color={"T": ["#F0E24D", "#B5AB3A"], "C": ["#5E6CFF", "#4650BD"]},
             alpha={"T": 0.3, "C": 1.0}, tool_tolerance=0.0005):
        """
        Plots the G-code job onto the given axes.

        :param axes: Matplotlib axes on which to plot.
        :param tooldia: Tool diameter.
        :param dpi: Not used!
        :param margin: Not used!
        :param color: Color specification.
        :param alpha: Transparency specification.
        :param tool_tolerance: Tolerance when drawing the toolshape.
        :return: None
        """
        if tooldia is None:
            tooldia = self.tooldia
        
        if tooldia == 0:
            for geo in self.gcode_parsed:
                linespec = '--'
                linecolor = color[geo['kind'][0]][1]
                if geo['kind'][0] == 'C':
                    linespec = 'k-'
                x, y = geo['geom'].coords.xy
                axes.plot(x, y, linespec, color=linecolor)
        else:
            for geo in self.gcode_parsed:
                poly = geo['geom'].buffer(tooldia/2.0).simplify(tool_tolerance)
                patch = PolygonPatch(poly, facecolor=color[geo['kind'][0]][0],
                                     edgecolor=color[geo['kind'][0]][1],
                                     alpha=alpha[geo['kind'][0]], zorder=2)
                axes.add_patch(patch)
        
    def create_geometry(self):
        # TODO: This takes forever. Too much data?
        self.solid_geometry = cascaded_union([geo['geom'] for geo in self.gcode_parsed])

    def polygon2gcode(self, polygon, tolerance=0):
        """
        Creates G-Code for the exterior and all interior paths
        of a polygon.

        :param polygon: A Shapely.Polygon
        :type polygon: Shapely.Polygon
        :param tolerance: All points in the simplified object will be within the
            tolerance distance of the original geometry.
        :type tolerance: float
        :return: G-code to cut along polygon.
        :rtype: str
        """

        if tolerance > 0:
            target_polygon = polygon.simplify(tolerance)
        else:
            target_polygon = polygon

        gcode = ""
        t = "G0%d X%.4fY%.4f\n"
        path = list(target_polygon.exterior.coords)             # Polygon exterior
        gcode += t % (0, path[0][0], path[0][1])  # Move to first point
        gcode += "G01 Z%.4f\n" % self.z_cut       # Start cutting
        for pt in path[1:]:
            gcode += t % (1, pt[0], pt[1])    # Linear motion to point
        gcode += "G00 Z%.4f\n" % self.z_move  # Stop cutting
        for ints in target_polygon.interiors:               # Polygon interiors
            path = list(ints.coords)
            gcode += t % (0, path[0][0], path[0][1])  # Move to first point
            gcode += "G01 Z%.4f\n" % self.z_cut       # Start cutting
            for pt in path[1:]:
                gcode += t % (1, pt[0], pt[1])    # Linear motion to point
            gcode += "G00 Z%.4f\n" % self.z_move  # Stop cutting
        return gcode

    def linear2gcode(self, linear, tolerance=0):
        """
        Generates G-code to cut along the linear feature.

        :param linear: The path to cut along.
        :type: Shapely.LinearRing or Shapely.Linear String
        :param tolerance: All points in the simplified object will be within the
            tolerance distance of the original geometry.
        :type tolerance: float
        :return: G-code to cut alon the linear feature.
        :rtype: str
        """

        if tolerance > 0:
            target_linear = linear.simplify(tolerance)
        else:
            target_linear = linear

        gcode = ""
        t = "G0%d X%.4fY%.4f\n"
        path = list(target_linear.coords)
        gcode += t % (0, path[0][0], path[0][1])  # Move to first point
        gcode += "G01 Z%.4f\n" % self.z_cut       # Start cutting
        for pt in path[1:]:
            gcode += t % (1, pt[0], pt[1])    # Linear motion to point
        gcode += "G00 Z%.4f\n" % self.z_move  # Stop cutting
        return gcode

    def point2gcode(self, point):
        # TODO: This is not doing anything.
        gcode = ""
        t = "G0%d X%.4fY%.4f\n"
        path = list(point.coords)
        gcode += t % (0, path[0][0], path[0][1])  # Move to first point
        gcode += "G01 Z%.4f\n" % self.z_cut       # Start cutting
        gcode += "G00 Z%.4f\n" % self.z_move      # Stop cutting

    def scale(self, factor):
        """
        Scales all the geometry on the XY plane in the object by the
        given factor. Tool sizes, feedrates, or Z-axis dimensions are
        not altered.

        :param factor: Number by which to scale the object.
        :type factor: float
        :return: None
        :rtype: None
        """

        for g in self.gcode_parsed:
            g['geom'] = affinity.scale(g['geom'], factor, factor, origin=(0, 0))

        self.create_geometry()

    def offset(self, vect):
        """
        Offsets all the geometry on the XY plane in the object by the
        given vector.

        :param vect: (x, y) offset vector.
        :type vect: tuple
        :return: None
        """
        dx, dy = vect

        for g in self.gcode_parsed:
            g['geom'] = affinity.translate(g['geom'], xoff=dx, yoff=dy)

        self.create_geometry()


# def get_bounds(geometry_set):
#     xmin = Inf
#     ymin = Inf
#     xmax = -Inf
#     ymax = -Inf
#
#     #print "Getting bounds of:", str(geometry_set)
#     for gs in geometry_set:
#         try:
#             gxmin, gymin, gxmax, gymax = geometry_set[gs].bounds()
#             xmin = min([xmin, gxmin])
#             ymin = min([ymin, gymin])
#             xmax = max([xmax, gxmax])
#             ymax = max([ymax, gymax])
#         except:
#             print "DEV WARNING: Tried to get bounds of empty geometry."
#
#     return [xmin, ymin, xmax, ymax]

def get_bounds(geometry_list):
    xmin = Inf
    ymin = Inf
    xmax = -Inf
    ymax = -Inf

    #print "Getting bounds of:", str(geometry_set)
    for gs in geometry_list:
        try:
            gxmin, gymin, gxmax, gymax = gs.bounds()
            xmin = min([xmin, gxmin])
            ymin = min([ymin, gymin])
            xmax = max([xmax, gxmax])
            ymax = max([ymax, gymax])
        except:
            log.warning("DEVELOPMENT: Tried to get bounds of empty geometry.")

    return [xmin, ymin, xmax, ymax]

def arc(center, radius, start, stop, direction, steps_per_circ):
    """
    Creates a list of point along the specified arc.

    :param center: Coordinates of the center [x, y]
    :type center: list
    :param radius: Radius of the arc.
    :type radius: float
    :param start: Starting angle in radians
    :type start: float
    :param stop: End angle in radians
    :type stop: float
    :param direction: Orientation of the arc, "CW" or "CCW"
    :type direction: string
    :param steps_per_circ: Number of straight line segments to
        represent a circle.
    :type steps_per_circ: int
    :return: The desired arc, as list of tuples
    :rtype: list
    """
    # TODO: Resolution should be established by fraction of total length, not angle.

    da_sign = {"cw": -1.0, "ccw": 1.0}
    points = []
    if direction == "ccw" and stop <= start:
        stop += 2*pi
    if direction == "cw" and stop >= start:
        stop -= 2*pi
    
    angle = abs(stop - start)
        
    #angle = stop-start
    steps = max([int(ceil(angle/(2*pi)*steps_per_circ)), 2])
    delta_angle = da_sign[direction]*angle*1.0/steps
    for i in range(steps+1):
        theta = start + delta_angle*i
        points.append((center[0]+radius*cos(theta), center[1]+radius*sin(theta)))
    return points


def clear_poly(poly, tooldia, overlap=0.1):
    """
    Creates a list of Shapely geometry objects covering the inside
    of a Shapely.Polygon. Use for removing all the copper in a region
    or bed flattening.

    :param poly: Target polygon
    :type poly: Shapely.Polygon
    :param tooldia: Diameter of the tool
    :type tooldia: float
    :param overlap: Fraction of the tool diameter to overlap
        in each pass.
    :type overlap: float
    :return: list of Shapely.Polygon
    :rtype: list
    """
    poly_cuts = [poly.buffer(-tooldia/2.0)]
    while True:
        poly = poly_cuts[-1].buffer(-tooldia*(1-overlap))
        if poly.area > 0:
            poly_cuts.append(poly)
        else:
            break
    return poly_cuts


def find_polygon(poly_set, point):
    """
    Return the first polygon in the list of polygons poly_set
    that contains the given point.
    """
    p = Point(point)
    for poly in poly_set:
        if poly.contains(p):
            return poly
    return None


def to_dict(obj):
    """
    Makes a Shapely geometry object into serializeable form.

    :param obj: Shapely geometry.
    :type obj: BaseGeometry
    :return: Dictionary with serializable form if ``obj`` was
        BaseGeometry or ApertureMacro, otherwise returns ``obj``.
    """
    if isinstance(obj, ApertureMacro):
        return {
            "__class__": "ApertureMacro",
            "__inst__": obj.to_dict()
        }
    if isinstance(obj, BaseGeometry):
        return {
            "__class__": "Shply",
            "__inst__": sdumps(obj)
        }
    raise TypeError("Unserialize object {} of type {}".format(obj, type(obj)))


def dict2obj(d):
    """
    Default deserializer.

    :param d:  Serializable dictionary representation of an object
        to be reconstructed.
    :return: Reconstructed object.
    """
    if '__class__' in d and '__inst__' in d:
        if d['__class__'] == "Shply":
            return sloads(d['__inst__'])
        if d['__class__'] == "ApertureMacro":
            am = ApertureMacro()
            am.from_dict(d['__inst__'])
            return am
        return d
    else:
        return d


def plotg(geo):
    try:
        _ = iter(geo)
    except:
        geo = [geo]

    for g in geo:
        if type(g) == Polygon:
            x, y = g.exterior.coords.xy
            plot(x, y)
            for ints in g.interiors:
                x, y = ints.coords.xy
                plot(x, y)
            continue

        if type(g) == LineString or type(g) == LinearRing:
            x, y = g.coords.xy
            plot(x, y)
            continue

        if type(g) == Point:
            x, y = g.coords.xy
            plot(x, y, 'o')
            continue

        try:
            _ = iter(g)
            plotg(g)
        except:
            log.error("Cannot plot: " + str(type(g)))
            continue


def parse_gerber_number(strnumber, frac_digits):
    """
    Parse a single number of Gerber coordinates.

    :param strnumber: String containing a number in decimal digits
    from a coordinate data block, possibly with a leading sign.
    :type strnumber: str
    :param frac_digits: Number of digits used for the fractional
    part of the number
    :type frac_digits: int
    :return: The number in floating point.
    :rtype: float
    """
    return int(strnumber)*(10**(-frac_digits))

