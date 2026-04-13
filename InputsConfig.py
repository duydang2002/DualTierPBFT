from Models.DualTierBlockchain.ECVRF import ECVRF
class InputsConfig:

    """ Seclect the model to be simulated.
    0 : The base model
    1 : Bitcoin model
    2 : Ethereum model
    3 : AppendableBlock model
    """
    model = 4

    ''' Input configurations for the base model '''
    if model == 0:

        ''' Block Parameters '''
        Binterval = 600  # Average time (in seconds)for creating a block in the blockchain
        Bsize = 1.0  # The block size in MB
        Bdelay = 0.42  # average block propogation delay in seconds, #Ref: https://bitslog.wordpress.com/2016/04/28/uncle-mining-an-ethereum-consensus-protocol-flaw/
        Breward = 12.5  # Reward for mining a block

        ''' Transaction Parameters '''
        hasTrans = True  # True/False to enable/disable transactions in the simulator
        Ttechnique = "Light"  # Full/Light to specify the way of modelling transactions
        Tn = 10  # The rate of the number of transactions to be created per second
        # The average transaction propagation delay in seconds (Only if Full technique is used)
        Tdelay = 5.1
        Tfee = 0.000062  # The average transaction fee
        Tsize = 0.000546  # The average transaction size  in MB

        ''' Node Parameters '''
        Nn = 3  # the total number of nodes in the network
        NODES = []
        from Models.Node import Node
        # here as an example we define three nodes by assigning a unique id for each one
        NODES = [Node(id=0), Node(id=1)]

        ''' Simulation Parameters '''
        simTime = 1000  # the simulation length (in seconds)
        Runs = 2  # Number of simulation runs

    ''' Input configurations for Bitcoin model '''
    if model == 1:
        ''' Block Parameters '''
        Binterval = 600  # Average time (in seconds)for creating a block in the blockchain
        Bsize = 1.0  # The block size in MB
        Bdelay = 0.42  # average block propogation delay in seconds, #Ref: https://bitslog.wordpress.com/2016/04/28/uncle-mining-an-ethereum-consensus-protocol-flaw/
        Breward = 12.5  # Reward for mining a block

        ''' Transaction Parameters '''
        hasTrans = True  # True/False to enable/disable transactions in the simulator
        Ttechnique = "Light"  # Full/Light to specify the way of modelling transactions
        Tn = 10  # The rate of the number of transactions to be created per second
        # The average transaction propagation delay in seconds (Only if Full technique is used)
        Tdelay = 5.1
        Tfee = 0.000062  # The average transaction fee
        Tsize = 0.000546  # The average transaction size  in MB

        ''' Node Parameters '''
        Nn = 3  # the total number of nodes in the network
        NODES = []
        from Models.Bitcoin.Node import Node
        # here as an example we define three nodes by assigning a unique id for each one + % of hash (computing) power
        NODES = [Node(id=0, hashPower=50), Node(
            id=1, hashPower=20), Node(id=2, hashPower=30)]

        ''' Simulation Parameters '''
        simTime = 10000  # the simulation length (in seconds)
        Runs = 2  # Number of simulation runs

    ''' Input configurations for Ethereum model '''
    if model == 2:

        ''' Block Parameters '''
        Binterval = 12.42  # Average time (in seconds)for creating a block in the blockchain
        Bsize = 1.0  # The block size in MB
        Blimit = 8000000  # The block gas limit
        Bdelay = 6  # average block propogation delay in seconds, #Ref: https://bitslog.wordpress.com/2016/04/28/uncle-mining-an-ethereum-consensus-protocol-flaw/
        Breward = 2  # Reward for mining a block

        ''' Transaction Parameters '''
        hasTrans = True  # True/False to enable/disable transactions in the simulator
        Ttechnique = "Light"  # Full/Light to specify the way of modelling transactions
        Tn = 20  # The rate of the number of transactions to be created per second
        # The average transaction propagation delay in seconds (Only if Full technique is used)
        Tdelay = 3
        # The transaction fee in Ethereum is calculated as: UsedGas X GasPrice
        Tsize = 0.000546  # The average transaction size  in MB

        ''' Drawing the values for gas related attributes (UsedGas and GasPrice, CPUTime) from fitted distributions '''

        ''' Uncles Parameters '''
        hasUncles = True  # boolean variable to indicate use of uncle mechansim or not
        Buncles = 2  # maximum number of uncle blocks allowed per block
        Ugenerations = 7  # the depth in which an uncle can be included in a block
        Ureward = 0
        UIreward = Breward / 32  # Reward for including an uncle

        ''' Node Parameters '''
        Nn = 3  # the total number of nodes in the network
        NODES = []
        from Models.Ethereum.Node import Node
        # here as an example we define three nodes by assigning a unique id for each one + % of hash (computing) power
        NODES = [Node(id=0, hashPower=50), Node(
            id=1, hashPower=20), Node(id=2, hashPower=30)]

        ''' Simulation Parameters '''
        simTime = 500  # the simulation length (in seconds)
        Runs = 2  # Number of simulation runs

        ''' Input configurations for AppendableBlock model '''
    if model == 3:
        ''' Transaction Parameters '''
        hasTrans = True  # True/False to enable/disable transactions in the simulator

        Ttechnique = "Full"

        # The rate of the number of transactions to be created per second
        Tn = 10

        # The maximum number of transactions that can be added into a transaction list
        txListSize = 100

        ''' Node Parameters '''
        # Number of device nodes per gateway in the network
        Dn = 10
        # Number of gateway nodes in the network
        Gn = 2
        # Total number of nodes in the network
        Nn = Gn + (Gn*Dn)
        # A list of all the nodes in the network
        NODES = []
        # A list of all the gateway Ids
        GATEWAYIDS = [chr(x+97) for x in range(Gn)]
        from Models.AppendableBlock.Node import Node

        # Create all the gateways
        for i in GATEWAYIDS:
            otherGatewayIds = GATEWAYIDS.copy()
            otherGatewayIds.remove(i)
            # Create gateway node
            NODES.append(Node(i, "g", otherGatewayIds))

        # Create the device nodes for each gateway
        deviceNodeId = 1
        for i in GATEWAYIDS:
            for j in range(Dn):
                NODES.append(Node(deviceNodeId, "d", i))
                deviceNodeId += 1

        ''' Simulation Parameters '''
        # The average transaction propagation delay in seconds
        propTxDelay = 0.000690847927

        # The average transaction list propagation delay in seconds
        propTxListDelay = 0.00864894

        # The average transaction insertion delay in seconds
        insertTxDelay = 0.000010367235

        # The simulation length (in seconds)
        simTime = 500

        # Number of simulation runs
        Runs = 5

        ''' Verification '''
        # Varify the model implementation at the end of first run
        VerifyImplemetation = True

        maxTxListSize = 0

    if model == 4:

        ''' Block & Round Parameters '''
        Binterval = 40      # Thời gian mỗi round (giây)
        Bsize = 2.0         # Kích thước block tối đa (MB)
        Blimit = 10000000   # Gas limit cho mỗi block (Chính phủ có thể cần giới hạn cao hơn)
        Bdelay = 0.05       # Độ trễ mạng nội bộ giữa các cơ quan chính phủ (thường thấp)
        Breward = 0         # Trong mạng permissioned, có thể không cần thưởng bằng tiền

        ''' Transaction Parameters '''
        hasTrans = True
        #Ttechnique = "Full" # Sử dụng Full để mô phỏng chính xác việc truyền nhận Tx
        Ttechnique = "Light" # Sử dụng Light để tập trung vào cơ chế đồng thuận
        Tn = 10000             # Số lượng giao dịch tạo ra mỗi giây
        Tdelay = 0.03        # Độ trễ lan truyền giao dịch
        Tsize = 0.000546    # Kích thước trung bình giao dịch
        
        T_timeout = 0.2
        T_prepare_timeout = 0.15
        T_commit_timeout = 0.15

        proposer_found_in_round = 0
        
        ''' Consensus Parameters (Dựa trên paper) '''
        k = 3            # Số lượng Proposers kỳ vọng mỗi round (theo Table 2 trong paper)
        t0 = 14              # Số lượng node Tier-0 (Các Bộ/Ngành - Finality Layer)
        t1 = 50             # Số lượng node Tier-1 (Các Tỉnh/Thành - Proposer Layer)
        epsilon = 0.99      # Xác suất mỗi round có honest node
        h1 = 0.7            # Số lượng honest node
        prob_to_proposer = k/t1

        T = (2**(256) - 1) * prob_to_proposer
        # Điều kiện an toàn: t0 >= 3f0 + 1. 
        # Với t0 = 14, hệ thống chịu được f0 = 4 node Byzantine ở Tier-0.
        f0 = round((t0-1)/3)
        
        no_proposer_found = 0

        debug = False
        round_num = 0
        seed_0 = "This is seed 0" # Nên thêm DRNG để tạo seed_0
        # VRF Threshold p = k / t1
        vrf_threshold = k / t1 
        count_proposer_index = 0 # Biến đếm để theo dõi số lượng proposer đã được chọn trong round hiện tại


        # PBFT latency: Thời gian để Tier-0 chạy xong 2 phase Prepare và Commit
        pbft_delay = 0.01
        pbft_timeout = 0.5
        ''' Node Parameters '''
        Nn = t0 + t1        # Tổng số node
        NODES = []
        from Models.DualTierBlockchain.Node import Node # Đảm bảo lớp Node đã được cập nhật để nhận tham số tier
        
        # Khởi tạo các node Tier-0 (Ministries, Departments)
        for i in range(t0):
            vrf = ECVRF()
            sk, pk = vrf.generate_keypair()
            new_node = Node(id=i, tier=0,pk = pk,sk = sk, seed = seed_0)
            NODES.append(new_node)
            
        # Khởi tạo các node Tier-1 (Provinces)
        for i in range(t0, t0 + t1):
            sk, pk = vrf.generate_keypair()
            new_node = Node(id=i, tier=1,pk = pk,sk = sk, seed = seed_0)
            NODES.append(new_node)

        ''' Simulation Parameters '''
        # Tn * SimTime <= 2 000 000 tx (vì tạo ra trước max là 2,000,000 tx )
        simTime = 20     # Tổng thời gian mô phỏng (giây)
        Runs = 1         # Số lần chạy thử nghiệm

        @staticmethod
        def reset_nodes(t0, t1, k):
            """
            Reset network with new size
            Used by experiment runner
            """
            from Models.DualTierBlockchain.ECVRF import ECVRF
            from Models.DualTierBlockchain.Node import Node
            InputsConfig.NODES = []
            # Update config
            InputsConfig.t0 = t0
            InputsConfig.t1 = t1
            InputsConfig.k = k
            InputsConfig.Nn = t0 + t1
            InputsConfig.prob_to_proposer = k / t1
            InputsConfig.T = int((2**(256) - 1) * InputsConfig.prob_to_proposer)
            InputsConfig.f0 = round((t0-1)/3)
            InputsConfig.round_num = 0
            InputsConfig.no_proposer_found = 0
            InputsConfig.count_proposer_index = 0
            InputsConfig.proposer_found_in_round = 0
            # Tier-0
            # Khởi tạo các node Tier-0 (Ministries, Departments)
            for i in range(t0):
                vrf = ECVRF()
                sk, pk = vrf.generate_keypair()
                new_node = Node(id=i, tier=0,pk = pk,sk = sk, seed = InputsConfig.seed_0)
                InputsConfig.NODES.append(new_node)
                
            # Khởi tạo các node Tier-1 (Provinces)
            for i in range(t0, t0 + t1):
                sk, pk = vrf.generate_keypair()
                new_node = Node(id=i, tier=1,pk = pk,sk = sk, seed = InputsConfig.seed_0)
                InputsConfig.NODES.append(new_node)