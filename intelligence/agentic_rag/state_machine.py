"""
intelligence/agentic_rag/state_machine.py
-----------------------------------------
V7.0 Lightweight Asynchronous State Machine Engine.

Inspired by LangGraph, this engine models the Agentic RAG pipeline as a Directed Graph:
  - Nodes: Asynchronous functions that mutate the AgentState.
  - Edges: Deterministic transitions from one node to another.
  - Conditional Edges: Functions that examine the State and route to different nodes.

This completely replaces procedural `if/else` and `while` loops with a rigid,
auditable, and cyclic AI workflow.
"""

import logging
from typing import Any, Awaitable, Callable, AsyncIterator

logger = logging.getLogger(__name__)

# Type aliases
# Nodes take (state, **kwargs) and return None (they mutate state directly).
NodeFunction = Callable[..., Awaitable[None]]
# Condition functions take (state) and return a string key to map to the next node.
ConditionFunction = Callable[[Any], str]

END = "__END__"


class StateMachineGraph:
    def __init__(self) -> None:
        self.nodes: dict[str, NodeFunction] = {}
        self.edges: dict[str, str] = {}
        self.conditional_edges: dict[str, tuple[ConditionFunction, dict[str, str]]] = {}
        self.entry_point: str | None = None

    def add_node(self, name: str, func: NodeFunction) -> None:
        """Register a node logic function."""
        if name in self.nodes:
            raise ValueError(f"Node '{name}' already exists.")
        self.nodes[name] = func

    def set_entry_point(self, name: str) -> None:
        """Set the starting node for the graph."""
        if name not in self.nodes:
            raise ValueError(f"Entry point '{name}' is not a registered node.")
        self.entry_point = name

    def add_edge(self, source: str, target: str) -> None:
        """Add a deterministic edge from source node to target node."""
        if source not in self.nodes:
            raise ValueError(f"Source node '{source}' not registered.")
        if target != END and target not in self.nodes:
            raise ValueError(f"Target node '{target}' not registered.")
        self.edges[source] = target

    def add_conditional_edges(
        self,
        source: str,
        condition: ConditionFunction,
        route_map: dict[str, str],
    ) -> None:
        """
        Add dynamic routing from a source node.
        `condition` evaluates the state and returns a key.
        `route_map` maps that key to the next node.
        """
        if source not in self.nodes:
            raise ValueError(f"Source node '{source}' not registered.")
        for k, target in route_map.items():
            if target != END and target not in self.nodes:
                raise ValueError(f"Route target '{target}' for key '{k}' not registered.")
        
        self.conditional_edges[source] = (condition, route_map)

    async def run_async(self, state: Any, **kwargs: Any) -> AsyncIterator[Any]:
        """
        Execute the graph and yield any events emitted by the nodes.
        Transitions state from the entry point through nodes via edges until "__END__" is reached.
        """
        if not self.entry_point:
            raise ValueError("Graph has no entry point set.")

        current_node = self.entry_point
        logger.debug("[StateMachine] Starting graph execution at node: %s", current_node)

        import inspect

        while current_node != END:
            # Execute current node
            func = self.nodes[current_node]
            logger.debug("[StateMachine] Executing node: %s", current_node)
            
            if inspect.isasyncgenfunction(func):
                # The node is an async generator yielding events
                async for item in func(state, **kwargs):
                    yield item
            else:
                # The node is a regular async function
                await func(state, **kwargs)

            # Determine next node
            if current_node in self.conditional_edges:
                condition_fn, route_map = self.conditional_edges[current_node]
                decision = condition_fn(state)
                next_node = route_map.get(decision)
                
                if next_node is None:
                    raise RuntimeError(
                        f"Condition from '{current_node}' returned '{decision}', "
                        f"but this key is not in the route map: {list(route_map.keys())}"
                    )
                logger.debug(
                    "[StateMachine] Conditional edge matched: '%s' -> Routing to '%s'", 
                    decision, next_node
                )
                current_node = next_node

            elif current_node in self.edges:
                next_node = self.edges[current_node]
                logger.debug("[StateMachine] Deterministic edge: Routing to '%s'", next_node)
                current_node = next_node

            else:
                raise RuntimeError(f"Node '{current_node}' has no outbound edges.")

        logger.debug("[StateMachine] Graph execution reached __END__.")
