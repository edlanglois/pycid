# Licensed to the Apache Software Foundation (ASF) under one or more contributor license
# agreements; and to You under the Apache License, Version 2.0.
from __future__ import annotations

import random
from functools import lru_cache
import matplotlib.pyplot as plt
import numpy as np
from pgmpy.factors.discrete import TabularCPD  # type: ignore
from pgmpy.models import BayesianModel  # type: ignore
from typing import List, Tuple, Dict, Any, Callable, Union
from pgmpy.inference.ExactInference import BeliefPropagation  # type: ignore
import networkx as nx
from core.cpd import UniformRandomCPD, FunctionCPD, DecisionDomain
import itertools
import matplotlib.cm as cm
from core.relevance_graph import RelevanceGraph


class MACIDBase(BayesianModel):

    def __init__(self,
                 edges: List[Tuple[str, str]],
                 node_types: Dict[Union[str, int], Dict]):
        super().__init__(ebunch=edges)

        self.decision_nodes_agent = {i: node_types[i]['D'] for i in node_types}
        for node in self.all_decision_nodes:
            if node not in self.nodes:
                raise Exception(f"Decision node {node} is not in the (MA)CID.")

        self.utility_nodes_agent = {i: node_types[i]['U'] for i in node_types}
        for node in self.all_utility_nodes:
            if node not in self.nodes:
                raise Exception(f"Utility node {node} is not in the (MA)CID.")

        self.whose_node = {}
        for agent in self.agents:
            for node in self.decision_nodes_agent[agent]:
                self.whose_node[node] = agent
            for node in self.utility_nodes_agent[agent]:
                self.whose_node[node] = agent

        self.cpds_to_add: Dict[str, TabularCPD] = {}

    @property
    def all_decision_nodes(self) -> List[str]:
        return list(set().union(*list(self.decision_nodes_agent.values())))

    @property
    def all_utility_nodes(self) -> List[str]:
        return list(set().union(*list(self.utility_nodes_agent.values())))

    @property
    def agents(self) -> List[Union[str, int]]:
        return list(self.decision_nodes_agent.keys())

    def remove_edge(self, u: str, v: str) -> None:
        super().remove_edge(u, v)
        if hasattr(self, "cpds") and isinstance(self.get_cpds(v), UniformRandomCPD):
            self.add_cpds(self.get_cpds(v))

    def add_edge(self, u: str, v: str) -> None:
        super().add_edge(u, v)
        if hasattr(self, "cpds") and isinstance(self.get_cpds(v), UniformRandomCPD):
            self.add_cpds(self.get_cpds(v))

    def make_decision(self, node: str, agent: Union[str, int] = 0) -> None:
        """"Turn a chance or utility node into a decision node."""
        if hasattr(self, "cpds") and isinstance(self.get_cpds(node), DecisionDomain):
            pass
        elif hasattr(self, "cpds") and not isinstance(self.get_cpds(node), DecisionDomain):
            cpd_new = DecisionDomain(node, self.get_cpds(node).state_names[node])
            self.decision_nodes_agent[agent].append(node)
            self.whose_node[node] = agent
            self.add_cpds(cpd_new)
        else:
            raise Exception(f"node {node} has not yet been assigned a domain.")

    def make_chance(self, node: str) -> None:
        """Turn a decision node into a chance node."""
        if node in self.all_decision_nodes:
            agent = self.whose_node[node]
            self.decision_nodes_agent[agent].remove(node)
            self.whose_node.pop(node)
        elif hasattr(self, "cpds") and node not in self.all_decision_nodes:
            pass
        elif not hasattr(self, "cpds"):
            raise Exception("The (MA)CID has not yet been parameterised")

    def add_cpds(self, *cpds: TabularCPD) -> None:
        """
        Add the given CPDs and initiate FunctionCPDs, UniformRandomCPDs etc
        """

        # Add each cpd to self.cpds_to_add after doing some checks
        for cpd in cpds:
            assert cpd.variable in self.nodes
            assert isinstance(cpd, TabularCPD)
            if isinstance(cpd, DecisionDomain) and cpd.variable not in self.all_decision_nodes:
                raise Exception(f"trying to add DecisionDomain to non-decision node {cpd.variable}")
            if isinstance(cpd, FunctionCPD) and set(cpd.evidence) != set(self.get_parents(cpd.variable)):
                raise Exception(f"parents {cpd.evidence} of {cpd} " + f"don't match graph parents \
                                {self.get_parents(cpd.variable)}")
            self.cpds_to_add[cpd.variable] = cpd

        # Initialize CPDs in topological order. Call super().add_cpds if initialized
        # successfully. Otherwise leave in self.cpds_to_add.
        for var in nx.topological_sort(self):
            if var in self.cpds_to_add:
                cpd_to_add = self.cpds_to_add[var]
                if hasattr(cpd_to_add, "initialize_tabular_cpd"):
                    cpd_to_add.initialize_tabular_cpd(self)
                if hasattr(cpd_to_add, "values"):  # cpd_to_add has been initialized
                    # if the state_names have changed, remember to update all descendants:
                    previous_cpd = self.get_cpds(var)
                    if previous_cpd and previous_cpd.state_names[var] != cpd_to_add.state_names[var]:
                        for descendant in nx.descendants(self, var):
                            if descendant not in self.cpds_to_add and self.get_cpds(descendant):
                                self.cpds_to_add[descendant] = self.get_cpds(descendant)
                    # add cpd to BayesianModel, and remove it from cpds_to_add
                    super().add_cpds(cpd_to_add)
                    del self.cpds_to_add[var]

    def query(self, query: List[str], context: Dict[str, Any],
              intervention: Dict["str", "Any"] = None) -> BeliefPropagation:
        """Return P(query|context, do(intervention))*P(context | do(intervention)).

        Use factor.normalize to get p(query|context, do(intervention)).
        Use context={} to get P(query). """

        # Check that strategically relevant decisions have a policy specified
        mech_graph = MechanismGraph(self)
        for decision in self.all_decision_nodes:
            for query_node in query:
                if mech_graph.is_active_trail(decision + "mec", query_node, observed=list(context.keys())):
                    cpd = self.get_cpds(decision)
                    if not cpd:
                        raise Exception(f"no DecisionDomain specified for {decision}")
                    elif isinstance(cpd, DecisionDomain):
                        raise Exception(f"query {query}|{context} depends on {decision}, but no policy imputed")

        for variable, value in context.items():
            if value not in self.get_cpds(variable).state_names[variable]:
                raise Exception(f"The value {value} is not in the state_names of {variable}")

        # query fails if graph includes nodes not in moralized graph, so we remove them
        # cid = self.copy()
        # mm = MarkovModel(cid.moralize().edges())
        # for node in self.nodes:
        #     if node not in mm.nodes:
        #         cid.remove_node(node)
        # filtered_context = {k:v for k,v in context.items() if k in mm.nodes}
        if intervention:
            cid = self.copy()
            cid.intervene(intervention)
        else:
            cid = self

        updated_state_names = {}
        for v in query:
            cpd = cid.get_cpds(v)
            updated_state_names[v] = cpd.state_names[v]

        bp = BeliefPropagation(cid)
        # TODO: check for probability 0 queries
        # factor = bp.query(query, filtered_context)

        # revise context so state_names are switched to their state number (overcomes pgmpy's bug)
        revised_context = {variable: self.get_cpds(variable).name_to_no[variable][value]
                           for variable, value in context.items()}
        factor = bp.query(query, revised_context, show_progress=False)
        factor.state_names = updated_state_names  # factor sometimes gets state_names wrong...
        return factor

    def intervene(self, intervention: Dict["str", "Any"]) -> None:
        """Given a dictionary of interventions, replace the CPDs for the relevant nodes.

        Soft interventions can be achieved by using add_cpds directly.
        """
        for variable, value in intervention.items():
            cpd = FunctionCPD(variable, lambda *x: value, evidence=self.get_parents(variable))
            self.add_cpds(cpd)

    def expected_value(self, variables: List[str], context: Dict["str", "Any"],
                       intervene: Dict["str", "Any"] = None,) -> List[float]:
        """Compute the expected value of a real-valued variable for a given context,
        under an optional intervention
        """
        factor = self.query(variables, context, intervention=intervene)
        factor.normalize()  # make probs add to one

        ev = np.array([0.0 for _ in factor.variables])
        for idx, prob in np.ndenumerate(factor.values):
            # idx contains the information about the value each variable takes
            # we use state_names to convert index into the actual value of the variable
            ev += prob * np.array([factor.state_names[variable][idx[var_idx]]
                                   for var_idx, variable in enumerate(factor.variables)])
            if np.isnan(ev).any():
                raise Exception("query {} | {} generated Nan from idx: {}, prob: {}, \
                                consider imputing a random decision".format(variables, context, idx, prob))
        return ev.tolist()  # type: ignore

    def expected_utility(self, context: Dict["str", "Any"],
                         intervene: Dict["str", "Any"] = None, agent: Union[str, int] = 0) -> float:
        """Compute the expected utility for a given context and optional intervention

        For example:
        cid = get_minimal_cid()
        out = self.expected_utility({'D':1}) #TODO: give example that uses context
        """
        return sum(self.expected_value(self.utility_nodes_agent[agent], context, intervene=intervene))

    def get_valid_order(self, nodes: List[str] = None) -> List[str]:
        """Get a topological order of the specified set of nodes (this may not be unique).

        By default, a topological ordering of the decision nodes is given"""
        if not nx.is_directed_acyclic_graph(self):
            raise Exception("A topological ordering of nodes can only be returned if the (MA)CID is acyclic")

        if nodes:
            for node in nodes:
                if node not in self.nodes:
                    raise Exception(f"{node} is not in the (MA)CID.")

        if not nodes:
            nodes = self.all_decision_nodes
        srt = [i for i in nx.topological_sort(self) if i in nodes]
        return srt

    def is_s_reachable(self, d1: Union[str, List[str]], d2: Union[str, List[str]]) -> bool:
        """
        Determine whether 'D2' is s-reachable from 'D1' (Koller and Milch, 2001)

        A node D2 is s-reachable from a node D1 in a MACID M if there is some utility node U ∈ U_D1 ∩ Desc(D1)
        such that if a new parent D2' were added to D2, there would be an active path in M from
        D2′ to U given Pa(D)∪{D}, where a path is active in a MAID if it is active in the same graph, viewed as a BN.

        """
        assert d2 in self.all_decision_nodes
        return self.is_r_reachable(d1, d2)

    def is_r_reachable(self, decisions: Union[str, List[str]], nodes: Union[str, List[str]]) -> bool:
        """
        Determine whether (a set of) node(s) is r-reachable from decision in the (MA)CID.
        - A node 𝑉 is r-reachable from a decision 𝐷 ∈ 𝑫^𝑖 in a MAID, M = (𝑵, 𝑽, 𝑬),
        if a newly added parent 𝑉ˆ of 𝑉 satisfies 𝑉ˆ ̸⊥ 𝑼^𝑖 ∩ Desc_𝐷 | Fa_𝐷 .
        - If a node V is r-reachable from a decision D that means D strategically or probabilisticaly relies on V.
        """
        if isinstance(decisions, str):
            decisions = [decisions]
        if isinstance(nodes, str):
            nodes = [nodes]
        mg = MechanismGraph(self)
        for decision in decisions:
            for node in nodes:
                con_nodes = [decision] + self.get_parents(decision)
                agent_utilities = self.utility_nodes_agent[self.whose_node[decision]]
                for utility in set(agent_utilities).intersection(nx.descendants(self, decision)):
                    if mg.is_active_trail(node + "mec", utility, con_nodes):
                        return True
        return False

    def sufficient_recall(self, agent: Union[str, int] = None) -> bool:
        """
        Finds whether a (MA)CID has sufficient recall.

        Agent i in the MAID has sufficient recall if the relevance graph
        restricted to contain only i's decision nodes is acyclic.

        If an agent is specified, sufficient recall is checked only for that agent.
        Otherwise, the check is done for all agents.
        """
        if not agent:
            agents = self.agents
        elif agent not in self.agents:
            raise Exception(f"There is no agent {agent}, in this (MA)CID")
        else:
            agents = [agent]

        for a in agents:
            rg = RelevanceGraph(self, self.decision_nodes_agent[a])
            if not rg.is_acyclic():
                return False
        return True

    def pure_decision_rules(self, decision: str) -> List[FunctionCPD]:
        """Return a list of the decision rules available at the given decision"""

        cpd: TabularCPD = self.get_cpds(decision)
        evidence_card = cpd.cardinality[1:]
        parents = cpd.variables[1:]
        state_names = cpd.state_names[decision]

        # We begin by representing each possible decision as a list values, with length
        # equal the number of decision contexts
        functions_as_lists = list(itertools.product(state_names, repeat=np.product(evidence_card)))

        def arg2idx(parent_values: tuple) -> int:
            """Convert a decision context into an index for the function list"""
            idx = 0
            for i, pv in enumerate(parent_values):
                name_to_no: Dict[Any, int] = self.get_cpds(parents[i]).name_to_no[parents[i]]
                idx += name_to_no[pv] * np.product(evidence_card[:i])
            assert 0 <= idx <= len(functions_as_lists)
            return idx

        function_cpds: List[FunctionCPD] = []
        for func_list in functions_as_lists:
            def function(*parent_values: tuple, early_eval_func_list: tuple = func_list) -> Any:
                return early_eval_func_list[arg2idx(parent_values)]
            function_cpds.append(FunctionCPD(decision, function, cpd.variables[1:], state_names=cpd.state_names))
        return function_cpds

    def pure_strategies(self, decision_nodes: List[str]) -> List[List[FunctionCPD]]:
        """
        Find all of an agent's pure policies in this subgame.
        """
        possible_dec_rules = list(map(self.pure_decision_rules, decision_nodes))
        return list(itertools.product(*possible_dec_rules))

    def optimal_pure_strategies(self, decisions: List[str]) -> List[List[FunctionCPD]]:
        """
        Return a list of all optimal strategies for a given set of decisions
        """
        if not decisions:
            return []
        agent = self.whose_node[decisions[0]]
        assert set(decisions).issubset(self.decision_nodes_agent[agent])
        macid = self.copy()
        for d in macid.all_decision_nodes:
            if not macid.is_s_reachable(decisions, d) and isinstance(macid.get_cpds(d), DecisionDomain):
                macid.impute_random_decision(d)
        expected_utility: List[float] = []
        strategies = macid.pure_strategies(decisions)
        for strategy in strategies:
            macid.add_cpds(*strategy)
            expected_utility.append(macid.expected_utility({}, agent=agent))
        return [strategy for i, strategy in enumerate(strategies)
                if expected_utility[i] == max(expected_utility)]

    def optimal_pure_decision_rules(self, decision: str) -> List[FunctionCPD]:
        """
        Return a list of all optimal decision rules for a given decision
        """
        return [strategy[0] for strategy in self.optimal_pure_strategies([decision])]

    def impute_random_decision(self, d: str) -> None:
        """Impute a random policy to the given decision node"""
        current_cpd = self.get_cpds(d)
        if current_cpd:
            sn = current_cpd.state_names[d]
        else:
            raise Exception(f"can't figure out domain for {d}, did you forget to specify DecisionDomain?")
        self.add_cpds(UniformRandomCPD(d, sn))

    def impute_fully_mixed_policy_profile(self) -> None:
        """Impute a fully mixed policy profile - ie a random decision rule to all decision nodes"""
        for d in self.all_decision_nodes:
            self.impute_random_decision(d)

    def impute_optimal_decision(self, d: str) -> None:
        """Impute an optimal policy to the given decision node"""
        self.add_cpds(random.choice(self.optimal_pure_decision_rules(d)))
        # self.impute_random_decision(d)
        # cpd = self.get_cpds(d)
        # parents = cpd.variables[1:]
        # idx2name = cpd.no_to_name[d]
        # utility_nodes = self.utility_nodes_agent[self.whose_node[d]]
        # descendant_utility_nodes = list(set(utility_nodes).intersection(nx.descendants(self, d)))
        # new = self.copy()  # using a copy "freezes" the policy so it doesn't adapt to future interventions
        #
        # @lru_cache(maxsize=1000)
        # def opt_policy(*parent_values: tuple) -> Any:
        #     nonlocal descendant_utility_nodes
        #     context: Dict[str, Any] = {parents[i]: parent_values[i] for i in range(len(parents))}
        #     eu = []
        #     for d_idx in range(new.get_cardinality(d)):
        #         context[d] = idx2name[d_idx]
        #         eu.append(sum(new.expected_value(descendant_utility_nodes, context)))
        #     return idx2name[np.argmax(eu)]
        #
        # self.add_cpds(FunctionCPD(d, opt_policy, parents, state_names=cpd.state_names, label="opt"))

    def impute_conditional_expectation_decision(self, d: str, y: str) -> None:
        """Imputes a policy for d = the expectation of y conditioning on d's parents"""
        # TODO: Move to analyze, as this is not really a core feature?
        parents = self.get_parents(d)
        new = self.copy()

        @lru_cache(maxsize=1000)
        def cond_exp_policy(*pv: tuple) -> float:
            context = {p: pv[i] for i, p in enumerate(parents)}
            return new.expected_value([y], context)[0]

        self.add_cpds(FunctionCPD(d, cond_exp_policy, parents, label="cond_exp({})".format(y)))

    def copy_without_cpds(self) -> MACIDBase:
        """copy the MACIDBase object without its CPDs"""
        return MACIDBase(self.edges(),
                         {agent: {'D': list(self.decision_nodes_agent[agent]),
                                  'U': list(self.utility_nodes_agent[agent])}
                          for agent in self.agents})

    def copy(self) -> MACIDBase:
        """copy the MACIDBase object"""
        model_copy = self.copy_without_cpds()
        if self.cpds:
            model_copy.add_cpds(*[cpd.copy() for cpd in self.cpds])
        return model_copy

    def _get_color(self, node: str) -> Union[np.ndarray, str]:
        """
        Assign a unique colour to each new agent's decision and utility nodes
        """
        colors = cm.rainbow(np.linspace(0, 1, len(self.agents)))
        if node in self.all_decision_nodes or node in self.all_utility_nodes:
            return colors[[self.agents.index(self.whose_node[node])]]  # type: ignore
        else:
            return 'lightgray'  # chance node

    def _get_shape(self, node: str) -> str:
        if node in self.all_decision_nodes:
            return 's'
        elif node in self.all_utility_nodes:
            return 'D'
        else:
            return 'o'

    def _get_label(self, node: str) -> Any:
        cpd = self.get_cpds(node)
        if hasattr(cpd, "label"):
            return cpd.label
        elif hasattr(cpd, "__name__"):
            return cpd.__name__
        else:
            return ""

    def draw(self,
             node_color: Callable[[str], str] = None,
             node_shape: Callable[[str], str] = None,
             node_label: Callable[[str], str] = None) -> None:
        """
        Draw the MACID or CID.
        """
        color = node_color if node_color else self._get_color
        shape = node_shape if node_shape else self._get_shape
        label = node_label if node_label else self._get_label
        layout = nx.kamada_kawai_layout(self)
        label_dict = {node: label(node) for node in self.nodes}
        pos_higher = {}
        for k, v in layout.items():
            if v[1] > 0:
                pos_higher[k] = (v[0] - 0.1, v[1] - 0.2)
            else:
                pos_higher[k] = (v[0] - 0.1, v[1] + 0.2)
        nx.draw_networkx(self, pos=layout, node_size=800, arrowsize=20)
        nx.draw_networkx_labels(self, pos_higher, label_dict)
        for node in self.nodes:
            nx.draw_networkx(self.to_directed().subgraph([node]), pos=layout, node_size=800, arrowsize=20,
                             node_color=color(node),
                             node_shape=shape(node))
        plt.show()

    def draw_property(self, node_property: Callable[[str], bool], color: str = 'red') -> None:
        """Draw a CID with the nodes satisfying node_property highlighted"""

        def node_color(node: str) -> Any:
            if node_property(node):
                return color
            else:
                return self._get_color(node)

        self.draw(node_color=node_color)


class MechanismGraph(MACIDBase):
    """A mechanism graph has an extra parent node+"mec" for each node"""

    def __init__(self, cid: MACIDBase):
        super().__init__(cid.edges(),
                         {agent: {'D': list(cid.decision_nodes_agent[agent]),
                                  'U': list(cid.utility_nodes_agent[agent])}
                          for agent in cid.agents})
        for node in cid.nodes:
            if node[:-3] == "mec":
                raise Exception("can't create a mechanism graph when node {node} already ends with mec")
            self.add_node(node + "mec")
            self.add_edge(node + "mec", node)
        # TODO: adapt the parameterization from cid as well
