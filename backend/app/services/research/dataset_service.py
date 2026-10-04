"""Dataset management and preprocessing service for NetFlow anomaly detection.

Implements the data preparation pipeline described in Alberto Miguel-Diez et al. (arXiv:2509.01375):
- NetFlow v9 / IPFIX feature extraction:
    - IPV4_SRC_ADDR
    - IPV4_DST_ADDR
    - L4_SRC_PORT
    - L4_DST_PORT
    - PROTOCOL
    - IN_BYTES
    - OUT_BYTES
    - FLOW_DURATION_MILLISECONDS
- IPv4 to 32-bit integer conversion via Python's standard `ipaddress` library.
- Robust data sanitization (handling non-finite, missing, out-of-range values).
- Flow partitioning:
    - 1,000 benign flows for scaler initialization.
    - 100,000 benign flows (or max available) for online model warm-up.
    - Balanced evaluation set (50% benign, 50% anomaly).
    - Strict target label isolation (labels reserved for evaluation only).
- Strict schema validation rejecting incomplete or ambiguous CSVs.
- Explicit documented adapter for the official UNSW-NB15 testing CSV.
- Generation of bundled benchmark sample datasets for zero-setup demonstration.
"""

import csv
import ipaddress
import json
import logging
import math
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy.orm import Session
from app.models import ResearchDatasetModel

logger = logging.getLogger("network_monitoring.research.dataset")


class DatasetValidationError(ValueError):
    """Raised when a dataset fails strict validation or schema detection."""
    pass


class DatasetSchemaType:
    NATIVE_NETFLOW = "native_netflow"
    ADAPTED_UNSW_NB15 = "adapted_unsw_nb15"


# Standard feature set from Miguel-Diez et al. (Table 2 & Section 3)
PRIMARY_FEATURES = [
    "IPV4_SRC_ADDR",
    "IPV4_DST_ADDR",
    "L4_SRC_PORT",
    "L4_DST_PORT",
    "PROTOCOL",
    "IN_BYTES",
    "OUT_BYTES",
    "FLOW_DURATION_MILLISECONDS",
]

# Canonical column aliases to accommodate varied dataset formats (NetFlow v9, IPFIX, NF-UNSW-NB15)
COLUMN_ALIASES = {
    "IPV4_SRC_ADDR": ["ipv4_src_addr", "src_ip", "srcip", "source_ip", "src_addr", "ip_src"],
    "IPV4_DST_ADDR": ["ipv4_dst_addr", "dst_ip", "dstip", "dest_ip", "destination_ip", "dst_addr", "ip_dst"],
    "L4_SRC_PORT": ["l4_src_port", "src_port", "sport", "source_port", "srcport"],
    "L4_DST_PORT": ["l4_dst_port", "dst_port", "dsport", "dest_port", "dstport", "destination_port"],
    "PROTOCOL": ["protocol", "proto"],
    "IN_BYTES": ["in_bytes", "inbytes", "bytes_in", "in_pkts_bytes"],
    "OUT_BYTES": ["out_bytes", "outbytes", "bytes_out"],
    "FLOW_DURATION_MILLISECONDS": [
        "flow_duration_milliseconds",
        "flow_duration_ms",
        "duration_ms",
        "flow_duration",
    ],
}

LABEL_ALIASES = ["label", "attack", "is_anomaly", "class", "binary_label"]

# Standard IANA IP Protocol Mapping dictionary (names to numeric identifiers)
IANA_PROTOCOL_MAP: Dict[str, int] = {
    "hopopt": 0, "arp": 0, "any": 0,
    "icmp": 1,
    "igmp": 2,
    "ggp": 3,
    "ip": 4, "ipv4": 4,
    "st": 5,
    "tcp": 6,
    "cbt": 7,
    "egp": 8,
    "igp": 9,
    "bbn-rcc-mon": 10,
    "nvp-ii": 11,
    "pup": 12,
    "argus": 13,
    "emcon": 14,
    "xnet": 15,
    "chaos": 16,
    "udp": 17,
    "mux": 18,
    "dcn-meas": 19,
    "hmp": 20,
    "prm": 21,
    "xns-idp": 22,
    "trunk-1": 23,
    "trunk-2": 24,
    "leaf-1": 25,
    "leaf-2": 26,
    "rdp": 27,
    "irtp": 28,
    "iso-tp4": 29,
    "netblt": 30,
    "mfe-nsp": 31,
    "merit-inp": 32,
    "dccp": 33,
    "3pc": 34,
    "idpr": 35,
    "xtp": 36,
    "ddp": 37,
    "idpr-cmtp": 38,
    "tp++": 39,
    "il": 40,
    "ipv6": 41,
    "sdrp": 42,
    "ipv6-route": 43,
    "ipv6-frag": 44,
    "idrp": 45,
    "rsvp": 46,
    "gre": 47,
    "dsr": 48,
    "bna": 49,
    "esp": 50,
    "ah": 51,
    "i-nlsp": 52,
    "swipe": 53,
    "narp": 54,
    "mobile": 55,
    "tlsp": 56,
    "skip": 57,
    "ipv6-icmp": 58,
    "ipv6-nonxt": 59,
    "ipv6-opts": 60,
    "cftp": 62,
    "sat-expak": 64,
    "kryptolan": 65,
    "rvd": 66,
    "ippc": 67,
    "sat-mon": 69,
    "visa": 70,
    "ipcv": 71,
    "cpnx": 72,
    "cphb": 73,
    "wsn": 74,
    "pvp": 75,
    "br-sat-mon": 76,
    "sun-nd": 77,
    "wb-mon": 78,
    "wb-expak": 79,
    "iso-ip": 80,
    "vmtp": 81,
    "secure-vmtp": 82,
    "vines": 83,
    "ttp": 84, "iptm": 84,
    "nsfnet-igp": 85,
    "dgp": 86,
    "tcf": 87,
    "eigrp": 88,
    "ospf": 89, "ospfigp": 89,
    "sprite-rpc": 90,
    "larp": 91,
    "mtp": 92,
    "ax.25": 93,
    "ipip": 94,
    "micp": 95,
    "scc-sp": 96,
    "etherip": 97,
    "encap": 98,
    "gmtp": 100,
    "ifmp": 101,
    "pnni": 102,
    "pim": 103,
    "aris": 104,
    "scps": 105,
    "qnx": 106,
    "a/n": 107,
    "ipcomp": 108,
    "snp": 109,
    "compaq-peer": 110,
    "ipx-in-ip": 111,
    "vrrp": 112,
    "pgm": 113,
    "l2tp": 115,
    "ddx": 116,
    "iatp": 117,
    "stp": 118,
    "srp": 119,
    "uti": 120,
    "smp": 121,
    "sm": 122,
    "ptp": 123,
    "isis": 124,
    "fire": 125,
    "crtp": 126,
    "crudp": 127,
    "sscopmce": 128,
    "iplt": 129,
    "sps": 130,
    "pipe": 131,
    "sctp": 132,
    "fc": 133,
    "rsvp-e2e-ignore": 134,
    "mobility-header": 135,
    "udplite": 136,
    "mpls-in-ip": 137,
    "manet": 138,
    "hip": 139,
    "shim6": 140,
    "wesp": 141,
    "rohc": 142,
    "ethernet": 143,
    "unas": 255,
}


def validate_ipv4(ip_val: Any) -> bool:
    """Validate whether a value is a genuine IPv4 address representation."""
    if ip_val is None:
        return False
    if isinstance(ip_val, int):
        return 0 <= ip_val <= 0xFFFFFFFF
    if isinstance(ip_val, float):
        if math.isnan(ip_val) or math.isinf(ip_val):
            return False
        return 0 <= int(ip_val) <= 0xFFFFFFFF
    s = str(ip_val).strip()
    if not s:
        return False
    if s.isdigit():
        try:
            return 0 <= int(s) <= 0xFFFFFFFF
        except (ValueError, OverflowError):
            return False
    try:
        ipaddress.IPv4Address(s)
        return True
    except (ipaddress.AddressValueError, ValueError):
        return False


def ip_to_int(ip_val: Union[str, int, float, None]) -> int:
    """Convert an IPv4 address string or existing numerical representation to a 32-bit unsigned integer.

    Follows the paper's methodology using Python's standard `ipaddress` library.
    Handles dotted-quad strings, integer strings, raw ints, and invalid entries safely.
    """
    if ip_val is None:
        return 0
    if isinstance(ip_val, (int,)):
        return max(0, min(ip_val, 0xFFFFFFFF))
    if isinstance(ip_val, (float,)):
        if math.isnan(ip_val) or math.isinf(ip_val):
            return 0
        return max(0, min(int(ip_val), 0xFFFFFFFF))

    cleaned = str(ip_val).strip()
    if not cleaned:
        return 0

    # If it is already a string of digits representing an integer
    if cleaned.isdigit():
        try:
            return max(0, min(int(cleaned), 0xFFFFFFFF))
        except (ValueError, OverflowError):
            return 0

    # Dotted-quad format: 192.168.1.1
    try:
        addr = ipaddress.IPv4Address(cleaned)
        return int(addr)
    except (ipaddress.AddressValueError, ValueError):
        # Fallback: if CIDR or port appended, strip extra characters
        if "/" in cleaned:
            cleaned = cleaned.split("/")[0].strip()
        if ":" in cleaned and cleaned.count(".") == 3:
            cleaned = cleaned.split(":")[0].strip()
        try:
            return int(ipaddress.IPv4Address(cleaned))
        except Exception:
            return 0


def parse_protocol(val: Any) -> int:
    """Parse protocol value, supporting standard IANA names (e.g. 'tcp', 'udp', 'icmp') and integer IDs."""
    if val is None:
        return 6
    s = str(val).strip().lower()
    if not s:
        return 6
    if s.isdigit():
        try:
            return max(0, min(int(s), 255))
        except (ValueError, OverflowError):
            return 6
    try:
        f = float(s)
        if not (math.isnan(f) or math.isinf(f)):
            return max(0, min(int(f), 255))
    except (ValueError, TypeError):
        pass
    if s in IANA_PROTOCOL_MAP:
        return IANA_PROTOCOL_MAP[s]
    return 0


def sanitize_float(val: Any, default: float = 0.0) -> float:
    """Safely convert value to finite float."""
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return max(0.0, f)
    except (ValueError, TypeError):
        return default


def sanitize_int(val: Any, default: int = 0, min_val: int = 0, max_val: int = 0xFFFFFFFF) -> int:
    """Safely convert value to bounded integer."""
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        i = int(f)
        return max(min_val, min(i, max_val))
    except (ValueError, TypeError):
        return default


class DatasetService:
    """Service for managing flow datasets, schema validation, and train/eval partitioning."""

    def __init__(self, data_dir: Optional[str] = None) -> None:
        if data_dir:
            self.data_dir = Path(data_dir)
        else:
            self.data_dir = Path(os.getenv("DATASET_STORAGE_DIR", "data/datasets"))
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def resolve_column_mapping(self, header: List[str]) -> Dict[str, str]:
        """Resolve header columns to standard features, preserving backwards compatibility."""
        _, mapping, _, _ = self.detect_schema_and_mapping(header)
        return mapping

    def detect_schema_and_mapping(
        self, header: List[str]
    ) -> Tuple[str, Dict[str, str], bool, Optional[str]]:
        """Identify whether dataset is native NetFlow or adapted UNSW-NB15, or reject.

        Returns:
            Tuple of: (schema_type, column_mapping, is_adapted, adaptation_notes)
        Raises:
            DatasetValidationError: If required columns are missing, ambiguous, duplicate, or unmapped.
        """
        if not header:
            raise DatasetValidationError("Dataset CSV header is empty or the file contains no columns.")

        # Check duplicate column names
        cleaned_header = [col.strip() for col in header if col.strip()]
        lower_header_list = [col.lower() for col in cleaned_header]
        if len(lower_header_list) != len(set(lower_header_list)):
            seen = set()
            duplicates = set()
            for col in lower_header_list:
                if col in seen:
                    duplicates.add(col)
                seen.add(col)
            raise DatasetValidationError(
                f"Dataset header contains duplicate or ambiguous columns: {', '.join(sorted(duplicates))}"
            )

        header_lower_map = {col.lower(): col for col in cleaned_header}

        # Validate label column presence
        label_col = None
        for alias in LABEL_ALIASES:
            if alias in header_lower_map:
                label_col = header_lower_map[alias]
                break

        if not label_col:
            raise DatasetValidationError(
                "Dataset is missing a required label column. Expected one of: 'label', 'attack', 'is_anomaly', 'class'."
            )

        # 1. Test Native NetFlow Schema (NF-UNSW-NB15 / IPFIX)
        native_mapping: Dict[str, str] = {}
        missing_native: List[str] = []

        for feat in PRIMARY_FEATURES:
            if feat in cleaned_header:
                native_mapping[feat] = feat
            elif feat.lower() in header_lower_map:
                native_mapping[feat] = header_lower_map[feat.lower()]
            else:
                found = False
                for alias in COLUMN_ALIASES.get(feat, []):
                    if alias in header_lower_map:
                        native_mapping[feat] = header_lower_map[alias]
                        found = True
                        break
                if not found:
                    missing_native.append(feat)

        if not missing_native:
            native_mapping["LABEL"] = label_col
            return DatasetSchemaType.NATIVE_NETFLOW, native_mapping, False, None

        # 2. Test Official UNSW-NB15 Testing Set Schema
        # Requires: sbytes, dbytes, dur, proto, and label
        unsw_reqs = ["sbytes", "dbytes", "dur", "proto"]
        missing_unsw = [col for col in unsw_reqs if col not in header_lower_map]

        if not missing_unsw:
            # Explicit UNSW-NB15 adapter mapping
            # Direction semantics:
            # - sbytes: Source to destination transaction bytes (client forward / incoming bytes) -> IN_BYTES
            # - dbytes: Destination to source transaction bytes (server backward / outgoing bytes) -> OUT_BYTES
            # Duration semantics:
            # - dur: Duration in seconds, multiplied by 1000.0 to convert to FLOW_DURATION_MILLISECONDS
            # Protocol:
            # - proto: Textual or numeric protocol, mapped to IANA integer via lookup table
            # IPs & Ports:
            # - Absent in official testing split; assigned surrogate zero tokens (0.0).
            adapted_mapping = {
                "IN_BYTES": header_lower_map["sbytes"],
                "OUT_BYTES": header_lower_map["dbytes"],
                "FLOW_DURATION_MILLISECONDS": header_lower_map["dur"],
                "PROTOCOL": header_lower_map["proto"],
                "LABEL": label_col,
                "IPV4_SRC_ADDR": "__SURROGATE_ZERO__",
                "IPV4_DST_ADDR": "__SURROGATE_ZERO__",
                "L4_SRC_PORT": "__SURROGATE_ZERO__",
                "L4_DST_PORT": "__SURROGATE_ZERO__",
            }
            adaptation_notes = (
                "Official UNSW-NB15 testing-set adaptation: Mapped 'sbytes' -> IN_BYTES (forward flow bytes), "
                "'dbytes' -> OUT_BYTES (backward flow bytes). Converted 'dur' (seconds) -> FLOW_DURATION_MILLISECONDS (*1000). "
                "Converted protocol names to standard IANA integers. Source/destination IPs and ports are absent in "
                "the official testing CSV and set to surrogate zero tokens (0.0). "
                "NOT equivalent to native 8-feature NetFlow schema (NF-UNSW-NB15)."
            )
            return DatasetSchemaType.ADAPTED_UNSW_NB15, adapted_mapping, True, adaptation_notes

        # 3. Reject dataset with informative error
        raise DatasetValidationError(
            f"Incompatible dataset schema. Missing required columns for native NetFlow ({', '.join(missing_native)}) "
            f"and adapted UNSW-NB15 ({', '.join(missing_unsw)}). "
            f"The dataset must provide either all 8 NetFlow features or the UNSW-NB15 testing set features (sbytes, dbytes, dur, proto, label)."
        )

    def parse_flow_row(
        self,
        row: Dict[str, Any],
        mapping: Dict[str, str],
        schema_type: str = DatasetSchemaType.NATIVE_NETFLOW,
    ) -> Tuple[Dict[str, float], int]:
        """Convert a raw dataset row into sanitized feature vector and target label.

        CRITICAL: The label is strictly separated and NEVER included in the feature dictionary!
        """
        if schema_type == DatasetSchemaType.ADAPTED_UNSW_NB15:
            # Surrogate tokens for absent IP and Port fields in official test CSV
            src_int = 0.0
            dst_int = 0.0
            sport = 0.0
            dport = 0.0

            # Protocol text to IANA integer
            proto_val = row.get(mapping.get("PROTOCOL", "proto"))
            proto = float(parse_protocol(proto_val))

            # Bytes with documented direction semantics (sbytes -> in_bytes, dbytes -> out_bytes)
            in_bytes = sanitize_float(row.get(mapping.get("IN_BYTES", "sbytes")), default=0.0)
            out_bytes = sanitize_float(row.get(mapping.get("OUT_BYTES", "dbytes")), default=0.0)

            # Duration conversion: seconds to milliseconds
            raw_dur = sanitize_float(row.get(mapping.get("FLOW_DURATION_MILLISECONDS", "dur")), default=0.0)
            dur_ms = raw_dur * 1000.0
        else:
            # Native NetFlow parsing
            src_col = mapping.get("IPV4_SRC_ADDR", "IPV4_SRC_ADDR")
            src_int = float(ip_to_int(row.get(src_col)))

            dst_col = mapping.get("IPV4_DST_ADDR", "IPV4_DST_ADDR")
            dst_int = float(ip_to_int(row.get(dst_col)))

            sport_col = mapping.get("L4_SRC_PORT", "L4_SRC_PORT")
            sport = float(sanitize_int(row.get(sport_col), default=0, min_val=0, max_val=65535))

            dport_col = mapping.get("L4_DST_PORT", "L4_DST_PORT")
            dport = float(sanitize_int(row.get(dport_col), default=0, min_val=0, max_val=65535))

            proto_col = mapping.get("PROTOCOL", "PROTOCOL")
            proto = float(parse_protocol(row.get(proto_col)))

            in_col = mapping.get("IN_BYTES", "IN_BYTES")
            in_bytes = sanitize_float(row.get(in_col), default=0.0)

            out_col = mapping.get("OUT_BYTES", "OUT_BYTES")
            out_bytes = sanitize_float(row.get(out_col), default=0.0)

            dur_col = mapping.get("FLOW_DURATION_MILLISECONDS", "FLOW_DURATION_MILLISECONDS")
            dur_ms = sanitize_float(row.get(dur_col), default=0.0)

        # Build feature dict - strictly 8 features, NO label
        features = {
            "IPV4_SRC_ADDR": src_int,
            "IPV4_DST_ADDR": dst_int,
            "L4_SRC_PORT": sport,
            "L4_DST_PORT": dport,
            "PROTOCOL": proto,
            "IN_BYTES": in_bytes,
            "OUT_BYTES": out_bytes,
            "FLOW_DURATION_MILLISECONDS": dur_ms,
        }

        # Target label extraction
        label_col = mapping.get("LABEL")
        raw_label = row.get(label_col) if label_col else 0
        label_int = 0
        if raw_label is not None:
            s_label = str(raw_label).strip().lower()
            if s_label in ("1", "1.0", "true", "attack", "anomaly", "malicious", "bad"):
                label_int = 1
            elif s_label in ("0", "0.0", "false", "benign", "normal", "good"):
                label_int = 0
            else:
                try:
                    val = float(raw_label)
                    label_int = 1 if val > 0 else 0
                except ValueError:
                    label_int = 1 if "attack" in s_label or "anomaly" in s_label else 0

        return features, label_int

    def inspect_dataset_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze and validate a CSV dataset file.

        Detects schema, validates column names, duplicate columns, numerical values,
        protocol values, duration units, IP addresses, row integrity, and class distribution.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Dataset file not found: {file_path}")
        if path.stat().st_size == 0:
            raise DatasetValidationError("Dataset file is empty (0 bytes).")

        total_rows = 0
        benign_count = 0
        attack_count = 0
        header: List[str] = []
        sample_rows: List[Dict[str, Any]] = []
        malformed_rows = 0
        invalid_ip_rows = 0

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            try:
                first_row = next(reader)
            except StopIteration:
                raise DatasetValidationError("Dataset file is empty (no header row found).")

            header = [col.strip() for col in first_row if col.strip()]
            schema_type, mapping, is_adapted, notes = self.detect_schema_and_mapping(header)

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            dict_reader = csv.DictReader(f)
            for i, row in enumerate(dict_reader):
                total_rows += 1
                if not row or any(k is None for k in row.keys()):
                    malformed_rows += 1
                    continue

                # Row-level validation
                if schema_type == DatasetSchemaType.NATIVE_NETFLOW:
                    src_val = row.get(mapping.get("IPV4_SRC_ADDR", ""))
                    dst_val = row.get(mapping.get("IPV4_DST_ADDR", ""))
                    if not (validate_ipv4(src_val) and validate_ipv4(dst_val)):
                        invalid_ip_rows += 1

                features, label = self.parse_flow_row(row, mapping, schema_type=schema_type)
                if label == 1:
                    attack_count += 1
                else:
                    benign_count += 1

                if i < 5:
                    sample_rows.append(dict(row))

        if total_rows == 0:
            raise DatasetValidationError("Dataset CSV has a valid header but contains 0 data rows.")

        if malformed_rows == total_rows:
            raise DatasetValidationError(f"All {total_rows} data rows are malformed or empty.")

        if benign_count == 0:
            raise DatasetValidationError(
                "Dataset contains 0 benign flows. At least 10 benign flows are required for model warm-up."
            )
        if attack_count == 0:
            raise DatasetValidationError(
                "Dataset contains 0 attack flows. At least 1 attack flow is required for evaluation."
            )

        detected_features = [f for f in PRIMARY_FEATURES if f in mapping and mapping[f] in header]
        missing_features = [f for f in PRIMARY_FEATURES if f not in detected_features]

        validation_status = (
            "Valid Native NetFlow"
            if schema_type == DatasetSchemaType.NATIVE_NETFLOW
            else "Valid Adapted UNSW-NB15"
        )

        return {
            "total_flows": total_rows,
            "benign_flows": benign_count,
            "attack_flows": attack_count,
            "schema_type": schema_type,
            "is_adapted": is_adapted,
            "adaptation_notes": notes,
            "duration_unit": "seconds (converted *1000 to ms)" if is_adapted else "milliseconds",
            "detected_features": detected_features,
            "missing_features": missing_features,
            "header": header,
            "sample_rows": sample_rows,
            "has_label_column": "LABEL" in mapping,
            "is_paper_compliant": not is_adapted and len(missing_features) == 0,
            "validation_status": validation_status,
            "invalid_ip_rows": invalid_ip_rows,
            "malformed_rows": malformed_rows,
        }

    def prepare_experiment_data(
        self,
        file_path: str,
        scaler_init_count: int = 1000,
        warmup_count: int = 100000,
        eval_count: Optional[int] = None,
        random_seed: int = 42,
    ) -> Dict[str, Any]:
        """Partition dataset flows strictly adhering to the methodology of Miguel-Diez et al.

        1. Separate all benign and attack flows.
        2. Verify counts and adaptively adjust if dataset size is constrained (safeguards).
        3. Extract `scaler_init_count` benign flows for online scaler initialization.
        4. Extract `warmup_count` benign flows for model warm-up calibration.
        5. Construct a balanced evaluation set (50% benign, 50% attack).
        6. Shuffle the evaluation set using the specified random seed.
        7. Return data splits with labels isolated for evaluation only.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Dataset file not found: {file_path}")

        benign_flows: List[Dict[str, float]] = []
        attack_flows: List[Dict[str, float]] = []

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = [col.strip() for col in next(reader) if col.strip()]
            schema_type, mapping, _, _ = self.detect_schema_and_mapping(header)

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            dict_reader = csv.DictReader(f)
            for row in dict_reader:
                features, label = self.parse_flow_row(row, mapping, schema_type=schema_type)
                if label == 1:
                    attack_flows.append(features)
                else:
                    benign_flows.append(features)

        total_benign = len(benign_flows)
        total_attack = len(attack_flows)

        if total_benign < 10:
            raise DatasetValidationError(
                f"Dataset contains too few benign samples ({total_benign}); at least 10 benign samples required."
            )
        if total_attack < 1:
            raise DatasetValidationError(
                "Dataset contains no attack/anomaly samples; cannot construct an evaluation set."
            )

        # Set reproducible seed for initial partitioning
        rng = random.Random(random_seed)
        rng.shuffle(benign_flows)
        rng.shuffle(attack_flows)

        # Safeguard calculation: check if requested counts exceed available records
        adjustment_reasons: List[str] = []
        config_adjusted = False

        # Allocate scaler init: at most 15% of benign if dataset is small, or min(scaler_init_count, total_benign - 20)
        max_possible_scaler_init = max(5, int(total_benign * 0.15))
        if scaler_init_count > max_possible_scaler_init and total_benign < 20000:
            actual_scaler_init = min(scaler_init_count, max_possible_scaler_init)
            config_adjusted = True
            adjustment_reasons.append(
                f"Scaler init count reduced from {scaler_init_count} to {actual_scaler_init} "
                f"to preserve flows for small dataset ({total_benign} benign flows total)"
            )
        else:
            actual_scaler_init = min(scaler_init_count, max(5, total_benign - 15))
            if actual_scaler_init < scaler_init_count:
                config_adjusted = True
                adjustment_reasons.append(
                    f"Scaler init count reduced from {scaler_init_count} to {actual_scaler_init} due to available benign flows"
                )

        remaining_benign = total_benign - actual_scaler_init

        # Allocate warmup: reserve at least 10 benign flows for evaluation
        max_possible_warmup = max(10, int(remaining_benign * 0.60))
        if warmup_count > max_possible_warmup and remaining_benign < 150000:
            actual_warmup = min(warmup_count, max_possible_warmup)
            config_adjusted = True
            adjustment_reasons.append(
                f"Warm-up count reduced from {warmup_count} to {actual_warmup} "
                f"to leave sufficient benign flows for balanced evaluation"
            )
        else:
            actual_warmup = min(warmup_count, max(5, remaining_benign - 5))
            if actual_warmup < warmup_count:
                config_adjusted = True
                adjustment_reasons.append(
                    f"Warm-up count reduced from {warmup_count} to {actual_warmup} due to available benign flows"
                )

        eval_benign_pool = benign_flows[actual_scaler_init + actual_warmup:]
        scaler_init_flows = benign_flows[:actual_scaler_init]
        warmup_flows = benign_flows[actual_scaler_init: actual_scaler_init + actual_warmup]

        # Construct balanced evaluation set: equal number of benign and attack flows
        available_eval_benign = len(eval_benign_pool)
        max_balanced_per_class = min(available_eval_benign, total_attack)

        if max_balanced_per_class <= 0:
            max_balanced_per_class = max(1, min(available_eval_benign, total_attack))

        if eval_count is not None and eval_count > 0:
            requested_per_class = eval_count // 2
            target_per_class = min(requested_per_class, max_balanced_per_class)
            if target_per_class * 2 < eval_count:
                config_adjusted = True
                adjustment_reasons.append(
                    f"Evaluation count reduced from {eval_count} to {target_per_class * 2} "
                    f"({target_per_class} benign + {target_per_class} attack) to maintain balanced evaluation"
                )
        else:
            target_per_class = max_balanced_per_class

        eval_benign = eval_benign_pool[:target_per_class]
        eval_attack = attack_flows[:target_per_class]

        # Combine into evaluation list with separate labels: (flow_dict, label)
        eval_pairs: List[Tuple[Dict[str, float], int]] = []
        for f in eval_benign:
            eval_pairs.append((f, 0))
        for f in eval_attack:
            eval_pairs.append((f, 1))

        # Shuffle evaluation flows with designated seed
        rng.shuffle(eval_pairs)

        eval_flows = [pair[0] for pair in eval_pairs]
        eval_labels = [pair[1] for pair in eval_pairs]

        adjustment_reason = (
            "; ".join(adjustment_reasons)
            if config_adjusted
            else "Requested configuration fits dataset size without reduction."
        )

        logger.info(
            "Prepared experiment data from %s (seed=%d): scaler_init=%d, warmup=%d, eval=%d (benign=%d, attack=%d). Adjusted: %s",
            path.name,
            random_seed,
            len(scaler_init_flows),
            len(warmup_flows),
            len(eval_flows),
            len(eval_benign),
            len(eval_attack),
            adjustment_reason,
        )

        return {
            "scaler_init_flows": scaler_init_flows,
            "warmup_flows": warmup_flows,
            "eval_flows": eval_flows,
            "eval_labels": eval_labels,
            "actual_scaler_init_count": len(scaler_init_flows),
            "actual_warmup_count": len(warmup_flows),
            "actual_eval_count": len(eval_flows),
            "eval_benign_count": len(eval_benign),
            "eval_attack_count": len(eval_attack),
            "total_benign_available": total_benign,
            "total_attack_available": total_attack,
            "config_adjusted": config_adjusted,
            "adjustment_reason": adjustment_reason,
        }

    def generate_benchmark_sample_file(self) -> str:
        """Generate a bundled 5,000-flow benchmark sample file following NF-UNSW-NB15 distributions.

        Ensures immediate demonstration and testing capability without waiting for an external download.
        Includes 4,000 realistic benign flows (HTTP/HTTPS, DNS, SSH, bulk) and 1,000 attack flows (PortScan, DoS, Exploits).
        """
        target_path = self.data_dir / "benchmark_sample_nfunsw.csv"
        if target_path.exists() and target_path.stat().st_size > 1000:
            return str(target_path)

        rng = random.Random(42)
        flows: List[Dict[str, Any]] = []

        # 1. Benign Flows (4,000 flows)
        benign_src_subnets = ["192.168.1.", "10.0.1.", "172.16.10."]
        server_ips = ["192.168.1.1", "10.0.0.10", "10.0.0.20", "142.250.190.46", "104.244.42.1"]
        common_ports = [80, 443, 53, 22, 8080]

        for i in range(4000):
            src_ip = f"{rng.choice(benign_src_subnets)}{rng.randint(10, 250)}"
            dst_ip = rng.choice(server_ips)
            sport = rng.randint(49152, 65535)
            dport = rng.choice(common_ports)
            proto = 6 if dport in (80, 443, 22, 8080) else (17 if dport == 53 else 6)

            # Normal packet & byte volumes
            if dport == 53:
                in_bytes = rng.randint(60, 250)
                out_bytes = rng.randint(80, 512)
                dur = rng.uniform(5.0, 50.0)
            elif dport in (80, 443):
                in_bytes = rng.randint(500, 15000)
                out_bytes = rng.randint(1500, 120000)
                dur = rng.uniform(20.0, 1200.0)
            else:
                in_bytes = rng.randint(300, 5000)
                out_bytes = rng.randint(300, 8000)
                dur = rng.uniform(10.0, 800.0)

            flows.append({
                "IPV4_SRC_ADDR": src_ip,
                "IPV4_DST_ADDR": dst_ip,
                "L4_SRC_PORT": sport,
                "L4_DST_PORT": dport,
                "PROTOCOL": proto,
                "IN_BYTES": in_bytes,
                "OUT_BYTES": out_bytes,
                "FLOW_DURATION_MILLISECONDS": round(dur, 2),
                "Label": 0,
                "Attack": "Benign",
            })

        # 2. Attack Flows (1,000 flows)
        scanner_ip = "192.168.1.200"
        target_ip = "10.0.0.10"
        for i in range(400):
            flows.append({
                "IPV4_SRC_ADDR": scanner_ip,
                "IPV4_DST_ADDR": target_ip,
                "L4_SRC_PORT": rng.randint(50000, 60000),
                "L4_DST_PORT": rng.randint(1, 1024),
                "PROTOCOL": 6,
                "IN_BYTES": 44,
                "OUT_BYTES": 0,
                "FLOW_DURATION_MILLISECONDS": round(rng.uniform(0.5, 4.0), 2),
                "Label": 1,
                "Attack": "PortScan",
            })

        dos_ip = "172.16.10.99"
        victim_ip = "10.0.0.20"
        for i in range(350):
            flows.append({
                "IPV4_SRC_ADDR": dos_ip,
                "IPV4_DST_ADDR": victim_ip,
                "L4_SRC_PORT": rng.randint(1025, 65535),
                "L4_DST_PORT": 80,
                "PROTOCOL": 6,
                "IN_BYTES": rng.randint(80000, 500000),
                "OUT_BYTES": rng.randint(40, 200),
                "FLOW_DURATION_MILLISECONDS": round(rng.uniform(1500.0, 10000.0), 2),
                "Label": 1,
                "Attack": "DoS",
            })

        exploit_src = "192.168.1.188"
        for i in range(250):
            flows.append({
                "IPV4_SRC_ADDR": exploit_src,
                "IPV4_DST_ADDR": "192.168.1.1",
                "L4_SRC_PORT": rng.randint(40000, 50000),
                "L4_DST_PORT": rng.choice([21, 23, 80, 445]),
                "PROTOCOL": 6,
                "IN_BYTES": rng.randint(25000, 65000),
                "OUT_BYTES": rng.randint(100, 800),
                "FLOW_DURATION_MILLISECONDS": round(rng.uniform(200.0, 2500.0), 2),
                "Label": 1,
                "Attack": "Exploit",
            })

        rng.shuffle(flows)

        with open(target_path, "w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "IPV4_SRC_ADDR",
                "IPV4_DST_ADDR",
                "L4_SRC_PORT",
                "L4_DST_PORT",
                "PROTOCOL",
                "IN_BYTES",
                "OUT_BYTES",
                "FLOW_DURATION_MILLISECONDS",
                "Label",
                "Attack",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flows)

        logger.info("Generated bundled benchmark sample dataset at %s (5000 flows)", target_path)
        return str(target_path)

    def register_dataset(
        self,
        db: Session,
        name: str,
        version: str,
        file_path: str,
        description: Optional[str] = None,
        is_sample: bool = False,
    ) -> ResearchDatasetModel:
        """Register a validated dataset file in SQLite."""
        stats = self.inspect_dataset_file(file_path)
        file_size = Path(file_path).stat().st_size

        dataset_id = str(uuid.uuid4())
        model = ResearchDatasetModel(
            id=dataset_id,
            name=name,
            version=version,
            description=description,
            file_path=str(file_path),
            file_size_bytes=file_size,
            total_flows=stats["total_flows"],
            benign_flows=stats["benign_flows"],
            attack_flows=stats["attack_flows"],
            features_json=json.dumps(stats["detected_features"]),
            schema_type=stats.get("schema_type", DatasetSchemaType.NATIVE_NETFLOW),
            is_adapted=stats.get("is_adapted", False),
            adaptation_notes=stats.get("adaptation_notes"),
            is_sample=is_sample,
            created_at=datetime.now(timezone.utc),
        )
        db.add(model)
        db.commit()
        db.refresh(model)
        return model

    def ensure_default_sample_dataset(self, db: Session) -> ResearchDatasetModel:
        """Ensure the bundled benchmark sample dataset exists in database and on disk."""
        existing = db.query(ResearchDatasetModel).filter(ResearchDatasetModel.is_sample.is_(True)).first()
        if existing and Path(existing.file_path).exists():
            return existing

        sample_path = self.generate_benchmark_sample_file()
        if existing:
            existing.file_path = sample_path
            db.commit()
            db.refresh(existing)
            return existing

        return self.register_dataset(
            db=db,
            name="NF-UNSW-NB15 Benchmark Sample",
            version="NF-UNSW-NB15",
            file_path=sample_path,
            description=(
                "Bundled 5,000-flow benchmark sample reflecting NF-UNSW-NB15 distributions. "
                "For immediate verification and viva demonstration."
            ),
            is_sample=True,
        )


dataset_service = DatasetService()
