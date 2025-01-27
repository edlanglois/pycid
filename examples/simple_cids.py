# Licensed to the Apache Software Foundation (ASF) under one or more contributor license
# agreements; and to You under the Apache License, Version 2.0.

from core.cid import CID
from core.cpd import FunctionCPD, DecisionDomain, UniformRandomCPD


def get_minimal_cid() -> CID:
    cid = CID([('A', 'B')],
              decision_nodes=['A'],
              utility_nodes=['B'])
    cpd_a = DecisionDomain('A', [0, 1])
    cpd_b = FunctionCPD('B', lambda a: a, evidence=['A'])
    cid.add_cpds(cpd_a, cpd_b)
    return cid


def get_3node_cid() -> CID:
    cid = CID([('S', 'D'), ('S', 'U'), ('D', 'U')],
              decision_nodes=['D'],
              utility_nodes=['U'])
    cpd_s = UniformRandomCPD('S', [-1, 1])
    cpd_u = FunctionCPD('U', lambda s, d: s * d, evidence=['S', 'D'])
    cpd_d = DecisionDomain('D', [-1, 1])
    cid.add_cpds(cpd_d, cpd_s, cpd_u)
    return cid


def get_5node_cid() -> CID:
    cid = CID([
        ('S1', 'D'),
        ('S1', 'U1'),
        ('S2', 'D'),
        ('S2', 'U2'),
        ('D', 'U1'),
        ('D', 'U2')],
        decision_nodes=['D'],
        utility_nodes=['U1', 'U2'])
    cpd_s1 = UniformRandomCPD('S1', [0, 1])
    cpd_s2 = UniformRandomCPD('S2', [0, 1])
    cpd_u1 = FunctionCPD('U1', lambda s1, d: int(s1 == d), evidence=['S1', 'D'])
    cpd_u2 = FunctionCPD('U2', lambda s2, d: int(s2 == d), evidence=['S2', 'D'])
    cpd_d = DecisionDomain('D', [0, 1])
    cid.add_cpds(cpd_d, cpd_s1, cpd_s2, cpd_u1, cpd_u2)
    return cid


def get_5node_cid_with_scaled_utility() -> CID:
    cid = CID([
        ('S1', 'D'),
        ('S1', 'U1'),
        ('S2', 'D'),
        ('S2', 'U2'),
        ('D', 'U1'),
        ('D', 'U2')],
        decision_nodes=['D'],
        utility_nodes=['U1', 'U2'])
    cpd_s1 = UniformRandomCPD('S1', [0, 1])
    cpd_s2 = UniformRandomCPD('S2', [0, 1])
    cpd_u1 = FunctionCPD('U1', lambda s1, d: 10 * int(s1 == d), evidence=['S1', 'D'])
    cpd_u2 = FunctionCPD('U2', lambda s2, d: 2 * int(s2 == d), evidence=['S2', 'D'])
    cpd_d = DecisionDomain('D', [0, 1])
    cid.add_cpds(cpd_d, cpd_s1, cpd_s2, cpd_u1, cpd_u2)
    return cid


def get_2dec_cid() -> CID:
    cid = CID([
        ('S1', 'S2'),
        ('S1', 'D1'),
        ('D1', 'S2'),
        ('S2', 'U'),
        ('S2', 'D2'),
        ('D2', 'U')
    ],
        decision_nodes=['D1', 'D2'],
        utility_nodes=['U'])
    cpd_s1 = UniformRandomCPD('S1', [0, 1])
    cpd_d1 = DecisionDomain('D1', [0, 1])
    cpd_d2 = DecisionDomain('D2', [0, 1])
    cpd_s2 = FunctionCPD('S2', lambda s2, d1: int(s2 == d1), evidence=['S1', 'D1'])
    cpd_u = FunctionCPD('U', lambda s2, d2: int(s2 == d2), evidence=['S2', 'D2'])
    cid.add_cpds(cpd_s1, cpd_d1, cpd_s2, cpd_d2, cpd_u)
    return cid


def get_sequential_cid() -> CID:
    """
    This CID is a subtle case of sufficient recall, as the strategy for D1 influences
    the expected utility of D2, but D2 can still be chosen without knowing D1, since
    D1 does not influence any utility nodes descending from D2.
    """
    cid = CID([
        ('S1', 'D1'),
        ('D1', 'U1'),
        ('S1', 'U1'),
        ('D1', 'S2'),
        ('S2', 'D2'),
        ('D2', 'U2'),
        ('S2', 'U2'),
    ],
        decision_nodes=['D1', 'D2'],
        utility_nodes=['U1', 'U2'])

    cid.add_cpds(
        UniformRandomCPD('S1', [0, 1]),
        DecisionDomain('D1', [0, 1]),
        FunctionCPD('U1', lambda s1, d1: int(s1 == d1), evidence=['S1', 'D1']),
        FunctionCPD('S2', lambda d1: d1, evidence=['D1']),
        DecisionDomain('D2', [0, 1]),
        FunctionCPD('U2', lambda s2, d2: int(s2 == d2), evidence=['S2', 'D2']),
    )
    return cid


def get_insufficient_recall_cid() -> CID:
    cid = CID([('A', 'U'), ('B', 'U')], decision_nodes=['A', 'B'], utility_nodes=['U'])
    cid.add_cpds(DecisionDomain('A', [0, 1]),
                 DecisionDomain('B', [0, 1]),
                 FunctionCPD('U', lambda a, b: a * b, evidence=['A', 'B']))
    return cid


def get_trim_example_cid() -> CID:
    cid = CID([
        ('Y1', 'D1'),
        ('Y1', 'Y2'),
        ('Y1', 'D2'),
        ('Y2', 'D2'),
        ('Y2', 'U'),
        ('D1', 'Y2'),
        ('D1', 'D2'),
        ('Z1', 'D1'),
        ('Z1', 'D2'),
        ('Z1', 'Z2'),
        ('Z2', 'D2'),
        ('D2', 'U'),
    ],
        decision_nodes=['D1', 'D2'],
        utility_nodes=['U'])
    return cid
