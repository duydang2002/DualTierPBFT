import random


class Network:

    # Delay for propagating blocks in the network
    def block_prop_delay():
        from InputsConfig import InputsConfig as p
        return min(random.expovariate(1 / p.Bdelay), p.Bdelay * 3)

    def tx_prop_delay():
        from InputsConfig import InputsConfig as p
        return min(random.expovariate(1/p.Tdelay), p.Tdelay * 3)
    
    def pbft_prop_delay():
        from InputsConfig import InputsConfig as p
        return min(random.expovariate(1/p.pbft_delay), p.pbft_delay * 3)
