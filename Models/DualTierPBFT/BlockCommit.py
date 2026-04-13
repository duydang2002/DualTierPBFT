from Scheduler import Scheduler
from InputsConfig import InputsConfig as p
from Models.DualTierBlockchain.Node import Node
from Statistics import Statistics
from Models.DualTierBlockchain.Transaction import LightTransaction as LT, FullTransaction as FT
from Models.Network import Network
from Models.DualTierBlockchain.Consensus import Consensus as c
from Models.DualTierBlockchain.ByzantineNode import ByzantineConfig, ByzantineType, ByzantineStatistics
from Models.BlockCommit import BlockCommit as BaseBlockCommit
from PBFT import PBFTConsensus, PBFTStatistics, PBFTPhase
from Event import Event,Queue
import time


class BlockCommit(BaseBlockCommit):

   # 1. Quản lý các loại sự kiện
    def handle_event(event):
        """Main event dispatcher"""
        if event.type == "create_block":
            # Tier-1 tạo block proposal
            BlockCommit.generate_proposal(event)
            
        elif event.type == "propose_block":
            # Tier-0 nhận block proposal từ Tier-1
            BlockCommit.receive_proposal(event)
            
        elif event.type == "start_pbft":
            # Timeout xong, bắt đầu PBFT trên block tốt nhất
            BlockCommit.start_pbft(event)
            
        elif event.type == "pbft_prepare":
            # Tier-0 nhận PREPARE message
            BlockCommit.handle_prepare(event)
            
        elif event.type == "pbft_commit":
            # Tier-0 nhận COMMIT message
            BlockCommit.handle_commit(event)

        elif event.type == "receive_finalized":
            BlockCommit.receive_finalized_block(event)

        elif event.type == "no_proposer_timeout":
            BlockCommit.handle_no_proposer(event)

        elif event.type == "pbft_timeout":
            # PBFT timeout - fallback sang VRF tiếp theo
            BlockCommit.handle_pbft_timeout(event)

    # 2. Khởi tạo vòng chạy đầu tiên (Phase A)
    def generate_initial_events():
        p.count_proposer_index   = 0
        """
        Khởi tạo vòng đầu tiên
        Mỗi Tier-1 node check VRF threshold
        """
        currentTime = 0
        p.proposer_found_in_round  = 0
        for node in p.NODES:
            if node.tier == 1:
                # Check nếu node này là proposer
                vrf_value, vrf_proof = c.check_vrf_threshold(
                    node
                )
                
                if vrf_value != 0:  # VRF <= threshold
                    
                    # Schedule block creation
                    Scheduler.create_block_event(
                        node, 
                        currentTime, 
                        vrf_value, 
                        vrf_proof
                    )
                    p.proposer_found_in_round +=1
                    print(f"[{currentTime:.2f}s] Round {p.round_num}] Node {node.id} (Tier-1) selected as proposer")

        if p.proposer_found_in_round  == 0:
            print(f"[{currentTime:.2f}s] Round {p.round_num}] ⚠️ NO PROPOSERS FOUND - Scheduling empty block")
            p.no_proposer_found+=1
            # Schedule timeout event để Tier-0 send empty block
            for tier0_node in p.NODES :
                if tier0_node.tier == 0:
                # Mỗi Tier-0 node schedule một empty block event
                    #Scheduler.no_proposer_timeout_event(tier0_node, currentTime + p.T_timeout)
                    BlockCommit.send_empty_block(tier0_node, currentTime + p.T_timeout)

        # 3. Phase B: Tier-1 tạo nội dung Block và gửi đi
    def generate_proposal(event):
        miner = p.NODES[event.node]
        eventTime = event.time
        vrf_value = event.vrf_value # VRF được truyền từ sự kiện
        vrf_proof = event.vrf_proof
        #byzantine_silent = False
                # Check if proposer is Byzantine
        if ByzantineConfig.is_byzantine(miner.id):
            behavior = ByzantineConfig.get_behavior(miner.id)
            
            # SILENT: Don't propose
            if behavior == ByzantineType.SILENT:
                print(f"[BYZANTINE] Node {miner.id} (SILENT) - Not proposing block")
                ByzantineStatistics.record_silent_node()
                
                if Queue.size() == 1:
                    for tier0_node in p.NODES :
                        if tier0_node.tier == 0:
                        # Mỗi Tier-0 node schedule một empty block event
                            Scheduler.no_proposer_timeout_event(tier0_node, eventTime + p.T_timeout)
                            #BlockCommit.send_empty_block(tier0_node, eventTime + p.T_timeout)
                    return
                return
                
                
            
            # INVALID_VRF: Send invalid VRF proof
            elif behavior == ByzantineType.INVALID_VRF:
                print(f"[BYZANTINE] Node {miner.id} (INVALID_VRF) - Sending corrupted VRF")
                vrf_proof = b"INVALID_PROOF"
                ByzantineStatistics.record_invalid_vrf()
            
            # DELAYED: Will propose late
            elif behavior == ByzantineType.DELAYED:
                print(f"[BYZANTINE] Node {miner.id} (DELAYED) - Delaying proposal")
                eventTime += p.T_timeout * ByzantineConfig.delay_factor
                
        # Thực thi giao dịch để đưa vào block
        if p.hasTrans:
            if p.Ttechnique == "Light": 
                p.count_proposer_index  += 1
                blockTrans, blockSize = LT.execute_transactions(p.proposer_found_in_round, p.count_proposer_index)
            elif p.Ttechnique == "Full": 
                blockTrans, blockSize = FT.execute_transactions(miner, eventTime)
            
            event.block.transactions = blockTrans
            #event.block.usedgas = blockSize
            if blockTrans == []:
                print("No transactions appear yet")

                create_block_found = False
                new_list = []

                # Bỏ qua các create block event của các proposer khác
                for e in Queue.event_list:
                    if e.type == 'create_block':
                        if not create_block_found:
                            new_list.append(e)
                            create_block_found = True
                        
                    else:
                        new_list.append(e)

                Queue.event_list = new_list

                for tier0_node in p.NODES :
                    if tier0_node.tier == 0:
                    # Mỗi Tier-0 node schedule một empty block event
                        Scheduler.no_proposer_timeout_event(tier0_node, eventTime + p.T_timeout)
                        #BlockCommit.send_empty_block(tier0_node, eventTime + p.T_timeout)
                return
        
        #Statistics.totalBlocks += 1 # Thống kê số block được đề xuất
        
        # Gửi block này tới toàn bộ các node Tier-0 (Bộ/Ngành)
        BlockCommit.send_to_tier0(event.block, vrf_proof, eventTime)

    def send_to_tier0(block, vrf_proof, eventTime):
        for recipient in p.NODES:
            if recipient.tier == 0:
                Statistics.messages+=1
                # Tính độ trễ mạng từ tỉnh tới bộ
                delay = Network.block_prop_delay() 
                Scheduler.propose_block_event(recipient, block, vrf_proof, delay, eventTime)

    # 4. Phase B (tiếp): Tier-0 nhận đề xuất và chờ đợi
    
    def receive_proposal(event):
        # Node nhận được proposer
        node = p.NODES[event.node] # Node Tier-0
        if node.tier != 0:
            return
    
        from Models.DualTierBlockchain.ECVRF import ECVRF
        vrf = ECVRF()

        # Get proposer's public key
        proposer = p.NODES[event.block.miner]
        seed_r = node.seed.encode("utf-8") + node.round.to_bytes(1, "big")

        if not vrf.verify(proposer.pk, seed_r, event.vrf_value, event.vrf_proof):
            print(f"[WARNING] Node {node.id} rejected invalid VRF from {proposer.id}")
            if ByzantineConfig.is_byzantine(proposer.id):
                #print(f"    → Confirmed: Node {proposer.id} is Byzantine ({ByzantineConfig.get_behavior(proposer.id).name})")
                ByzantineStatistics.record_invalid_vrf()
                if Queue.size() == 1:
                    for tier0_node in p.NODES :
                        if tier0_node.tier == 0:
                        # Mỗi Tier-0 node schedule một empty block event
                            Scheduler.no_proposer_timeout_event(tier0_node, event.time + p.T_timeout)
                            #BlockCommit.send_empty_block(tier0_node, eventTime + p.T_timeout)
            return
        

        node.received_proposals.append({
            'block': event.block,
            'vrf': event.vrf_value,
            'proof': event.vrf_proof,
            'proposer_id': event.block.miner,
            'received_time' : event.time
        })
        if p.debug == True:
            print(f"[{event.time:.2f}s] Node {node.id} (Tier-0) received proposal from Node {proposer.id}")

        if len(node.received_proposals) == 1:
            Scheduler.start_pbft_event(
                node, 
                event.start_pbft_time
            )


    # 5. Phase C: PBFT
    def start_pbft(event):
        """
        Timeout hết, bắt đầu PBFT trên block tốt nhất
        """
        node = p.NODES[event.node]
        
        if node.tier != 0:
            return
        
        # Chọn proposal với VRF nhỏ nhất
        best_proposal = node.get_next_valid_proposal()
        
        if not best_proposal:
            print(f"[{event.time:.2f}s] Node {node.id} - No valid proposals, sending empty block")
            #Statistics.messages+=1
            BlockCommit.send_empty_block(node, event.time + p.T_timeout)
            return
        
        if p.debug == True: print(f"[{event.time:.2f}s] Node {node.id} starting PBFT on block from Node {best_proposal['proposer_id']}")
        
        # Bắt đầu PBFT
        node.start_pbft_on_block(
            best_proposal['block'],
            best_proposal['vrf'],
            p.round_num,
            event.time + p.T_prepare_timeout
        )
        
        # Set PBFT timeout
        Scheduler.pbft_timeout_event(
            node,
            event.time + p.pbft_timeout
        )

    ################################################################
    # 6. PBFT Message Handlers
    ################################################################
    
    def handle_prepare(event):
        """
        Xử lý PREPARE message
        """
        node = p.NODES[event.node]
        msg = event.message
        
        if node.tier != 0:
            return
        
        # Chỉ xử lý PREPARE trong PREPARE phase (đảm bảo không xử lý message cũ hoặc ngoài phase)
        if node.pbft_state.phase != PBFTPhase.PREPARE:
            return
        
        if p.debug == True: print(f"[{event.time:.2f}s] Node {node.id} received PREPARE from Node {msg.sender_id}")
        
        #PBFTStatistics.prepare_messages += 1
        #Statistics.messages+=1
        # Process PREPARE message
        has_quorum = PBFTConsensus.handle_prepare_message(node, msg, event.time)
        
        if has_quorum:
            node.commit_msgs_sent += 1
            node.pbft_state.start_commit()

    def handle_commit(event):
        """
        Xử lý COMMIT message
        """
        from Event import Event, Queue
        node = p.NODES[event.node]
        msg = event.message

        if node.tier != 0:
            return
        
        # Chỉ xử lý COMMIT trong COMMIT phase
        if node.pbft_state.phase != PBFTPhase.COMMIT:
            return
        
        if p.debug == True: print(f"[{event.time:.2f}s] Node {node.id} received COMMIT from Node {msg.sender_id}")
        
        #PBFTStatistics.commit_messages += 1
        #Statistics.messages+=1
        # Process COMMIT message
        has_quorum = PBFTConsensus.handle_commit_message(node, msg, event.time)
        
        if has_quorum:
            print(f"[{event.time:.2f}s] ✅ Node {node.id} FINALIZED block from Node {node.current_pbft_block.miner}")
            
            # Finalize block
            finalized_block = node.finalize_block()
            
            # Record statistics
            #PBFTStatistics.record_success()
            Statistics.mainBlocks += 1
            
            # Broadcast finalized block + new seed tới Tier-1
            BlockCommit.broadcast_finalized_block(node, finalized_block, event.time)

    ################################################################
    # 7. PBFT Timeout & Fallback
    ################################################################
    
    def handle_pbft_timeout(event):
        """
        PBFT timeout - fallback sang proposal tiếp theo
        """
        node = p.NODES[event.node]
        
        if node.tier != 0:
            return
        
        # Check nếu PBFT đã finalize rồi thì ignore timeout
        if node.is_pbft_finalized():
            if Queue.size() == 1:
                BlockCommit.start_next_round(event.time)
            return
        
        print(f"[{event.time:.2f}s] ⚠️ Node {node.id} - PBFT TIMEOUT")
        
        # Mark current VRF as failed
        if node.current_pbft_block:
            current_vrf = node.pbft_state.current_vrf
            node.mark_vrf_failed(current_vrf)
            
            print(f"    → Marking VRF from Node {node.current_pbft_block.miner} as failed")
        
        # Record failure
        node.pbft_failure_count += 1
        #PBFTStatistics.record_failure()
        
        # Clear PBFT state
        node.pbft_state.reset()
        
        # Try next proposal
        next_proposal = node.get_next_valid_proposal()
        
        if next_proposal:
            print(f"    → Trying next proposal from Node {next_proposal['proposer_id']}")
            
            # Start PBFT on next proposal
            node.start_pbft_on_block(
                next_proposal['block'],
                next_proposal['vrf'],
                p.round_num,
                event.time
            )
            
            # Set new timeout
            Scheduler.pbft_timeout_event(
                node,
                event.time + p.pbft_timeout
            )
        else:
            # Hết proposals → send empty block
            print(f"    → No more proposals, sending empty block")
            BlockCommit.send_empty_block(node, event.time+ p.T_timeout)

    ################################################################
    # 8. Block Distribution & Round Management
    ################################################################

    def handle_no_proposer(event):
        BlockCommit.send_empty_block(event.node, event.time + p.T_timeout)

    def broadcast_finalized_block(node, block, currentTime):
        """
        Tier-0 broadcast finalized block + new seed tới Tier-1
        """
        # Generate new seed from winner's VRF
        new_seed = c.generate_new_seed(
            node.seed,
            node.round,
            winner_vrf=node.pbft_state.current_vrf
        )
        
        node.seed = str(new_seed)
        node.round +=1 

        if p.debug == True: print(f" Node {node.id} update New seed generated for next round: {new_seed} with {node.round}")
        # Broadcast tới Tier-1
        for recipient in p.NODES:
            if recipient.tier == 1:
                Statistics.messages+=1
                delay = Network.block_prop_delay()
                Scheduler.receive_finalized_block_event(
                    node,
                    recipient,
                    block,
                    (new_seed),
                    currentTime + delay
                )

    def send_empty_block(node, currentTime):
        """
        Gửi empty block khi không có proposal nào valid
        """
        from Models.DualTierBlockchain.Block import Block
        
        empty_block = Block()
        empty_block.miner = -1  # Indicate empty block
        empty_block.is_empty = True
        empty_block.previous = node.last_block().id
        empty_block.id = node.round 
        empty_block.block_hash = PBFTConsensus.compute_block_hash(empty_block)
        empty_block.seed = node.seed

        # Generate new seed by hashing
        new_seed = c.generate_new_seed(
            node.seed,
            node.round,
            winner_vrf=None  # No winner
        )
        

        node.seed = str(new_seed)
        node.round +=1 
        if p.debug == True: print(f" Node {node.id} update New seed generated for next round: {new_seed} with {node.round}")
        node.blockchain.append(empty_block)
        node.blocks += 1
        # Broadcast empty block
        for recipient in p.NODES:
            if recipient.tier == 1:
                Statistics.messages+=1
                delay = Network.block_prop_delay()
                Scheduler.receive_finalized_block_event(
                    node,
                    recipient,
                    empty_block,
                    new_seed,
                    currentTime + delay
                )
                
    def receive_finalized_block(event):
        """
        Tier-1 nhận finalized block từ Tier-0
        """
        sender = p.NODES[event.node]
        recipient = p.NODES[event.recipient]

        if recipient.done_finalized_block:
            #Statistics.messages+=1
            # If already done finalized and this is the last event -> next round
            if Queue.size() == 1:
                # Start next round
                BlockCommit.start_next_round(event.time)
                return
            else:
                return
        if recipient.tier != 1:
            return
        
        if sender.tier != 0:
            print(f"[WARNING] Node {recipient.id} rejected finalized block from non-Tier-0 node {sender.id}")
            return

        block_hash = event.block.block_hash
            # Initialize tracking if needed
        if block_hash not in recipient.finalized_confirmations:
            recipient.finalized_confirmations[block_hash] = set()
            recipient.pending_finalized_blocks[block_hash] = (event.block, event.new_seed)

        recipient.finalized_confirmations[block_hash].add(sender.id)
        confirmation_count = len(recipient.finalized_confirmations[block_hash])
        quorum = 2 * p.f0 + 1
        #if p.debug == True: print(f"[{event.time:.2f}s] Node {recipient.id} (Tier-1) received finalized block confirmation from Node {sender.id} ({confirmation_count}/{quorum})")

        #Statistics.messages+=1
        if confirmation_count >= quorum:
            #print(f"[{event.time:.2f}s] ✅ Node {recipient.id} (Tier-1) ACCEPTED finalized block (quorum reached: {confirmation_count}/{quorum})")
            
            # Get block and seed
            block, new_seed = recipient.pending_finalized_blocks[block_hash]
            
            # Add to blockchain
            recipient.blockchain.append(block)
            recipient.blocks += 1
            
            # Update seed for next round
            recipient.seed= str(new_seed)
            recipient.round += 1
            # Clear confirmations
            del recipient.finalized_confirmations[block_hash]
            del recipient.pending_finalized_blocks[block_hash]
            
            # Log acceptance
            #if p.debug == True: 
            #    print(f"    → Block from round {p.round_num} added to blockchain")
            #    print(f"    → Node {recipient.id} Seed updated for round {p.round_num + 1} with")
            recipient.done_finalized_block = True  # Mark that we've accepted a finalized block this round




    def start_next_round(currentTime):
        """
        Bắt đầu round mới
        """
        p.round_num += 1
        p.proposer_found_in_round  = 0
        p.count_proposer_index  = 0
        print(f"\n{'='*60}")
        print(f"Starting Round {p.round_num} at time {currentTime:.2f}s {Statistics.messages} , {PBFTStatistics.prepare_messages} , {PBFTStatistics.commit_messages}")
        print(f"{'='*60}\n")
        
        
        # Clear round state cho tất cả Tier-0 nodes
        for node in p.NODES:
            if node.tier == 0:
                #print(f"{node.seed}, {node.round}\n")
                node.clear_round_state()
                
        # Tier-1 nodes check VRF
        for node in p.NODES:
            if node.tier == 1:
                node.done_finalized_block = False  # Reset flag for new round
                #print(f"{node.seed}, {node.round}\n")
                vrf_value, vrf_proof = c.check_vrf_threshold(
                    node
                )
                
                if vrf_value != 0:
                    
                    Scheduler.create_block_event(
                        node,
                        currentTime,
                        vrf_value,
                        vrf_proof
                    )
                    p.proposer_found_in_round  += 1
                    print(f"[{currentTime:.2f}s] Round {p.round_num}] Node {node.id} (Tier-1) selected as proposer")
        
        if p.proposer_found_in_round  == 0:
            print(f"[{currentTime:.2f}s] Round {p.round_num}] ⚠️ NO PROPOSERS FOUND - Scheduling empty block")
            # Schedule timeout event để Tier-0 send empty block
            p.no_proposer_found+=1
            # Schedule timeout event để Tier-0 send empty block
            for tier0_node in p.NODES :
                if tier0_node.tier == 0:
                # Mỗi Tier-0 node schedule một empty block event
                    #Scheduler.no_proposer_timeout_event(tier0_node, currentTime + p.T_timeout)
                    BlockCommit.send_empty_block(tier0_node, currentTime + p.T_timeout)
                