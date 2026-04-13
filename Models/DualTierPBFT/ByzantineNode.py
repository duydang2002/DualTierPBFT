# ByzantineNode.py - NEW FILE

from enum import Enum
import random



class ByzantineType(Enum):
    """Types of Byzantine behaviors"""
    HONEST = 0           # Normal honest node (for comparison)
    SILENT = 1           # Never responds (crash-like)
    DELAYED = 2          # Always responds late
    EQUIVOCATING = 3     # Votes for conflicting blocks
    RANDOM = 4           # Random unpredictable behavior
    SELFISH = 5          # Only proposes own blocks, ignores others
    WRONG_SIGNATURE = 6  # Sends messages with invalid signatures
    INVALID_VRF = 7      # Tier-1: submits invalid VRF proofs


class ByzantineConfig:
    """Configuration for Byzantine experiments"""
    
    # Byzantine node distribution
    byzantine_tier0_ids = []      # IDs of Byzantine Tier-0 nodes
    byzantine_tier1_ids = []      # IDs of Byzantine Tier-1 nodes
    
    # Byzantine behavior mapping
    byzantine_behaviors = {}      # {node_id: ByzantineType}
    
    # Attack parameters
    delay_factor = 2.0           # Multiplier for DELAYED nodes (2x normal delay)
    equivocation_probability = 0.5  # Probability of equivocating
    random_behavior_probability = 0.3  # Probability of misbehaving
    
    @staticmethod
    def set_byzantine_nodes(tier0_byzantine, tier1_byzantine, behavior_type=ByzantineType.EQUIVOCATING):
        from InputsConfig import InputsConfig as p
        """
        Configure Byzantine nodes
        
        :param tier0_byzantine: Number of Byzantine Tier-0 nodes
        :param tier1_byzantine: Number of Byzantine Tier-1 nodes
        :param behavior_type: Default Byzantine behavior
        """
        ByzantineConfig.byzantine_tier0_ids = []
        ByzantineConfig.byzantine_tier1_ids = []
        ByzantineConfig.byzantine_behaviors = {}
        
        # Select random Tier-0 nodes to be Byzantine
        tier0_nodes = [i for i in range(p.t0)]
        if tier0_byzantine > 0:
            ByzantineConfig.byzantine_tier0_ids = random.sample(tier0_nodes, min(tier0_byzantine, len(tier0_nodes)))
            
            for node_id in ByzantineConfig.byzantine_tier0_ids:
                ByzantineConfig.byzantine_behaviors[node_id] = behavior_type
        
        # Select random Tier-1 nodes to be Byzantine
        tier1_nodes = [i for i in range(p.t0, p.t0 + p.t1)]
        if tier1_byzantine > 0:
            ByzantineConfig.byzantine_tier1_ids = random.sample(tier1_nodes, min(tier1_byzantine, len(tier1_nodes)))
            
            for node_id in ByzantineConfig.byzantine_tier1_ids:
                ByzantineConfig.byzantine_behaviors[node_id] = behavior_type
        
        print(f"\n🔴 Byzantine Configuration:")
        print(f"  Tier-0 Byzantine nodes: {ByzantineConfig.byzantine_tier0_ids}")
        print(f"  Tier-1 Byzantine nodes: {ByzantineConfig.byzantine_tier1_ids}")
        print(f"  Default behavior: {behavior_type.name}")
    
    @staticmethod
    def set_mixed_behaviors(tier0_behaviors, tier1_behaviors):
        from InputsConfig import InputsConfig as p
        """
        Set different behaviors for different nodes
        
        :param tier0_behaviors: {node_id: ByzantineType} for Tier-0
        :param tier1_behaviors: {node_id: ByzantineType} for Tier-1
        """
        ByzantineConfig.byzantine_tier0_ids = list(tier0_behaviors.keys())
        ByzantineConfig.byzantine_tier1_ids = list(tier1_behaviors.keys())
        ByzantineConfig.byzantine_behaviors = {**tier0_behaviors, **tier1_behaviors}
        
        print(f"\n🔴 Byzantine Configuration (Mixed):")
        for node_id, behavior in ByzantineConfig.byzantine_behaviors.items():
            tier = "Tier-0" if node_id < p.t0 else "Tier-1"
            print(f"  Node {node_id} ({tier}): {behavior.name}")
    
    @staticmethod
    def is_byzantine(node_id):
        """Check if node is Byzantine"""
        return node_id in ByzantineConfig.byzantine_behaviors
    
    @staticmethod
    def get_behavior(node_id):
        """Get Byzantine behavior for node"""
        return ByzantineConfig.byzantine_behaviors.get(node_id, ByzantineType.HONEST)


class ByzantineStatistics:
    """Track Byzantine attack impacts"""
    
    # Attack statistics
    equivocations_detected = 0
    invalid_signatures_detected = 0
    late_messages_count = 0
    silent_nodes_count = 0
    invalid_vrfs_rejected = 0
    
    # System resilience
    blocks_finalized_under_attack = 0
    rounds_failed_due_to_byzantine = 0
    
    @staticmethod
    def record_equivocation():
        ByzantineStatistics.equivocations_detected += 1
    
    @staticmethod
    def record_invalid_signature():
        ByzantineStatistics.invalid_signatures_detected += 1
    
    @staticmethod
    def record_late_message():
        ByzantineStatistics.late_messages_count += 1
    
    @staticmethod
    def record_silent_node():
        ByzantineStatistics.silent_nodes_count += 1
    
    @staticmethod
    def record_invalid_vrf():
        ByzantineStatistics.invalid_vrfs_rejected += 1
    
    @staticmethod
    def reset():
        ByzantineStatistics.equivocations_detected = 0
        ByzantineStatistics.invalid_signatures_detected = 0
        ByzantineStatistics.late_messages_count = 0
        ByzantineStatistics.silent_nodes_count = 0
        ByzantineStatistics.invalid_vrfs_rejected = 0
        ByzantineStatistics.blocks_finalized_under_attack = 0
        ByzantineStatistics.rounds_failed_due_to_byzantine = 0
    
    @staticmethod
    def print_summary():
        print("\n Byzantine Attack Statistics:")
        print(f"  Equivocations Detected: {ByzantineStatistics.equivocations_detected}")
        print(f"  Invalid Signatures Detected: {ByzantineStatistics.invalid_signatures_detected}")
        print(f"  Late Messages: {ByzantineStatistics.late_messages_count}")
        print(f"  Silent Node Instances: {ByzantineStatistics.silent_nodes_count}")
        print(f"  Invalid VRFs Rejected: {ByzantineStatistics.invalid_vrfs_rejected}")
        print(f"  Blocks Finalized Under Attack: {ByzantineStatistics.blocks_finalized_under_attack}")
        print(f"  Rounds Failed Due to Byzantine: {ByzantineStatistics.rounds_failed_due_to_byzantine}")