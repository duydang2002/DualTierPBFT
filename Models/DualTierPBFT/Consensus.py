import numpy as np
from InputsConfig import InputsConfig as p
from Models.DualTierBlockchain.Node import Node
from Models.Consensus import Consensus as BaseConsensus
from Models.DualTierBlockchain.ECVRF import ECVRF 
import random
import hashlib

#from ImportClasses import Node
class Consensus(BaseConsensus):

    # Phase A: Kiểm tra xem Node Tier-1 có được quyền đề xuất không
    def check_vrf_threshold(node):
        # p_prob = T / 2^B như trong ảnh (xác suất trở thành proposer)
        vrf = ECVRF()
        seed_r = node.seed.encode("utf-8") + node.round.to_bytes(1,"big") 
        vrf_value, proof = vrf.prove(node.sk, seed_r)
        vrf_int = int.from_bytes(vrf_value, byteorder="big")
        if vrf_int <= p.T:
            return vrf_value, proof
        return 0,0

    # Phase C: Tier-0 chọn block có VRF nhỏ nhất
    def select_best_proposal(proposals):
        if not proposals:
            return None
        # Chọn block có VRF thấp nhất (min VRF random value)
        return min(proposals, key=lambda x: int.from_bytes(x['vrf'], byteorder="big"))


    def generate_new_seed(old_seed, round_number, winner_vrf=None):
        """
        - Nếu PBFT thành công: seed_r = VRF của winner
        - Nếu PBFT thất bại: seed_r = Hash(seed_{r-1} || r)
        """
        if winner_vrf is not None:
            # PBFT thành công
            new_seed = winner_vrf
        else:
            # PBFT thất bại hoặc empty block
            hash_input = f"{old_seed}||{round_number}"
            new_seed = hashlib.sha256(hash_input.encode()).digest()
            #new_seed = int(hash_output[:8], 16)
        return new_seed