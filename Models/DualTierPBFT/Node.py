from Models.DualTierBlockchain.Block import Block
from Models.Node import Node as BaseNode
from PBFT import PBFTState

#from InputsConfig import InputsConfig as p
#from Models.DualTierBlockchain.Consensus import Consensus as c
#from ImportClasses import Block
class Node(BaseNode):
    def __init__(self,id,tier, pk, sk, seed): #blockchain=[],transactionsPool=[],unclechain=[],blocks=0,balance=0,uncles=0,hashPower=0.0):

        """
        Initialize a Government Node.
        :param int id: unique id
        :param int tier: 0 for Tier-0 (Ministries), 1 for Tier-1 (Provinces)
        """
        super().__init__(id)#,blockchain,transactionsPool,blocks,balance)
        self.tier = tier
        self.pk = pk
        self.sk = sk
        self.seed = seed
        self.round = 0

        if self.tier == 0:
            # PBFT State Management
            self.pbft_state = PBFTState(id)
            self.current_pbft_block = None
            self.pbft_start_time = 0
            
            # Proposal Management
            self.received_proposals = []
            self.failed_vrfs = set()  # Track VRFs that failed PBFT
            self.current_round = 0
            
            # Statistics
            self.pbft_success_count = 0
            self.pbft_failure_count = 0
            self.prepare_msgs_sent = 0
            self.commit_msgs_sent = 0

        if self.tier == 1:
        # Track finalized block confirmations
            self.finalized_confirmations = {}  # {block_hash: set of sender_ids}
            self.pending_finalized_blocks = {}  # {block_hash: (block, seed)}
            self.done_finalized_block = False  # Flag to indicate if we've accepted a finalized block this round

    def generate_gensis_block():
        from InputsConfig import InputsConfig as p
        from Models.DualTierBlockchain.Consensus import Consensus as c
        #Generate seed for round 1 after create genesis block
        new_seed = c.generate_new_seed(p.seed_0, 0, winner_vrf=None)
        p.round_num+=1
        for node in p.NODES:
            node.blockchain.append(Block())
            node.seed = str(new_seed)
            node.round +=1

    def clear_round_state(self):
        """Reset state cho round mới"""
        if self.tier == 0:
            self.received_proposals = []
            self.pbft_state.reset()
            self.current_pbft_block = None
            self.pbft_start_time = 0

    def start_pbft_on_block(self, block, vrf_value, round_num, current_time):
        """
        Bắt đầu PBFT process trên một block
        """
        if self.tier != 0:
            return
        
        from PBFT import PBFTConsensus
        
        # Set up PBFT state
        block_hash = PBFTConsensus.compute_block_hash(block)
        self.pbft_state.start_prepare(block_hash, round_num, vrf_value)
        self.current_pbft_block = block
        self.pbft_start_time = current_time
        
        # Broadcast PREPARE message
        PBFTConsensus.broadcast_prepare(self, block, vrf_value, round_num, current_time)
        self.prepare_msgs_sent += 1

    def is_pbft_finalized(self):
        """Check if PBFT đã finalize"""
        if self.tier != 0:
            return False
        
        from PBFT import PBFTPhase
        return self.pbft_state.phase == PBFTPhase.FINALIZED

    def is_pbft_failed(self):
        """Check if PBFT đã fail"""
        if self.tier != 0:
            return False
        
        from PBFT import PBFTPhase
        return self.pbft_state.phase == PBFTPhase.FAILED

    def finalize_block(self):
        """
        Finalize block sau khi PBFT thành công
        """
        if self.tier != 0 or not self.current_pbft_block:
            return None
        
        # Add block to blockchain
        self.blockchain.append(self.current_pbft_block)
        self.blocks += 1
        
        # Update statistics
        self.pbft_success_count += 1
        
        # Return finalized block
        finalized_block = self.current_pbft_block
        
        # Clear state
        self.current_pbft_block = None
        
        return finalized_block

    def mark_vrf_failed(self, vrf_value):
        """
        Mark một VRF value đã fail PBFT (để fallback)
        """
        if self.tier == 0:
            self.failed_vrfs.add(vrf_value)

    def get_next_valid_proposal(self):
        """
        Lấy proposal có VRF nhỏ nhất chưa fail
        """
        if self.tier != 0:
            return None
        
        # Filter out failed VRFs
        valid_proposals = [
            p for p in self.received_proposals 
            if p['vrf'] not in self.failed_vrfs
        ]
        
        if not valid_proposals:
            return None
        
        # Return proposal với VRF nhỏ nhất
        return min(valid_proposals, key=lambda x: int.from_bytes(x['vrf'], byteorder="big"))

    ########################################################### 
    # Reset methods
    ###########################################################
    
    def resetState():
        from InputsConfig import InputsConfig as p
        for node in p.NODES:
            node.blockchain = []
            node.transactionsPool = []
            node.blocks = 0
            node.balance = 0
            
            if node.tier == 0:
                node.pbft_state.reset()
                node.received_proposals = []
                node.failed_vrfs = set()
                node.current_pbft_block = None
                node.pbft_start_time = 0
                node.pbft_success_count = 0
                node.pbft_failure_count = 0
                node.prepare_msgs_sent = 0
                node.commit_msgs_sent = 0
