"""
Concept Graph Engine.

Models the absolute truth of Data Structures and Algorithms as a Directed Acyclic Graph (DAG).
Provides O(V+E) Topological Sorting for Learning Paths and rigorous Prerequisite validation.
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class ConceptType(Enum):
    DATA_STRUCTURE = "DATA_STRUCTURE"
    ALGORITHM = "ALGORITHM"
    PATTERN = "PATTERN"
    PROBLEM = "PROBLEM"


class EdgeType(Enum):
    REQUIRES = "REQUIRES"        # Must learn A before B (Forms strict DAG)
    IMPLEMENTS = "IMPLEMENTS"    # A uses B under the hood (e.g. BFS implements Queue)
    SIMILAR_TO = "SIMILAR_TO"    # Undirected conceptual similarity
    PROGRESSES = "PROGRESSES"    # B is a harder version of A (Difficulty Progression)


@dataclass
class ConceptNode:
    """A highly-typed node within the absolute DAG."""
    id: str
    concept_type: ConceptType
    difficulty: int = 1  # 1 (Easy), 2 (Medium), 3 (Hard)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ConceptEdge:
    """A unidirectional mathematical vector."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0


class CycleDetectedError(ValueError):
    """Raised when an Admin accidentally creates an infinite learning loop."""
    pass


class ConceptGraph:
    """Directed Acyclic Graph (DAG) representing a Computer Science curriculum."""
    
    def __init__(self) -> None:
        self._nodes: Dict[str, ConceptNode] = {}
        # Double Adjacency Lists for blazing fast O(1) directional traversal
        self._out_edges: Dict[str, List[ConceptEdge]] = defaultdict(list)
        self._in_edges: Dict[str, List[ConceptEdge]] = defaultdict(list)
        self._logger = logging.getLogger(__name__)

    def add_concept(self, node: ConceptNode) -> None:
        """Registers a new mathematical node in the graph."""
        if node.id in self._nodes:
            self._logger.warning(f"Concept '{node.id}' already exists. Overwriting.")
        self._nodes[node.id] = node

    def add_edge(self, source_id: str, target_id: str, edge_type: EdgeType, weight: float = 1.0) -> None:
        """
        Draws a directed edge vector. 
        Mathematically guarantees acyclic integrity for STRICT edges.
        """
        if source_id not in self._nodes or target_id not in self._nodes:
            raise ValueError(f"Cannot draw edge. Missing node: {source_id} or {target_id}")
            
        edge = ConceptEdge(source_id, target_id, edge_type, weight)
        
        # Only strict prerequisites MUST form a pure DAG.
        # "SIMILAR_TO" can legally form cycles, which is perfectly fine.
        if edge_type in (EdgeType.REQUIRES, EdgeType.PROGRESSES):
            if self._would_create_cycle(source_id, target_id, edge_type):
                raise CycleDetectedError(f"Drawing {edge_type.value} from {source_id} to {target_id} creates an impossible infinite loop.")
                
        self._out_edges[source_id].append(edge)
        self._in_edges[target_id].append(edge)

    def _would_create_cycle(self, source_id: str, target_id: str, edge_type: EdgeType) -> bool:
        """Runs a physical BFS in memory to detect if target_id can already reach source_id."""
        if source_id == target_id:
            return True
            
        visited = set()
        queue = deque([target_id])
        
        while queue:
            current = queue.popleft()
            if current == source_id:
                return True
                
            if current not in visited:
                visited.add(current)
                # Traverse strictly outwards along the specific edge type
                for edge in self._out_edges[current]:
                    if edge.edge_type == edge_type:
                        queue.append(edge.target_id)
                        
        return False

    # ---------------------------------------------------------
    # Traversal & Logic Resolution
    # ---------------------------------------------------------
    def get_prerequisites(self, concept_id: str, deep: bool = False) -> List[str]:
        """
        Calculates exactly what must be learned before attacking this concept.
        If deep=True, performs Reverse-BFS to gather the entire historical dependency tree.
        """
        if concept_id not in self._nodes:
            return []
            
        if not deep:
            return [e.source_id for e in self._in_edges[concept_id] if e.edge_type == EdgeType.REQUIRES]
            
        deps = set()
        queue = deque([concept_id])
        
        while queue:
            current = queue.popleft()
            for edge in self._in_edges[current]:
                if edge.edge_type == EdgeType.REQUIRES and edge.source_id not in deps:
                    deps.add(edge.source_id)
                    queue.append(edge.source_id)
                    
        return list(deps)

    def get_successors(self, concept_id: str) -> List[str]:
        """Returns concepts that unlock immediately after mastering this specific node."""
        if concept_id not in self._nodes:
            return []
        return [e.target_id for e in self._out_edges[concept_id] if e.edge_type == EdgeType.REQUIRES]

    def get_difficulty_progression(self, start_concept_id: str) -> List[str]:
        """Traverses the PROGRESSES edges to build a scaled difficulty track (e.g., Easy -> Med -> Hard)."""
        progression = [start_concept_id]
        current = start_concept_id
        
        while True:
            next_nodes = [e.target_id for e in self._out_edges[current] if e.edge_type == EdgeType.PROGRESSES]
            if not next_nodes:
                break
                
            # Follow the first valid progression branch
            current = next_nodes[0]
            progression.append(current)
            
        return progression

    def generate_learning_path(self, target_concept_id: str) -> List[str]:
        """
        Uses Kahn's Algorithm (Topological Sort) on the prerequisite subgraph
        to mathematically generate a flawless, step-by-step educational curriculum.
        """
        # 1. Identify all required historical nodes via Reverse BFS
        subgraph_nodes = set(self.get_prerequisites(target_concept_id, deep=True))
        subgraph_nodes.add(target_concept_id)
        
        # 2. Build local In-Degree map specifically for this localized subgraph
        in_degree = {node: 0 for node in subgraph_nodes}
        for node in subgraph_nodes:
            for edge in self._out_edges[node]:
                if edge.edge_type == EdgeType.REQUIRES and edge.target_id in subgraph_nodes:
                    in_degree[edge.target_id] += 1
                    
        # 3. Queue nodes with 0 prerequisites (The absolute fundamentals)
        queue = deque([n for n in subgraph_nodes if in_degree[n] == 0])
        path = []
        
        # 4. Execute Kahn's Topological Sort
        while queue:
            current = queue.popleft()
            path.append(current)
            
            for edge in self._out_edges[current]:
                if edge.edge_type == EdgeType.REQUIRES and edge.target_id in subgraph_nodes:
                    in_degree[edge.target_id] -= 1
                    
                    # When a node's dependencies are fully met, unlock it in the queue
                    if in_degree[edge.target_id] == 0:
                        queue.append(edge.target_id)
                        
        return path
