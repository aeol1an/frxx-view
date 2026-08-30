#include <pybind11/pybind11.h>

#include <iostream>

void hello_world() {
    std::cout << "Hello, world! " << std::endl;
}

PYBIND11_MODULE(_pcolormesh, module) {
    module.doc() = "Accelerated pcolormesh helpers.";
    module.def("hello_world", &hello_world);
}
