"""
PBFT Implementation for Dual-Tier Blockchain
Simplified PBFT với 2 phases: Prepare và Commit
"""

from enum import Enum
import hashlib
from random import *
import random
from Models.DualTierBlockchain.ByzantineNode import ByzantineConfig, ByzantineType, ByzantineStatistics
from Models.Network import Network

class PBFTPhase(Enum):
    IDLE = 0
    PREPARE = 1
    COMMIT = 2
    FINALIZED = 3
    FAILED = 4

class PBFTMessage:
    """
    PBFT message structure
    """
    def __init__(self, msg_type, block_hash, round_num, sender_id, vrf_value=None):
        self.msg_type = msg_type  # "PREPARE" or "COMMIT"
        self.block_hash = block_hash
        self.round_num = round_num
        self.sender_id = sender_id
        self.vrf_value = vrf_value
        self.signature = self.sign()
    
    def sign(self):
        """Mock signature - trong thực tế dùng cryptographic signature"""
        data = f"{self.msg_type}|{self.block_hash}|{self.round_num}|{self.sender_id}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def verify(self):
        """Verify message signature"""
        expected_sig = hashlib.sha256(
            f"{self.msg_type}|{self.block_hash}|{self.round_num}|{self.sender_id}".encode()
        ).hexdigest()[:16]
        return self.signature == expected_sig


class PBFTState:
    """
    PBFT State Machine cho mỗi Tier-0 node
    """
    def __init__(self, node_id):
        self.node_id = node_id
        self.phase = PBFTPhase.IDLE
        self.current_block_hash = None
        self.current_round = 0
        self.current_vrf = None
        
        # Vote tracking
        self.prepare_votes = {}  # {block_hash: set of sender_ids}
        self.commit_votes = {}   # {block_hash: set of sender_ids}
        
        # Byzantine detection
        self.equivocating_nodes = set()  # Nodes that sent conflicting messages
        
    def reset(self):
        """Reset state cho round mới"""
        self.phase = PBFTPhase.IDLE
        self.current_block_hash = None
        self.current_vrf = None
        self.prepare_votes.clear()
        self.commit_votes.clear()
        
    def start_prepare(self, block_hash, round_num, vrf_value):
        """Bắt đầu Prepare phase"""
        self.phase = PBFTPhase.PREPARE
        self.current_block_hash = block_hash
        self.current_round = round_num
        self.current_vrf = vrf_value
        self.prepare_votes[block_hash] = {self.node_id}  # Self-vote
        
    def add_prepare_vote(self, msg):
        """
        Thêm PREPARE vote
        Returns: True nếu đủ votes (2f0+1), False otherwise
        """
        if not msg.verify():
            return False
            
        # Detect equivocation (node sends 2 different PREPARE for same round)
        if msg.block_hash != self.current_block_hash and msg.sender_id in self.prepare_votes.get(self.current_block_hash, set()):
            self.equivocating_nodes.add(msg.sender_id)
            return False
        
        if msg.block_hash not in self.prepare_votes:
            self.prepare_votes[msg.block_hash] = set()
        
        self.prepare_votes[msg.block_hash].add(msg.sender_id)
        
        # Check if we have 2f0+1 votes for this block
        from InputsConfig import InputsConfig as p
        quorum = 2 * p.f0 + 1
        if len(self.prepare_votes[msg.block_hash]) >= quorum:
            return True
        
        return False
    
    def start_commit(self):
        """Chuyển sang Commit phase"""
        self.phase = PBFTPhase.COMMIT
        self.commit_votes[self.current_block_hash] = {self.node_id}  # Self-vote
        
    def add_commit_vote(self, msg):
        """
        Thêm COMMIT vote
        Returns: True nếu đủ votes (2f0+1), False otherwise
        """
        if not msg.verify():
            return False
        
        # Detect equivocation
        if msg.block_hash != self.current_block_hash and msg.sender_id in self.commit_votes.get(self.current_block_hash, set()):
            self.equivocating_nodes.add(msg.sender_id)
            return False
            
        if msg.block_hash not in self.commit_votes:
            self.commit_votes[msg.block_hash] = set()
        
        self.commit_votes[msg.block_hash].add(msg.sender_id)
        
        # Check if we have 2f0+1 votes
        from InputsConfig import InputsConfig as p
        quorum = 2 * p.f0 + 1
        if len(self.commit_votes[msg.block_hash]) >= quorum:
            return True
        
        return False
    
    def finalize(self):
        """Mark block as finalized"""
        self.phase = PBFTPhase.FINALIZED
        
    def mark_failed(self):
        """Mark PBFT as failed for this block"""
        self.phase = PBFTPhase.FAILED


class PBFTConsensus:
    """
    PBFT Consensus Manager
    Quản lý toàn bộ PBFT process cho Tier-0
    """
    
    @staticmethod
    def compute_block_hash(block):
        """Tính hash của block để làm identifier"""
        block_data = f"{block.id}|{block.previous}|{block.miner}|{block.vrf_value}"
        return hashlib.sha256(block_data.encode()).hexdigest()
    
    @staticmethod
    def create_prepare_message(node, block, vrf_value, round_num):
        """Tier-0 node tạo PREPARE message"""
        block_hash = PBFTConsensus.compute_block_hash(block)
        return PBFTMessage("PREPARE", block_hash, round_num, node.id, vrf_value)
    
    @staticmethod
    def create_commit_message(node, block, round_num):
        """Tier-0 node tạo COMMIT message"""
        block_hash = PBFTConsensus.compute_block_hash(block)
        return PBFTMessage("COMMIT", block_hash, round_num, node.id)
    """
    @staticmethod
    def broadcast_prepare(node, block, vrf_value, round_num, current_time):
        """
        #Node broadcast PREPARE message tới tất cả Tier-0 nodes
    """
        from Scheduler import Scheduler
        from Models.Network import Network
        
        msg = PBFTConsensus.create_prepare_message(node, block, vrf_value, round_num)
        
        # Gửi tới tất cả Tier-0 nodes (trừ chính nó)
        from InputsConfig import InputsConfig as p
        from Statistics import Statistics

        for recipient in p.NODES:
            if recipient.tier == 0 and recipient.id != node.id:
                Statistics.messages+=1
                PBFTStatistics.prepare_messages+=1
                delay = Network.pbft_prop_delay()
                Scheduler.pbft_prepare_event(recipient, msg, current_time + delay)
        
        return msg
    
    @staticmethod
    def broadcast_commit(node, block, round_num, current_time):
        """
        #Node broadcast COMMIT message tới tất cả Tier-0 nodes
    """
        from Scheduler import Scheduler
        from Models.Network import Network
        from Statistics import Statistics

        msg = PBFTConsensus.create_commit_message(node, block, round_num)
        # Gửi tới tất cả Tier-0 nodes (trừ chính nó)
        from InputsConfig import InputsConfig as p
        for recipient in p.NODES:
            if recipient.tier == 0 and recipient.id != node.id:
                Statistics.messages+=1
                PBFTStatistics.commit_messages+=1
                delay = Network.pbft_prop_delay()
                Scheduler.pbft_commit_event(recipient, msg, current_time + delay)
                
        return msg
    
    @staticmethod
    def handle_prepare_message(node, msg, current_time):
        """
        #Xử lý PREPARE message nhận được
    """
        if not hasattr(node, 'pbft_state'):
            return False
        from InputsConfig import InputsConfig as p
        # Add vote và check nếu đủ quorum
        has_quorum = node.pbft_state.add_prepare_vote(msg)
        
        if has_quorum and node.pbft_state.phase == PBFTPhase.PREPARE:
            # Đủ 2f0+1 PREPARE votes → chuyển sang COMMIT phase
            node.pbft_state.start_commit()
            
            # Broadcast COMMIT message
            block = node.current_pbft_block  # Block đang được PBFT
            PBFTConsensus.broadcast_commit(node, block, msg.round_num, current_time + p.T_commit_timeout)
            
            return True
        
        return False
    
    @staticmethod
    def handle_commit_message(node, msg, current_time):
        """
        #Xử lý COMMIT message nhận được
    """
        if not hasattr(node, 'pbft_state'):
            return False
        
        # Add vote và check nếu đủ quorum
        has_quorum = node.pbft_state.add_commit_vote(msg)
        
        if has_quorum and node.pbft_state.phase == PBFTPhase.COMMIT:
            # Đủ 2f0+1 COMMIT votes → FINALIZE block
            node.pbft_state.finalize()
            return True
        
        return False
    """
    @staticmethod
    def check_timeout(node, timeout_duration, current_time):
        """
        Check nếu PBFT timeout (không đủ votes trong thời gian cho phép)
        """
        if not hasattr(node, 'pbft_start_time'):
            return False
        
        if current_time - node.pbft_start_time > timeout_duration:
            node.pbft_state.mark_failed()
            return True
        
        return False
    @staticmethod
    def broadcast_prepare(node, block, vrf_value, round_num, current_time):
        """
        Broadcast PREPARE message
        ⭐ Modified to handle Byzantine behavior
        """
        from Scheduler import Scheduler
        from InputsConfig import InputsConfig as p
        from Statistics import Statistics
        # Check if node is Byzantine
        if ByzantineConfig.is_byzantine(node.id):
            behavior = ByzantineConfig.get_behavior(node.id)
            
            # SILENT: Don't send anything
            if behavior == ByzantineType.SILENT:
                ByzantineStatistics.record_silent_node()
                print(f"[BYZANTINE] Node {node.id} (SILENT) - Not sending PREPARE")
                return None
            
            # DELAYED: Will send later
            elif behavior == ByzantineType.DELAYED:
                delay_multiplier = ByzantineConfig.delay_factor
                print(f"[BYZANTINE] Node {node.id} (DELAYED) - Delaying PREPARE by {delay_multiplier}x")
            else:
                delay_multiplier = 1.0
        else:
            delay_multiplier = 1.0
        
        # Create message
        msg = PBFTConsensus.create_prepare_message(node, block, vrf_value, round_num)
        
        # WRONG_SIGNATURE: Corrupt the signature
        if ByzantineConfig.is_byzantine(node.id):
            behavior = ByzantineConfig.get_behavior(node.id)
            if behavior == ByzantineType.WRONG_SIGNATURE:
                msg.signature = b"INVALID_SIGNATURE"
                print(f"[BYZANTINE] Node {node.id} (WRONG_SIGNATURE) - Sending invalid signature")
        
        # EQUIVOCATING: Send different messages to different nodes
        if ByzantineConfig.is_byzantine(node.id):
            behavior = ByzantineConfig.get_behavior(node.id)
            if behavior == ByzantineType.EQUIVOCATING:
                if random.random() < ByzantineConfig.equivocation_probability:
                    print(f"[BYZANTINE] Node {node.id} (EQUIVOCATING) - Sending conflicting PREPAREs")
                    PBFTConsensus._send_equivocating_prepares(node, block, round_num, current_time, delay_multiplier)
                    return msg
        
        # Normal broadcast
        for recipient in p.NODES:
            if recipient.tier == 0 and recipient.id != node.id:
                Statistics.messages+=1
                PBFTStatistics.prepare_messages+=1
                delay = Network.pbft_prop_delay() * delay_multiplier
                Scheduler.pbft_prepare_event(recipient, msg, current_time + delay)
        
        return msg
    
    @staticmethod
    def _send_equivocating_prepares(node, block, round_num, current_time, delay_multiplier):
        """
        Send different PREPARE messages to different nodes (equivocation attack)
        """
        from Scheduler import Scheduler
        from InputsConfig import InputsConfig as p
        from Models.Network import Network
        
        # Create two different messages with different block hashes
        msg1 = PBFTConsensus.create_prepare_message(node, block, node.pbft_state.current_vrf, round_num)
        
        # Create fake conflicting block
        from Models.DualTierBlockchain.Block import Block
        fake_block = Block()
        fake_block.id = block.id
        fake_block.miner = block.miner-1
        fake_block.previous = block.previous
        fake_block.transactions = block.transactions
        fake_block.block_hash = PBFTConsensus.compute_block_hash(fake_block)
        
        msg2 = PBFTConsensus.create_prepare_message(node, fake_block, node.pbft_state.current_vrf, round_num)
        
        # Send half nodes msg1, half nodes msg2
        tier0_nodes = [n for n in p.NODES if n.tier == 0 and n.id != node.id]
        random.shuffle(tier0_nodes)
        
        mid = len(tier0_nodes) // 2
        
        for i, recipient in enumerate(tier0_nodes):
            msg = msg1 if i < mid else msg2
            delay = Network.pbft_prop_delay() * delay_multiplier
            Scheduler.pbft_prepare_event(recipient, msg, current_time + delay)
        
        ByzantineStatistics.record_equivocation()
    
    @staticmethod
    def broadcast_commit(node, block, round_num, current_time):
        """
        Broadcast COMMIT message
        ⭐ Modified to handle Byzantine behavior
        """
        from Scheduler import Scheduler
        from InputsConfig import InputsConfig as p
        from Statistics import Statistics
        # Check if node is Byzantine
        if ByzantineConfig.is_byzantine(node.id):
            behavior = ByzantineConfig.get_behavior(node.id)
            
            # SILENT: Don't send
            if behavior == ByzantineType.SILENT:
                ByzantineStatistics.record_silent_node()
                print(f"[BYZANTINE] Node {node.id} (SILENT) - Not sending COMMIT")
                return None
            
            # DELAYED: Will send later
            elif behavior == ByzantineType.DELAYED:
                delay_multiplier = ByzantineConfig.delay_factor
                ByzantineStatistics.record_late_message()
            else:
                delay_multiplier = 1.0
        else:
            delay_multiplier = 1.0
        
        # Create message
        msg = PBFTConsensus.create_commit_message(node, block, round_num)
        
        # WRONG_SIGNATURE: Corrupt signature
        if ByzantineConfig.is_byzantine(node.id):
            behavior = ByzantineConfig.get_behavior(node.id)
            if behavior == ByzantineType.WRONG_SIGNATURE:
                msg.signature = b"INVALID_SIGNATURE"
                ByzantineStatistics.record_invalid_signature()
        
        # EQUIVOCATING: Send different commits
        if ByzantineConfig.is_byzantine(node.id):
            behavior = ByzantineConfig.get_behavior(node.id)
            if behavior == ByzantineType.EQUIVOCATING:
                if random.random() < ByzantineConfig.equivocation_probability:
                    print(f"[BYZANTINE] Node {node.id} (EQUIVOCATING) - Sending conflicting COMMITs")
                    PBFTConsensus._send_equivocating_commits(node, block, round_num, current_time, delay_multiplier)
                    return msg
                
        print(f"Node {node.id} Broadcasting COMMIT")
        # Normal broadcast
        for recipient in p.NODES:
            if recipient.tier == 0 and recipient.id != node.id:
                Statistics.messages+=1
                PBFTStatistics.commit_messages += 1
                delay = Network.pbft_prop_delay() * delay_multiplier
                Scheduler.pbft_commit_event(recipient, msg, current_time + delay)
        
        return msg
    
    @staticmethod
    def _send_equivocating_commits(node, block, round_num, current_time, delay_multiplier):
        """Send conflicting COMMIT messages"""
        from Scheduler import Scheduler
        from InputsConfig import InputsConfig as p
        from Models.Network import Network
        
        msg1 = PBFTConsensus.create_commit_message(node, block, round_num)
        
        # Create fake conflicting message
        from Models.DualTierBlockchain.Block import Block
        fake_block = Block()
        fake_block.id = block.id
        fake_block.miner = randint(1, 100)
        fake_block.previous = block.previous
        fake_block.transactions = block.transactions
        msg2 = PBFTConsensus.create_commit_message(node, fake_block, round_num)
        
        tier0_nodes = [n for n in p.NODES if n.tier == 0 and n.id != node.id]
        random.shuffle(tier0_nodes)
        
        mid = len(tier0_nodes) // 2
        
        for i, recipient in enumerate(tier0_nodes):
            msg = msg1 if i < mid else msg2
            delay = Network.pbft_prop_delay() * delay_multiplier
            Scheduler.pbft_commit_event(recipient, msg, current_time + delay)
        
        ByzantineStatistics.record_equivocation()
    
    @staticmethod
    def handle_prepare_message(node, msg, current_time):
        """
        Handle PREPARE message received
        """
        # Handle Byzantine behavior detection
        # Verify signature
        if not msg.verify():
            print(f"[DETECTION] Node {node.id} detected invalid PREPARE signature from Node {msg.sender_id}")
            ByzantineStatistics.record_invalid_signature()
            return False
        
        # Detect equivocation
        if msg.block_hash in node.pbft_state.prepare_votes:
            if msg.sender_id in node.pbft_state.prepare_votes[msg.block_hash]:
                # Already voted for this block
                return False
        
        # Check if sender already voted for DIFFERENT block (equivocation)
        for block_hash, voters in node.pbft_state.prepare_votes.items():
            if block_hash != msg.block_hash and msg.sender_id in voters:
                print(f"[DETECTION] Node {node.id} detected EQUIVOCATION from Node {msg.sender_id}")
                ByzantineStatistics.record_equivocation()
                # Ignore this message
                return False
        
        # Handle normally
        if not hasattr(node, 'pbft_state'):
            return False
        from InputsConfig import InputsConfig as p
        # Add vote và check nếu đủ quorum
        has_quorum = node.pbft_state.add_prepare_vote(msg)
        
        if has_quorum and node.pbft_state.phase == PBFTPhase.PREPARE:
            print(f"[{current_time:.2f}s] Node {node.id} reached PREPARE quorum ")
            # Đủ 2f0+1 PREPARE votes → chuyển sang COMMIT phase
            node.pbft_state.start_commit()
            
            # Broadcast COMMIT message
            block = node.current_pbft_block  # Block đang được PBFT
            
            PBFTConsensus.broadcast_commit(node, block, msg.round_num, current_time + p.T_commit_timeout)
            
            return True
        
        return False
    
    @staticmethod
    def handle_commit_message(node, msg, current_time):
        """
        handle COMMIT message received
        """
        # Handle Byzantine behavior detection
        # Verify signature
        if not msg.verify():
            print(f"[DETECTION] Node {node.id} detected invalid COMMIT signature from Node {msg.sender_id}")
            ByzantineStatistics.record_invalid_signature()
            return False
        
        # Detect equivocation
        if msg.block_hash in node.pbft_state.commit_votes:
            if msg.sender_id in node.pbft_state.commit_votes[msg.block_hash]:
                # Already voted for this block
                return False
        
        # Check if sender already voted for DIFFERENT block (equivocation)
        for block_hash, voters in node.pbft_state.commit_votes.items():
            if block_hash != msg.block_hash and msg.sender_id in voters:
                print(f"[DETECTION] Node {node.id} detected EQUIVOCATION from Node {msg.sender_id}")
                ByzantineStatistics.record_equivocation()
                # Ignore this message
                return False
            
        if not hasattr(node, 'pbft_state'):
            return False
        
        # Add vote và check nếu đủ quorum
        has_quorum = node.pbft_state.add_commit_vote(msg)
        
        if has_quorum and node.pbft_state.phase == PBFTPhase.COMMIT:
            # Đủ 2f0+1 COMMIT votes → FINALIZE block
            node.pbft_state.finalize()
            return True
        
        return False

class PBFTStatistics:
    """
    Track PBFT statistics cho analysis
    """
    total_pbft_rounds = 0
    successful_pbft = 0
    failed_pbft = 0
    prepare_messages = 0
    commit_messages = 0
    equivocations_detected = 0
    successful_rounds=0
    failed_rounds=0
    @staticmethod
    def reset():
        """Reset PBFT statistics for new experiment"""
        PBFTStatistics.prepare_messages = 0
        PBFTStatistics.commit_messages = 0
        PBFTStatistics.successful_rounds = 0
        PBFTStatistics.failed_rounds = 0

    @staticmethod
    def record_success():
        PBFTStatistics.total_pbft_rounds += 1
        PBFTStatistics.successful_pbft += 1
    
    @staticmethod
    def record_failure():
        PBFTStatistics.total_pbft_rounds += 1
        PBFTStatistics.failed_pbft += 1
        
    def get_success_rate():
        """Calculate PBFT success rate"""
        total = PBFTStatistics.successful_rounds + PBFTStatistics.failed_rounds
        if total == 0:
            return 0.0
        return (PBFTStatistics.successful_rounds / total) * 100
    
    @staticmethod
    def reset():
        PBFTStatistics.total_pbft_rounds = 0
        PBFTStatistics.successful_pbft = 0
        PBFTStatistics.failed_pbft = 0
        PBFTStatistics.prepare_messages = 0
        PBFTStatistics.commit_messages = 0
        PBFTStatistics.equivocations_detected = 0
