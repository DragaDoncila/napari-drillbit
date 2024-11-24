from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from magicgui.widgets import Container, PushButton, create_widget
from matplotlib.backends.backend_qt5agg import (
    FigureCanvas,
    NavigationToolbar2QT,
)
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from qtpy.QtWidgets import QVBoxLayout, QWidget

if TYPE_CHECKING:
    import napari


def set_axes_lims(axes, all_ys):
    all_ys = np.concatenate(all_ys).flatten()
    minval, maxval = np.min(all_ys), np.max(all_ys)
    range_ = maxval - minval
    centre = (maxval + minval) / 2
    min_y = centre - 1.05 * range_ / 2
    max_y = centre + 1.05 * range_ / 2
    axes.set_ylim(min_y, max_y)


class Driller(Container):
    def __init__(self, viewer: "napari.viewer.Viewer"):
        super().__init__()
        self._viewer = viewer
        self._image_layer_combo = create_widget(
            label="Image", annotation="napari.layers.Image"
        )
        self._start_stop_button = PushButton(label="Start Drilling")
        self._drilling = False
        self.image_layer = None
        self.drill_points = None

        self.extend([self._image_layer_combo, self._start_stop_button])
        self._drill_canvas = self.create_plot_dock()
        self._start_stop_button.changed.connect(self.start_stop_drilling)

    def create_plot_dock(self):
        with plt.style.context("dark_background"):
            drill_canvas = FigureCanvas(Figure(figsize=(5, 3)))
            drill_axes = drill_canvas.figure.subplots()

            drill_axes.set_ylim(-1, 1)
            drill_axes.set_xlabel("slice")
            drill_axes.set_ylabel("value")
            # ndvi_axes.set_title("NDVI")
            drill_canvas.figure.tight_layout()

        # add matplotlib toolbar
        toolbar = NavigationToolbar2QT(
            drill_canvas, self._viewer.window._qt_window
        )
        widget = QWidget()
        layout = QVBoxLayout()
        widget.setLayout(layout)
        layout.addWidget(toolbar)
        layout.addWidget(drill_canvas)
        self._viewer.window.add_dock_widget(widget, area="bottom")

        return drill_canvas

    def start_stop_drilling(self):
        if self._drilling:
            self._drilling = False
            self._start_stop_button.text = "Start Drilling"
            self.image_layer = None
            self.drill_points = None
            self.added_cb()
            self.added_cb = None
        else:
            self._drilling = True
            self._start_stop_button.text = "Stop Drilling"
            if self._image_layer_combo.value is not None:
                self.image_layer = self._image_layer_combo.value
                if len(self.image_layer.data.shape) < 3:
                    raise ValueError("Image must have >=3 dimensions.")
                self.drill_points = self._viewer.add_points(
                    name=f"{self.image_layer.name}_Drillbit"
                )
                self.added_cb = self.drill_points.events.data.connect(
                    self.update_drill_points
                )

    def update_drill_points(self, event):
        if event.action != "added":
            return
        added_coords = event.value[-1]
        displayed_dimensions = self._viewer.dims.displayed
        first_non_displayed = min(np.asarray(displayed_dimensions)) - 1
        if len(self.image_layer.data.shape) > 3:
            current_slices = self._viewer.dims.current_step[
                : first_non_displayed + 1
            ]
            values_of_interest = self.image_layer.data[
                current_slices
                + (slice(None),)
                + tuple([int(coord) for coord in added_coords])
            ]
        else:
            values_of_interest = self.image_layer.data[
                (slice(None),) + tuple(int(coord) for coord in added_coords)
            ]
        self.add_new_line(values_of_interest)

    def add_new_line(self, values):
        axes = self._drill_canvas.figure.axes[0]
        current_lines = axes.get_lines()
        if current_lines:
            xs, _ = current_lines[0].get_data()
            all_ys = [line.get_data()[1] for line in current_lines]
        else:
            xs = np.arange(self.image_layer.data.shape[0])
            axes.set_xlim(xs[0], xs[-1])
            all_ys = []

        all_ys += [values]
        set_axes_lims(axes, all_ys)
        line = axes.plot(xs, values)[0]
        current_colors = self.drill_points.face_color
        current_colors[-1] = to_rgba(line.get_color())
        self.drill_points.face_color = current_colors

        self._drill_canvas.draw_idle()
        self.drill_points.current_face_color = "white"
