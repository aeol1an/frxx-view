# 𝓕(Rₓₓ)-view

A cross-platform matplotlib radar data graphical visualizer and editor. Support for custom handlers is planned.

---

### Installation

```bash
pip install frxx-view
```

---

### Basic Usage

Navigate to a directory of `cfrad.*.nc` files, and simply enter:

```bash
frxxv
```

Basic navigation is done with the forward and back keys on the keyboard. The layout can be changed with the top menu bar. Any panel can be selected by right-clicking it, and contents can be replotted via keys on the keyboard (e.g., `Z` for DBZ or `V` for velocity; for the full list, see the config section below), or with the :p command (`:help p`). `ESC` clears panel selection.

---

### Config

```bash
frxxv --dumpconfig
```

The default configuration file will be printed to the terminal. This file contains basic navigation information, like keybindings to switch products and search priority for specific products. This output can be redirected to a file with:

```bash
frxxv --dumpconfig > /path/to/frxxv_sample_config.json
```

After editing, frxx-view can be configured to read this file upon startup with:

```bash
frxxv --addconfig /path/to/frxxv_sample_config.json
```

---

### Further Usage

Frxx-view takes inspiration from vim. Pressing the `:` key opens a shell. `:help` prints all implemented commands. At this time, solo3 style manual dealiasing is supported via `:bnd` and `:fu COUNT` (forced unfolding). 

---

As a caveat, I haven't fully determined the exact dependencies for matplotlib, but I have been using matplotlib 3.10.9 and 3.11.1. Since standard matplotlib pcolormesh rendering is sequential and quite slow for radar data with many pixels, I rewrote the rendering in a multi-threaded C++ backend that is invisible to the Python frontend. Performance improvements are very significant, but I haven't tested which versions exactly are required. I do know that matplotlib 3.9.1 doesn't work, but it is possible that versions of matplotlib older than 3.10.9 are compatible.
