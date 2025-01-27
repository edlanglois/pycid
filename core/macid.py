# Licensed to the Apache Software Foundation (ASF) under one or more contributor license
# agreements; and to You under the Apache License, Version 2.0.
from __future__ import annotations
from core.cpd import FunctionCPD
import numpy as np
from typing import List, Tuple, Dict, Union, Optional
import itertools
import networkx as nx
import copy
import matplotlib.cm as cm
from core.macid_base import MACIDBase
from core.relevance_graph import CondensedRelevanceGraph
from core.cpd import DecisionDomain


class MACID(MACIDBase):

    def __init__(self, edges: List[Tuple[Union[str, int], str]],
                 node_types: Dict[Union[str, int], Dict]):
        super().__init__(edges, node_types)

    def get_all_pure_ne(self) -> List[List[FunctionCPD]]:
        """
        Return a list of all pure Nash equilbiria in the MACID.
        - Each NE comes as a list of FunctionCPDs, one for each decision node in the MACID.
        """
        return self.get_all_pure_ne_in_sg()

    def joint_pure_strategies(self, decisions: List[str]) -> List[FunctionCPD]:
        all_dec_decision_rules = list(map(self.pure_decision_rules, decisions))
        return list(itertools.product(*all_dec_decision_rules))

    def get_all_pure_ne_in_sg(self, decisions_in_sg: Optional[List[str]] = None) -> List[List[FunctionCPD]]:
        """
        Return a list of all pure Nash equilbiria in a MACID subgame.
        - Each NE comes as a list of FunctionCPDs, one for each decision node in the MAID subgame.
        - If decisions_in_sg is not specified, this method finds all pure NE in the full MACID.
        - If the MACID being operated on already has function CPDs for some decision nodes, it is
        assumed that these have already been optimised and so these are not changed.
        TODO: Check that the decisions in decisions_in_sg actually make up a MAID subgame
        """
        if decisions_in_sg is None:
            decisions_in_sg = self.all_decision_nodes

        for dec in decisions_in_sg:
            if dec not in self.all_decision_nodes:
                raise Exception(f"The node {dec} is not a decision node in the (MACID")

        agents_in_sg = list({self.whose_node[dec] for dec in decisions_in_sg})
        agent_decs_in_sg = {agent: [dec for dec in self.decision_nodes_agent[agent]
                            if dec in decisions_in_sg] for agent in agents_in_sg}

        # impute random decisions to non-instantiated, irrelevant decision nodes
        macid = self.copy()
        for d in macid.all_decision_nodes:
            if not macid.is_s_reachable(decisions_in_sg, d) and isinstance(macid.get_cpds(d), DecisionDomain):
                macid.impute_random_decision(d)

        # NE finder
        all_pure_ne_in_sg: List[List[FunctionCPD]] = []
        for pp in self.joint_pure_strategies(decisions_in_sg):
            macid.add_cpds(*pp)  # impute the strategy profile

            for a in agents_in_sg:  # check that each agent is happy
                eu_pp_agent_a = macid.expected_utility({}, agent=a)
                macid.add_cpds(*macid.optimal_pure_strategies(agent_decs_in_sg[a])[0])
                max_eu_agent_a = macid.expected_utility({}, agent=a)

                if max_eu_agent_a > eu_pp_agent_a:  # not an NE
                    break
            else:  # it's an NE
                all_pure_ne_in_sg.append(list(pp))

        return all_pure_ne_in_sg

    def policy_profile_assignment(self, partial_policy: List[FunctionCPD]) -> Dict:
        """Return a dictionary with the joint or partial policy profile assigned -
        ie a decision rule for each of the MACIM's decision nodes."""
        new_macid = self.copy_without_cpds()
        new_macid.add_cpds(*partial_policy)
        return {d: new_macid.get_cpds(d) for d in new_macid.all_decision_nodes}

    def get_all_pure_spe(self) -> List[List[FunctionCPD]]:
        """Return a list of all pure subgame perfect Nash equilbiria (SPE) in the MACIM
        - Each SPE comes as a list of FunctionCPDs, one for each decision node in the MACID.
        """
        spes: List[List[FunctionCPD]] = [[]]

        # backwards induction over the sccs in the condensed relevance graph (handling tie-breaks)
        for scc in reversed(CondensedRelevanceGraph(self).get_scc_topological_ordering()):
            extended_spes = []
            for partial_profile in spes:
                self.add_cpds(*partial_profile)
                all_ne_in_sg = self.get_all_pure_ne_in_sg(scc)
                for ne in all_ne_in_sg:
                    extended_spes.append(partial_profile + list(ne))
            spes = extended_spes
        return spes

    def decs_in_each_maid_subgame(self) -> List[set]:
        """
        Return a list giving the set of decision nodes in each MAID subgame of the original MAID.
        """
        con_rel = CondensedRelevanceGraph(self)
        con_rel_sccs = con_rel.nodes  # the nodes of the condensed relevance graph are the maximal sccs of the MA(C)ID
        powerset = list(itertools.chain.from_iterable(itertools.combinations(con_rel_sccs, r)
                                                      for r in range(1, len(con_rel_sccs) + 1)))
        con_rel_subgames = copy.deepcopy(powerset)
        for subset in powerset:
            for node in subset:
                if not nx.descendants(con_rel, node).issubset(subset) and subset in con_rel_subgames:
                    con_rel_subgames.remove(subset)

        dec_subgames = [[con_rel.get_decisions_in_scc()[scc] for scc in con_rel_subgame]
                        for con_rel_subgame in con_rel_subgames]

        return [set(itertools.chain.from_iterable(i)) for i in dec_subgames]

    def copy_without_cpds(self) -> MACID:
        """copy the MACID structure"""
        return MACID(self.edges(),
                     {agent: {'D': list(self.decision_nodes_agent[agent]),
                              'U': list(self.utility_nodes_agent[agent])}
                     for agent in self.agents})

    def _get_color(self, node: str) -> Union[str, np.ndarray]:
        """
        Assign a unique colour with each new agent's decision and utility nodes
        """
        colors = cm.rainbow(np.linspace(0, 1, len(self.agents)))
        if node in self.all_decision_nodes or node in self.all_utility_nodes:
            return colors[[self.agents.index(self.whose_node[node])]]  # type: ignore
        else:
            return 'lightgray'  # chance node
