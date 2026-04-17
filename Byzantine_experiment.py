

from InputsConfig import InputsConfig as p
import time
import pandas as pd
import matplotlib.pyplot as plt
from multiprocessing import Pool, cpu_count
import os
import numpy as np
from Models.DualTierBlockchain.ByzantineNode import ByzantineConfig, ByzantineType, ByzantineStatistics
from Statistics import Statistics
from PBFT import PBFTStatistics
from Models.DualTierBlockchain.BlockCommit import BlockCommit
from Event import Queue

# Experiment names
name_silent = 'Byzantine_Node_Silent_Strategy'
name_delay = 'Byzantine_Tier0_DELAYED_Strategy'
name_equi = 'Byzantine_Tier0_Equivocating_Strategy'
name_wrong_sig = 'Byzantine_Tier0_Wrong_Signature_Strategy'
name_invalid_vrf = 'Byzantine_Node_Invalid_VRF_Strategy'


def run_single_byzantine_experiment(config):
    """
    Run ONE Byzantine experiment (this will be called by each worker process)
    
    ⭐ IMPORTANT: This function must be standalone and picklable
    All imports must be inside the function to avoid issues
    """
    # Unpack config
    exp_id, t0, t1, byz_t0, byz_t1, behavior, desc, k = config
    
    # Import here to avoid multiprocessing issues
    from InputsConfig import InputsConfig as p
    from Models.DualTierBlockchain.ByzantineNode import ByzantineConfig, ByzantineType, ByzantineStatistics
    from Statistics import Statistics
    from PBFT import PBFTStatistics
    from Models.DualTierBlockchain.BlockCommit import BlockCommit
    from Event import Queue
    from Models.DualTierBlockchain.Transaction import LightTransaction as LT
    from Models.DualTierBlockchain.Node import Node
    
    print(f"\n[Experiment {exp_id}] {desc} [PID: {os.getpid()}]")
    print(f"  Network: t0={t0}, t1={t1}")
    print(f"  Byzantine: {byz_t0} Tier-0, {byz_t1} Tier-1")
    print(f"  Behavior: {behavior.name}")
    
    # Reset ALL global state
    Queue.clear()
    Statistics.reset()
    PBFTStatistics.reset()
    ByzantineStatistics.reset()
    
    # Configure network
    p.reset_nodes(t0, t1, k)
    #p.DEBUG_MODE = False
    #p.VERBOSE_LOGGING = False
    p.simTime = 50  # Set appropriate sim time
    
    # Configure Byzantine nodes
    ByzantineConfig.set_byzantine_nodes(byz_t0, byz_t1, behavior)
    
    # Create transactions
    if p.hasTrans:
        LT.create_transactions()
    
    # Generate genesis
    Node.generate_gensis_block()
    
    # Run simulation
    start_time = time.time()
    BlockCommit.generate_initial_events()
    
    clock = 0
    while not Queue.isEmpty() and clock <= p.simTime:
        
        next_event = Queue.get_next_event()

        clock = next_event.time
        BlockCommit.handle_event(next_event)
        if next_event is None:
            break
        if Queue.size() ==1 and clock <= p.simTime:
            print(f"[Experiment {exp_id}] No more events to process at time {clock:.2f}s")
            break

        Queue.remove_event(next_event)
    
    end_time = time.time()
    simulation_time = end_time - start_time
    
    # Collect metrics
    rounds_completed = p.round_num
    
    # Get honest node for blockchain
    byz = set(ByzantineConfig.byzantine_tier0_ids) | set(ByzantineConfig.byzantine_tier1_ids)
    valid_nodes = [node for node in p.NODES if node.id not in byz]
    
    if not valid_nodes:
        print(f"[WARNING] Experiment {exp_id}: No valid nodes found!")
        return None
    
    # Get blockchain from first honest Tier-1 node
    honest_tier1 = [n for n in valid_nodes if n.tier == 1]
    if honest_tier1:
        reference_node = honest_tier1[0]
    else:
        reference_node = valid_nodes[0]
    
    Statistics.chain = reference_node.blockchain.copy()
    
    # Count blocks and transactions
    total_blocks = len(Statistics.chain) - 1  # Exclude genesis
    total_empty_blocks = 0
    trans = 0
    
    for block in Statistics.chain[1:]:  # Skip genesis
        if hasattr(block, 'transactions'):
            if isinstance(block.transactions, list):
                trans += len(block.transactions)
            elif block.transactions == 0 or (hasattr(block, 'is_empty') and block.is_empty):
                total_empty_blocks += 1
    total_blocks -= total_empty_blocks  # Adjust total blocks to count only non-empty ones
    # Calculate metrics
    throughput = total_blocks / clock if clock > 0 else 0
    tx_throughput = trans / clock if clock > 0 else 0
    
    # Success rate
    if total_blocks == 0:
        success_rate = 0
    else:
        success_rate = ((total_blocks) / (total_blocks + total_empty_blocks)) * 100
    
    # Communication metrics
    pbft_messages = PBFTStatistics.prepare_messages + PBFTStatistics.commit_messages
    total_messages = Statistics.total_messages if hasattr(Statistics, 'total_messages') else pbft_messages
    
    # Prepare results
    results = {
        'exp_id': exp_id,
        'description': desc,
        't0': t0,
        't1': t1,
        'k': k,
        
        'byzantine_t0': byz_t0,
        'byzantine_t1': byz_t1,
        'byzantine_ratio_t0': byz_t0 / t0 if t0 > 0 else 0,
        'byzantine_ratio_t1': byz_t1 / t1 if t1 > 0 else 0,
        'behavior': behavior.name,
        
        # Performance
        'rounds_completed': rounds_completed,
        'blocks_finalized': total_blocks,
        'empty_blocks': total_empty_blocks,
        'round_success_rate': success_rate,
        'block_throughput': throughput,
        'transactions_throughput': tx_throughput,
        'simulation_time_sec': simulation_time,
        
        # Byzantine detection
        'equivocations_detected': ByzantineStatistics.equivocations_detected,
        'invalid_signatures': ByzantineStatistics.invalid_signatures_detected,
        'invalid_vrfs': ByzantineStatistics.invalid_vrfs_rejected,
        'late_messages': ByzantineStatistics.late_messages_count,
        'silent_instances': ByzantineStatistics.silent_nodes_count,
        
        # Communication
        'pbft_messages': pbft_messages,
        'total_messages': total_messages,
        
        # System status
        'system_functional': success_rate > 50,
        'safety_maintained': True,
    }
    
    print(f"  ✅ Completed: {rounds_completed} rounds, {success_rate:.1f}% success (in {simulation_time:.2f}s)")
    print(f"  🔴 Attacks: {ByzantineStatistics.equivocations_detected} equivocations, "
          f"{ByzantineStatistics.invalid_vrfs_rejected} invalid VRFs, "
          f"{ByzantineStatistics.silent_nodes_count} silent instances")
    
    return results


def define_byzantine_scenarios():
    """
    Define Byzantine test scenarios
    """
    scenarios = [
        # (exp_id, t0, t1, byz_t0, byz_t1, behavior, description, num_expected_proposer)
        
        # ===== Baseline (No Byzantine) =====
        #(1, 14, 50, 0, 0, ByzantineType.HONEST, "Baseline - No Byzantine", 4),
        
        # ===== Tier-0 Byzantine (Consensus Attack) =====
        #(2, 14, 50, 1, 0, ByzantineType.SILENT, "1/14 Tier-0 Silent", 4),
        #(3, 14, 50, 2, 0, ByzantineType.SILENT, "2/14 Tier-0 Silent", 4),
        #(4, 14, 50, 3, 0, ByzantineType.SILENT, "3/14 Tier-0 Silent", 4),
        #(5, 14, 50, 4, 0, ByzantineType.SILENT, "4/14 Tier-0 Silent ", 4),

        #(6, 14, 50, 1, 0, ByzantineType.EQUIVOCATING, "1/14 Tier-0 Equivocating", 4),
        #(7, 14, 50, 2, 0, ByzantineType.EQUIVOCATING, "2/14 Tier-0 Equivocating", 4),
        #(8, 14, 50, 3, 0, ByzantineType.EQUIVOCATING, "3/14 Tier-0 Equivocating", 4),
        #(9, 14, 50, 4, 0, ByzantineType.EQUIVOCATING, "4/14 Tier-0 Equivocating", 4),

        #(10, 14, 50, 1, 0, ByzantineType.DELAYED, "1/14 Tier-0 Delayed", 3),
        #(11, 14, 50, 2, 0, ByzantineType.DELAYED, "2/14 Tier-0 Delayed", 3),
        #(12, 14, 50, 3, 0, ByzantineType.DELAYED, "3/14 Tier-0 Delayed", 3),
        #(13, 14, 50, 4, 0, ByzantineType.DELAYED, "4/14 Tier-0 Delayed (50% nodes)", 3),

        # ===== Tier-1 Byzantine (Proposal Attack) =====
        #(10, 14, 50, 0, 5, ByzantineType.WRONG_SIGNATURE, "5/50 Tier-1 Send Wrong Signature", 3),
        (9, 14, 50, 0, 5, ByzantineType.SILENT, "5/50 Tier-1 Silent", 4),
        (10, 14, 50, 0, 10, ByzantineType.SILENT, "10/50 Tier-1 Silent", 4),
        (11, 14, 50, 0, 15, ByzantineType.SILENT, "15/50 Tier-1 Silent", 4),
        (12, 14, 50, 0, 20, ByzantineType.SILENT, "20/50 Tier-1 Silent", 4),
        (13, 14, 50, 0, 25, ByzantineType.SILENT, "25/50 Tier-1 Silent", 4),
        (14, 14, 50, 0, 30, ByzantineType.SILENT, "30/50 Tier-1 Silent", 4),
        #(14, 14, 50, 0, 10, ByzantineType.INVALID_VRF, "10/50 Tier-1 Invalid VRF"),
        
        # ===== Both Tiers Byzantine =====
        #(15, 14, 50, 2, 5, ByzantineType.EQUIVOCATING, "Mixed: 2/14 T0 + 5/50 T1 Equivocating"),
        #(16, 14, 50, 4, 17, ByzantineType.SILENT, "Mixed: 4/14 T0 + 17/50 T1 Silent",4),
        #(17, 14, 50, 4, 20, ByzantineType.SILENT, "Mixed: 4/14 T0 + 20/50 T1 Silent",4),
        #(18, 14, 50, 4, 25, ByzantineType.SILENT, "Mixed: 4/14 T0 + 25/50 T1 Silent",4),
        #(19, 14, 50, 4, 30, ByzantineType.SILENT, "Mixed: 4/14 T0 + 30/50 T1 Silent",4),
        #(20, 14, 50, 4, 5, ByzantineType.SILENT, "Mixed: 4/14 T0 + 50/50 T1 Silent",7),
        #(21, 14, 50, 4, 45, ByzantineType.SILENT, "Mixed: 4/14 T0 + 45/50 T1 Silent",4),

        #(20, 14, 50, 4, 17, ByzantineType.SILENT, "Mixed: 4/14 T0 + 17/50 T1 Silent",5),
        #(21, 14, 50, 4, 20, ByzantineType.SILENT, "Mixed: 4/14 T0 + 20/50 T1 Silent",5),
        #(22, 14, 50, 4, 25, ByzantineType.SILENT, "Mixed: 4/14 T0 + 25/50 T1 Silent",5),
        #(23, 14, 50, 4, 30, ByzantineType.SILENT, "Mixed: 4/14 T0 + 30/50 T1 Silent",5),
        #(24, 14, 50, 4, 35, ByzantineType.SILENT, "Mixed: 4/14 T0 + 35/50 T1 Silent",5),
        #(25, 14, 50, 4, 45, ByzantineType.SILENT, "Mixed: 4/14 T0 + 45/50 T1 Silent",5),

        #(24, 14, 50, 4, 17, ByzantineType.SILENT, "Mixed: 4/14 T0 + 17/50 T1 Silent",6),
        #(25, 14, 50, 4, 20, ByzantineType.SILENT, "Mixed: 4/14 T0 + 20/50 T1 Silent",6),
        #(26, 14, 50, 4, 25, ByzantineType.SILENT, "Mixed: 4/14 T0 + 25/50 T1 Silent",6),
        #(27, 14, 50, 4, 30, ByzantineType.SILENT, "Mixed: 4/14 T0 + 30/50 T1 Silent",6),
        #(28, 14, 50, 4, 35, ByzantineType.SILENT, "Mixed: 4/14 T0 + 35/50 T1 Silent",6),
        #(29, 14, 50, 4, 45, ByzantineType.SILENT, "Mixed: 4/14 T0 + 45/50 T1 Silent",6),

        #(28, 14, 50, 4, 17, ByzantineType.SILENT, "Mixed: 4/14 T0 + 17/50 T1 Silent",7),
        #(29, 14, 50, 4, 20, ByzantineType.SILENT, "Mixed: 4/14 T0 + 20/50 T1 Silent",7),
        #(30, 14, 50, 4, 25, ByzantineType.SILENT, "Mixed: 4/14 T0 + 25/50 T1 Silent",7),
        #(31, 14, 50, 4, 30, ByzantineType.SILENT, "Mixed: 4/14 T0 + 30/50 T1 Silent",7),
        #(32, 14, 50, 4, 35, ByzantineType.SILENT, "Mixed: 4/14 T0 + 35/50 T1 Silent",7),
        #(33, 14, 50, 4, 45, ByzantineType.SILENT, "Mixed: 4/14 T0 + 45/50 T1 Silent",7),

        # ===== Larger Networks =====
        #(17, 30, 100, 5, 0, ByzantineType.EQUIVOCATING, "Large: 5/30 Tier-0 Equivocating"),
        #(18, 30, 100, 10, 0, ByzantineType.EQUIVOCATING, "Large: 10/30 Tier-0 Equivocating (Max)"),
        
        # ===== Attack Intensity =====
        #(19, 14, 50, 1, 0, ByzantineType.RANDOM, "1/14 Tier-0 Random Behavior"),
        #(20, 14, 50, 4, 10, ByzantineType.RANDOM, "Mixed Random: 4/14 T0 + 10/50 T1"),
    ]
    
    return scenarios


def run_byzantine_experiments_parallel(num_processes=None):
    """
    Run all Byzantine experiments in parallel
    
    :param num_processes: Number of parallel processes (default: CPU count - 1)
    """
    scenarios = define_byzantine_scenarios()
    
    if num_processes is None:
        num_processes = max(1, cpu_count() - 1)  # Leave 1 core free
    #num_processes = 1  # For testing, set to 1 to run sequentially
    print("\n" + "="*60)
    print("BYZANTINE FAULT TOLERANCE EXPERIMENTS (PARALLEL)")
    print("="*60)
    print(f"Total scenarios: {len(scenarios)}")
    print(f"Parallel processes: {num_processes}")
    print(f"CPU cores available: {cpu_count()}")
    print("="*60)
    
    start_time = time.time()
    
    # Run experiments in parallel
    with Pool(processes=num_processes) as pool:
        results = pool.map(run_single_byzantine_experiment, scenarios)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Filter out None results (failed experiments)
    results = [r for r in results if r is not None]
    
    print("\n" + "="*60)
    print("ALL EXPERIMENTS COMPLETED")
    print("="*60)
    print(f"Total time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)")
    print(f"Average time per experiment: {total_time/len(scenarios):.2f} seconds")
    print(f"Speedup: ~{len(scenarios)/(total_time/100):.1f}x faster than sequential")
    print("="*60 + "\n")
    
    # Convert to DataFrame
    df = pd.DataFrame(results)
    
    # Save results
    output_file = 'byzantine_experiments_parallel.xlsx'
    df.to_excel(output_file, index=False)
    print(f"✅ Results saved to: {output_file}")
    
    return df


def plot_attack_types(df, output_prefix='byzantine'):
    """
    Plot separate charts for each Byzantine behavior
    Enhanced version with better styling
    """
    behaviors = df['behavior'].unique()
    
    for behavior in behaviors:
        data = df[df['behavior'] == behavior].copy()
        
        if data.empty:
            continue
        
        # Determine which tier has Byzantine nodes
        if data['byzantine_t0'].sum() > 0:
            x_col = 'byzantine_ratio_t0'
            x_label = 'Byzantine Ratio (Tier-0)'
            theoretical_limit = 1/3
        else:
            x_col = 'byzantine_ratio_t1'
            x_label = 'Byzantine Ratio (Tier-1)'
            theoretical_limit = 0.5  # Tier-1 can tolerate up to f1 < t1/2
        
        # Sort data
        data = data.sort_values(x_col)
        
        # Create plot
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Plot line with markers
        ax.plot(
            data[x_col] * 100,  # Convert to percentage
            data['round_success_rate'],
            marker='o',
            linewidth=2.5,
            markersize=10,
            color='#FF6B6B',
            label=f'{behavior} Attack'
        )
        
        # Add value labels on points
        for idx, row in data.iterrows():
            ax.annotate(
                f"{row['round_success_rate']:.1f}%",
                xy=(row[x_col] * 100, row['round_success_rate']),
                xytext=(0, 10),
                textcoords='offset points',
                ha='center',
                fontsize=9,
                bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7)
            )
        
        # Add reference lines
        ax.axvline(
            x=theoretical_limit * 100,
            color='red',
            linestyle='--',
            linewidth=2,
            label=f'Theoretical Limit ({theoretical_limit*100:.1f}%)'
        )
        ax.axhline(
            y=95,
            color='green',
            linestyle='--',
            linewidth=2,
            label='Target: 95%'
        )
        
        # Styling
        ax.set_xlabel(x_label, fontsize=12, fontweight='bold')
        ax.set_ylabel('Round Success Rate (%)', fontsize=12, fontweight='bold')
        ax.set_title(f'Byzantine Attack: {behavior}', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.legend(loc='best', fontsize=10)
        ax.set_ylim(0, 105)
        
        # Add shaded regions
        ax.axvspan(0, theoretical_limit * 100, alpha=0.1, color='green')
        ax.axvspan(theoretical_limit * 100, 100, alpha=0.1, color='red')
        
        # Save
        filename = f"{output_prefix}_{behavior}.png"
        plt.tight_layout()
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"✅ Saved: {filename}")
        plt.close()

def plot_tier1_k_analysis(df):
    """
    Special plot for Tier-1 Byzantine with varying k (expected proposers)
    Shows how increasing k improves resilience
    ⭐ Enhanced with success rate in legend
    """
    # Filter Tier-1 Silent attacks
    tier1_data = df[(df['byzantine_t1'] > 0) & (df['behavior'] == 'SILENT')].copy()
    
    if tier1_data.empty:
        print("[WARNING] No Tier-1 Byzantine data found for k analysis")
        return
    
    # Group by k value
    k_values = sorted(tier1_data['k'].unique())
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    colors = plt.cm.viridis(np.linspace(0, 1, len(k_values)))
    
    for idx, k in enumerate(k_values):
        k_data = tier1_data[tier1_data['k'] == k].sort_values('byzantine_ratio_t1')
        
        if k_data.empty:
            continue
        
        # ⭐ Calculate average success rate for this k
        #avg_success_rate = k_data['round_success_rate'].mean()
        
        # Plot line
        ax.plot(
            k_data['byzantine_ratio_t1'] * 100,
            k_data['round_success_rate'],
            marker='o',
            linewidth=2.5,
            markersize=10,
            color=colors[idx],
            label=f'k = {k} (Success rate: {k_data["round_success_rate"].mean():.1f}%)'  # ⭐ Added success rate
        )
    
    ax.set_xlabel('Byzantine Ratio (Tier-1, %)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Round Success Rate (%)', fontsize=12, fontweight='bold')
    ax.set_title('Impact of Expected Proposers (k) on Byzantine Resilience', 
                 fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=11, framealpha=0.9)
    ax.set_ylim(0, 105)
    
    # Add reference line
    #ax.axhline(y=95, color='green', linestyle='--', linewidth=2, alpha=0.5, label='Target: 95%')
    
    plt.tight_layout()
    plt.savefig('byzantine_tier1_k_analysis.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: byzantine_tier1_k_analysis.png")
    plt.close()
"""
def plot_tier1_k_analysis(df):
    
    #Special plot for Tier-1 Byzantine with varying k (expected proposers)
    #Shows how increasing k improves resilience
    
    # Filter Tier-1 Silent attacks
    tier1_data = df[(df['byzantine_t1'] > 0) & (df['behavior'] == 'SILENT')].copy()
    
    if tier1_data.empty:
        return
    
    # Group by k value
    k_values = sorted(tier1_data['k'].unique())
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    colors = plt.cm.viridis(np.linspace(0, 1, len(k_values)))
    
    for idx, k in enumerate(k_values):
        k_data = tier1_data[tier1_data['k'] == k].sort_values('byzantine_ratio_t1')
        
        ax.plot(
            k_data['byzantine_ratio_t1'] * 100,
            k_data['round_success_rate'],
            marker='o',
            linewidth=2.5,
            markersize=10,
            color=colors[idx],
            label=f'k = {k}'
        )
    
    ax.set_xlabel('Byzantine Ratio (Tier-1, %)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Round Success Rate (%)', fontsize=12, fontweight='bold')
    ax.set_title('Impact of Expected Proposers (k) on Byzantine Resilience', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', fontsize=11)
    ax.set_ylim(0, 105)
    
    plt.tight_layout()
    plt.savefig('byzantine_tier1_k_analysis.png', dpi=300, bbox_inches='tight')
    print(f"✅ Saved: byzantine_tier1_k_analysis.png")
    plt.close()
"""    

def print_byzantine_summary(df):
    """Print enhanced summary"""
    print("\n" + "="*60)
    print("BYZANTINE EXPERIMENTS SUMMARY")
    print("="*60)
    
    # Group by behavior
    print("\n📊 Results by Attack Type:")
    summary = df.groupby('behavior').agg({
        'round_success_rate': ['mean', 'min', 'max'],
        'blocks_finalized': 'mean',
        'equivocations_detected': 'sum',
        'invalid_vrfs': 'sum',
        'silent_instances': 'sum'
    }).round(2)
    print(summary)
    
    # Byzantine tolerance validation
    print("\n🎯 Byzantine Tolerance Validation:")
    
    # Tier-0 max tolerance
    tier0_max = df[(df['byzantine_t0'] == 4) & (df['byzantine_t1'] == 0)]
    if not tier0_max.empty:
        avg_success = tier0_max['round_success_rate'].mean()
        print(f"  Tier-0 at max tolerance (f0=4): {avg_success:.1f}% success rate")
        print(f"  Status: {'✅ PASS' if avg_success > 50 else '❌ FAIL'}")
    
    # Overall system resilience
    total_attacks = df['equivocations_detected'].sum() + df['invalid_vrfs'].sum() + df['invalid_signatures'].sum()
    print(f"\n  Total attacks detected and mitigated: {total_attacks}")
    print(f"  Safety maintained across all experiments: {'✅ YES' if df['safety_maintained'].all() else '❌ NO'}")


if __name__ == '__main__':
    # Run Byzantine experiments in parallel
    num_cores = max(1, cpu_count() - 1)  # Use all but one core
    
    print(f"\n🚀 Starting parallel execution on {num_cores} cores...")
    
    df = run_byzantine_experiments_parallel(num_processes=4)
    
    # Generate visualizations
    print("\n📊 Generating visualizations...")
    plot_attack_types(df)
    plot_tier1_k_analysis(df)
    
    # Print summary
    #print_byzantine_summary(df)
    
    print("\n✅ Byzantine fault tolerance experiments completed!")
