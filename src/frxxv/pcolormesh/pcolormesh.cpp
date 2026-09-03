#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <condition_variable>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <queue>
#include <thread>
#include <vector>

// Set this to true to enable diagnostics regardless of the build type.
#define FRXXPCMDEBUG false

// C++ compilers do not define a portable macro specifically for -g. Debug
// builds conventionally omit NDEBUG, while release builds define it.
#ifdef NDEBUG
#define FRXXPCM_SYSTEM_DEBUG false
#else
#define FRXXPCM_SYSTEM_DEBUG true
#endif

#define FRXXPCM_DEBUG_LOG(message) \
	do { \
		if constexpr (FRXXPCMDEBUG || FRXXPCM_SYSTEM_DEBUG) { \
			std::cerr << message << std::endl; \
		} \
	} while (false)

namespace py = pybind11;

namespace {

class WorkerPool {
	public:
	explicit WorkerPool(std::size_t thread_count) {
		workers.reserve(thread_count);
		for (std::size_t i = 0; i < thread_count; ++i) {
			workers.emplace_back([this] { run(); });
		}
	}

	~WorkerPool() {
		{
			std::lock_guard lock(queue_mutex);
			stopping = true;
		}
		work_available.notify_all();
		for (auto& worker : workers) {
			worker.join();
		}
	}

	WorkerPool(const WorkerPool &) = delete;
	WorkerPool& operator=(const WorkerPool&) = delete;

	std::size_t size() const {
		return workers.size();
	}

	template <class Function>
	void parallel_for(std::size_t count, Function function) {
		if (count == 0) {
			return;
		}

		const std::size_t job_count = std::min(count, workers.size());
		struct Batch {
			std::mutex mutex;
			std::condition_variable completed;
			std::size_t remaining;
		};
		auto batch = std::make_shared<Batch>();
		batch->remaining = job_count;

		for (std::size_t job = 0; job < job_count; ++job) {
			const std::size_t begin = count * job / job_count;
			const std::size_t end = count * (job + 1) / job_count;
			enqueue([begin, end, batch, &function] {
				for (std::size_t i = begin; i < end; ++i) {
					function(i);
				}
				{
					std::lock_guard lock(batch->mutex);
					--batch->remaining;
				}
				batch->completed.notify_one();
			});
		}

		std::unique_lock lock(batch->mutex);
		batch->completed.wait(lock, [&batch] { return batch->remaining == 0; });
	}

	private:
	void enqueue(std::function<void()> job) {
		{
			std::lock_guard lock(queue_mutex);
			jobs.push(std::move(job));
		}
		work_available.notify_one();
	}

	void run() {
		while (true) {
			std::function<void()> job;
			{
				std::unique_lock lock(queue_mutex);
				work_available.wait(lock, [this] { return stopping || !jobs.empty(); });
				if (stopping && jobs.empty()) {
					return;
				}
				job = std::move(jobs.front());
				jobs.pop();
			}
			job();
		}
	}

	std::vector<std::thread> workers;
	std::queue<std::function<void()>> jobs;
	std::mutex queue_mutex;
	std::condition_variable work_available;
	bool stopping = false;
};

WorkerPool& quad_worker_pool() {
	// hardware_concurrency() is only a hint and may return zero. Use half of
	// the reported logical CPUs, but always keep at least one worker.
	static WorkerPool pool(
		//4);
		std::max(1u, std::thread::hardware_concurrency() / 2));
	return pool;
}

struct Point {
	double x;
	double y;
};

struct ProcessedQuad {
	std::array<Point, 4> vertices;
	std::array<std::uint8_t, 4> color;
	int x0 = 0;
	int x1 = 0;
	int y0 = 0;
	int y1 = 0;
};

double cross(const Point& a, const Point& b, const Point& p) {
	return (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x);
}

bool is_convex(const std::array<Point, 4>& quad) {
	double max_edge_length_squared = 0.0;
	for (std::size_t i = 0; i < quad.size(); ++i) {
		const Point& start = quad[i];
		const Point& end = quad[(i + 1) % quad.size()];
		const double dx = end.x - start.x;
		const double dy = end.y - start.y;
		max_edge_length_squared = std::max(
			max_edge_length_squared, dx * dx + dy * dy);
	}

	// Cross products have units of length squared, so scale their tolerance by
	// the longest edge squared. Coordinates commonly originate as float32 even
	// though Matplotlib supplies doubles here; allow a few float ULPs for corner
	// interpolation and affine transformation noise.
	const double tolerance = 8.0 * std::numeric_limits<float>::epsilon() *
		max_edge_length_squared;
	bool positive = false;
	bool negative = false;
	for (std::size_t i = 0; i < quad.size(); ++i) {
		const double value = cross(quad[i], quad[(i + 1) % 4], quad[(i + 2) % 4]);
		positive |= value > tolerance;
		negative |= value < -tolerance;
	}
	return !(positive && negative);
}

enum class QuadGeometry : std::uint8_t {
	convex,
	reordered,
	unsupported,
};

QuadGeometry normalize_quad(std::array<Point, 4>& quad) {
	if (is_convex(quad)) {
		return QuadGeometry::convex;
	}

	// A bow-tie generally still consists of four points on a convex hull; only
	// their traversal order is crossed. Sorting around the centroid restores a
	// cyclic perimeter without guessing which particular pair should be swapped.
	Point centroid{0.0, 0.0};
	for (const Point& point : quad) {
		centroid.x += point.x;
		centroid.y += point.y;
	}
	centroid.x /= static_cast<double>(quad.size());
	centroid.y /= static_cast<double>(quad.size());
	std::sort(quad.begin(), quad.end(), [&centroid](const Point& a, const Point& b) {
		const double angle_a = std::atan2(a.y - centroid.y, a.x - centroid.x);
		const double angle_b = std::atan2(b.y - centroid.y, b.x - centroid.x);
		if (angle_a != angle_b) {
			return angle_a < angle_b;
		}
		const double distance_a =
			(a.x - centroid.x) * (a.x - centroid.x) +
			(a.y - centroid.y) * (a.y - centroid.y);
		const double distance_b =
			(b.x - centroid.x) * (b.x - centroid.x) +
			(b.y - centroid.y) * (b.y - centroid.y);
		return distance_a < distance_b;
	});

	return is_convex(quad) ? QuadGeometry::reordered : QuadGeometry::unsupported;
}

bool contains(const std::array<Point, 4>& quad, const Point& point) {
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

bool render_fast(py::buffer renderer_buffer, const py::args& args) {
	// Matplotlib passes RendererAgg.draw_quad_mesh these ten arguments:
	//   0: graphics context     5: mesh offsets
	//   1: main transform      6: offset transform
	//   2: mesh width          7: face colors
	//   3: mesh height         8: antialiasing enabled
	//   4: corner coordinates  9: edge colors
	if (args.size() != 10) {
		FRXXPCM_DEBUG_LOG("pcolormesh render_fast fallback: expected 10 arguments, got "
			<< args.size());
		return false;
	}
	if (args[8].cast<bool>()) {
		FRXXPCM_DEBUG_LOG("pcolormesh render_fast fallback: antialiasing is enabled");
		return false;
	}

	py::object gc = args[0];
	if (!gc.attr("get_hatch")().is_none()) {
		FRXXPCM_DEBUG_LOG("pcolormesh render_fast fallback: hatching is enabled");
		return false;
	}
	py::tuple clip_path = gc.attr("get_clip_path")().cast<py::tuple>();
	if (!clip_path[0].is_none()) {
		FRXXPCM_DEBUG_LOG("pcolormesh render_fast fallback: a clip path is set");
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
		FRXXPCM_DEBUG_LOG("pcolormesh render_fast fallback: coordinates, offsets, "
			"facecolors, or edgecolors could not be converted to a C-contiguous double array");
		return false;
	}
	if (py::hasattr(args[4], "mask")) {
		py::object mask = args[4].attr("mask");
		if ((py::isinstance<py::array>(mask) && mask.attr("any")().cast<bool>()) ||
			(!py::isinstance<py::array>(mask) && mask.cast<bool>())) {
			FRXXPCM_DEBUG_LOG(
				"pcolormesh render_fast fallback: coordinates contain masked values");
			return false;
		}
	}
	if (coordinates.ndim() != 3 ||
		coordinates.shape(0) != static_cast<py::ssize_t>(mesh_height + 1) ||
		coordinates.shape(1) != static_cast<py::ssize_t>(mesh_width + 1) ||
		coordinates.shape(2) != 2 || offsets.ndim() != 2 || offsets.shape(1) != 2 ||
		facecolors.ndim() != 2 || facecolors.shape(1) != 4 || facecolors.shape(0) == 0 ||
		edgecolors.ndim() != 2 || edgecolors.shape(0) != 0) {
		FRXXPCM_DEBUG_LOG(
			"pcolormesh render_fast fallback: unsupported coordinate/color shapes; "
			<< "coordinates=" << py::str(coordinates.attr("shape")).cast<std::string>()
			<< ", offsets=" << py::str(offsets.attr("shape")).cast<std::string>()
			<< ", facecolors=" << py::str(facecolors.attr("shape")).cast<std::string>()
			<< ", edgecolors=" << py::str(edgecolors.attr("shape")).cast<std::string>());
		return false;
	}

	// The normal QuadMesh default is one zero offset. More general collection
	// offsets remain on Matplotlib's path until they have a measured use case.
	if (offsets.shape(0) != 1 || std::abs(*offsets.data(0, 0)) > 1e-12 ||
		std::abs(*offsets.data(0, 1)) > 1e-12) {
		FRXXPCM_DEBUG_LOG(
			"pcolormesh render_fast fallback: expected one zero offset, got shape[0]="
			<< offsets.shape(0));
		return false;
	}

	auto matrix = py::array_t<double, py::array::c_style | py::array::forcecast>::ensure(
		args[1].attr("get_matrix")());
	if (!matrix || matrix.ndim() != 2 || matrix.shape(0) != 3 || matrix.shape(1) != 3) {
		FRXXPCM_DEBUG_LOG("pcolormesh render_fast fallback: transform matrix is not a 3x3 "
			"C-contiguous double array");
		return false;
	}
	const double* m = matrix.data();

	py::object clip_rectangle = gc.attr("get_clip_rectangle")();
	if (clip_rectangle.is_none()) {
		FRXXPCM_DEBUG_LOG("pcolormesh render_fast fallback: no clip rectangle is set");
		return false;
	}
	auto clip_extents = py::array_t<double, py::array::c_style | py::array::forcecast>::ensure(
		clip_rectangle.attr("extents"));
	if (!clip_extents || clip_extents.size() != 4) {
		FRXXPCM_DEBUG_LOG("pcolormesh render_fast fallback: clip rectangle extents could "
			"not be converted to four doubles");
		return false;
	}

	const double* coords = coordinates.data();
	const double* colors = facecolors.data();
	const std::size_t coordinate_stride = mesh_width + 1;
	const std::size_t color_count = static_cast<std::size_t>(facecolors.shape(0));

	auto transform = [&](std::size_t row, std::size_t column) {
		const std::size_t index = (row * coordinate_stride + column) * 2;
		const double x = coords[index];
		const double y = coords[index + 1];
		return Point{m[0] * x + m[1] * y + m[2], m[3] * x + m[4] * y + m[5]};
	};

	// Validate the colors before touching the renderer buffer. This initial
	// native path only handles fully transparent or fully opaque cells.
	for (std::size_t i = 0; i < color_count; ++i) {
		const double alpha = colors[i * 4 + 3];
		if (std::abs(alpha) > 1e-12 && std::abs(alpha - 1.0) > 1e-12) {
			FRXXPCM_DEBUG_LOG("pcolormesh render_fast fallback: facecolor " << i
				<< " has unsupported alpha=" << alpha);
			return false;
		}
	}

	py::buffer_info buffer = renderer_buffer.request(true);
	if (buffer.ndim != 3 || buffer.shape[2] != 4 || buffer.itemsize != 1) {
		FRXXPCM_DEBUG_LOG("pcolormesh render_fast fallback: renderer buffer must have "
			"ndim=3, four channels, and one-byte items");
		return false;
	}

	const int image_height = static_cast<int>(buffer.shape[0]);
	const int image_width = static_cast<int>(buffer.shape[1]);
	const double* clip = clip_extents.data();
	const int clip_x0 = std::max(0, static_cast<int>(std::floor(clip[0])));
	const int clip_y0 = std::max(0, static_cast<int>(std::floor(clip[1])));
	const int clip_x1 = std::min(image_width, static_cast<int>(std::ceil(clip[2])));
	const int clip_y1 = std::min(image_height, static_cast<int>(std::ceil(clip[3])));
	auto* pixels = static_cast<std::uint8_t*>(buffer.ptr);

	const std::size_t quad_count = mesh_width * mesh_height;
	const std::size_t preprocessing_job_count = std::min(
		quad_count, quad_worker_pool().size());
	std::vector<std::vector<ProcessedQuad>> visible_by_job(preprocessing_job_count);
	std::atomic<bool> supported = true;
	std::atomic<std::size_t> non_finite_quad{quad_count};
	std::atomic<std::size_t> first_reordered_quad{quad_count};
	std::atomic<std::size_t> first_skipped_quad{quad_count};
	std::atomic<std::size_t> reordered_quad_count{0};
	std::atomic<std::size_t> skipped_quad_count{0};

	// The pool is process-wide and its threads persist across every draw.
	// Each worker builds a compact list for one contiguous input range. Merging
	// those lists in job order below preserves the original quad draw order.
	{
		py::gil_scoped_release release;
		quad_worker_pool().parallel_for(preprocessing_job_count, [&](std::size_t job) {
			const std::size_t begin = quad_count * job / preprocessing_job_count;
			const std::size_t end = quad_count * (job + 1) / preprocessing_job_count;
			auto& visible = visible_by_job[job];

			for (std::size_t index = begin; index < end; ++index) {
				const double* color = colors + (index % color_count) * 4;
				if (color[3] == 0.0) {
					continue;
				}

				const std::size_t row = index / mesh_width;
				const std::size_t column = index % mesh_width;
				ProcessedQuad result;
				result.vertices = {
					transform(row, column),
					transform(row + 1, column),
					transform(row + 1, column + 1),
					transform(row, column + 1),
				};

				for (const Point& point : result.vertices) {
					if (!std::isfinite(point.x) || !std::isfinite(point.y)) {
						std::size_t expected = quad_count;
						non_finite_quad.compare_exchange_strong(
							expected, index, std::memory_order_relaxed);
						supported.store(false, std::memory_order_relaxed);
						return;
					}
				}
				const QuadGeometry geometry = normalize_quad(result.vertices);
				if (geometry == QuadGeometry::reordered) {
					std::size_t expected = quad_count;
					first_reordered_quad.compare_exchange_strong(
						expected, index, std::memory_order_relaxed);
					reordered_quad_count.fetch_add(1, std::memory_order_relaxed);
				} else if (geometry == QuadGeometry::unsupported) {
					std::size_t expected = quad_count;
					first_skipped_quad.compare_exchange_strong(
						expected, index, std::memory_order_relaxed);
					skipped_quad_count.fetch_add(1, std::memory_order_relaxed);
					continue;
				}

				const auto [min_x, max_x] = std::minmax_element(
					result.vertices.begin(), result.vertices.end(),
					[](const Point& a, const Point& b) { return a.x < b.x; });
				const auto [min_y, max_y] = std::minmax_element(
					result.vertices.begin(), result.vertices.end(),
					[](const Point& a, const Point& b) { return a.y < b.y; });
				result.x0 = std::max(clip_x0, static_cast<int>(std::floor(min_x->x)));
				result.x1 = std::min(clip_x1, static_cast<int>(std::ceil(max_x->x)));
				result.y0 = std::max(clip_y0, static_cast<int>(std::floor(min_y->y)));
				result.y1 = std::min(clip_y1, static_cast<int>(std::ceil(max_y->y)));
				if (result.x0 >= result.x1 || result.y0 >= result.y1) {
					continue;
				}

				result.color = {
					color_component(color[0]), color_component(color[1]),
					color_component(color[2]), 255,
				};
				visible.push_back(std::move(result));
			}
		});
	}
	const std::size_t reordered_count = reordered_quad_count.load(std::memory_order_relaxed);
	if (reordered_count != 0) {
		FRXXPCM_DEBUG_LOG("pcolormesh render_fast: reordered " << reordered_count
			<< " bow-tie quad(s); first was quad "
			<< first_reordered_quad.load(std::memory_order_relaxed));
	}
	const std::size_t skipped_count = skipped_quad_count.load(std::memory_order_relaxed);
	if (skipped_count != 0) {
		FRXXPCM_DEBUG_LOG("pcolormesh render_fast: skipped " << skipped_count
			<< " irreparable concave quad(s); first was quad "
			<< first_skipped_quad.load(std::memory_order_relaxed));
	}
	if (!supported.load(std::memory_order_relaxed)) {
		const std::size_t non_finite = non_finite_quad.load(std::memory_order_relaxed);
		if (non_finite != quad_count) {
			FRXXPCM_DEBUG_LOG("pcolormesh render_fast fallback: quad " << non_finite
				<< " has non-finite transformed coordinates");
		}
		return false;
	}

	// Split the framebuffer into disjoint horizontal bands. Each worker visits
	// quads in draw order, but writes only to rows owned by its band, preserving
	// overdraw semantics without concurrent writes to the same pixel.
	const int raster_height = std::max(0, clip_y1 - clip_y0);
	const std::size_t band_count = std::min<std::size_t>(
		static_cast<std::size_t>(raster_height), quad_worker_pool().size());
	{
		py::gil_scoped_release release;
		quad_worker_pool().parallel_for(band_count, [&](std::size_t band) {
			const int band_y0 = clip_y0 + raster_height * static_cast<int>(band) /
				static_cast<int>(band_count);
			const int band_y1 = clip_y0 + raster_height * static_cast<int>(band + 1) /
				static_cast<int>(band_count);

			for (const auto& visible : visible_by_job) {
				for (const ProcessedQuad& quad : visible) {
					const int y0 = std::max(quad.y0, band_y0);
					const int y1 = std::min(quad.y1, band_y1);
					for (int y = y0; y < y1; ++y) {
						for (int x = quad.x0; x < quad.x1; ++x) {
							if (!contains(quad.vertices, Point{x + 0.5, y + 0.5})) {
								continue;
							}
							const int buffer_row = image_height - 1 - y;
							auto* pixel = pixels + buffer_row * buffer.strides[0] + x * buffer.strides[1];
							std::copy(quad.color.begin(), quad.color.end(), pixel);
						}
					}
				}
			}
		});
	}
	return true;
}

}  // namespace

py::object draw_quad_mesh(py::object fallback, py::args args) {
	py::buffer renderer_buffer = fallback.attr("__self__").cast<py::buffer>();
	if (render_fast(renderer_buffer, args)) {
		// FRXXPCM_DEBUG_LOG("fast");
		return py::none();
	}
	// FRXXPCM_DEBUG_LOG("fell back");
	return fallback(*args);
}

PYBIND11_MODULE(pcolormesh, module) {
	module.doc() = "Accelerated pcolormesh helpers.";
	module.def("draw_quad_mesh", &draw_quad_mesh);
}
