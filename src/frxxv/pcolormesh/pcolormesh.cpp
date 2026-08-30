#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>

namespace py = pybind11;

namespace {

struct Point {
    double x;
    double y;
};

double cross(const Point &a, const Point &b, const Point &p) {
    return (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x);
}

bool is_convex(const std::array<Point, 4> &quad) {
    bool positive = false;
    bool negative = false;
    for (std::size_t i = 0; i < quad.size(); ++i) {
        const double value = cross(quad[i], quad[(i + 1) % 4], quad[(i + 2) % 4]);
        positive |= value > 1e-12;
        negative |= value < -1e-12;
    }
    return !(positive && negative);
}

bool contains(const std::array<Point, 4> &quad, const Point &point) {
    bool positive = false;
    bool negative = false;
    for (std::size_t i = 0; i < quad.size(); ++i) {
        const double value = cross(quad[i], quad[(i + 1) % 4], point);
        positive |= value > 1e-12;
        negative |= value < -1e-12;
    }
    return !(positive && negative);
}

std::uint8_t color_component(double value) {
    return static_cast<std::uint8_t>(std::lround(std::clamp(value, 0.0, 1.0) * 255.0));
}

bool render_fast(py::object fallback, const py::args &args) {
    if (args.size() != 10 || args[8].cast<bool>()) {
        return false;
    }

    py::object gc = args[0];
    if (!gc.attr("get_hatch")().is_none()) {
        return false;
    }
    py::tuple clip_path = gc.attr("get_clip_path")().cast<py::tuple>();
    if (!clip_path[0].is_none()) {
        return false;
    }

    const auto mesh_width = args[2].cast<std::size_t>();
    const auto mesh_height = args[3].cast<std::size_t>();
    if (mesh_width == 0 || mesh_height == 0) {
        return true;
    }

    auto coordinates = py::array_t<double, py::array::c_style | py::array::forcecast>::ensure(args[4]);
    auto offsets = py::array_t<double, py::array::c_style | py::array::forcecast>::ensure(args[5]);
    auto facecolors = py::array_t<double, py::array::c_style | py::array::forcecast>::ensure(args[7]);
    auto edgecolors = py::array_t<double, py::array::c_style | py::array::forcecast>::ensure(args[9]);
    if (!coordinates || !offsets || !facecolors || !edgecolors) {
        return false;
    }
    if (py::hasattr(args[4], "mask")) {
        py::object mask = args[4].attr("mask");
        if ((py::isinstance<py::array>(mask) && mask.attr("any")().cast<bool>()) ||
            (!py::isinstance<py::array>(mask) && mask.cast<bool>())) {
            return false;
        }
    }
    if (coordinates.ndim() != 3 ||
        coordinates.shape(0) != static_cast<py::ssize_t>(mesh_height + 1) ||
        coordinates.shape(1) != static_cast<py::ssize_t>(mesh_width + 1) ||
        coordinates.shape(2) != 2 || offsets.ndim() != 2 || offsets.shape(1) != 2 ||
        facecolors.ndim() != 2 || facecolors.shape(1) != 4 || facecolors.shape(0) == 0 ||
        edgecolors.ndim() != 2 || edgecolors.shape(0) != 0) {
        return false;
    }

    // The normal QuadMesh default is one zero offset. More general collection
    // offsets remain on Matplotlib's path until they have a measured use case.
    if (offsets.shape(0) != 1 || std::abs(*offsets.data(0, 0)) > 1e-12 ||
        std::abs(*offsets.data(0, 1)) > 1e-12) {
        return false;
    }

    auto matrix = py::array_t<double, py::array::c_style | py::array::forcecast>::ensure(
        args[1].attr("get_matrix")());
    if (!matrix || matrix.ndim() != 2 || matrix.shape(0) != 3 || matrix.shape(1) != 3) {
        return false;
    }
    const double *m = matrix.data();

    py::object clip_rectangle = gc.attr("get_clip_rectangle")();
    if (clip_rectangle.is_none()) {
        return false;
    }
    auto clip_extents = py::array_t<double, py::array::c_style | py::array::forcecast>::ensure(
        clip_rectangle.attr("extents"));
    if (!clip_extents || clip_extents.size() != 4) {
        return false;
    }

    const double *coords = coordinates.data();
    const double *colors = facecolors.data();
    const std::size_t coordinate_stride = mesh_width + 1;
    const std::size_t color_count = static_cast<std::size_t>(facecolors.shape(0));

    auto transform = [&](std::size_t row, std::size_t column) {
        const std::size_t index = (row * coordinate_stride + column) * 2;
        const double x = coords[index];
        const double y = coords[index + 1];
        return Point{m[0] * x + m[1] * y + m[2], m[3] * x + m[4] * y + m[5]};
    };

    // Validate the whole call before touching the renderer buffer. This keeps
    // fallback safe if the mesh contains geometry the initial path cannot draw.
    for (std::size_t i = 0; i < static_cast<std::size_t>(coordinates.size()); ++i) {
        if (!std::isfinite(coords[i])) {
            return false;
        }
    }
    for (std::size_t i = 0; i < color_count; ++i) {
        const double alpha = colors[i * 4 + 3];
        if (std::abs(alpha) > 1e-12 && std::abs(alpha - 1.0) > 1e-12) {
            return false;
        }
    }
    for (std::size_t row = 0; row < mesh_height; ++row) {
        for (std::size_t column = 0; column < mesh_width; ++column) {
            const std::array<Point, 4> quad{
                transform(row, column),
                transform(row + 1, column),
                transform(row + 1, column + 1),
                transform(row, column + 1),
            };
            if (!is_convex(quad)) {
                return false;
            }
        }
    }

    py::buffer renderer_buffer = fallback.attr("__self__").cast<py::buffer>();
    py::buffer_info buffer = renderer_buffer.request(true);
    if (buffer.ndim != 3 || buffer.shape[2] != 4 || buffer.itemsize != 1) {
        return false;
    }

    const int image_height = static_cast<int>(buffer.shape[0]);
    const int image_width = static_cast<int>(buffer.shape[1]);
    const double *clip = clip_extents.data();
    const int clip_x0 = std::max(0, static_cast<int>(std::floor(clip[0])));
    const int clip_y0 = std::max(0, static_cast<int>(std::floor(clip[1])));
    const int clip_x1 = std::min(image_width, static_cast<int>(std::ceil(clip[2])));
    const int clip_y1 = std::min(image_height, static_cast<int>(std::ceil(clip[3])));
    auto *pixels = static_cast<std::uint8_t *>(buffer.ptr);

    py::gil_scoped_release release;
    for (std::size_t row = 0; row < mesh_height; ++row) {
        for (std::size_t column = 0; column < mesh_width; ++column) {
            const std::size_t face_index = (row * mesh_width + column) % color_count;
            const double *color = colors + face_index * 4;
            if (color[3] == 0.0) {
                continue;
            }

            const std::array<Point, 4> quad{
                transform(row, column),
                transform(row + 1, column),
                transform(row + 1, column + 1),
                transform(row, column + 1),
            };
            const auto [min_x, max_x] = std::minmax_element(
                quad.begin(), quad.end(), [](const Point &a, const Point &b) { return a.x < b.x; });
            const auto [min_y, max_y] = std::minmax_element(
                quad.begin(), quad.end(), [](const Point &a, const Point &b) { return a.y < b.y; });
            const int x0 = std::max(clip_x0, static_cast<int>(std::floor(min_x->x)));
            const int x1 = std::min(clip_x1, static_cast<int>(std::ceil(max_x->x)));
            const int y0 = std::max(clip_y0, static_cast<int>(std::floor(min_y->y)));
            const int y1 = std::min(clip_y1, static_cast<int>(std::ceil(max_y->y)));
            if (x0 >= x1 || y0 >= y1) {
                continue;
            }

            const std::array<std::uint8_t, 4> rgba{
                color_component(color[0]), color_component(color[1]),
                color_component(color[2]), 255,
            };
            for (int y = y0; y < y1; ++y) {
                for (int x = x0; x < x1; ++x) {
                    if (!contains(quad, Point{x + 0.5, y + 0.5})) {
                        continue;
                    }
                    const int buffer_row = image_height - 1 - y;
                    auto *pixel = pixels + buffer_row * buffer.strides[0] + x * buffer.strides[1];
                    std::copy(rgba.begin(), rgba.end(), pixel);
                }
            }
        }
    }
    return true;
}

}  // namespace

void hello_world() {
    std::cout << "Hello, world! " << std::endl;
}

py::object draw_quad_mesh(py::object fallback, py::args args) {
    if (render_fast(fallback, args)) {
        return py::none();
    }
    return fallback(*args);
}

PYBIND11_MODULE(_pcolormesh, module) {
    module.doc() = "Accelerated pcolormesh helpers.";
    module.def("hello_world", &hello_world);
    module.def("draw_quad_mesh", &draw_quad_mesh);
}
