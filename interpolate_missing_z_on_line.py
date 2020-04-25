# -*- coding: utf-8 -*-

"""Algorithm for QGIS 3 to interpolate missing Z values on a line Z vector layer.

This algorithm takes a line Z vector layer as input (consisting of one
or several lines) and performs the following:
- If the first or last vertices of a line have missing values, fill them in
  (extrapolate) by setting their value equal to the first/last valid ones found.
- Interpolate the remaining missing Z values.

QGIS doesn't have a NULL for declaring missing Z values in vector layers.
A newly created Z vector layer will have Z values defaulting to 0.
The parameter 'NoData Z' provides a way to declare what numerical value should
be considered as the NoData one. It should be 0 in most cases.

An exemplary use case:
A line Z layer representing roads where the elevations would be
known only at a few locations. Interpolating the Z values between
these locations with the algorithm is a fast way to populate the Z
values of the layer. Doing it by hand could be really slow, particularly
if the roads have curves and so many vertices.

How edge cases are handled:
- If a line feature only has missing values, it is left as is.
- If a line feature has no missing value, it is left as is.

The algorithm provides a message for each line that it processes,
giving the user the ability to check that the quality of the
input line Z layer and how it was processed.

Notes:
    - This algorithm was developed based on the default
      template provided with QGIS 3.12. Instead of declaring
      it through a class with lots of boilerplate code, it'd 
      be possible to use the @alg decorator.
      See https://github.com/volaya/qgis-python-course/blob/master/processing/processing.rst
      or https://docs.qgis.org/testing/en/docs/user_manual/processing/scripts.html#the-alg-decorator

Author: Maxime Liquet
Date: 03/2020
License: MIT
"""

# Imports for the core algorithm
import itertools
import math

# Imports for QGIS
from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsGeometry,
                       QgsFeature,
                       QgsFeatureSink,
                       QgsMapLayer,
                       QgsProcessing,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterNumber,
                       QgsProcessingUtils,
                       QgsWkbTypes)
from qgis import processing

### HELPER FUNCTIONS

def interpolate_z(d_target, d_start, d_end, z_start, z_end):
    """Linearly interpolate z = f(d) between two points.
    
    Parameters
    ----------
    d_target : float
        z is computed at this d value.
    d_start : float
        x coordinate of the first point.
    d_end : float
        x coordinate of the last point.
    z_start : float
        y coordinate of the first point.
    z_end : float
        y coordinate of the last point.
    
    Returns
    -------
    float
        Interpolated value of z.
    
    Usage
    -----
    >>> interpolate_z(1, 0, 2, 0, 2)
    1.0
    """
    return z_start + (z_end - z_start) * (d_target - d_start) / (d_end - d_start)


def idx_first_last_valid_items(list_, invalid_item):
    """Determine the indexes of the first and last valid items in a sequence.
    
    Parameters
    ----------
    list_ : list
        A list whose one or both ends has invalid items.
    invalid_item : float
        Invalid item that needs to be replaced (eg. 0).
    
    Returns
    -------
    tuple
        Two elements:
            - int: first valid item
            - int: last valid item
    
    Usage
    -----
    >>> idx_first_last_valid_items([0, 0, 1, 0, 2, 0], 0)
    (2, 4)
    >>> idx_first_last_valid_items([1, 1, 1], 0)
    (0, 2)
    """
    if list_[0] != invalid_item:
        idx_first_valid_item = 0
    else:
        for idx, e in enumerate(list_):
            if e == invalid_item:
                continue
            idx_first_valid_item = idx
            break
    if list_[-1] != invalid_item:
        idx_last_valid_item = len(list_) - 1
    else:
        for idx, e in enumerate(reversed(list_)):
            if e == invalid_item:
                continue
            idx_last_valid_item = len(list_) - idx - 1
            break
    return idx_first_valid_item, idx_last_valid_item


def fill_list_ends(list_, invalid_item):
    """Fill the ends of a list with the first/last valid item found.
    
    Parameters
    ----------
    list_ : list
        A list whose one or both ends has invalid items.
    invalid_item : float
        Invalid item that needs to be replaced (eg. 0).
    
    Returns
    -------
    tuple
        Two elements:
            - list: Original list with filled ends
            - int: Number of filled items.
    
    Usage
    -----
    >>> fill_list_ends([0, 0, 1, 0, 2, 0], 0)
    ([1, 1, 1, 0, 2, 2], 3)
    >>> fill_list_ends([0, 0, 0], 0)
    None
    >>> fill_list_ends([1, 1, 1], 0)
    ([1, 1, 1], 0)
    """
    # All the items are invalid, we don't know how to fill the new list.
    if all(e == invalid_item for e in list_):
        return None
    # These is no invalid item, return the original list.
    if invalid_item not in list_:
        return list_, 0
    idx_first_valid_item, idx_last_valid_item = idx_first_last_valid_items(list_, invalid_item)
    new_list = list_.copy()
    for i in range(len(list_)):
        # Fill the new list ends with the valid items.
        if i < idx_first_valid_item:
            new_list[i] = list_[idx_first_valid_item]
        if i > idx_last_valid_item:
            new_list[i] = list_[idx_last_valid_item]
    no_filled_item = len(list_) - idx_last_valid_item - 1 + idx_first_valid_item
    return new_list, no_filled_item

### QGIS ALGORITHM

class InterpolateMissingZOnLine(QgsProcessingAlgorithm):

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    NODATAZ = 'NODATAZ'

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return InterpolateMissingZOnLine()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'interpolate_missing_z_on_line'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Interpolate missing Z on line')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('External Scripts')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'externalscripts'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr(
            "This algorithm interpolates missing Z values on a lineZ layer.\n\n"
            "QGIS doesn't have a NULL for declaring missing Z values in vector layers. "
            "A newly created vector layer will have Z values defaulting to 0. "
            "The parameter 'NoData Z' provides a way to declare what numerical value should "
            "be considered as the NoData one (0 in most cases).\n\n"
            "If the first or last vertices of a line have missing values, the "
            "algorithm will fill them in (extrapolate) by setting their value "
            "to the first/last valid ones found.\n\n"
            "Author: Maxime Liquet"
        )
    
    def helpUrl(self):
        return "https://github.com/maximlt/qgis_interpolate_missing_z_line"

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """
        # We add the input vector features source.
        # The algorithm only works with lines.
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input Line Z layer'),
                [QgsProcessing.TypeVectorLine]
            )
        )

        # From https://gis.stackexchange.com/questions/285570/changing-parameter-values-according-to-other-parameter-choice-in-processing-scri
        self.addParameter(
            QgsProcessingParameterNumber(
                name=self.NODATAZ,
                description=self.tr('NoData Z'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0,
                optional=False,
            )
        )
        
        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('InterpolatedMissingZ')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """Here is where the processing itself takes place.
        
        Validate the input (could have used prepareAlgorithm() apparently),
        perform the computation and generate the output.
        """

        # Retrieve the feature source and sink. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        source = self.parameterAsSource(
            parameters,
            self.INPUT,
            context
        )

        # From https://docs.qgis.org/testing/en/docs/user_manual/processing/scripts.html#the-alg-decorator
        nodataz = self.parameterAsDouble(
            parameters,
            'NODATAZ',
            context
        )

        # If source was not found, throw an exception to indicate that the algorithm
        # encountered a fatal error. The exception text can be any string, but in this
        # case we use the pre-built invalidSourceError method to return a standard
        # helper text for when a source cannot be evaluated
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        # Adapted from https://github.com/qgis/QGIS/blob/master/python/plugins/processing/algs/qgis/GeometryConvert.py
        if not QgsWkbTypes.hasZ(source.wkbType()):
            raise QgsProcessingException(self.tr("The input layer has no Z dimension."))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            source.fields(),
            source.wkbType(),
            source.sourceCrs()
        )

        # If sink was not created, throw an exception to indicate that the algorithm
        # encountered a fatal error. The exception text can be any string, but in this
        # case we use the pre-built invalidSinkError method to return a standard
        # helper text for when a sink cannot be evaluated
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        # In QGIS 3 shapelines containing lines are MultiLineStrings. It needs a
        # nested loops to loop over each line they contain.
        # I haven't found a method to convert them to single parts in Python,
        # so I use this processing algorithm to 
        multipart_to_singlepart_algo = processing.run(
            "native:multiparttosingleparts",
            {
                'INPUT': parameters[self.INPUT],
                'OUTPUT': 'memory:'
            },
            context=context,
            feedback=feedback,
            is_child_algorithm=True
        )
        # There has to be a better way but it seemed like the output was always a string here.
        source = QgsProcessingUtils.mapLayerFromString(multipart_to_singlepart_algo['OUTPUT'], context=context)

        # Compute the number of steps to display within the progress bar and
        # get features from source
        total = 100.0 / source.featureCount() if source.featureCount() else 0
        features = source.getFeatures()

        feedback.pushInfo(
            self.tr("Processing {featurecount} line(s)...").format(featurecount=source.featureCount())
        )
        # Looping through all the lines found in the layer.
        for current, feature in enumerate(features):
            # Stop the algorithm if cancel button is clicked
            if feedback.isCanceled():
                break

            # Using .constGet() allows to retrieve the Z values.
            line = feature.geometry().constGet()
            original_z_values = [pt.z() for pt in line]

            # Do not do anything special with a line if it does not contain any NoData Z.
            # So it's just copied to the output (=sink).
            # Yet, report is as a warning to the user.
            if nodataz not in original_z_values:
                sink.addFeature(feature, QgsFeatureSink.FastInsert)
                feedback.reportError(
                    self.tr(
                        "Line {feature_id}: Left unchanched as it has no vertex with missing value."
                    ).format(feature_id=feature.id())
                )
                continue

            # A line that would contain only NoData Z is considered as okayish
            # and doesn't stop the algorithm. It's also copied to the output.
            # It is notified to the user though through an error message that
            # doesn't stop the algorithm.
            if all(z == nodataz for z in original_z_values):
                sink.addFeature(feature, QgsFeatureSink.FastInsert)
                feedback.reportError(
                    self.tr(
                        "Line {feature_id}: Contains missing values only, left as is."
                    ).format(feature_id=feature.id())
                )
                continue

            # Computing the interpolated values will be based on this list.
            base_z_values = original_z_values

            # The start and the end vertices of a line can have missing values.
            # Their values are filled with the closest (in terms of indexes, not geographically)
            # non missing value.
            if base_z_values[0] == nodataz or base_z_values[-1] == nodataz:
                base_z_values, no_filled_vertices = fill_list_ends(original_z_values, invalid_item=nodataz)
                feedback.reportError(
                    self.tr(
                        "Line {feature_id}: Has one or both end(s) with missing Z values. "
                        "{no_filled_vertices} vertices set with the first/last valid Z value(s) found."
                    ).format(feature_id=feature.id(), no_filled_vertices=no_filled_vertices)
                )
                # Dev check
                if len(base_z_values) != len(original_z_values):
                    raise QgsProcessingException(
                        self.tr(
                            "Problem with the code itself: "
                            "The count of filled vertices is different than the original count."
                        )
                )

            # Calculate each segment (line between two vertices) length.
            points = feature.geometry().asPolyline()
            seg_lengths = [
                math.sqrt(pt_i.sqrDist(pt_j)) 
                for pt_i, pt_j in zip(points[:-1], points[1:])
            ]
            # Calculate the distance of each vertex from the starting one (= cumulated segment length).
            dist = [0] + list(itertools.accumulate(seg_lengths))

            new_zs = []  # To store the new/old Z values.

            # Description of the algorithm:
            #
            # The algorithm starts from the first vertex and progresses forward.
            # When it encounters a valid Z value, it stores it. If the next vertex has
            # a valid Z value, that value replaces the one stored. If the next vertex
            # has a missing Z value, the algorithm doesn't progress but looks farther
            # forward for a valid Z value. It can handle several missing Z values in a row.
            # Once it has found a valid Z value forward, it uses both valid Z values
            # to interpolate the Z value at the current location. The interpolation
            # uses the distance between the valid vertices and the distance between
            # the first valid vertex and the vertex where the missing value is to
            # be interpolated.

            # Initialize the index of the end vertex used for interpolating.
            end_interp_idx = 0
            # Loop through each vertex.
            for vert_idx, (current_dist, current_z) in enumerate(zip(dist, base_z_values)):
                if current_z != nodataz:
                    # The first encountered Z before a NoDataZ is stored for
                    # interpolatingthe following adjacent missing values.
                    start_interp_z = current_z
                    # Same for the distance.
                    start_interp_dist = current_dist
                    # The Z is left unchanged for creating the new line.
                    new_z = current_z
                else:
                    # If the interpolation end vertex needs to be found.
                    # This is always true for the first vertex with a missing Z value.
                    if vert_idx >= end_interp_idx:
                        end_interp_idx = vert_idx + 1
                        while base_z_values[end_interp_idx] == nodataz:
                            end_interp_idx += 1
                        # Retrieve its Z and distance.
                        end_interp_z = base_z_values[end_interp_idx]
                        end_interp_dist = dist[end_interp_idx]
                    # Interpolate the Z value of the vertex being currently processed.
                    new_z = interpolate_z(
                        current_dist, start_interp_dist, end_interp_dist, start_interp_z, end_interp_z
                    )
                # Add the Z values.
                new_zs.append(new_z)

            # Dev check to see whether the algo worked correctly.
            if len(new_zs) != len(base_z_values):
                raise QgsProcessingException(
                    self.tr(
                        "Problem with the code itself: "
                        "The count of interpolated vertices is different than the original count."
                        )
                )

            feedback.pushInfo(
                self.tr(
                    "Line {feature_id}: {count_missing_z} vertices with missing"
                    "values interpolated (total no. of vertices: {count_vertices})."
                ).format(
                    feature_id=feature.id(),
                    count_missing_z=base_z_values.count(nodataz),
                    count_vertices=len(base_z_values)
                )
            )

            # The new lines are created with the original, filled and interpolated points.
            new_pt = []
            for pt, new_z in zip(line, new_zs):
                pt.setZ(new_z)
                new_pt.append(pt)
            new_line = QgsGeometry.fromPolyline(new_pt)
            feat = QgsFeature(feature)
            feat.setGeometry(new_line)

            # Add a feature in the sink
            sink.addFeature(feat, QgsFeatureSink.FastInsert)

            # Update the progress bar
            feedback.setProgress(int(current * total))

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return {self.OUTPUT: dest_id}


