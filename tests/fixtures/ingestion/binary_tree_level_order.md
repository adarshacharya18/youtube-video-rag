# 102. Binary Tree Level Order Traversal

- **Difficulty:** Medium
- **Tags:** Tree, Breadth-First Search, Binary Tree
- **Slug:** binary-tree-level-order-traversal
- **Scraped At:** 2026-07-24T10:10:00Z

## Description
Given the `root` of a binary tree, return the level order traversal of its nodes' values. (i.e., from left to right, level by level).

## Examples

### Example 1:
**Input:** root = [3,9,20,null,null,15,7]
**Output:** [[3],[9,20],[15,7]]

### Example 2:
**Input:** root = [1]
**Output:** [[1]]

### Example 3:
**Input:** root = []
**Output:** []

## Constraints
- The number of nodes in the tree is in the range [0, 2000].
- -1000 <= Node.val <= 1000

## Solution
```python
from collections import deque

class Solution:
    def levelOrder(self, root: Optional[TreeNode]) -> list[list[int]]:
        if not root:
            return []
        res = []
        q = deque([root])
        while q:
            level = []
            for _ in range(len(q)):
                node = q.popleft()
                level.append(node.val)
                if node.left:
                    q.append(node.left)
                if node.right:
                    q.append(node.right)
            res.append(level)
        return res
```
