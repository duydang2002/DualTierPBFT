from time import time

from InputsConfig import InputsConfig as p
import random
from Models.Block import Block
from Event import Event, Queue, EventPBFT
from PBFT import PBFTConsensus as pc
if p.model == 2:
    from Models.Ethereum.Block import Block
elif p.model == 3:
    from Models.AppendableBlock.Block import Block as AB
    from Models.AppendableBlock.Node import Node
elif p.model == 4:
    from Models.DualTierBlockchain.Block import Block
    from Models.DualTierBlockchain.Node import Node
else:
    from Models.Block import Block


class Scheduler:
    # Schedule a block creation event for a miner and add it to the event list
    def create_block_event(miner, eventTime,vrf, proof):
        eventType = "create_block"
        if eventTime <= p.simTime:
            # prepare attributes for the event
            block = Block()
            block.miner = miner.id
            block.depth = 0
            block.id = miner.last_block().id + 1
            block.previous = miner.last_block().id
            block.vrf_value = vrf
            block.seed = miner.seed
            block.block_hash = pc.compute_block_hash(block)
            event = Event(eventType, block.miner, eventTime,
                          block, vrf= vrf, proof= proof)  # create the event
            Queue.add_event(event)  # add the event to the queue

    # Schedule a block receiving event for a node and add it to the event list
    def receive_block_event(recipient, block, blockDelay):
        receive_block_time = block.timestamp + blockDelay
        if receive_block_time <= p.simTime:
            e = Event("receive_block", recipient.id, receive_block_time, block)
            Queue.add_event(e)

    # Schedule a block creation event for a gateway - AppendableBlock model
    def create_block_event_AB(node, eventTime, receiverGatewayId):
        eventType = "create_block"
        if eventTime <= p.simTime:
            # Populate event attributes
            block = AB()
            block.id = node.round
            block.timestamp = eventTime
            block.nodeId = node.id
            block.gatewayIds = node.gatewayIds
            block.receiverGatewayId = receiverGatewayId
            event = Event(eventType, node.id, eventTime, block)
            Queue.add_event(event)  # add the event to the queue

    # Schedule a create transaction list event for a gateway
    def append_tx_list_event(txList, gatewayId, tokenTime, eventTime):
        eventType = "append_tx_list"
        if eventTime <= p.simTime:
            block = AB()
            block.transactions = txList.copy()
            block.timestamp = tokenTime
            event = Event(eventType, gatewayId, eventTime, block)
            Queue.add_event(event)

    # Schedule a transaction list receiving event for a gateway
    def receive_tx_list_event(txList, gatewayId, tokenTime, eventTime):
        eventType = "receive_tx_list"
        if eventTime <= p.simTime:
            block = AB()
            block.transactions = txList.copy()
            block.timestamp = tokenTime
            event = Event(eventType, gatewayId, eventTime, block)
            Queue.add_event(event)

    
    def propose_block_event(recipient, block, vrf_proof, blockDelay, eventTime):
        receive_time = eventTime + blockDelay
        if receive_time <= p.simTime:
            e = EventPBFT(event_type="propose_block", node=recipient.id, time=receive_time, block=block, vrf_value=block.vrf_value, vrf_proof=vrf_proof, start_pbft_time = eventTime+p.T_timeout)
            Queue.add_event(e)
  
    def start_pbft_event(node, time):
        """
        Schedule event: Start PBFT 
        """
        event = EventPBFT(
            event_type="start_pbft",
            node=node.id,
            time=time
        )
        
        Queue.add_event(event)
    
    @staticmethod
    def pbft_prepare_event(node, message, time):
        """
        Schedule event: Node nhận PREPARE message
        """
        event = EventPBFT(
            event_type="pbft_prepare",
            node=node.id,
            time=time,
            message=message
        )
        
        Queue.add_event(event)
    
    def pbft_commit_event(node, message, time):
        """
        Schedule event: Node nhận COMMIT message
        """
        event = EventPBFT(
            event_type="pbft_commit",
            node=node.id,
            time=time,
            message=message
        )
        
        Queue.add_event(event)

    def pbft_timeout_event(node, time):
        """
        Schedule event: PBFT timeout - fallback mechanism
        """
        event = EventPBFT(
            event_type="pbft_timeout",
            node=node.id,
            time=time
        )
        
        Queue.add_event(event)
    
    ################################################################
    # Block Distribution Events
    ################################################################
    
    @staticmethod
    def receive_finalized_block_event(node, receive,block, new_seed, time):
        """
        Schedule event: Tier-1 nhận finalized block từ Tier-0
        """
        event = EventPBFT(
            event_type="receive_finalized",
            node=node.id,
            recipient = receive.id,
            time=time,
            block=block,
            new_seed=new_seed
        )
        Queue.add_event(event) 
    def no_proposer_timeout_event(node, time):
        """
        Schedule event: Không có proposer → Send empty block
        """
        event = EventPBFT(
            event_type="no_proposer_timeout",
            node=node,
            time=time
        )
        Queue.add_event(event)