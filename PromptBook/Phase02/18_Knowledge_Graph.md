# Phase02/18_Knowledge_Graph.md

**Author:** Principal AI Architect  
**Target System:** Automated DSA Educational YouTube Video Pipeline (RAG Subsystem)  
**Document Version:** 1.0.0  
**Status:** Canonical

---

# Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Graph Schema Design](#2-graph-schema-design)
   - [Node Types](#21-node-types)
   - [Edge Types](#22-edge-types)
3. [Knowledge Graph Architecture](#3-knowledge-graph-architecture)
4. [Traversal & Routing Logic](#4-traversal--routing-logic)
5. [Query & Vector Search Integration (GraphRAG)](#5-query--vector-search-integration-graphrag)
6. [Future Expansion](#6-future-expansion)

---

# 1. Executive Summary

While dense vector databases (ChromaDB) excel at finding semantically similar text, they struggle to model strict hierarchies, prerequisites, and relationships (e.g., *understanding that a Priority Queue is required for Dijkstra's Algorithm*). 

To solve this, the RAG subsystem implements a **Lightweight Knowledge Graph**. This graph acts as a semantic overlay on top of the Multi-Knowledge-Base architecture. By combining Vector Search with Graph Traversal (a technique known as GraphRAG), the system can proactively fetch prerequisite algorithms, related animations, and progressive difficulty paths, drastically improving the educational depth of the generated videos.

---

# 2. Graph Schema Design

The Knowledge Graph is built using a lightweight local graph store (e.g., NetworkX in Python, or a lightweight Neo4j/KuzuDB instance). 

### 2.1 Node Types
Every node in the graph maps to a specific concept or document across our Knowledge Bases.

- **`Algorithm`**: Core algorithms (e.g., `Dijkstra`, `BFS`).
- **`Pattern`**: DSA patterns (e.g., `Sliding Window`, `Two Pointers`).
- **`LeetCode Problem`**: Specific problems (e.g., `LC-1`, `LC-42`).
- **`Data Structure`**: Underlying structures (e.g., `Array`, `Hash Map`, `Heap`).
- **`Complexity`**: Big-O definitions (e.g., `O(N)`, `O(V+E)`).
- **`Animation`**: Visual templates (e.g., `Tree_Traversal_Anim`).
- **`Teaching Analogy`**: Pedagogical tools (e.g., `Queue_is_a_Line`).
- **`Code Template`**: Boilerplate code (e.g., `CPP_Trie_Struct`).
- **`Interview Tip`**: "Gotchas" (e.g., `Integer_Overflow_Check`).
- **`Language`**: e.g., `C++`, `Python`.

### 2.2 Edge Types
Edges define the directional relationships and operational rules between nodes.

- **`REQUIRES`** (Prerequisite): E.g., `Dijkstra` -> `REQUIRES` -> `Heap`.
- **`LEADS_TO`** (Successor Concept): E.g., `Two Pointers` -> `LEADS_TO` -> `Sliding Window`.
- **`PROGRESSES_TO`** (Difficulty Progression): E.g., `LC-1 (Easy)` -> `PROGRESSES_TO` -> `LC-15 (Medium)`.
- **`IMPLEMENTS`**: E.g., `LC-42` -> `IMPLEMENTS` -> `Two Pointers`.
- **`HAS_COMPLEXITY`**: E.g., `Binary Search` -> `HAS_COMPLEXITY` -> `O(log N)`.
- **`VISUALIZED_BY`**: E.g., `Binary Tree` -> `VISUALIZED_BY` -> `Tree_Traversal_Anim`.
- **`EXPLAINED_BY`**: E.g., `Heap` -> `EXPLAINED_BY` -> `Priority_Queue_Analogy`.
- **`CODED_IN`**: E.g., `CPP_Trie_Struct` -> `CODED_IN` -> `C++`.

---

# 3. Knowledge Graph Architecture

```mermaid
graph TD
    %% Nodes
    LC[Node: LC-42 Trapping Rain Water]
    Patt[Node: Two Pointers]
    DS[Node: Array]
    Comp[Node: O(N) Time]
    Anim[Node: Pointer_Contraction_Anim]
    Code[Node: CPP_Two_Pointer_Template]
    Analogy[Node: Walls_and_Water_Analogy]
    Tip[Node: Off_By_One_Check]
    NextLC[Node: LC-11 Container with Most Water]

    %% Relationships
    LC -- IMPLEMENTS --> Patt
    LC -- USES --> DS
    LC -- HAS_COMPLEXITY --> Comp
    LC -- PROGRESSES_TO --> NextLC

    Patt -- VISUALIZED_BY --> Anim
    Patt -- CODED_IN --> Code
    Patt -- EXPLAINED_BY --> Analogy
    Patt -- REQUIRES --> Tip

    classDef problem fill:#f9c2ff,stroke:#d056d6,stroke-width:2px,color:#000
    classDef theory fill:#c2dfff,stroke:#569cd6,stroke-width:2px,color:#000
    classDef visual fill:#c2ffd6,stroke:#56d67b,stroke-width:2px,color:#000
    
    class LC,NextLC problem
    class Patt,DS,Comp,Code,Tip theory
    class Anim,Analogy visual
```

---

# 4. Traversal & Routing Logic

When the Retrieval Orchestrator receives a task, it traverses the graph to expand its query scope dynamically.

### 4.1 The Prerequisite Traversal (Educational Depth)
If the Video Assembler requests a script for `Dijkstra`:
1. The Orchestrator locates the `Dijkstra` node.
2. It traverses all outgoing `REQUIRES` edges.
3. It discovers the `Heap` node.
4. *Action:* The Orchestrator automatically injects a small instructional chunk about `Heaps` into the `RAGContext`, ensuring the LLM explains the prerequisite data structure before jumping into the main algorithm.

### 4.2 The Successor Traversal (Viewer Retention)
At the end of a video, the script generator needs an "Outro" hook.
1. The Orchestrator locates the current problem (`LC-1 Two Sum`).
2. It traverses the `PROGRESSES_TO` edge.
3. It discovers `LC-15 3Sum`.
4. *Action:* The Orchestrator passes this to the LLM, prompting it to end the video with: *"Now that you've mastered Two Sum, the natural next step is 3Sum. Click the video on screen to tackle that next!"*

---

# 5. Query & Vector Search Integration (GraphRAG)

The Knowledge Graph does not replace ChromaDB; it enhances it. The system uses a **Graph-Augmented Vector Search**.

1. **Entity Extraction (Graph Entry):** The incoming problem tags (e.g., `"Sliding Window"`) are matched to a Graph Node.
2. **Sub-graph Expansion (Traversal):** The Orchestrator traverses depth=1 or depth=2 from the entry node to find related concepts (e.g., `Array`, `O(N)`, `Pointer_Contraction_Anim`).
3. **Targeted Vector Search:** Instead of doing a blind cosine similarity search across the entire vector database, the Orchestrator uses the traversed node names to dynamically construct the metadata `WHERE` clauses for ChromaDB.
   - *Example:* `SELECT chunks FROM Chroma WHERE pattern="Sliding Window" OR pattern="Array"`
4. **Context Building:** The retrieved vector chunks are reordered based on graph proximity (Prerequisites always placed before the main algorithm).

---

# 6. Future Expansion

Because the graph relies on standard triple formats (Subject -> Predicate -> Object), it is infinitely extensible.

- **Student Knowledge Graphs (Personalization):** In the future Chatbot or Website phase, every authenticated user can have an attached sub-graph (e.g., `User_Adarsh` -> `HAS_MASTERED` -> `BFS`). The orchestrator can traverse this graph, skipping prerequisite explanations if it sees the user has already mastered them, creating a hyper-personalized tutoring experience.
- **Automated Curriculum Generation:** By traversing `LEADS_TO` and `PROGRESSES_TO` edges, the system can automatically generate 50-video playlist curriculums (e.g., "From Zero to Graph Theory Master") ensuring perfect, steady difficulty scaling.
- **LLM-Driven Graph Updates:** As new LeetCode problems are scraped nightly, a secondary LLM pipeline can automatically extract relationships from the problem description and create new nodes/edges, growing the graph dynamically without human intervention.
