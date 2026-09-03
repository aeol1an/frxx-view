import struct
import re
import warnings
import numpy as np
import datetime

from .rle_decode_core import _rle_decode_core

class DoradeFile:
    def __init__(self, filename, endian="<"):
        if hasattr(filename, "read"):
            self.filename = None
            self._fh = filename
            self.buf = self._fh.read()
        else:
            self.filename = filename
            self._fh = None
            with open(filename, "rb") as fh:
                self.buf = fh.read()
        #self.endian = endian
        self.endian = self._detect_endian()

        self.blocks = []
        self.params = {}
        self.data = {}
        self.rays = []
        self.dist_cells = None
        self._block_records = []

        self._parse()

    def write(self, filename=None):
        """Write the current data fields to a DORADE file or file object."""
        if filename is None:
            filename = self.filename
        if filename is None:
            raise ValueError(
                "An output filename is required when the DORADE file was read "
                "from a file object"
            )

        rendered_blocks = []
        block_offsets = []
        offset = 0
        for record in self._block_records:
            block_offsets.append(offset)
            if record["id"] == b"RDAT":
                rendered = self._encode_rdat_block(record)
            else:
                rendered = record["raw"]
            rendered_blocks.append(rendered)
            offset += len(rendered)

        output = bytearray().join(rendered_blocks)
        def translate_offset(old_offset):
            if old_offset == len(self.buf):
                return len(output)
            for record, new_offset, rendered in zip(
                self._block_records, block_offsets, rendered_blocks
            ):
                relative = old_offset - record["offset"]
                if 0 <= relative < len(record["raw"]):
                    if relative <= len(rendered):
                        return new_offset + relative
                    break
            return old_offset

        for record, new_offset in zip(self._block_records, block_offsets):
            if record["id"] == b"SSWB":
                struct.pack_into(
                    self.endian + "i",
                    output,
                    new_offset + _structure_field_offset(SSWB_BLOCK, "sizeof_file"),
                    len(output),
                )
                for index in range(8):
                    field = f"key_table_{index}_offset"
                    field_offset = (
                        new_offset + _structure_field_offset(SSWB_BLOCK, field)
                    )
                    old_offset = struct.unpack_from(
                        self.endian + "i", output, field_offset
                    )[0]
                    if old_offset > 0:
                        struct.pack_into(
                            self.endian + "i",
                            output,
                            field_offset,
                            translate_offset(old_offset),
                        )

            if record["id"] != b"RKTB":
                continue
            first_key_field = (
                new_offset + _structure_field_offset(RKTB_BLOCK, "first_key_offset")
            )
            num_rays_field = (
                new_offset + _structure_field_offset(RKTB_BLOCK, "num_rays")
            )
            first_key_offset = struct.unpack_from(
                self.endian + "i", output, first_key_field
            )[0]
            table_num_rays = struct.unpack_from(
                self.endian + "i", output, num_rays_field
            )[0]
            for index in range(table_num_rays):
                entry_offset = (
                    new_offset
                    + first_key_offset
                    + index * _structure_size(ROT_TABLE_ENTRY, self.endian)
                )
                if entry_offset + _structure_size(ROT_TABLE_ENTRY) > len(output):
                    raise RuntimeError("RKTB angle table extends beyond the file")
                ray_offset_field = entry_offset + _structure_field_offset(
                    ROT_TABLE_ENTRY, "offset"
                )
                ray_size_field = entry_offset + _structure_field_offset(
                    ROT_TABLE_ENTRY, "size"
                )
                old_ray_offset = struct.unpack_from(
                    self.endian + "i", output, ray_offset_field
                )[0]
                old_ray_size = struct.unpack_from(
                    self.endian + "i", output, ray_size_field
                )[0]
                new_ray_offset = translate_offset(old_ray_offset)
                new_ray_end = translate_offset(old_ray_offset + old_ray_size)
                struct.pack_into(
                    self.endian + "i", output, ray_offset_field, new_ray_offset
                )
                struct.pack_into(
                    self.endian + "i",
                    output,
                    ray_size_field,
                    new_ray_end - new_ray_offset,
                )

        if hasattr(filename, "write"):
            filename.write(output)
        else:
            with open(filename, "wb") as fh:
                fh.write(output)

    def _encode_rdat_block(self, record):
        product_name = record["product_name"]
        data = self.data.get(product_name)
        if not isinstance(data, np.ndarray):
            raise TypeError(f"Data field {product_name!r} must be a numpy array")
        if data.dtype != np.float32:
            raise TypeError(f"Data field {product_name!r} must have dtype float32")
        if data.ndim != 2 or data.shape != self._field_shapes[product_name]:
            raise ValueError(
                f"Data field {product_name!r} must have shape "
                f"{self._field_shapes[product_name]}"
            )

        values = data[record["ray_index"], :record["gate_count"]]
        parm = self.params[product_name]
        scale = np.float32(parm["parameter_scale"])
        bias = np.float32(parm["parameter_bias"])
        bad_data = int(parm["bad_data"])
        if scale == 0:
            raise ValueError(f"Data field {product_name!r} has a zero scale")
        if not np.iinfo(np.int16).min <= bad_data <= np.iinfo(np.int16).max:
            raise ValueError(
                f"Data field {product_name!r} has a bad-data value outside int16"
            )

        finite = np.isfinite(values)
        encoded_values = np.full(values.shape, bad_data, dtype=np.int16)
        if np.any(finite):
            scaled = np.rint(values[finite] * scale + bias)
            limits = np.iinfo(np.int16)
            if np.any((scaled < limits.min) | (scaled > limits.max)):
                raise ValueError(
                    f"Data field {product_name!r} contains values outside its "
                    "int16 encoding range"
                )
            collides_with_missing = scaled == bad_data
            if self.compression == 1:
                collides_with_missing |= scaled == -32768
            if np.any(collides_with_missing):
                raise ValueError(
                    f"Data field {product_name!r} contains a finite value that "
                    "encodes as its missing-data value"
                )
            encoded_values[finite] = scaled.astype(np.int16)

        if self.compression == 1:
            payload = self._rle_encode_row(encoded_values)
        else:
            payload = encoded_values.astype(self.endian + "i2", copy=False).tobytes()

        offset_to_data = record["offset_to_data"]
        block = bytearray(record["raw"][:offset_to_data])
        block.extend(payload)
        struct.pack_into(self.endian + "i", block, 4, len(block))
        return bytes(block)

    def _rle_encode_row(self, data):
        data = np.asarray(data, dtype=np.int16)
        data_u16 = data.view(np.uint16)
        words = []
        i = 0
        n_words = len(data)

        while i < n_words:
            if data[i] == -32768 and i + 1 < n_words and data[i + 1] == -32768:
                end = i + 2
                while end < n_words and data[end] == -32768 and end - i < 0x7FFF:
                    end += 1
                words.append(end - i)
                i = end
                if i < n_words and data[i] == -32768:
                    words.append(0x8001)
                    words.append(data_u16[i])
                    i += 1
                continue

            end = i + 1
            while end < n_words and end - i < 0x7FFF:
                if (
                    data[end] == -32768
                    and end + 1 < n_words
                    and data[end + 1] == -32768
                ):
                    break
                end += 1
            words.append(0x8000 | (end - i))
            words.extend(data_u16[i:end])
            i = end

        words.append(1)
        if len(words) % 2:
            words.append(0)
        return np.asarray(words, dtype=np.uint16).astype(
            self.endian + "u2", copy=False
        ).tobytes()

    def _detect_endian(self):
        buf = self.buf
        block_id = buf[0:4]
        nbytes_le = struct.unpack("<i", buf[4:8])[0]
        nbytes_be = struct.unpack(">i", buf[4:8])[0]
        file_len = len(buf)
        le_ok = 0 < nbytes_le < file_len
        be_ok = 0 < nbytes_be < file_len
        if le_ok and not be_ok:
            return "<"
        elif be_ok and not le_ok:
            return ">"
        elif be_ok and le_ok:
            if block_id in BLOCK_MAP:
                return ">"
            else:
                return "<"
        else:
            raise RuntimeError("Cannot determine endian (both invalid)")


    def _parse(self):
        pos = 0
        buf = self.buf
        current_ray_index = None
        field_rows = {}
        while pos < len(buf):
            if len(buf) - pos < 8:
                raise RuntimeError(f"Truncated DORADE block header at offset {pos}")
            block_id = buf[pos:pos+4]
            nbytes = struct.unpack_from(self.endian + "i", buf, pos + 4)[0]
            if nbytes < 8 or pos + nbytes > len(buf):
                raise RuntimeError(
                    f"Invalid DORADE block length {nbytes} at offset {pos}"
                )
            record = {
                "id": block_id,
                "offset": pos,
                "raw": bytes(buf[pos:pos+nbytes]),
            }

            if block_id == b"PARM":
                block = read_parm_block(buf, pos, self.endian)
                name = block["parameter_name"].decode(errors="ignore").strip("\x00").strip()
                self.params[name] = block

            elif block_id == b"RYIB":
                block = _unpack_from_buf(buf, pos, RYIB_BLOCK, self.endian)
                current_ray = {
                    "azimuth": block["azimuth"],
                    "elevation": block["elevation"],
                    "status": block["ray_status"],
                    "julian_day": block["julian_day"],
                    "hour": block["hour"],
                    "minute": block["minute"],
                    "second": block["second"],
                    "millisecond": block["millisecond"],
                }
                self.rays.append(current_ray)
                current_ray_index = len(self.rays) - 1

            elif block_id == b"RADD":
                block = _unpack_from_buf(buf, pos, RADD_BLOCK, self.endian)
                self.instrument_name = block["radar_name"].decode(errors="ignore").strip("\x00").strip()
                self.compression = block["data_compress"]
                self.lat = block["radar_latitude"]
                self.lon = block["radar_longitude"]
                self.alt = block["radar_altitude"] * 1000 # this is in km
                self.frequency = block["freq1"] # freq1 is always the usual frequency block with the true value, when working with DORADE data
                self._radd_freq1 = block["freq1"]
                self._radd_freq2 = block["freq2"]
                self._radd_freq3 = block["freq3"]
                self._radd_freq4 = block["freq4"]
                self._radd_freq5 = block["freq5"]
                self.sweep_mode = _sweep_mode(block["scan_mode"])
                self.nyquist_velocity = block["eff_unamb_vel"]
                self.unambiguous_range = block["eff_unamb_range"]
                self._radd_num_freq = block["num_freq_trans"]
                self._radd_num_ipps = block["num_ipps_trans"]
                self._radd_prt1 = block["prt1"]
                self._radd_prt2 = block["prt2"]
                self._radd_prt3 = block["prt3"]
                self._radd_prt4 = block["prt4"]
                self._radd_prt5 = block["prt5"]

            elif block_id == b"RDAT":
                if current_ray_index is None:
                    raise RuntimeError(
                        f"RDAT block at offset {pos} appears before its RYIB block"
                    )
                block = _unpack_from_buf(buf, pos, RDAT_BLOCK, self.endian)
                min_offset = struct.calcsize(self.endian + "4si8s")  # 16
                product_name = block["pdata_name"].decode(errors="ignore").strip("\x00").strip()
                data_length = block["nbytes"]
                parm = self.params.get(product_name)
                if parm is None:
                    raise RuntimeError(
                        f"RDAT product {product_name!r} has no PARM definition"
                    )

                # Prefer the PARM block's offset_to_data when available
                # (newer 216-byte PARM blocks carry it); older 104-byte
                # PARM blocks don't have the field, and some files leave
                # it at 0, so fall back to the fixed RDAT header size in
                # that case. This mirrors lrose-core's DoradeRadxFile::
                # _handleField16, which does the same min-clamp.
                offset_to_data = min_offset
                if "offset_to_data" in parm:
                    parm_offset = int(parm["offset_to_data"])
                    if parm_offset >= min_offset:
                        offset_to_data = parm_offset

                raw = buf[pos + offset_to_data : pos + data_length]
                data = np.frombuffer(raw, dtype=self.endian + "i2")

                if self.compression == 1:  # COMPRESSION_HRD
                    if hasattr(self, "dist_cells") and self.dist_cells is not None:
                        ngates = len(self.dist_cells)
                    elif product_name in self.params and "number_cells" in self.params[product_name]:
                        ngates = self.params[product_name]["number_cells"]
                    else:
                        raise RuntimeError(f"Cannot determine ngates for compressed param '{product_name}'")
                    data = self._rle_decode_row(data, ngates)

                raw_data = data.astype(np.int16, copy=False)
                scale = np.float32(parm["parameter_scale"])
                bias = np.float32(parm["parameter_bias"])
                bad_data = int(parm["bad_data"])
                if scale == 0:
                    raise RuntimeError(f"DORADE product {product_name!r} has a zero scale")
                data = np.full(raw_data.shape, np.nan, dtype=np.float32)
                valid = raw_data != bad_data
                if self.compression == 1:
                    valid &= raw_data != -32768
                data[valid] = (
                    raw_data[valid].astype(np.float32) - bias
                ) / scale
                field_rows.setdefault(product_name, {})[current_ray_index] = data
                record.update({
                    "product_name": product_name,
                    "ray_index": current_ray_index,
                    "gate_count": len(data),
                    "offset_to_data": offset_to_data,
                })

            elif block_id == b"SSWB":
                block = _unpack_from_buf(buf, pos, SSWB_BLOCK, self.endian)
                self.sweep_start_time = datetime.datetime.fromtimestamp(block["start_time"], tz=datetime.timezone.utc).replace(tzinfo=None)
                self.sweep_stop_time = datetime.datetime.fromtimestamp(block["stop_time"], tz=datetime.timezone.utc).replace(tzinfo=None)

            elif block_id == b"VOLD":
                block = _unpack_from_buf(buf, pos, VOLD_BLOCK, self.endian)
                self.volume_number = block["volume_num"]
                try:
                    self.volume_datetime = datetime.datetime(
                        block["year"],
                        block["month"],
                        block["day"],
                        block["data_set_hour"],
                        block["data_set_minute"],
                        block["data_set_second"],
                    )
                except ValueError:
                    self.volume_datetime = None
                
            elif block_id == b"SWIB":
                block = _unpack_from_buf(buf, pos, SWIB_BLOCK, self.endian)
                self.sweep_number = block["sweep_num"]
                self.fixed_angle = block["fixed_angle"]
                self.num_rays = block["num_rays"]

            elif block_id == b"CELV":
                block = _unpack_from_buf(buf, pos, CELV_BLOCK, self.endian)
                ncells = block["number_cells"]
                raw_dist = block["dist_cells"][:ncells * 4]
                self.dist_cells = np.frombuffer(raw_dist, dtype=self.endian + "f4").copy()

            elif block_id == b"CSFD":
                block = _unpack_from_buf(buf, pos, CSFD_BLOCK, self.endian)
                num_segments = block["num_segments"]
                dist_to_first = block["dist_to_first"]
                spacing = np.frombuffer(
                    block["spacing"], dtype=self.endian + "f4"
                )[:num_segments]
                num_cells = np.frombuffer(
                    block["num_cells"], dtype=self.endian + "i2"
                )[:num_segments]

                segments = []
                r = float(dist_to_first)
                for seg_spacing, seg_ncells in zip(spacing, num_cells):
                    seg_spacing = float(seg_spacing)
                    seg_ncells = int(seg_ncells)
                    if seg_ncells <= 0:
                        continue
                    seg_ranges = r + np.arange(seg_ncells, dtype="float32") * seg_spacing
                    segments.append(seg_ranges)
                    r += seg_ncells * seg_spacing

                if segments and self.dist_cells is None:
                    self.dist_cells = np.concatenate(segments)

            elif block_id in BLOCK_MAP:
                block_def = BLOCK_MAP[block_id]
                block = _unpack_from_buf(buf, pos, block_def, self.endian)
                self.blocks.append((block_id, block))

            self._block_records.append(record)
            pos += nbytes

        self._finalize_data(field_rows)

    def _finalize_data(self, field_rows):
        self._field_shapes = {}
        for product_name, rows in field_rows.items():
            gate_count = max(len(row) for row in rows.values())
            data = np.full(
                (len(self.rays), gate_count),
                np.nan,
                dtype=np.float32,
            )
            for ray_index, row in rows.items():
                data[ray_index, :len(row)] = row
            self.data[product_name] = data
            self._field_shapes[product_name] = data.shape

    def get_param(self, name):
        return self.params.get(name)
    
    def _rle_decode_row(self, data_comp, ngates):
        """Decompress one ray's MIT/HRD run-length-encoded 16-bit field
        data. Ported from lrose-core's DoradeData::decompressHrd16
        (DoradeData.cc):

          - a count word's low 15 bits (MASK15 = 0x7fff) give a run
            length
          - if the high bit (SIGN16 = 0x8000) is set, the run is
            literal data: that many words immediately follow and are
            copied verbatim
          - if the high bit is clear, the run is a run of bad/missing
            gates: no data words follow, just fill with the bad value
          - a count word of 0 or 1 ends the row
          - two bad-data runs in a row (with no literal run between
            them) is used as an alternate termination flag

        `data_comp` carries this file's byte order (self.endian) in its
        dtype. We need that converted to native order before treating
        it as plain integers; `.astype()` does that conversion
        correctly, unlike `.view()`, which only reinterprets the
        existing bytes and silently produces garbage when the source
        byte order doesn't match the host's.
        """
        comp = data_comp.astype(np.uint16)

        comp_i16 = comp.view(np.int16)
        out, j_reached = _rle_decode_core(comp, comp_i16, ngates)
        if j_reached == 0:
            warnings.warn(
                f"RLE decode produced no gates (ngates={ngates}, "
                f"words={len(comp)}); filling this ray with bad/missing data.",
                RuntimeWarning,
            )
        return out
    
    def get_sweep(self, param_name):
        parm = self.params.get(param_name)
        if parm is None:
            raise KeyError(f"Product '{param_name}' not found")
        data_arr = self.data.get(param_name)
        if data_arr is None:
            raise KeyError(f"Product '{param_name}' has no data")
        ngates = data_arr.shape[1]

        if "meters_to_first_cell" in parm and parm["meters_to_first_cell"] != 0:
            r0      = parm["meters_to_first_cell"]
            spacing = parm["meters_between_cells"]
        elif hasattr(self, "dist_cells") and self.dist_cells is not None:
            r0      = self.dist_cells[0]
            spacing = self.dist_cells[1] - self.dist_cells[0]
        else:
            raise RuntimeError("No range information available")

        ranges = r0 + np.arange(ngates) * spacing

        return {
            "azimuth":    np.asarray(
                [ray["azimuth"] for ray in self.rays], dtype=np.float32
            ),
            "elevation":  np.asarray(
                [ray["elevation"] for ray in self.rays], dtype=np.float32
            ),
            "data":       data_arr,
            "range":      ranges,
            "radar_name": self.instrument_name,
            "start_time": self.sweep_start_time,
            "stop_time":  self.sweep_stop_time,
        }

def read_parm_block(buf, pos, endian="<"):
    header = struct.unpack(endian + "4s i", buf[pos:pos+8])
    block_id, nbytes = header

    if block_id != b"PARM":
        raise ValueError("Not a PARM block")

    if nbytes == 104:
        block_def = PARM_BLOCK_104
    elif nbytes == 216:
        block_def = PARM_BLOCK_216
    else:
        raise ValueError(f"Unknown PARM size: {nbytes}")

    return _unpack_from_buf(buf, pos, block_def, endian)

def _sweep_mode(value):
    return {
        0: "Cal",
        1: "PPI",
        2: "Coplane",
        3: "RHI",
        4: "Vertical",
        5: "Target",
        6: "Manual",
        7: "Idle",
        8: "PPI",
    }[value]

def _ray_status(value):
    return {
        0: "normal",
        1: "transition",
        2: "bad",
    }[value]

def _structure_size(structure, endian=">"):
    return struct.calcsize(endian + "".join([i[1] for i in structure]))


def _structure_field_offset(structure, field_name, endian=">"):
    formats = []
    for name, fmt in structure:
        if name == field_name:
            return struct.calcsize(endian + "".join(formats))
        formats.append(fmt)
    raise KeyError(field_name)


def _unpack_from_buf(buf, pos, structure, endian=">"):
    size = _structure_size(structure, endian)
    return _unpack_structure(buf[pos : pos + size], structure, endian)


def _unpack_structure(string, structure, endian=">"):
    fmt = endian + "".join([i[1] for i in structure])
    lst = struct.unpack(fmt, string)
    return dict(zip([i[0] for i in structure], lst))

BYTE = "B"
INT1 = "B"
INT2 = "H"
INT4 = "I"
REAL4 = "f"
REAL8 = "d"
SINT1 = "b"
SINT2 = "h"
SINT4 = "i"

# below claude did the block organizing, saved me a lot of time

# ── SSWB  (196 bytes) ────────────────────────────────────────────────────────
SSWB_BLOCK = (
    ("id",                   "4s"),
    ("nbytes",               SINT4),
    ("last_used",            SINT4),   # Unix time; 0 = never age off
    ("start_time",           SINT4),   # Unix time
    ("stop_time",            SINT4),   # Unix time
    ("sizeof_file",          SINT4),
    ("compression_flag",     SINT4),
    ("volume_time_stamp",    SINT4),
    ("num_params",           SINT4),
    ("radar_name",           "8s"),
    ("d_start_time",         REAL8),   # high-precision volume start
    ("d_stop_time",          REAL8),   # high-precision volume stop
    ("version_num",          SINT4),
    ("num_key_tables",       SINT4),
    ("status",               SINT4),
    ("place_holder",         "28s"),   # 7 × si32 unused
    # key_table[0]
    ("key_table_0_offset",   SINT4),
    ("key_table_0_size",     SINT4),
    ("key_table_0_type",     SINT4),
    # key_table[1]
    ("key_table_1_offset",   SINT4),
    ("key_table_1_size",     SINT4),
    ("key_table_1_type",     SINT4),
    # key_table[2]
    ("key_table_2_offset",   SINT4),
    ("key_table_2_size",     SINT4),
    ("key_table_2_type",     SINT4),
    # key_table[3]
    ("key_table_3_offset",   SINT4),
    ("key_table_3_size",     SINT4),
    ("key_table_3_type",     SINT4),
    # key_table[4]
    ("key_table_4_offset",   SINT4),
    ("key_table_4_size",     SINT4),
    ("key_table_4_type",     SINT4),
    # key_table[5]
    ("key_table_5_offset",   SINT4),
    ("key_table_5_size",     SINT4),
    ("key_table_5_type",     SINT4),
    # key_table[6]
    ("key_table_6_offset",   SINT4),
    ("key_table_6_size",     SINT4),
    ("key_table_6_type",     SINT4),
    # key_table[7]
    ("key_table_7_offset",   SINT4),
    ("key_table_7_size",     SINT4),
    ("key_table_7_type",     SINT4),
)

# ── COMM  (508 bytes) ────────────────────────────────────────────────────────
COMM_BLOCK = (
    ("id",      "4s"),
    ("nbytes",  SINT4),
    ("comment", "500s"),
)

# ── VOLD  (72 bytes) ─────────────────────────────────────────────────────────
VOLD_BLOCK = (
    ("id",                "4s"),
    ("nbytes",            SINT4),
    ("format_version",    SINT2),
    ("volume_num",        SINT2),
    ("maximum_bytes",     SINT4),
    ("proj_name",         "20s"),
    ("year",              SINT2),
    ("month",             SINT2),
    ("day",               SINT2),
    ("data_set_hour",     SINT2),
    ("data_set_minute",   SINT2),
    ("data_set_second",   SINT2),
    ("flight_num",        "8s"),
    ("gen_facility",      "8s"),
    ("gen_year",          SINT2),
    ("gen_month",         SINT2),
    ("gen_day",           SINT2),
    ("number_sensor_des", SINT2),
)

# ── RADD  (300 bytes) ────────────────────────────────────────────────────────
RADD_BLOCK = (
    ("id",                    "4s"),
    ("nbytes",                SINT4),
    ("radar_name",            "8s"),
    ("radar_const",           REAL4),
    ("peak_power",            REAL4),
    ("noise_power",           REAL4),
    ("receiver_gain",         REAL4),
    ("antenna_gain",          REAL4),
    ("system_gain",           REAL4),
    ("horz_beam_width",       REAL4),
    ("vert_beam_width",       REAL4),
    ("radar_type",            SINT2),
    ("scan_mode",             SINT2),
    ("req_rotat_vel",         REAL4),
    ("scan_mode_pram0",       REAL4),
    ("scan_mode_pram1",       REAL4),
    ("num_parameter_des",     SINT2),
    ("total_num_des",         SINT2),
    ("data_compress",         SINT2),
    ("data_reduction",        SINT2),
    ("data_red_parm0",        REAL4),
    ("data_red_parm1",        REAL4),
    ("radar_longitude",       REAL4),
    ("radar_latitude",        REAL4),
    ("radar_altitude",        REAL4),
    ("eff_unamb_vel",         REAL4),
    ("eff_unamb_range",       REAL4),
    ("num_freq_trans",        SINT2),
    ("num_ipps_trans",        SINT2),
    ("freq1",                 REAL4),
    ("freq2",                 REAL4),
    ("freq3",                 REAL4),
    ("freq4",                 REAL4),
    ("freq5",                 REAL4),
    ("prt1",                  REAL4),
    ("prt2",                  REAL4),
    ("prt3",                  REAL4),
    ("prt4",                  REAL4),
    ("prt5",                  REAL4),
)

# ── CFAC  (72 bytes) ─────────────────────────────────────────────────────────
CFAC_BLOCK = (
    ("id",                "4s"),
    ("nbytes",            SINT4),
    ("azimuth_corr",      REAL4),
    ("elevation_corr",    REAL4),
    ("range_delay_corr",  REAL4),
    ("longitude_corr",    REAL4),
    ("latitude_corr",     REAL4),
    ("pressure_alt_corr", REAL4),
    ("radar_alt_corr",    REAL4),
    ("ew_gndspd_corr",    REAL4),
    ("ns_gndspd_corr",    REAL4),
    ("vert_vel_corr",     REAL4),
    ("heading_corr",      REAL4),
    ("roll_corr",         REAL4),
    ("pitch_corr",        REAL4),
    ("drift_corr",        REAL4),
    ("rot_angle_corr",    REAL4),
    ("tilt_corr",         REAL4),
)

PARM_BLOCK_104 = (
    ("id",                    "4s"),
    ("nbytes",                SINT4),
    ("parameter_name",        "8s"),
    ("param_description",     "40s"),
    ("param_units",           "8s"),
    ("interpulse_time",       SINT2),
    ("xmitted_freq",          SINT2),
    ("recvr_bandwidth",       REAL4),
    ("pulse_width",           SINT2),
    ("polarization",          SINT2),
    ("num_samples",           SINT2),
    ("binary_format",         SINT2),
    ("threshold_field",       "8s"),
    ("threshold_value",       REAL4),
    ("parameter_scale",       REAL4),
    ("parameter_bias",        REAL4),
    ("bad_data",              SINT4),
)

PARM_BLOCK_216 = (
    ("id",                    "4s"),
    ("nbytes",                SINT4),
    ("parameter_name",        "8s"),
    ("param_description",     "40s"),
    ("param_units",           "8s"),
    ("interpulse_time",       SINT2),
    ("xmitted_freq",          SINT2),
    ("recvr_bandwidth",       REAL4),
    ("pulse_width",           SINT2),
    ("polarization",          SINT2),
    ("num_samples",           SINT2),
    ("binary_format",         SINT2),
    ("threshold_field",       "8s"),
    ("threshold_value",       REAL4),
    ("parameter_scale",       REAL4),
    ("parameter_bias",        REAL4),
    ("bad_data",              SINT4),
    ("extension_num",         SINT4),
    ("config_name",           "8s"),
    ("config_num",            SINT4),
    ("offset_to_data",        SINT4),
    ("mks_conversion",        REAL4),
    ("num_qnames",            SINT4),
    ("qdata_names",           "32s"),
    ("num_criteria",          SINT4),
    ("criteria_names",        "32s"),
    ("number_cells",          SINT4),
    ("meters_to_first_cell",  REAL4),
    ("meters_between_cells",  REAL4),
    ("eff_unamb_vel",         REAL4),
)

# ── CELV  (6012 bytes) ───────────────────────────────────────────────────────
CELV_BLOCK = (
    ("id",           "4s"),
    ("nbytes",       SINT4),
    ("number_cells", SINT4),
    ("dist_cells",   "6000s"),  # fl32[1500] — parse separately
)

# ── CSFD  (64 bytes) ─────────────────────────────────────────────────────────
CSFD_BLOCK = (
    ("id",            "4s"),
    ("nbytes",        SINT4),
    ("num_segments",  SINT4),
    ("dist_to_first", REAL4),
    ("spacing",       "32s"),   # fl32[8]
    ("num_cells",     "16s"),   # si16[8]
)

# ── SWIB  (40 bytes) ─────────────────────────────────────────────────────────
SWIB_BLOCK = (
    ("id",          "4s"),
    ("nbytes",      SINT4),
    ("radar_name",  "8s"),
    ("sweep_num",   SINT4),
    ("num_rays",    SINT4),
    ("start_angle", REAL4),
    ("stop_angle",  REAL4),
    ("fixed_angle", REAL4),
    ("filter_flag", SINT4),
)

# ── ASIB  (80 bytes) ─────────────────────────────────────────────────────────
ASIB_BLOCK = (
    ("id",              "4s"),
    ("nbytes",          SINT4),
    ("longitude",       REAL4),
    ("latitude",        REAL4),
    ("altitude_msl",    REAL4),
    ("altitude_agl",    REAL4),
    ("ew_velocity",     REAL4),
    ("ns_velocity",     REAL4),
    ("vert_velocity",   REAL4),
    ("heading",         REAL4),
    ("roll",            REAL4),
    ("pitch",           REAL4),
    ("drift_angle",     REAL4),
    ("rotation_angle",  REAL4),
    ("tilt",            REAL4),
    ("ew_horiz_wind",   REAL4),
    ("ns_horiz_wind",   REAL4),
    ("vert_wind",       REAL4),
    ("heading_change",  REAL4),
    ("pitch_change",    REAL4),
)

# ── RYIB  (44 bytes) ─────────────────────────────────────────────────────────
RYIB_BLOCK = (
    ("id",             "4s"),
    ("nbytes",         SINT4),
    ("sweep_num",      SINT4),
    ("julian_day",     SINT4),
    ("hour",           SINT2),
    ("minute",         SINT2),
    ("second",         SINT2),
    ("millisecond",    SINT2),
    ("azimuth",        REAL4),
    ("elevation",      REAL4),
    ("peak_power",     REAL4),
    ("true_scan_rate", REAL4),
    ("ray_status",     SINT4),
)

# ── RDAT  (16 bytes header; field data follows) ──────────────────────────────
RDAT_BLOCK = (
    ("id",         "4s"),
    ("nbytes",     SINT4),
    ("pdata_name", "8s"),
)

# ── QDAT  (56 bytes header; field data follows) ──────────────────────────────
QDAT_BLOCK = (
    ("id",              "4s"),
    ("nbytes",          SINT4),
    ("pdata_name",      "8s"),
    ("extension_num",   SINT4),
    ("config_num",      SINT4),
    ("first_cell",      "8s"),   # si16[4]
    ("num_cells",       "8s"),   # si16[4]
    ("criteria_value",  "16s"),  # fl32[4]
)

# ── XSTF  (24 bytes) ─────────────────────────────────────────────────────────
XSTF_BLOCK = (
    ("id",                  "4s"),
    ("nbytes",              SINT4),
    ("one",                 SINT4),   # always 1 (endian flag)
    ("source_format",       SINT4),
    ("offset_to_first_item", SINT4),
    ("transition_flag",     SINT4),
)

# ── NULL  (8 bytes) ──────────────────────────────────────────────────────────
NULL_BLOCK = (
    ("id",     "4s"),
    ("nbytes", SINT4),
)

# ── RKTB  (28 bytes header) ──────────────────────────────────────────────────
RKTB_BLOCK = (
    ("id",                  "4s"),
    ("nbytes",              SINT4),
    ("angle2ndx",           REAL4),   # 360.0 / ndx_que_size
    ("ndx_que_size",        SINT4),
    ("first_key_offset",    SINT4),
    ("angle_table_offset",  SINT4),
    ("num_rays",            SINT4),
)

# ── rot_table_entry  (12 bytes, repeated num_rays times after RKTB) ──────────
ROT_TABLE_ENTRY = (
    ("rotation_angle", REAL4),
    ("offset",         SINT4),
    ("size",           SINT4),
)

# ── FRAD  (52 bytes) ─────────────────────────────────────────────────────────
FRAD_BLOCK = (
    ("id",                "4s"),
    ("nbytes",            SINT4),
    ("data_sys_status",   SINT4),
    ("radar_name",        "8s"),
    ("test_pulse_level",  REAL4),
    ("test_pulse_dist",   REAL4),
    ("test_pulse_width",  REAL4),
    ("test_pulse_freq",   REAL4),
    ("test_pulse_atten",  SINT2),
    ("test_pulse_fnum",   SINT2),
    ("noise_power",       REAL4),
    ("ray_count",         SINT4),
    ("first_rec_gate",    SINT2),
    ("last_rec_gate",     SINT2),
)

# ── FRIB  (264 bytes) ────────────────────────────────────────────────────────
FRIB_BLOCK = (
    ("id",                      "4s"),
    ("nbytes",                  SINT4),
    ("data_sys_id",             SINT4),
    ("loss_out",                REAL4),
    ("loss_in",                 REAL4),
    ("loss_rjoint",             REAL4),
    ("ant_v_dim",               REAL4),
    ("ant_h_dim",               REAL4),
    ("ant_noise_temp",          REAL4),
    ("r_noise_figure",          REAL4),
    ("xmit_power",              "20s"),  # fl32[5]
    ("x_band_gain",             REAL4),
    ("receiver_gain",           "20s"),  # fl32[5]
    ("if_gain",                 "20s"),  # fl32[5]
    ("conversion_gain",         REAL4),
    ("scale_factor",            "20s"),  # fl32[5]
    ("processor_const",         REAL4),
    ("dly_tube_antenna",        SINT4),
    ("dly_rndtrip_chip_atod",   SINT4),
    ("dly_timmod_testpulse",    SINT4),
    ("dly_modulator_on",        SINT4),
    ("dly_modulator_off",       SINT4),
    ("peak_power_offset",       REAL4),
    ("test_pulse_offset",       REAL4),
    ("E_plane_angle",           REAL4),
    ("H_plane_angle",           REAL4),
    ("encoder_antenna_up",      REAL4),
    ("pitch_antenna_up",        REAL4),
    ("indepf_times_flg",        SINT2),
    ("indep_freq_gate",         SINT2),
    ("time_series_gate",        SINT2),
    ("num_base_params",         SINT2),
    ("file_name",               "80s"),
)

# ── LIDR  (148 bytes) ────────────────────────────────────────────────────────
LIDR_BLOCK = (
    ("id",                "4s"),
    ("nbytes",            SINT4),
    ("lidar_name",        "8s"),
    ("lidar_const",       REAL4),
    ("pulse_energy",      REAL4),
    ("peak_power",        REAL4),
    ("pulse_width",       REAL4),
    ("aperture_size",     REAL4),
    ("field_of_view",     REAL4),
    ("aperture_eff",      REAL4),
    ("beam_divergence",   REAL4),
    ("lidar_type",        SINT2),
    ("scan_mode",         SINT2),
    ("req_rotat_vel",     REAL4),
    ("scan_mode_pram0",   REAL4),
    ("scan_mode_pram1",   REAL4),
    ("num_parameter_des", SINT2),
    ("total_num_des",     SINT2),
    ("data_compress",     SINT2),
    ("data_reduction",    SINT2),
    ("data_red_parm0",    REAL4),
    ("data_red_parm1",    REAL4),
    ("lidar_longitude",   REAL4),
    ("lidar_latitude",    REAL4),
    ("lidar_altitude",    REAL4),
    ("eff_unamb_vel",     REAL4),
    ("eff_unamb_range",   REAL4),
    ("num_wvlen_trans",   SINT4),
    ("prf",               REAL4),
    ("wavelength",        "40s"),  # fl32[10]
)

# ── FLIB  (748 bytes) ────────────────────────────────────────────────────────
FLIB_BLOCK = (
    ("id",                  "4s"),
    ("nbytes",              SINT4),
    ("data_sys_id",         SINT4),
    ("transmit_beam_div",   "40s"),  # fl32[10]
    ("xmit_power",          "40s"),  # fl32[10]
    ("receiver_fov",        "40s"),  # fl32[10]
    ("receiver_type",       "40s"),  # si32[10]
    ("r_noise_floor",       "40s"),  # fl32[10]
    ("receiver_spec_bw",    "40s"),  # fl32[10]
    ("receiver_elec_bw",    "40s"),  # fl32[10]
    ("calibration",         "40s"),  # fl32[10]
    ("range_delay",         SINT4),
    ("peak_power_multi",    "40s"),  # fl32[10]
    ("encoder_mirror_up",   REAL4),
    ("pitch_mirror_up",     REAL4),
    ("max_digitizer_count", SINT4),
    ("max_digitizer_volt",  REAL4),
    ("digitizer_rate",      REAL4),
    ("total_num_samples",   SINT4),
    ("samples_per_cell",    SINT4),
    ("cells_per_ray",       SINT4),
    ("pmt_temp",            REAL4),
    ("pmt_gain",            REAL4),
    ("apd_temp",            REAL4),
    ("apd_gain",            REAL4),
    ("transect",            SINT4),
    ("derived_names",       "120s"),  # char[10][12]
    ("derived_units",       "80s"),   # char[10][8]
    ("temp_names",          "120s"),  # char[10][12]
)

# ── SITU  (4108 bytes) ───────────────────────────────────────────────────────
SITU_BLOCK = (
    ("id",            "4s"),
    ("nbytes",        SINT4),
    ("number_params", SINT4),
    ("params",        "4096s"),  # insitu_parameter_t[256]: name[8]+units[8] each
)

# ── ISIT  (16 bytes) ─────────────────────────────────────────────────────────
ISIT_BLOCK = (
    ("id",         "4s"),
    ("nbytes",     SINT4),
    ("julian_day", SINT2),
    ("hours",      SINT2),
    ("minutes",    SINT2),
    ("seconds",    SINT2),
)

# ── INDF  (8 bytes) ──────────────────────────────────────────────────────────
INDF_BLOCK = (
    ("id",     "4s"),
    ("nbytes", SINT4),
)

# ── MINI  (4112 bytes) ───────────────────────────────────────────────────────
MINI_BLOCK = (
    ("id",           "4s"),
    ("nbytes",       SINT4),
    ("command",      SINT2),
    ("status",       SINT2),
    ("temperature",  REAL4),
    ("x_axis_gyro",  "512s"),   # fl32[128]
    ("y_axis_gyro",  "512s"),   # fl32[128]
    ("z_axis_gyro",  "512s"),   # fl32[128]
    ("xr_axis_gyro", "512s"),   # fl32[128]
    ("x_axis_vel",   "512s"),   # fl32[128]
    ("y_axis_vel",   "512s"),   # fl32[128]
    ("z_axis_vel",   "512s"),   # fl32[128]
    ("x_axis_pos",   "512s"),   # fl32[128]
)

# ── NDDS  (16 bytes) ─────────────────────────────────────────────────────────
NDDS_BLOCK = (
    ("id",             "4s"),
    ("nbytes",         SINT4),
    ("ins_flag",       SINT2),
    ("gps_flag",       SINT2),
    ("minirims_flag",  SINT2),
    ("kalman_flag",    SINT2),
)

# ── TIME  (8 bytes) ──────────────────────────────────────────────────────────
TIME_BLOCK = (
    ("id",     "4s"),
    ("nbytes", SINT4),
)

# ── WAVE  (364 bytes) ────────────────────────────────────────────────────────
WAVE_BLOCK = (
    ("id",              "4s"),
    ("nbytes",          SINT4),
    ("ps_file_name",    "16s"),
    ("num_chips",       "12s"),   # si16[6]
    ("blank_chip",      "256s"),
    ("repeat_seq",      REAL4),
    ("repeat_seq_dwel", SINT2),
    ("total_pcp",       SINT2),
    ("chip_offset",     "12s"),   # si16[6]
    ("chip_width",      "12s"),   # si16[6]
    ("ur_pcp",          REAL4),
    ("uv_pcp",          REAL4),
    ("num_gates",       "12s"),   # si16[6]
    ("gate_dist1",      "4s"),    # si16[2]
    ("gate_dist2",      "4s"),    # si16[2]
    ("gate_dist3",      "4s"),    # si16[2]
    ("gate_dist4",      "4s"),    # si16[2]
    ("gate_dist5",      "4s"),    # si16[2]
)


# ── Helper: build a struct format string from a block definition ──────────────
def _block_fmt(block, big_endian=True):
    endian = ">" if big_endian else "<"
    return endian + "".join(fmt for _, fmt in block)


def _block_size(block):
    return struct.calcsize(_block_fmt(block))


def unpack_block(block_def, data, big_endian=True):
    """Unpack raw bytes into an OrderedDict using a block definition tuple."""
    fmt = _block_fmt(block_def, big_endian)
    size = struct.calcsize(fmt)
    values = struct.unpack(fmt, data[:size])
    return dict(zip((name for name, _ in block_def), values))


# ── Block-ID → definition map ────────────────────────────────────────────────
BLOCK_MAP = {
    b"COMM": COMM_BLOCK,
    b"SSWB": SSWB_BLOCK,
    b"VOLD": VOLD_BLOCK,
    b"RADD": RADD_BLOCK,
    b"CFAC": CFAC_BLOCK,
    b"CELV": CELV_BLOCK,
    b"CSFD": CSFD_BLOCK,
    b"SWIB": SWIB_BLOCK,
    b"ASIB": ASIB_BLOCK,
    b"RYIB": RYIB_BLOCK,
    b"RDAT": RDAT_BLOCK,
    b"QDAT": QDAT_BLOCK,
    b"XSTF": XSTF_BLOCK,
    b"NULL": NULL_BLOCK,
    b"RKTB": RKTB_BLOCK,
    b"FRAD": FRAD_BLOCK,
    b"FRIB": FRIB_BLOCK,
    b"LIDR": LIDR_BLOCK,
    b"FLIB": FLIB_BLOCK,
    b"SITU": SITU_BLOCK,
    b"ISIT": ISIT_BLOCK,
    b"INDF": INDF_BLOCK,
    b"MINI": MINI_BLOCK,
    b"NDDS": NDDS_BLOCK,
    b"TIME": TIME_BLOCK,
    b"WAVE": WAVE_BLOCK,
}
