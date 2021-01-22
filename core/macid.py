#Licensed to the Apache Software Foundation (ASF) under one or more contributor license
#agreements; and to You under the Apache License, Version 2.0.

import numpy as np
from pgmpy.models import BayesianModel
from pgmpy.factors.continuous import ContinuousFactor
from pgmpy.factors.discrete import TabularCPD
import logging
from typing import List, Tuple, Dict, Any, Callable, Union
#import numpy.typing as npt
import itertools
from pgmpy.inference import BeliefPropagation
import networkx as nx
from core.cpd import UniformRandomCPD, FunctionCPD, DecisionDomain
import matplotlib.pyplot as plt
import operator
from collections import defaultdict
from collections import deque
import copy
import matplotlib.cm as cm
from analyze.get_paths import get_motifs, get_motif
from core.macid_base import MACIDBase

class MACID(MACIDBase):
    def __init__(self, edges: List[Tuple[Union[str, int], str]],
                node_types: Dict[str, Dict]):
        super().__init__(edges, node_types)


# class MACID(BayesianModel):
#     def __init__(self, ebunch:List[Tuple[str, str]]=None, node_types:Dict=None, utility_domains:Dict=None ):
#         super(MACID, self).__init__(ebunch=ebunch)
#         self.node_types = node_types
#         self.utility_domains = utility_domains
#         self.utility_nodes = {i:node_types[i]['U'] for i in node_types if i != 'C'}     # this gives a dictionary matching each agent with their decision and utility nodes
#         self.decision_nodes = {i:node_types[i]['D'] for i in node_types if i != 'C'}     #  eg {'A': ['U1', 'U2'], 'B': ['U3', 'U4']}
#         self.chance_nodes = node_types['C']     # list of chance nodes
#         self.agents = [agent for agent in node_types if agent != 'C']   # gives a list of the MAID's agents
#         self.all_utility_nodes = list(itertools.chain(*self.utility_nodes.values()))
#         self.all_decision_nodes = list(itertools.chain(*self.decision_nodes.values()))
#         self.reversed_acyclic_ordering = list(reversed(self.get_acyclic_topological_ordering()))
#         self.numDecisions = len(self.reversed_acyclic_ordering)
#         self.cpds_to_add = {}


    def _get_color(self, node: str):
        # TODO declare type as np.ndarray, but then this requires np.typing package installed - I assume we want this though?
        """
        This matches a unique colour with each new agent's decision and utility nodes
        """
        colors = cm.rainbow(np.linspace(0, 1, len(self.agents)))
        if node in self.all_decision_nodes or node in self.all_utility_nodes:
            return colors[[int(self.whose_node[node])]]


    def is_s_reachable(self, d1: str, d2: str) -> bool:
        """ 
        Determine whether 'D2' is s-reachable from 'D1' (Koller and Milch 2001)
        
        A node D2 is s-reachable from a node D1 in a MACID M if there is some utility node U ∈ U_D
        such that if a new parent D2' were added to D2, there would be an active path in M from
        D2′ to U given Pa(D)∪{D}, where a path is active in a MAID if it is active in the same graph, viewed as a BN.

        """
        self.add_edge('temp_par', d2)
        agent = self.whose_node[d1]
        agent_utilities = self.utility_nodes_agent[agent]
        con_nodes = [d1] + self.get_parents(d1) 
        is_active_trail = any([self.is_active_trail('temp_par', u_node, con_nodes) for u_node in agent_utilities])
        self.remove_node('temp_par')
        return is_active_trail

    def strategic_rel_graph(self) -> nx.DiGraph:
        #TODO move this to macid_base
        """
        Find the strategic relevance graph of the MAID
        - an edge D -> D' exists iff D' is s-reachable from D
        """
        G = nx.DiGraph()
        dec_pair_perms = list(itertools.permutations(self.all_decision_nodes, 2))
        for dec_pair in dec_pair_perms:
            if self.is_s_reachable(dec_pair[0], dec_pair[1]):
                G.add_edge(dec_pair[0], dec_pair[1])
        return G

    def draw_strategic_rel_graph(self) -> None:
        """
        Draw the MACID's strategic relevance graph
        """
        rg = self.strategic_rel_graph()
        nx.draw_networkx(rg, node_size=400, arrowsize=20, node_color='k', font_color='w', edge_color='k', with_labels=True)
        plt.figure()
        plt.draw()
        

    def is_strategically_acyclic(self) -> bool:
        """
        Find whether the MACID has an acyclic strategic relevance graph.
        """
        rg = self.strategic_rel_graph()
        return nx.is_directed_acyclic_graph(rg)
        

    def get_acyclic_topological_ordering(self) -> List[str]:
        """
        Return a topological ordering (which might not be unique) of the decision nodes 
        if the strategic relevance graph is acyclic

        """
        rg = self.strategic_rel_graph()
        if not self.is_strategically_acyclic():
            raise Exception('The strategic relevance graph for this MACID is not acyclic and so \
                        no topological ordering can be immediately given.')
        else:
            return list(nx.topological_sort(rg))
    
            
   

# # ---------- methods setting up MACID for probabilistic inference ------



#     def random_instantiation_dec_nodes(self):
#         """
#         imputes random uniform policy to all decision nodes (NullCPDs) - arbitrary fully mixed strategy profile for MACID   #perhaps add something checking whether it's "isinstance(cpd, NullCPD)" is true
#         """
#         for dec in self.all_decision_nodes:
#             dec_card = self.get_cardinality(dec)
#             parents = self.get_parents(dec)
#             parents_card = [self.get_cardinality(par) for par in parents]
#             table = np.ones((dec_card, np.product(parents_card).astype(int))) / dec_card
#             uniform_cpd = TabularCPD(variable=dec, variable_card=dec_card,
#                             values=table, evidence=parents,
#                             evidence_card=parents_card
#                             )
#             print(uniform_cpd)
#             self.add_cpds(uniform_cpd)





# # ----------- methods for finding MACID properties -----------

#     def _get_dec_agent(self, dec: str):
#         """
#         finds which agent a decision node belongs to
#         """
#         for agent, decisions in self.decision_nodes.items():
#             if dec in decisions:
#                 return agent

#     def _get_util_agent(self, util: str):
#         """
#         finds which agent a utility node belongs to
#         """
#         for agent, utilities in self.utility_nodes.items():
#             if util in utilities:
#                 return agent

#     def get_node_type(self, node):
#         """
#         finds a node's type
#         """
#         if node in self.chance_nodes:
#             return 'c'
#         elif node in self.all_decision_nodes:
#             return 'p'  #gambit calls decision nodes player nodes
#         elif node in self.all_utility_nodes:
#             return 'u'
#         else:
#             return "node is not in MACID"




# -------------Methods for returning all pure strategy subgame perfect NE ------------------------------------------------------------


#     def _instantiate_initial_tree(self):
#         #creates a tree (a nested dictionary) which we use to fill up with the subgame perfect NE of each sub-tree.
#         cardinalities = map(self.get_cardinality, self.all_decision_nodes)
#         decision_cardinalities = dict(zip(self.all_decision_nodes, cardinalities)) #returns a dictionary matching each decision with its cardinality

#         action_space_list = list(itertools.accumulate(decision_cardinalities.values(), operator.mul))  #gives number of pure strategies for each decision node (ie taking into account prev decisions)
#         cols_in_each_tree_row = [1] + action_space_list

#         actions_for_dec_list = []
#         for card in decision_cardinalities.values():
#             actions_for_dec_list.append(list(range(card)))     # appending the range of actions each decion can make as a list
#         final_row_actions = list(itertools.product(*actions_for_dec_list))     # creates entry for final row of decision array (cartesian product of actions_seq_list))

#         tree_initial = defaultdict(dict)   # creates a nested dictionary
#         for i in range(0, self.numDecisions+1):
#             for j in range(cols_in_each_tree_row[i]):     #initialises entire decision/action array with empty tuples.
#                 tree_initial[i][j] = ()

#         for i in range(cols_in_each_tree_row[-1]):
#             tree_initial[self.numDecisions][i] = final_row_actions[i]

#         trees_queue = [tree_initial]  # list of all possible decision trees
#         return trees_queue


#     def _reduce_tree_once(self, queue:List[str], bp):
#         #finds node not yet evaluated and then updates tree by evaluating this node - we apply this repeatedly to fill up all nodes in the tree
#         tree = queue.pop(0)
#         for row in range(len(tree) -2, -1,-1):
#             for col in range (0, len(tree[row])):
#                 node_full = bool(tree[row][col])
#                 if node_full:
#                     continue
#                 else:    # if node is empty => update it by finding maximum children
#                     queue_update = self._max_childen(tree, row, col, queue, bp)
#                     return queue_update

#     def _max_childen(self, tree, row: int, col: int, queue, bp):
#         # adds to the queue the tree(s) filled with the node updated with whichever child(ren) yield the most utilty for the agent making the decision.
#         cardinalities = map(self.get_cardinality, self.all_decision_nodes)
#         decision_cardinalities = dict(zip(self.all_decision_nodes, cardinalities)) #returns a dictionary matching each decision with its cardinality

#         l = []
#         dec_num_act = decision_cardinalities[self.reversed_acyclic_ordering[row]]  # number of possible actions for that decision
#         for indx in range (col*dec_num_act, (col*dec_num_act)+dec_num_act):   # using col*dec_num_act and (col*dec_num_act)+dec_num_act so we iterate over all actions that agent is considering
#             l.append(self._get_ev(tree[row+1][indx], row, bp))
#         max_indexes = [i for i, j in enumerate(l) if j == max(l)]

#         for i in range(len(max_indexes)):
#             tree[row][col] = tree[row+1][(col*dec_num_act)+max_indexes[i]]
#             new_tree = copy.deepcopy(tree)
#             queue.append(new_tree)
#         return queue


#     def _get_ev(self, dec_list:List[int], row: int, bp):
#         #returns the expected value of that decision for the agent making the decision
#         dec = self.reversed_acyclic_ordering[row]   #gets the decision being made on this row
#         agent = self._get_dec_agent(dec)      #gets the agent making that decision
#         utils = self.utility_nodes[agent]       #gets the utility nodes for that agent

#         h = bp.query(variables=utils, evidence=dict(zip(self.reversed_acyclic_ordering, dec_list)))
#         ev = 0
#         for idx, prob in np.ndenumerate(h.values):
#             for i in range(len(utils)): # account for each agent having multiple utilty nodes
#                 if prob != 0:
#                     ev += prob*self.utility_domains[utils[i]][idx[i]]

#                         #ev += prob*self.utility_values[agent][idx[agent-1]]     #(need agent -1 because idx starts from 0, but agents starts from 1)
#         return ev

#     def _stopping_condition(self, queue):
#         """stopping condition for recursive tree filling"""
#         tree = queue[0]
#         root_node_full = bool(tree[0][0])
#         return root_node_full

#     def _PSNE_finder(self):
#         """this finds all pure strategy subgame perfect NE when the strategic relevance graph is acyclic
#         - first initialises the maid with uniform random conditional probability distributions at every decision.
#         - then fills up a queue with trees containing each solution
#         - the queue will contain only one entry (tree) if there's only one pure strategy subgame perfect NE"""
#         self.random_instantiation_dec_nodes()

#         bp = BeliefPropagation(self)
#         queue = self._instantiate_initial_tree()
#         while not self._stopping_condition(queue):
#             queue = self._reduce_tree_once(queue, bp)
#         return queue

#     def get_all_PSNE(self):
#         """yields all pure strategy subgame perfect NE when the strategic relevance graph is acyclic
#         !should still decide how the solutions are best displayed! """
#         solutions = self._PSNE_finder()
#         solution_array = []
#         for tree in solutions:
#             for row in range(len(tree)-1):
#                 for col in tree[row]:
#                     chosen_dec = tree[row][col][:row]
#                     matching_of_chosen_dec = zip(self.reversed_acyclic_ordering, chosen_dec)
#                     matching_of_solution = zip(self.reversed_acyclic_ordering, tree[row][col])
#                     solution_array.append((list(matching_of_chosen_dec), list(matching_of_solution)))
#         return solution_array


#             # can adapt how it displays the result (perhaps break into each agent's information sets)






# #----------------cyclic relevance graph methods:--------------------------------------

#     def find_SCCs(self):
#         """
#         Uses Tarjan’s algorithm with Nuutila’s modifications
#         - complexity is linear in the number of edges and nodes """
#         rg = self.strategic_rel_graph()
#         l = list(nx.strongly_connected_components(rg))


#         numSCCs = nx.number_strongly_connected_components(rg)
#         print(f"num = {numSCCs}")


#     def _set_color_SCC(self, node, SCCs):
#         colors = cm.rainbow(np.linspace(0, 1, len(SCCs)))
#         for SCC in SCCs:
#             idx = SCCs.index(SCC)
#             if node in SCC:
#                 col = colors[idx]
#         return col

#     def draw_SCCs(self):
#         """
#         This shows the strategic relevance graph's SCCs
#         """
#         rg = self.strategic_rel_graph()
#         SCCs = list(nx.strongly_connected_components(rg))
#         layout = nx.kamada_kawai_layout(rg)
#         colors = [self._set_color_SCC(node, SCCs) for node in rg.nodes]
#         nx.draw_networkx(rg, pos=layout, node_size=400, arrowsize=20, edge_color='g', node_color=colors)
#         plt.draw()

#     def component_graph(self):
#         """
#         draws and returns the component graph whose nodes are the maximal SCCs of the relevance graph
#         the component graph will always be acyclic. Therefore, we can return a topological ordering.
#         comp_graph.graph['mapping'] returns a dictionary matching the original nodes to the nodes in the new component (condensation) graph
#         """
#         rg = self.strategic_rel_graph()
#         comp_graph = nx.condensation(rg)
#         nx.draw_networkx(comp_graph, with_labels=True)
#         plt.figure(4)
#         plt.draw()
#         return comp_graph

#     def get_cyclic_topological_ordering(self):
#         """first checks whether the strategic relevance graph is cyclic
#         if it's cyclic
#         returns a topological ordering (which might not be unique) of the decision nodes
#         """
#         rg = self.strategic_rel_graph()
#         if self.strategically_acyclic():
#             return TypeError(f"Relevance graph is acyclic")
#         else:
#             comp_graph = self.component_graph()
#             return list(nx.topological_sort(comp_graph))


#         numSCCs = nx.number_strongly_connected_components(rg)
#         print(f"num = {numSCCs}")


#     def _set_color_SCC(self, node, SCCs):
#         colors = cm.rainbow(np.linspace(0, 1, len(SCCs)))
#         for SCC in SCCs:
#             if node in SCC:
#                 col = colors[SCCs.index(SCC)]
#         return col