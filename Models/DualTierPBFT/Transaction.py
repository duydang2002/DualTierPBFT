"""
Transaction model for DualTierBlockchain - Government/Enterprise Permissioned Network.

Design:
- No gas/fee (permissioned chain, no token economy)
- Block capacity limited by SIZE (MB)
- Transactions represent government documents, approvals, records, etc.
- sender/to can be ANY entity: citizen, business, department — not just network nodes
- Tier-1 nodes hold tx pools and propose blocks
- Tier-0 nodes do NOT hold pools — only finalize via PBFT

Performance optimization:
- Transaction attributes (type, size, sender, to) are pre-generated ONCE
  and saved to a pickle file (tx_pool_cache.pkl)
- At runtime, just sample rows + assign timestamps and propagation delays
  → much faster than re-computing distributions every run
"""

import os
import random
import copy
import pickle
import numpy as np
from InputsConfig import InputsConfig as p
from Models.Network import Network

# ---------------------------------------------------------------------------
# Transaction types for a government network
# ---------------------------------------------------------------------------
TX_TYPES = [
    "document_submission",   # Nộp hồ sơ, văn bản hành chính
    "approval_request",      # Yêu cầu phê duyệt từ cấp trên
    "data_record",           # Ghi nhận dữ liệu công khai / hành chính
    "license_issuance",      # Cấp phép, giấy phép
    "budget_allocation",     # Phân bổ / chuyển ngân sách
    "inter_agency_report",   # Báo cáo liên cơ quan
]

TX_TYPE_WEIGHTS = [0.30, 0.20, 0.25, 0.10, 0.05, 0.10]  # must sum to 1.0

# Priority: 1=low, 2=medium, 3=high

# Default path for the pre-generated pool cache
DEFAULT_POOL_FILE = "tx_pool_cache.pkl"

# ---------------------------------------------------------------------------
# Sender / Receiver entity types
# ---------------------------------------------------------------------------
# Transactions originate ONLY from external entities (citizens, businesses,
# departments). Government blockchain nodes (Tier-0 / Tier-1) are
# infrastructure nodes — they validate and finalize, NOT initiate transactions.
#
# SENDER types (external entities only):
#   - "citizen"    : individual citizens submitting requests / documents
#   - "business"   : enterprises filing permits, taxes, reports, etc.
#   - "department" : internal sub-departments (not full consensus nodes)
#
# RECEIVER types (can include actual Tier-1 nodes as destination agencies):
#   - "citizen"    : citizen receiving a response / approved document
#   - "business"   : business receiving license, approval, etc.
#   - "department" : sub-department receiving an assignment

SENDER_TYPES   = ["citizen", "business", "department"]
SENDER_WEIGHTS = [0.45, 0.35, 0.20]          # citizens most common senders

RECEIVER_TYPES   = ["citizen", "business", "department"]
RECEIVER_WEIGHTS = [0.40, 0.35, 0.25]


def _random_entity_id(types, weights):
    """Generate an entity id (citizen / business / department only)."""
    entity_type = random.choices(types, weights=weights)[0]
    if entity_type == "citizen":
        return f"CIT_{random.randint(1, 10_000_000):08d}"
    elif entity_type == "business":
        return f"BIZ_{random.randint(1, 1_000_000):07d}"
    else:  # department
        return f"DEPT_{random.randint(1, 500):04d}"


def _random_sender_id():
    return _random_entity_id(SENDER_TYPES, SENDER_WEIGHTS)


def _random_receiver_id():
    return _random_entity_id(RECEIVER_TYPES, RECEIVER_WEIGHTS)


# ---------------------------------------------------------------------------
# Transaction class
# ---------------------------------------------------------------------------
class Transaction:
    """
    A government/enterprise transaction.

    Fields
    ------
    id          : unique transaction identifier (int)
    timestamp   : float (Light) or [creation_time, arrival_time] (Full)
    sender      : entity id — citizen id string, business id string, or node int id
    to          : destination entity id (same format as sender)
    tx_type     : category (see TX_TYPES)
    size        : size in MB
    data_hash   : mock hash of document payload
    """

    _id_counter = 0

    def __init__(
        self,
        id=None,
        timestamp=0,
        sender=0,
        to=0,
        tx_type="data_record",
        size=0.000546,
        data_hash=None,
    ):
        Transaction._id_counter += 1
        self.id = id if id is not None else Transaction._id_counter
        self.timestamp = timestamp
        self.sender = sender
        self.to = to
        self.tx_type = tx_type
        self.size = size
        self.data_hash = data_hash or f"hash_{self.id:08x}"

    def __repr__(self):
        ts = self.timestamp if not isinstance(self.timestamp, list) else self.timestamp[0]
        return (
            f"Tx(id={self.id}, type={self.tx_type}, "
            f"size={self.size:.6f}MB, t={ts:.2f})"
        )


# ---------------------------------------------------------------------------
# Pre-generation utilities
# ---------------------------------------------------------------------------

def pregenerate_pool(pool_size=None, filepath=DEFAULT_POOL_FILE, force=False):
    """
    Pre-generate transaction attribute templates and save to pickle file.
    Only needs to run ONCE (or when network topology changes significantly).

    Parameters
    ----------
    pool_size : int   — number of templates (default: Tn * simTime * 10)
    filepath  : str   — output file path
    force     : bool  — regenerate even if file already exists
    """
    if not force and os.path.exists(filepath):
        print(f"[TxPool] Cache exists at '{filepath}'. Use force=True to regenerate.")
        return

    if pool_size is None:
        # 10x expected demand so we never run out across multiple runs
        pool_size = int(2000000)

    print(f"[TxPool] Pre-generating {pool_size:,} transaction templates → '{filepath}'...")

    # Vectorized attribute generation
    tx_types    = random.choices(TX_TYPES, weights=TX_TYPE_WEIGHTS, k=pool_size)
    sizes       = np.abs(np.random.normal(p.Tsize, p.Tsize * 0.2, pool_size)).tolist()

    templates = [
        {
            "tx_type":   tx_types[i],
            "size":      sizes[i],
            "sender":    _random_sender_id(),
            "to":        _random_receiver_id(),
            "data_hash": f"hash_{i:08x}",
        }
        for i in range(pool_size)
    ]

    with open(filepath, "wb") as f:
        pickle.dump(templates, f)

    print(f"[TxPool] Done. {pool_size:,} templates saved.")


def load_pool(filepath=DEFAULT_POOL_FILE):
    """Load pre-generated templates from file. Auto-generates if missing."""
    if not os.path.exists(filepath):
        print(f"[TxPool] Cache not found, generating now...")
        pregenerate_pool(filepath=filepath)
    with open(filepath, "rb") as f:
        print("Cache found")
        return pickle.load(f)


# ---------------------------------------------------------------------------
# Light Transaction — shared pool, single timestamp
# ---------------------------------------------------------------------------

class LightTransaction:
    """
    Light mode: one global shared pool, no per-node propagation.
    Fast simulation — timestamps are single floats.
    """

    pool = []
    _templates = None  # in-memory cache after first load

    @staticmethod
    def create_transactions(pool_file=DEFAULT_POOL_FILE):
        """
        Sample from pre-generated templates and assign random creation times.
        """
        LightTransaction.pool = []
        Transaction._id_counter = 0

        if LightTransaction._templates is None:
            LightTransaction._templates = load_pool(pool_file)

        pool_size = int(p.Tn * p.simTime)
        templates = random.sample(
            LightTransaction._templates,
            min(pool_size, len(LightTransaction._templates))
        )

        for i, tmpl in enumerate(templates):
            tx = Transaction(
                id=i + 1,
                timestamp=random.uniform(0, p.simTime),
                sender=tmpl["sender"],
                to=tmpl["to"],
                tx_type=tmpl["tx_type"],
                size=tmpl["size"],
                data_hash=tmpl["data_hash"],
            )
            LightTransaction.pool.append(tx)

        # FIFO: sort by creation time
        LightTransaction.pool.sort(key=lambda x: x.timestamp)
        print(f"[LightTx] Sampled {len(LightTransaction.pool):,} transactions.")

    @staticmethod
    def execute_transactions(proposer_num, count_proposer_index):
        """
        Pull transactions into a block (limited by p.Bsize MB).
        Returns (selected_transactions, total_size_used_MB).
        """
        selected = []
        remaining = p.Bsize

        pool = LightTransaction.pool
        i = 0
        while i < len(pool):
            tx = pool[i]
            if tx.size <= remaining:
                selected.append(tx)
                remaining -= tx.size
                
                if proposer_num == count_proposer_index:
                    del pool[i] 
                else: i+=1
            else:
                i += 1
            if remaining < p.Tsize * 0.5:
                break

        return selected, p.Bsize - remaining


# ---------------------------------------------------------------------------
# Full Transaction — per-node pools + propagation delay
# ---------------------------------------------------------------------------

class FullTransaction:
    """
    Full mode: each Tier-1 node maintains its own transaction pool.
    Transactions are propagated with realistic network delays.
    Tier-0 nodes are excluded from all pools.
    """

    _templates = None
    _initialized = False

    @staticmethod
    def create_transactions(pool_file=DEFAULT_POOL_FILE):
        """
        Sample templates, assign timestamps, distribute to Tier-1 pools.
        """
        FullTransaction._initialized = True
        Transaction._id_counter = 0

        if FullTransaction._templates is None:
            FullTransaction._templates = load_pool(pool_file)

        pool_size = int(p.Tn * p.simTime)
        templates = random.sample(
            FullTransaction._templates,
            min(pool_size, len(FullTransaction._templates))
        )

        tier1_nodes = [n for n in p.NODES if n.tier == 1]
        if not tier1_nodes:
            return

        for i, tmpl in enumerate(templates):
            creation_time = random.uniform(0, p.simTime - 1)

            tx = Transaction(
                id=i + 1,
                timestamp=[creation_time, creation_time],
                sender=tmpl["sender"],   # always an external entity string
                to=tmpl["to"],
                tx_type=tmpl["tx_type"],
                size=tmpl["size"],
                data_hash=tmpl["data_hash"],
            )

            # Propagate to all Tier-1 nodes with individual delay
            # (no "direct" add — sender is never a network node)
            FullTransaction.transaction_prop(tx)

        print(f"[FullTx] Distributed {pool_size:,} transactions to Tier-1 pools.")

    @staticmethod
    def transaction_prop(tx):
        """
        Broadcast tx to ALL Tier-1 nodes with individual propagation delays.
        Tier-0 nodes are excluded — they do not hold pools.
        No sender-skip needed: sender is always an external entity, not a node.
        """
        for node in p.NODES:
            if node.tier != 1:
                continue
            t = copy.copy(tx)
            t.timestamp = [tx.timestamp[0], tx.timestamp[0] + Network.tx_prop_delay()]
            node.transactionsPool.append(t)

    @staticmethod
    def execute_transactions(miner, current_time):
        """
        Select transactions for a block proposal.

        Policy:
        1. Only include txs that have arrived by current_time.
        3. Fill up to p.Bsize MB.

        Returns (selected_transactions, total_size_used_MB).
        """
        if not hasattr(miner, "transactionsPool"):
            return [], 0.0

        available = [
            tx for tx in miner.transactionsPool
            if isinstance(tx.timestamp, list) and tx.timestamp[1] <= current_time
        ]

        if not available:
            return [], 0.0

        available.sort(key=lambda x: x.timestamp[1])  # FIFO

        selected = []
        selected_ids = set()
        remaining = p.Bsize

        for tx in available:
            if tx.size <= remaining:
                selected.append(tx)
                selected_ids.add(tx.id)
                remaining -= tx.size
            if remaining < p.Tsize * 0.5:
                break

        # Remove selected txs from pool
        miner.transactionsPool = [
            tx for tx in miner.transactionsPool if tx.id not in selected_ids
        ]

        return selected, p.Bsize - remaining