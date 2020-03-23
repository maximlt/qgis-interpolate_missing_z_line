# Algorithm for QGIS 3 to interpolate missing Z values on a line Z vector layer.

This algorithm takes a line Z vector layer as input (consisting of one
or several lines) and performs the following:
* If the first or last vertices of a line have missing values, fill them in (extrapolate) by setting their value equal to the first/last valid ones found.
* Interpolate the remaining missing Z values.

<p align="center"><img src="https://raw.githubusercontent.com/maximlt/qgis_interpolate_missing_z_line/master/example.png" alt="Example"/></p>

## NULL Z data in QGIS

QGIS doesn't have a NULL for declaring missing Z values in vector layers.
A newly created Z vector layer will have Z values defaulting to 0.
The parameter `NoData Z` provides a way to declare what numerical value should
be considered as the NoData one. It should be 0 in most cases.

## An examplary use case

A line Z layer representing roads where the elevations would be
known only at a few locations. Interpolating the Z values between
these locations with the algorithm is a fast way to populate the Z
values of the layer. Doing it by hand could be really slow, particularly if the roads have curves, hence many vertices.

## Edge case handling

* If a line feature only has missing values, it is left as is.
* If a line feature has no missing value, it is left as is.

## Installation

<p align="center"><img src="https://raw.githubusercontent.com/maximlt/qgis_interpolate_missing_z_line/master/install1.PNG" alt="Install" width=250/></p>
<p align="center"><img src="https://raw.githubusercontent.com/maximlt/qgis_interpolate_missing_z_line/master/install2.PNG" alt="Install" width=250/></p>

## Usage

The algorithm is parameterized through the classic user interface provided by QGIS.

<p align="center"><img src="https://raw.githubusercontent.com/maximlt/qgis_interpolate_missing_z_line/master/ui_parameters.PNG" alt="User Interface" width=500/></p>

The algorithm provides a message for each line that it processes,
giving the user the ability to check the quality of the
input line Z layer and how each feature was processed.

The exemple below illustrates the log messages obtained after running
the algorithm for the example above. The messages in red are warnings
that point the user to have a closer look at the input line Z layer.

<p align="center"><img src="https://raw.githubusercontent.com/maximlt/qgis_interpolate_missing_z_line/master/ui_log.PNG" alt="User Interface" width=500/></p>

## Layer Style

QGIS has no way (as of writing in 03/2020) to directly label the Z values
of a vector layer. A style file (*.qml) was created to display the Z value of each vertex as a way to check whether the algorithm worked correctly. It also displays missing Z values (hardcoded at 0 in the style) with red markers.

The QML file can be downloaded [here](./display_and_label_z_vertices.qml).

One useful trick is to associate this style with the algorithm output.

<p align="center"><img src="https://raw.githubusercontent.com/maximlt/qgis_interpolate_missing_z_line/master/algo_style.PNG" alt="Algo style" width=300/></p>

Note: Make sure that `Clip Features to Canvas Extent` is unticked in the `Avanced` property of the `Symbology` pane. If not, the style might weirdly change when you zoom in and out.

## License

MIT License

Copyright (c) 2020 Maxime Liquet

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.