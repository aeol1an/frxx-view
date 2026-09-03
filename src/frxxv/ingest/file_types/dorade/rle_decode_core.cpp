#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>

#include <algorithm>
#include <cstdint>

namespace py = pybind11;

namespace {

py::tuple _rle_decode_core(
	py::array_t<std::uint16_t, py::array::c_style | py::array::forcecast> comp_u16,
	py::array_t<std::int16_t, py::array::c_style | py::array::forcecast> comp_i16,
	py::ssize_t ngates) {
	if (comp_u16.ndim() != 1 || comp_i16.ndim() != 1) {
		throw py::value_error("comp_u16 and comp_i16 must be one-dimensional");
	}
	if (comp_u16.shape(0) != comp_i16.shape(0)) {
		throw py::value_error("comp_u16 and comp_i16 must have the same length");
	}

	const py::ssize_t n_words = comp_u16.shape(0);
	py::array_t<std::int16_t> out(ngates);
	auto comp_u16_data = comp_u16.unchecked<1>();
	auto comp_i16_data = comp_i16.unchecked<1>();
	auto out_data = out.mutable_unchecked<1>();
	std::fill_n(out_data.mutable_data(0), ngates, static_cast<std::int16_t>(-32768));
	py::ssize_t i = 0;
	py::ssize_t j = 0;
	bool prev_was_bad_run = false;
	while (i < n_words && j < ngates) {
		const std::uint16_t val = comp_u16_data(i);
		if (val == 0 || val == 1) {
			break;  // end-of-row sentinel
		}
		py::ssize_t n = val & 0x7FFF;
		const bool is_literal = (val & 0x8000) != 0;
		if (is_literal) {
			prev_was_bad_run = false;
			i += 1;
			const py::ssize_t available = n_words - i;
			if (n > available) {
				n = available;
			}
			if (n > ngates - j) {
				n = ngates - j;
			}
			if (n <= 0) {
				break;
			}
			for (py::ssize_t k = 0; k < n; ++k) {
				out_data(j + k) = comp_i16_data(i + k);
			}
			i += n;
		} else {
			if (prev_was_bad_run) {
				break;
			}
			prev_was_bad_run = true;
			if (n > ngates - j) {
				n = ngates - j;
			}
			for (py::ssize_t k = 0; k < n; ++k) {
				out_data(j + k) = -32768;
			}
			i += 1;
		}
		j += n;
	}
	return py::make_tuple(std::move(out), j);
}

}

PYBIND11_MODULE(rle_decode_core, module) {
	module.doc() = "DORADE HRD run-length decoding.";
	module.def("_rle_decode_core", &_rle_decode_core);
}
